"""pandapower adapter for distribution grid power flow analysis."""
import copy
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandapower as pp
import pandapower.networks as pn
from pandapower.timeseries import run_timeseries
from pandapower.timeseries import DFData
from pandapower.control import ConstControl

from src.schemas.scenario import (
    PandapowerConfig, GridBusMapping, ScenarioConfig, BuildingConfig
)
from src.schemas.diagnostics import (
    Diagnostic, DiagnosticCategory, Severity, DiagnosticReport,
    PowerFlowDiagnostic, VoltageDiagnostic, LineLoadingDiagnostic,
    TransformerLoadingDiagnostic, GridLimitDiagnostic
)
from src.schemas.action import SimulationStepResult


class PandapowerAdapter:
    """Adapter for pandapower distribution grid simulation and power flow analysis."""
    
    def __init__(self, config: PandapowerConfig):
        self.config = config
        self.net = None
        self.bus_mapping: Dict[str, int] = {}  # building_id -> bus_idx
        self.phase_mapping: Dict[str, str] = {}  # building_id -> phase
        self.load_indices: Dict[str, int] = {}  # building_id -> load_idx
        self.sgen_indices: Dict[str, int] = {}  # building_id -> sgen_idx (for PV)
        self.storage_indices: Dict[str, int] = {}  # building_id -> storage_idx
        self.time_step = 0
        self.convergence_history: List[bool] = []
        self.voltage_history: List[Dict[int, float]] = []
        self.loading_history: List[Dict[str, Dict[int, float]]] = []
        
        self._create_network()
        self._setup_bus_mapping()
    
    def _create_network(self):
        """Create pandapower network from configuration."""
        if self.config.network_type == "ieee_13":
            self.net = pn.case14()  # Use IEEE 14 bus as substitute
        elif self.config.network_type == "ieee_34":
            self.net = pn.ieee_european_lv_asymmetric()  # Large LV network
        elif self.config.network_type == "ieee_123":
            self.net = pn.case_ieee30()  # Use IEEE 30 bus
        elif self.config.network_type == "cigre_lv":
            self.net = pn.create_cigre_network_lv()
        elif self.config.network_type == "simbench":
            self.net = self._create_simbench_network()
        elif self.config.network_type == "custom" and self.config.network_file:
            self.net = pp.from_json(self.config.network_file)
        else:
            # Default to CIGRE LV network
            self.net = pn.create_cigre_network_lv()
        
        # Ensure slack bus is set
        if self.config.slack_bus < len(self.net.bus):
            self.net.ext_grid.at[0, 'bus'] = self.config.slack_bus
    
    def _create_simbench_network(self):
        """Create a SimBench network (placeholder - would need actual SimBench data)."""
        # For now, create a synthetic LV network similar to SimBench
        return self._create_simple_lv_network()
    
    def _create_simple_lv_network(self):
        """Create a simple low voltage test network."""
        net = pp.create_empty_network()
        
        # Create buses (MV/LV substation + LV feeders)
        bus_mv = pp.create_bus(net, vn_kv=20., name="MV Bus")
        bus_lv_main = pp.create_bus(net, vn_kv=0.4, name="LV Main Bus")
        
        # Transformer
        pp.create_transformer(net, bus_mv, bus_lv_main, std_type="0.4 MVA 20/0.4 kV")
        pp.create_ext_grid(net, bus_mv, vm_pu=1.0, name="Grid Connection")
        
        # Create LV feeders (radial)
        prev_bus = bus_lv_main
        for i in range(10):  # 10 LV buses for buildings
            bus = pp.create_bus(net, vn_kv=0.4, name=f"LV Bus {i+1}")
            pp.create_line(net, prev_bus, bus, length_km=0.1, 
                          std_type="NAYY 4x50 SE", name=f"Line {i+1}")
            prev_bus = bus
        
        return net
    
    def _setup_bus_mapping(self):
        """Setup mapping from buildings to grid buses."""
        for mapping in self.config.bus_mappings:
            self.bus_mapping[mapping.building_id] = mapping.bus_idx
            self.phase_mapping[mapping.building_id] = mapping.phase
            
            # Create load at bus for this building
            load_idx = pp.create_load(
                self.net, 
                bus=mapping.bus_idx, 
                p_mw=0.0, 
                q_mvar=0.0, 
                name=f"Load_{mapping.building_id}"
            )
            self.load_indices[mapping.building_id] = load_idx
    
    def update_building_loads(self, building_powers: Dict[str, float], building_pvs: Dict[str, float]):
        """Update building loads and PV generation in the network.
        
        Args:
            building_powers: Dict of building_id -> net power demand (kW, positive = consumption)
            building_pvs: Dict of building_id -> PV generation (kW)
        """
        for building_id, power_kw in building_powers.items():
            if building_id in self.load_indices:
                # Net load = consumption - PV generation
                pv_kw = building_pvs.get(building_id, 0.0)
                net_load_kw = power_kw - pv_kw
                
                # Update load (pandapower uses MW)
                load_idx = self.load_indices[building_id]
                self.net.load.at[load_idx, 'p_mw'] = net_load_kw / 1000.0
                # Assume power factor of 0.95
                self.net.load.at[load_idx, 'q_mvar'] = (net_load_kw / 1000.0) * np.tan(np.arccos(0.95))
    
    def run_power_flow(self) -> Tuple[bool, DiagnosticReport]:
        """Run power flow and return convergence status and diagnostics."""
        report = DiagnosticReport(
            scenario_id="grid",
            run_id=f"step_{self.time_step}",
            timestep=self.time_step
        )
        
        try:
            pp.runpp(self.net, algorithm='bfsw', max_iteration=100, tolerance_mva=1e-6)
            converged = self.net.converged
        except Exception as e:
            converged = False
            report.add_diagnostic(PowerFlowDiagnostic(
                diagnostic_id=f"pf_error_{self.time_step}",
                severity=Severity.CRITICAL,
                message=f"Power flow failed: {str(e)}",
                timestep=self.time_step,
                converged=False,
                max_mismatch=float('inf')
            ))
        
        if converged:
            report.power_flow_converged = True
            # Check voltages
            self._check_voltages(report)
            # Check line loading
            self._check_line_loading(report)
            # Check transformer loading
            self._check_transformer_loading(report)
        else:
            report.power_flow_converged = False
            report.add_diagnostic(PowerFlowDiagnostic(
                diagnostic_id=f"pf_nc_{self.time_step}",
                severity=Severity.CRITICAL,
                message="Power flow did not converge",
                timestep=self.time_step,
                converged=False
            ))
        
        self.convergence_history.append(converged)
        self.time_step += 1
        
        return converged, report
    
    def _check_voltages(self, report: DiagnosticReport):
        """Check bus voltage limits."""
        vm_pu = self.net.res_bus.vm_pu.values
        min_limit = self.config.voltage_limits.get("min", 0.95)
        max_limit = self.config.voltage_limits.get("max", 1.05)
        
        self.voltage_history.append({i: vm_pu[i] for i in range(len(vm_pu))})
        
        for i, v in enumerate(vm_pu):
            if v < min_limit:
                report.add_diagnostic(VoltageDiagnostic(
                    diagnostic_id=f"v_low_{i}_{self.time_step}",
                    severity=Severity.VIOLATION if v < 0.9 else Severity.CRITICAL,
                    message=f"Bus {i} undervoltage: {v:.4f} pu",
                    timestep=self.time_step,
                    bus_indices=[i],
                    bus_idx=i,
                    phase="all",
                    voltage_pu=v,
                    limit_min_pu=min_limit,
                    limit_max_pu=max_limit
                ))
            elif v > max_limit:
                report.add_diagnostic(VoltageDiagnostic(
                    diagnostic_id=f"v_high_{i}_{self.time_step}",
                    severity=Severity.VIOLATION if v < 1.1 else Severity.CRITICAL,
                    message=f"Bus {i} overvoltage: {v:.4f} pu",
                    timestep=self.time_step,
                    bus_indices=[i],
                    bus_idx=i,
                    phase="all",
                    voltage_pu=v,
                    limit_min_pu=min_limit,
                    limit_max_pu=max_limit
                ))
    
    def _check_line_loading(self, report: DiagnosticReport):
        """Check line loading limits."""
        if len(self.net.res_line) == 0:
            return
            
        loading = self.net.res_line.loading_percent.values / 100.0
        limit = self.config.line_loading_limit
        
        self.loading_history.append({
            "lines": {i: loading[i] for i in range(len(loading))},
            "trafos": {}
        })
        
        for i, ld in enumerate(loading):
            if ld > limit:
                report.add_diagnostic(LineLoadingDiagnostic(
                    diagnostic_id=f"line_ol_{i}_{self.time_step}",
                    severity=Severity.VIOLATION if ld < 1.2 else Severity.CRITICAL,
                    message=f"Line {i} overloaded: {ld*100:.1f}%",
                    timestep=self.time_step,
                    line_idx=i,
                    loading_pct=ld * 100,
                    limit_pct=limit * 100
                ))
    
    def _check_transformer_loading(self, report: DiagnosticReport):
        """Check transformer loading limits."""
        if len(self.net.res_trafo) == 0:
            return
            
        loading = self.net.res_trafo.loading_percent.values / 100.0
        limit = self.config.transformer_loading_limit
        
        # Update loading history
        if self.loading_history:
            self.loading_history[-1]["trafos"] = {i: loading[i] for i in range(len(loading))}
        
        for i, ld in enumerate(loading):
            if ld > limit:
                report.add_diagnostic(TransformerLoadingDiagnostic(
                    diagnostic_id=f"trafo_ol_{i}_{self.time_step}",
                    severity=Severity.VIOLATION if ld < 1.2 else Severity.CRITICAL,
                    message=f"Transformer {i} overloaded: {ld*100:.1f}%",
                    timestep=self.time_step,
                    trafo_idx=i,
                    loading_pct=ld * 100,
                    limit_pct=limit * 100
                ))
    
    def check_grid_limits(self, community_import_kw: float, community_export_kw: float,
                          import_limit_kw: float, export_limit_kw: float) -> List[Diagnostic]:
        """Check community-level grid import/export limits."""
        diagnostics = []
        
        if community_import_kw > import_limit_kw:
            diagnostics.append(GridLimitDiagnostic(
                diagnostic_id=f"import_limit_{self.time_step}",
                severity=Severity.VIOLATION,
                message=f"Community import limit exceeded: {community_import_kw:.1f} > {import_limit_kw:.1f} kW",
                timestep=self.time_step,
                limit_type="import",
                limit_kw=import_limit_kw,
                actual_kw=community_import_kw,
                excess_kw=community_import_kw - import_limit_kw
            ))
        
        if community_export_kw > export_limit_kw:
            diagnostics.append(GridLimitDiagnostic(
                diagnostic_id=f"export_limit_{self.time_step}",
                severity=Severity.VIOLATION,
                message=f"Community export limit exceeded: {community_export_kw:.1f} > {export_limit_kw:.1f} kW",
                timestep=self.time_step,
                limit_type="export",
                limit_kw=export_limit_kw,
                actual_kw=community_export_kw,
                excess_kw=community_export_kw - export_limit_kw
            ))
        
        return diagnostics
    
    def get_voltage_profile(self) -> Dict[int, float]:
        """Get current voltage profile (bus_idx -> vm_pu)."""
        if self.net.converged and hasattr(self.net, 'res_bus'):
            return {i: self.net.res_bus.vm_pu.at[i] for i in self.net.res_bus.index}
        return {}
    
    def get_loading_profile(self) -> Dict[str, Dict[int, float]]:
        """Get current loading profile."""
        profile = {"lines": {}, "trafos": {}}
        if self.net.converged:
            if hasattr(self.net, 'res_line') and len(self.net.res_line) > 0:
                profile["lines"] = {i: self.net.res_line.loading_percent.at[i] / 100.0 
                                   for i in self.net.res_line.index}
            if hasattr(self.net, 'res_trafo') and len(self.net.res_trafo) > 0:
                profile["trafos"] = {i: self.net.res_trafo.loading_percent.at[i] / 100.0 
                                    for i in self.net.res_trafo.index}
        return profile
    
    def get_network_state(self) -> Dict[str, Any]:
        """Get complete network state for logging/analysis."""
        return {
            "converged": self.net.converged if self.net else False,
            "bus_voltages": self.get_voltage_profile(),
            "line_loading": self.get_loading_profile().get("lines", {}),
            "trafo_loading": self.get_loading_profile().get("trafos", {}),
            "total_load_mw": self.net.load.p_mw.sum() if len(self.net.load) > 0 else 0,
            "total_gen_mw": self.net.sgen.p_mw.sum() if len(self.net.sgen) > 0 else 0,
        }
    
    def reset(self):
        """Reset adapter state."""
        self.time_step = 0
        self.convergence_history = []
        self.voltage_history = []
        self.loading_history = []
    
    def export_results(self, output_path: str):
        """Export network and results to JSON."""
        pp.to_json(self.net, output_path)


def create_grid_from_scenario(scenario: ScenarioConfig) -> PandapowerAdapter:
    """Factory function to create PandapowerAdapter from scenario config."""
    if scenario.pandapower is None:
        # Create default config
        from src.schemas.scenario import PandapowerConfig, GridBusMapping
        bus_mappings = []
        for i, building in enumerate(scenario.buildings):
            bus_mappings.append(GridBusMapping(
                building_id=building.building_id,
                bus_idx=i + 1,  # Bus 0 is slack
                phase="all"
            ))
        
        pandapower_config = PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=bus_mappings,
            slack_bus=0
        )
    else:
        pandapower_config = scenario.pandapower
    
    return PandapowerAdapter(pandapower_config)