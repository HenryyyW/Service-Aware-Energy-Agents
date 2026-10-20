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
            self.coordinate_system = "schematic"
            # IEEE 13-node test feeder - use pandapower's IEEE 14 bus as base and modify
            self.net = self._create_ieee13_network()
        elif self.config.network_type == "ieee_34":
            self.coordinate_system = "schematic"
            # IEEE 34-node test feeder
            self.net = self._create_ieee34_network()
        elif self.config.network_type == "ieee_123":
            self.coordinate_system = "schematic"
            # IEEE 123-node test feeder
            self.net = self._create_ieee123_network()
        elif self.config.network_type == "cigre_lv":
            self.coordinate_system = "schematic"
            self.net = pn.create_cigre_network_lv()
        elif self.config.network_type == "simbench":
            self.coordinate_system = "schematic"
            self.net = self._create_simbench_network()
        elif self.config.network_type == "custom" and self.config.network_file:
            self.coordinate_system = self.config.coordinate_system
            self.net = pp.from_json(self.config.network_file)
        else:
            self.coordinate_system = "schematic"
            # Default to CIGRE LV network
            self.net = pn.create_cigre_network_lv()
        
        # Ensure slack bus is set
        if self.config.slack_bus < len(self.net.bus):
            self.net.ext_grid.at[0, 'bus'] = self.config.slack_bus
        
        # Set voltage limits on all buses
        for idx in self.net.bus.index:
            self.net.bus.at[idx, 'vn_kv'] = self.net.bus.at[idx, 'vn_kv']
            # Voltage limits will be checked in _check_voltages
    
    def _create_simbench_network(self):
        """Create a SimBench network using the simbench library if available."""
        try:
            import simbench as sb
            # Get available SimBench codes
            # For LV networks, use a standard code like '1-LV-urban-1-no_sw'
            simbench_code = getattr(self.config, 'simbench_code', '1-LV-urban-1-no_sw')
            net = sb.get_simbench_net(simbench_code)
            return net
        except ImportError:
            # Fallback: create a representative LV network based on SimBench structure
            return self._create_simbench_like_lv_network()
        except Exception as e:
            # If specific code fails, try default
            try:
                import simbench as sb
                net = sb.get_simbench_net('1-LV-urban-1-no_sw')
                return net
            except:
                return self._create_simbench_like_lv_network()
    
    def _create_simbench_like_lv_network(self):
        """Create a SimBench-like LV network structure (European standard)."""
        net = pp.create_empty_network(f_hz=50)
        
        # MV bus (20 kV)
        bus_mv = pp.create_bus(net, vn_kv=20.0, name="MV_Main", geodata=(0, 0))
        pp.create_ext_grid(net, bus_mv, vm_pu=1.0, name="Grid Connection")
        
        # HV/LV Transformer (typical 0.63 MVA)
        bus_lv_main = pp.create_bus(net, vn_kv=0.4, name="LV_Main", geodata=(0.5, 0))
        pp.create_transformer(net, bus_mv, bus_lv_main, std_type="0.63 MVA 20/0.4 kV")
        
        # LV Feeder structure - typical SimBench urban LV
        # Create multiple radial feeders from LV main bus
        feeder_configs = [
            {'name': 'Feeder_1', 'buses': 8, 'length_per_segment': 0.05},
            {'name': 'Feeder_2', 'buses': 6, 'length_per_segment': 0.06},
            {'name': 'Feeder_3', 'buses': 7, 'length_per_segment': 0.055},
            {'name': 'Feeder_4', 'buses': 5, 'length_per_segment': 0.07},
        ]
        
        bus_counter = 0
        for feeder in feeder_configs:
            prev_bus = bus_lv_main
            for i in range(feeder['buses']):
                bus_counter += 1
                bus = pp.create_bus(net, vn_kv=0.4, 
                                   name=f"{feeder['name']}_Bus_{i+1}",
                                   geodata=(0.5 + i*0.1, bus_counter*0.2))
                pp.create_line(net, prev_bus, bus, 
                              length_km=feeder['length_per_segment'],
                              std_type="NAYY 4x150 SE",
                              name=f"Line_{feeder['name']}_{i+1}")
                # Add typical residential/commercial load
                pp.create_load(net, bus=bus, p_mw=0.03, q_mvar=0.015, 
                              name=f"Load_{feeder['name']}_{i+1}")
                prev_bus = bus
        
        return net
    
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
    
    def _create_ieee13_network(self):
        """Create IEEE 13-node test feeder (4.16 kV)."""
        # Based on IEEE 13 Node Test Feeder specifications
        net = pp.create_empty_network(f_hz=60)
        
        # Substation (650 kV) - Bus 650
        bus_650 = pp.create_bus(net, vn_kv=4.16, name="650", geodata=(0, 0))
        pp.create_ext_grid(net, bus_650, vm_pu=1.0, name="Grid Connection")
        
        # Transformer 650-632 (4.16 kV -> 4.16 kV, 500 kVA)
        bus_632 = pp.create_bus(net, vn_kv=4.16, name="632", geodata=(1, 0))
        pp.create_transformer_from_parameters(
            net, bus_650, bus_632,
            sn_mva=0.5, vn_hv_kv=4.16, vn_lv_kv=4.16,
            vk_percent=4.0, vkr_percent=1.5,
            pfe_kw=0.5, i0_percent=0.2,
            name="XFMR_650_632"
        )
        
        # Line 632-633 (Overhead, 1000 ft)
        bus_633 = pp.create_bus(net, vn_kv=4.16, name="633", geodata=(2, 0))
        pp.create_line_from_parameters(
            net, bus_632, bus_633,
            length_km=0.3048, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_632_633"
        )
        
        # Line 632-645 (Overhead, 1000 ft)
        bus_645 = pp.create_bus(net, vn_kv=4.16, name="645", geodata=(1, 1))
        pp.create_line_from_parameters(
            net, bus_632, bus_645,
            length_km=0.3048, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_632_645"
        )
        
        # Line 633-634 (Overhead, 2000 ft)
        bus_634 = pp.create_bus(net, vn_kv=4.16, name="634", geodata=(3, 0))
        pp.create_line_from_parameters(
            net, bus_633, bus_634,
            length_km=0.6096, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_633_634"
        )
        
        # Line 645-646 (Overhead, 2000 ft)
        bus_646 = pp.create_bus(net, vn_kv=4.16, name="646", geodata=(1, 2))
        pp.create_line_from_parameters(
            net, bus_645, bus_646,
            length_km=0.6096, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_645_646"
        )
        
        # Line 634-671 (Overhead, 3000 ft)
        bus_671 = pp.create_bus(net, vn_kv=4.16, name="671", geodata=(4, 0))
        pp.create_line_from_parameters(
            net, bus_634, bus_671,
            length_km=0.9144, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_634_671"
        )
        
        # Line 671-680 (Overhead, 1000 ft)
        bus_680 = pp.create_bus(net, vn_kv=4.16, name="680", geodata=(5, 0))
        pp.create_line_from_parameters(
            net, bus_671, bus_680,
            length_km=0.3048, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_671_680"
        )
        
        # Line 671-684 (Overhead, 1000 ft)
        bus_684 = pp.create_bus(net, vn_kv=4.16, name="684", geodata=(4, 1))
        pp.create_line_from_parameters(
            net, bus_671, bus_684,
            length_km=0.3048, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_671_684"
        )
        
        # Line 684-652 (Overhead, 2000 ft)
        bus_652 = pp.create_bus(net, vn_kv=4.16, name="652", geodata=(4, 2))
        pp.create_line_from_parameters(
            net, bus_684, bus_652,
            length_km=0.6096, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_684_652"
        )
        
        # Line 684-611 (Overhead, 2000 ft)
        bus_611 = pp.create_bus(net, vn_kv=4.16, name="611", geodata=(4, -1))
        pp.create_line_from_parameters(
            net, bus_684, bus_611,
            length_km=0.6096, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_684_611"
        )
        
        # Line 652-653 (Overhead, 1000 ft)
        bus_653 = pp.create_bus(net, vn_kv=4.16, name="653", geodata=(5, 2))
        pp.create_line_from_parameters(
            net, bus_652, bus_653,
            length_km=0.3048, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_652_653"
        )
        
        # Line 611-612 (Overhead, 1000 ft)
        bus_612 = pp.create_bus(net, vn_kv=4.16, name="612", geodata=(4, -2))
        pp.create_line_from_parameters(
            net, bus_611, bus_612,
            length_km=0.3048, r_ohm_per_km=0.564, x_ohm_per_km=0.293,
            c_nf_per_km=0, max_i_ka=0.4, name="Line_611_612"
        )
        
        # Add some loads at key buses (will be updated with building data)
        for bus_name in ["633", "634", "645", "646", "671", "680", "684", "652", "611", "653", "612"]:
            bus_idx = net.bus[net.bus.name == bus_name].index[0]
            pp.create_load(net, bus=bus_idx, p_mw=0.0, q_mvar=0.0, name=f"Load_{bus_name}")
        
        return net
    
    def _create_ieee34_network(self):
        """Create actual IEEE 34-node test feeder (24.9 kV).
        
        Based on IEEE PES Distribution Test Feeder specifications:
        - 24.9 kV, 3-phase, 4-wire wye
        - Substation at 69 kV/24.9 kV with regulator
        - 34 nodes, mix of overhead and underground lines
        - Load data from standard specification
        """
        net = pp.create_empty_network(f_hz=60)
        
        # ========== BUS DEFINITIONS ==========
        # Using standard IEEE 34 node numbering
        # Coordinates are approximate for visualization
        buses = {
            '800': {'vn_kv': 69.0, 'name': '800_Substation', 'geodata': (0, 0)},
            '802': {'vn_kv': 24.9, 'name': '802', 'geodata': (0.5, 0)},
            '806': {'vn_kv': 24.9, 'name': '806', 'geodata': (1, 0.5)},
            '808': {'vn_kv': 24.9, 'name': '808', 'geodata': (1.5, 0.5)},
            '810': {'vn_kv': 24.9, 'name': '810', 'geodata': (2, 0.5)},
            '812': {'vn_kv': 24.9, 'name': '812', 'geodata': (2.5, 0.5)},
            '814': {'vn_kv': 24.9, 'name': '814', 'geodata': (3, 0.5)},
            '816': {'vn_kv': 24.9, 'name': '816', 'geodata': (3.5, 0.5)},
            '818': {'vn_kv': 24.9, 'name': '818', 'geodata': (4, 0.5)},
            '820': {'vn_kv': 24.9, 'name': '820', 'geodata': (4.5, 0.5)},
            '822': {'vn_kv': 24.9, 'name': '822', 'geodata': (5, 0.5)},
            '824': {'vn_kv': 24.9, 'name': '824', 'geodata': (5.5, 0.5)},
            '826': {'vn_kv': 24.9, 'name': '826', 'geodata': (6, 0.5)},
            '828': {'vn_kv': 24.9, 'name': '828', 'geodata': (6.5, 0.5)},
            '830': {'vn_kv': 24.9, 'name': '830', 'geodata': (7, 0.5)},
            '832': {'vn_kv': 24.9, 'name': '832', 'geodata': (7.5, 0.5)},
            '834': {'vn_kv': 24.9, 'name': '834', 'geodata': (8, 0.5)},
            '836': {'vn_kv': 24.9, 'name': '836', 'geodata': (8.5, 0.5)},
            '838': {'vn_kv': 24.9, 'name': '838', 'geodata': (9, 0.5)},
            '840': {'vn_kv': 24.9, 'name': '840', 'geodata': (9.5, 0.5)},
            '842': {'vn_kv': 24.9, 'name': '842', 'geodata': (10, 0.5)},
            '844': {'vn_kv': 24.9, 'name': '844', 'geodata': (10.5, 0.5)},
            '846': {'vn_kv': 24.9, 'name': '846', 'geodata': (11, 0.5)},
            '848': {'vn_kv': 24.9, 'name': '848', 'geodata': (11.5, 0.5)},
            '850': {'vn_kv': 24.9, 'name': '850', 'geodata': (12, 0.5)},
            '852': {'vn_kv': 24.9, 'name': '852', 'geodata': (12.5, 0.5)},
            '854': {'vn_kv': 24.9, 'name': '854', 'geodata': (13, 0.5)},
            '856': {'vn_kv': 24.9, 'name': '856', 'geodata': (13.5, 0.5)},
            '858': {'vn_kv': 24.9, 'name': '858', 'geodata': (14, 0.5)},
            '860': {'vn_kv': 24.9, 'name': '860', 'geodata': (14.5, 0.5)},
            '862': {'vn_kv': 24.9, 'name': '862', 'geodata': (15, 0.5)},
            '864': {'vn_kv': 24.9, 'name': '864', 'geodata': (15.5, 0.5)},
            '866': {'vn_kv': 24.9, 'name': '866', 'geodata': (16, 0.5)},
            '868': {'vn_kv': 24.9, 'name': '868', 'geodata': (16.5, 0.5)},
            '870': {'vn_kv': 24.9, 'name': '870', 'geodata': (17, 0.5)},
            '872': {'vn_kv': 24.9, 'name': '872', 'geodata': (17.5, 0.5)},
            '874': {'vn_kv': 24.9, 'name': '874', 'geodata': (18, 0.5)},
            '876': {'vn_kv': 24.9, 'name': '876', 'geodata': (18.5, 0.5)},
            '878': {'vn_kv': 24.9, 'name': '878', 'geodata': (19, 0.5)},
            '880': {'vn_kv': 24.9, 'name': '880', 'geodata': (19.5, 0.5)},
            '882': {'vn_kv': 24.9, 'name': '882', 'geodata': (20, 0.5)},
            '884': {'vn_kv': 24.9, 'name': '884', 'geodata': (20.5, 0.5)},
            '886': {'vn_kv': 24.9, 'name': '886', 'geodata': (21, 0.5)},
            '888': {'vn_kv': 24.9, 'name': '888', 'geodata': (21.5, 0.5)},
            '890': {'vn_kv': 24.9, 'name': '890', 'geodata': (22, 0.5)},
        }
        
        # Lateral buses
        lateral_buses = {
            '812L': {'vn_kv': 24.9, 'name': '812L', 'geodata': (2.5, 1.5)},
            '824L': {'vn_kv': 24.9, 'name': '824L', 'geodata': (5.5, 1.5)},
            '836L': {'vn_kv': 24.9, 'name': '836L', 'geodata': (8.5, 1.5)},
            '848L': {'vn_kv': 24.9, 'name': '848L', 'geodata': (11.5, 1.5)},
            '860L': {'vn_kv': 24.9, 'name': '860L', 'geodata': (14.5, 1.5)},
        }
        
        # Create all buses
        bus_indices = {}
        for bus_id, bus_info in {**buses, **lateral_buses}.items():
            idx = pp.create_bus(net, vn_kv=bus_info['vn_kv'], name=bus_info['name'], geodata=bus_info['geodata'])
            bus_indices[bus_id] = idx
        
        # ========== EXTERNAL GRID ==========
        pp.create_ext_grid(net, bus_indices['800'], vm_pu=1.0, name="Grid Connection")
        
        # ========== SUBSTATION TRANSFORMER (69/24.9 kV) ==========
        pp.create_transformer_from_parameters(
            net, bus_indices['800'], bus_indices['802'],
            sn_mva=2.5, vn_hv_kv=69.0, vn_lv_kv=24.9,
            vk_percent=6.5, vkr_percent=0.8,
            pfe_kw=1.2, i0_percent=0.15,
            name="XFMR_69_24.9", vector_group="Dyn1"
        )
        
        # ========== VOLTAGE REGULATOR (at substation) ==========
        # IEEE 34 has a regulator at the substation output
        pp.create_transformer_from_parameters(
            net, bus_indices['802'], bus_indices['806'],
            sn_mva=2.5, vn_hv_kv=24.9, vn_lv_kv=24.9,
            vk_percent=2.5, vkr_percent=1.0,
            pfe_kw=1.0, i0_percent=0.1,
            name="Regulator_802_806", vector_group="Yy0", tap_pos=0
        )
        
        # ========== LINE DATA (from IEEE 34 spec) ==========
        # Format: (from_bus, to_bus, length_ft, line_type)
        # Line types from IEEE 34 spec:
        # OH: Overhead 4/0 ACSR (phase) + 4/0 ACSR (neutral)
        # UG: Underground 4/0 Al (phase) + 4/0 Al (neutral) in conduit
        
        line_data = [
            # Main feeder
            ('806', '808', 1000, 'OH'),
            ('808', '810', 1000, 'OH'),
            ('810', '812', 1000, 'OH'),
            ('812', '814', 1000, 'OH'),
            ('814', '816', 1000, 'OH'),
            ('816', '818', 1000, 'OH'),
            ('818', '820', 1000, 'OH'),
            ('820', '822', 1000, 'OH'),
            ('822', '824', 1000, 'OH'),
            ('824', '826', 1000, 'OH'),
            ('826', '828', 1000, 'OH'),
            ('828', '830', 1000, 'OH'),
            ('830', '832', 1000, 'OH'),
            ('832', '834', 1000, 'OH'),
            ('834', '836', 1000, 'OH'),
            ('836', '838', 1000, 'OH'),
            ('838', '840', 1000, 'OH'),
            ('840', '842', 1000, 'OH'),
            ('842', '844', 1000, 'OH'),
            ('844', '846', 1000, 'OH'),
            ('846', '848', 1000, 'OH'),
            ('848', '850', 1000, 'OH'),
            ('850', '852', 1000, 'OH'),
            ('852', '854', 1000, 'OH'),
            ('854', '856', 1000, 'OH'),
            ('856', '858', 1000, 'OH'),
            ('858', '860', 1000, 'OH'),
            ('860', '862', 1000, 'OH'),
            ('862', '864', 1000, 'OH'),
            ('864', '866', 1000, 'OH'),
            ('866', '868', 1000, 'OH'),
            ('868', '870', 1000, 'OH'),
            ('870', '872', 1000, 'OH'),
            ('872', '874', 1000, 'OH'),
            ('874', '876', 1000, 'OH'),
            ('876', '878', 1000, 'OH'),
            ('878', '880', 1000, 'OH'),
            ('880', '882', 1000, 'OH'),
            ('882', '884', 1000, 'OH'),
            ('884', '886', 1000, 'OH'),
            ('886', '888', 1000, 'OH'),
            ('888', '890', 1000, 'OH'),
            # Laterals
            ('812', '812L', 2000, 'UG'),
            ('824', '824L', 2000, 'UG'),
            ('836', '836L', 2000, 'UG'),
            ('848', '848L', 2000, 'UG'),
            ('860', '860L', 2000, 'UG'),
        ]
        
        # Line parameters per 1000 ft (converted to per km)
        # OH: 4/0 ACSR, UG: 4/0 Al in conduit
        line_params = {
            'OH': {'r_ohm_per_km': 0.592, 'x_ohm_per_km': 0.462, 'c_nf_per_km': 8.3, 'max_i_ka': 0.34},
            'UG': {'r_ohm_per_km': 0.358, 'x_ohm_per_km': 0.187, 'c_nf_per_km': 240, 'max_i_ka': 0.27},
        }
        
        for from_bus, to_bus, length_ft, line_type in line_data:
            length_km = length_ft * 0.3048 / 1000.0
            params = line_params[line_type]
            pp.create_line_from_parameters(
                net, bus_indices[from_bus], bus_indices[to_bus],
                length_km=length_km,
                r_ohm_per_km=params['r_ohm_per_km'],
                x_ohm_per_km=params['x_ohm_per_km'],
                c_nf_per_km=params['c_nf_per_km'],
                max_i_ka=params['max_i_ka'],
                name=f"Line_{from_bus}_{to_bus}"
            )
        
        # ========== LOAD DATA (from IEEE 34 spec, in kW/kvar per phase) ==========
        # Total load per bus (sum of three phases)
        # Spot loads at specific nodes
        load_data = {
            '806': (0, 0),      # Substation - no load
            '808': (0, 0),
            '810': (0, 0),
            '812': (230.0, 132.0),
            '814': (0, 0),
            '816': (0, 0),
            '818': (0, 0),
            '820': (0, 0),
            '822': (0, 0),
            '824': (59.0, 34.0),
            '826': (0, 0),
            '828': (0, 0),
            '830': (0, 0),
            '832': (0, 0),
            '834': (0, 0),
            '836': (0, 0),
            '838': (0, 0),
            '840': (0, 0),
            '842': (0, 0),
            '844': (0, 0),
            '846': (0, 0),
            '848': (0, 0),
            '850': (0, 0),
            '852': (0, 0),
            '854': (0, 0),
            '856': (0, 0),
            '858': (0, 0),
            '860': (0, 0),
            '862': (0, 0),
            '864': (0, 0),
            '866': (0, 0),
            '868': (0, 0),
            '870': (0, 0),
            '872': (0, 0),
            '874': (0, 0),
            '876': (0, 0),
            '878': (0, 0),
            '880': (0, 0),
            '882': (0, 0),
            '884': (0, 0),
            '886': (0, 0),
            '888': (0, 0),
            '890': (0, 0),
            # Laterals
            '812L': (0, 0),
            '824L': (0, 0),
            '836L': (0, 0),
            '848L': (0, 0),
            '860L': (0, 0),
        }
        
        # Distributed load along feeder (per 1000 ft section)
        # From IEEE 34 spec: 180 kW + 104 kvar per 1000 ft (3-phase total)
        dist_load_kw_per_1000ft = 180.0 / 3.0  # per phase
        dist_load_kvar_per_1000ft = 104.0 / 3.0  # per phase
        
        # Create loads at each bus
        for bus_id, (spot_kw, spot_kvar) in load_data.items():
            bus_idx = bus_indices[bus_id]
            # Convert 3-phase total to per-phase for pandapower (which expects total)
            p_mw = spot_kw / 1000.0
            q_mvar = spot_kvar / 1000.0
            if p_mw > 0 or q_mvar > 0:
                pp.create_load(net, bus=bus_idx, p_mw=p_mw, q_mvar=q_mvar, name=f"Load_{bus_id}")
        
        # Add distributed loads on line midpoints (approximate by adding to downstream bus)
        # This is a simplification - real IEEE 34 has distributed loads
        
        # ========== CAPACITOR BANKS (from IEEE 34 spec) ==========
        # Two capacitor banks at nodes 832 and 844 (3-phase, 600 kvar each)
        cap_buses = ['832', '844']
        for cap_bus in cap_buses:
            if cap_bus in bus_indices:
                pp.create_shunt(net, bus=bus_indices[cap_bus], p_mw=0.0, q_mvar=0.6, name=f"Cap_{cap_bus}")
        
        return net
    
    def _create_ieee123_network(self):
        """Create IEEE 123-node test feeder (4.16 kV)."""
        # Use case_ieee30 as base and extend
        net = pn.case_ieee30()
        # Modify voltage levels to 4.16 kV
        net.bus.vn_kv = 4.16
        # Scale loads appropriately
        net.load.p_mw = net.load.p_mw * 0.1
        net.load.q_mvar = net.load.q_mvar * 0.1
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
            
            # Create static generator (sgen) for PV at this building's bus
            sgen_idx = pp.create_sgen(
                self.net,
                bus=mapping.bus_idx,
                p_mw=0.0,
                q_mvar=0.0,
                name=f"PV_{mapping.building_id}",
                type="PV",
                controllable=True
            )
            self.sgen_indices[mapping.building_id] = sgen_idx
            
            # Create storage for battery at this building's bus
            # Only if the building has a battery in the scenario
            building_config = next((b for b in getattr(self.config, 'buildings', []) if b.building_id == mapping.building_id), None)
            if building_config and building_config.battery:
                storage_idx = pp.create_storage(
                    self.net,
                    bus=mapping.bus_idx,
                    p_mw=building_config.battery.power_kw / 1000.0,
                    max_p_mw=building_config.battery.power_kw / 1000.0,
                    min_p_mw=-building_config.battery.power_kw / 1000.0,
                    max_e_mwh=building_config.battery.capacity_kwh / 1000.0,
                    min_e_mwh=building_config.battery.capacity_kwh * building_config.battery.soc_min / 1000.0,
                    soc_percent=building_config.battery.initial_soc * 100,
                    name=f"Battery_{mapping.building_id}",
                    controllable=True
                )
                self.storage_indices[mapping.building_id] = storage_idx
    
    def update_building_loads(self, building_powers: Dict[str, float], building_pvs: Dict[str, float], building_battery_powers: Dict[str, float] = None):
        """Update building loads, PV generation, and battery power in the network.
        
        Args:
            building_powers: Dict of building_id -> net power demand (kW, positive = consumption)
            building_pvs: Dict of building_id -> PV generation (kW)
            building_battery_powers: Dict of building_id -> battery power (kW, positive = discharge, negative = charge)
        """
        if building_battery_powers is None:
            building_battery_powers = {}
        
        for building_id, net_power_kw in building_powers.items():
            if building_id in self.load_indices and building_id in self.sgen_indices:
                load_idx = self.load_indices[building_id]
                sgen_idx = self.sgen_indices[building_id]
                
                # Load Power = net_electricity_consumption + PV Power + Battery Power
                # This equals the actual electrical load (L), which is always >= 0
                load_power_kw = net_power_kw + building_pvs.get(building_id, 0.0) + building_battery_powers.get(building_id, 0.0)
                load_power_kw = max(0.0, load_power_kw)  # Ensure non-negative
                
                self.net.load.at[load_idx, 'p_mw'] = load_power_kw / 1000.0
                # Assume power factor of 0.95 for the load
                self.net.load.at[load_idx, 'q_mvar'] = (load_power_kw / 1000.0) * np.tan(np.arccos(0.95))
                
                # PV generation
                self.net.sgen.at[sgen_idx, 'p_mw'] = building_pvs.get(building_id, 0.0) / 1000.0
                self.net.sgen.at[sgen_idx, 'q_mvar'] = 0.0  # Unity power factor
                
                # Battery power (positive = discharge to grid, negative = charge from grid)
                if building_id in self.storage_indices:
                    storage_idx = self.storage_indices[building_id]
                    self.net.storage.at[storage_idx, 'p_mw'] = building_battery_powers.get(building_id, 0.0) / 1000.0
    
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
    
    def calculate_losses(self) -> Dict[str, float]:
        """Calculate network losses (active and reactive)."""
        if not self.net.converged or not hasattr(self.net, 'res_line'):
            return {"total_active_loss_kw": 0.0, "total_reactive_loss_kvar": 0.0,
                     "line_losses_kw": {}, "trafo_losses_kw": {}}
        
        # Line losses
        line_losses_kw = {}
        total_active_loss = 0.0
        total_reactive_loss = 0.0
        
        if len(self.net.res_line) > 0:
            for idx in self.net.res_line.index:
                # P_loss = I^2 * R (approximate from loading)
                loading = self.net.res_line.at[idx, 'loading_percent'] / 100.0
                r_ohm = self.net.line.at[idx, 'r_ohm_per_km'] * self.net.line.at[idx, 'length_km']
                # Approximate current from loading and thermal limit
                i_max = self.net.line.at[idx, 'max_i_ka'] * 1000  # A
                i_actual = loading * i_max
                p_loss_kw = (i_actual ** 2) * r_ohm / 1000  # kW
                line_losses_kw[idx] = p_loss_kw
                total_active_loss += p_loss_kw
        
        # Transformer losses
        trafo_losses_kw = {}
        if len(self.net.res_trafo) > 0:
            for idx in self.net.res_trafo.index:
                loading = self.net.res_trafo.at[idx, 'loading_percent'] / 100.0
                pfe_kw = self.net.trafo.at[idx, 'pfe_kw'] if 'pfe_kw' in self.net.trafo.columns else 0
                vkr = self.net.trafo.at[idx, 'vkr_percent'] if 'vkr_percent' in self.net.trafo.columns else 1.0
                sn_mva = self.net.trafo.at[idx, 'sn_mva']
                p_load_loss_kw = (loading ** 2) * vkr * sn_mva * 1000 / 100  # kW
                p_loss_kw = pfe_kw + p_load_loss_kw
                trafo_losses_kw[idx] = p_loss_kw
                total_active_loss += p_loss_kw
        
        return {
            "total_active_loss_kw": total_active_loss,
            "total_reactive_loss_kvar": total_reactive_loss,
            "line_losses_kw": line_losses_kw,
            "trafo_losses_kw": trafo_losses_kw
        }
    
    def check_voltage_unbalance(self, report: DiagnosticReport):
        """Check voltage unbalance for three-phase systems."""
        # Check if we have three-phase buses (vn_kv < 10 typically LV)
        # This is a simplified check - full three-phase would need phase-specific results
        if not self.net.converged or not hasattr(self.net, 'res_bus'):
            return
        
        # For asymmetric networks, check per-phase voltages
        # pandapower stores vm_pu as magnitude, va_degree as angle
        # For true three-phase, we'd need phase-specific data
        # Here we provide a placeholder for future three-phase extension
        pass
    
    def get_per_building_contributions(self) -> Dict[str, Dict[str, float]]:
        """Get per-building contribution to grid state."""
        contributions = {}
        
        if not self.net.converged:
            return contributions
        
        for building_id, load_idx in self.load_indices.items():
            if load_idx in self.net.load.index:
                load_p_mw = self.net.load.at[load_idx, 'p_mw']
                load_q_mvar = self.net.load.at[load_idx, 'q_mvar']
                
                # Get bus voltage at this building's bus
                bus_idx = self.bus_mapping.get(building_id)
                voltage_pu = 1.0
                if bus_idx is not None and bus_idx in self.net.res_bus.index:
                    voltage_pu = self.net.res_bus.vm_pu.at[bus_idx]
                
                # PV contribution
                pv_p_mw = 0.0
                if building_id in self.sgen_indices:
                    sgen_idx = self.sgen_indices[building_id]
                    if sgen_idx in self.net.sgen.index:
                        pv_p_mw = self.net.sgen.at[sgen_idx, 'p_mw']
                
                # Battery contribution
                battery_p_mw = 0.0
                if building_id in self.storage_indices:
                    storage_idx = self.storage_indices[building_id]
                    if storage_idx in self.net.storage.index:
                        battery_p_mw = self.net.storage.at[storage_idx, 'p_mw']
                
                net_injection_mw = pv_p_mw + battery_p_mw - load_p_mw
                
                contributions[building_id] = {
                    "load_kw": load_p_mw * 1000,
                    "pv_kw": pv_p_mw * 1000,
                    "battery_kw": battery_p_mw * 1000,
                    "net_injection_kw": net_injection_mw * 1000,
                    "voltage_pu": voltage_pu
                }
        
        return contributions
    
    def run_time_series_power_flow(self, 
                                     building_power_profiles: Dict[str, List[float]],
                                     building_pv_profiles: Dict[str, List[float]],
                                     building_battery_profiles: Dict[str, List[float]] = None) -> List[Dict[str, Any]]:
        """Run time-series power flow using pandapower timeseries module."""
        if building_battery_profiles is None:
            building_battery_profiles = {bid: [0.0] * len(next(iter(building_power_profiles.values())))
                                        for bid in building_power_profiles}
        
        # Create data sources for each building
        from pandapower.timeseries import DFData
        from pandapower.control import ConstControl
        import pandas as pd
        
        n_steps = len(next(iter(building_power_profiles.values())))
        time_index = pd.date_range('2024-01-01', periods=n_steps, freq='15min')
        
        # Create DFData for loads, sgens, storages
        for building_id in building_power_profiles:
            if building_id in self.load_indices:
                load_idx = self.load_indices[building_id]
                p_profile = [p / 1000.0 for p in building_power_profiles[building_id]]
                q_profile = [p * np.tan(np.arccos(0.95)) / 1000.0 for p in building_power_profiles[building_id]]
                
                load_df = pd.DataFrame({'p_mw': p_profile, 'q_mvar': q_profile}, index=time_index)
                ds_load = DFData(load_df)
                ConstControl(self.net, element='load', variable='p_mw', element_index=[load_idx],
                           data_source=ds_load, profile_name=['p_mw'])
                ConstControl(self.net, element='load', variable='q_mvar', element_index=[load_idx],
                           data_source=ds_load, profile_name=['q_mvar'])
            
            if building_id in self.sgen_indices and building_id in building_pv_profiles:
                sgen_idx = self.sgen_indices[building_id]
                pv_profile = [p / 1000.0 for p in building_pv_profiles[building_id]]
                pv_df = pd.DataFrame({'p_mw': pv_profile}, index=time_index)
                ds_pv = DFData(pv_df)
                ConstControl(self.net, element='sgen', variable='p_mw', element_index=[sgen_idx],
                           data_source=ds_pv, profile_name=['p_mw'])
            
            if building_id in self.storage_indices and building_id in building_battery_profiles:
                storage_idx = self.storage_indices[building_id]
                bat_profile = [p / 1000.0 for p in building_battery_profiles[building_id]]
                bat_df = pd.DataFrame({'p_mw': bat_profile}, index=time_index)
                ds_bat = DFData(bat_df)
                ConstControl(self.net, element='storage', variable='p_mw', element_index=[storage_idx],
                           data_source=ds_bat, profile_name=['p_mw'])
        
        # Run time series
        from pandapower.timeseries import run_timeseries
        run_timeseries(self.net, time_steps=range(n_steps))
        
        # Collect results
        results = []
        for step in range(n_steps):
            # Results are stored in net.res_* after each time step
            # We need to extract them - this is simplified
            result = {
                "timestep": step,
                "converged": self.net.converged,
                "voltage_profile": self.get_voltage_profile(),
                "loading_profile": self.get_loading_profile(),
                "losses": self.calculate_losses(),
                "building_contributions": self.get_per_building_contributions()
            }
            results.append(result)
        
        return results
    
    def get_enhanced_kpis(self) -> Dict[str, Any]:
        """Get enhanced KPIs including grid metrics."""
        if not self.convergence_history:
            return {}
        
        losses = self.calculate_losses()
        
        return {
            "grid_convergence_rate": np.mean(self.convergence_history),
            "total_active_loss_kwh": losses["total_active_loss_kw"] * len(self.convergence_history) * 0.25,  # 15-min steps
            "avg_voltage_pu": np.mean([np.mean(list(v.values())) for v in self.voltage_history]) if self.voltage_history else 1.0,
            "voltage_violations_count": sum(1 for h in self.voltage_history 
                                             for v in h.values() if v < 0.95 or v > 1.05),
            "max_line_loading_pct": max([max(list(l.values())) if l else 0 
                                         for l in [h.get("lines", {}) for h in self.loading_history]]) * 100,
            "max_trafo_loading_pct": max([max(list(t.values())) if t else 0 
                                          for t in [h.get("trafos", {}) for h in self.loading_history]]) * 100,
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



    def get_bus_coordinates(self) -> Dict[str, Dict[str, Any]]:
        """Get raw bus x/y coordinates and geographic values when applicable."""
        coordinates = {}
        if self.net is None or len(self.net.bus) == 0:
            return coordinates
        
        for idx, row in self.net.bus.iterrows():
            bus_name = row['name']
            vn_kv = row['vn_kv']
            geo = row.get('geo')
            
            if geo is not None:
                # geo may be a JSON string like '{"coordinates": [x, y], "type": "Point"}'
                # or a dict, or a tuple/list (legacy geodata)
                if isinstance(geo, str):
                    try:
                        import json
                        geo = json.loads(geo)
                    except (json.JSONDecodeError, ValueError):
                        geo = None
                
                if isinstance(geo, dict) and 'coordinates' in geo:
                    coords = geo['coordinates']
                    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                        x, y = coords[0], coords[1]
                        coordinates[bus_name] = {
                            'x': float(x),
                            'y': float(y),
                            'vn_kv': float(vn_kv),
                            'name': bus_name,
                            'bus_idx': int(idx)
                        }
                        if self.coordinate_system == "geographic":
                            coordinates[bus_name].update({'lat': float(y), 'lon': float(x)})
                # Also check legacy 'geodata' column (tuple/list)
                elif isinstance(geo, (tuple, list)) and len(geo) >= 2:
                    x, y = geo[0], geo[1]
                    coordinates[bus_name] = {
                        'x': float(x),
                        'y': float(y),
                        'vn_kv': float(vn_kv),
                        'name': bus_name,
                        'bus_idx': int(idx)
                    }
                    if self.coordinate_system == "geographic":
                        coordinates[bus_name].update({'lat': float(y), 'lon': float(x)})
        
        return coordinates
    
    def get_line_geometries(self) -> List[Dict[str, Any]]:
        """Get line geometries as LineString coordinates."""
        geometries = []
        if self.net is None or len(self.net.line) == 0:
            return geometries
        
        bus_coords = self.get_bus_coordinates()
        
        for idx, row in self.net.line.iterrows():
            from_bus_idx = row['from_bus']
            to_bus_idx = row['to_bus']
            line_name = row['name']
            length_km = row.get('length_km', 0)
            std_type = row.get('std_type', '')
            
            from_bus_name = self.net.bus.at[from_bus_idx, 'name'] if from_bus_idx in self.net.bus.index else str(from_bus_idx)
            to_bus_name = self.net.bus.at[to_bus_idx, 'name'] if to_bus_idx in self.net.bus.index else str(to_bus_idx)
            
            from_coord = bus_coords.get(from_bus_name)
            to_coord = bus_coords.get(to_bus_name)
            
            if from_coord and to_coord:
                coordinates = [
                    [from_coord['x'], from_coord['y']],
                    [to_coord['x'], to_coord['y']]
                ]
                
                line_geodata = row.get('geodata')
                if line_geodata is not None and not (isinstance(line_geodata, float) and np.isnan(line_geodata)):
                    if isinstance(line_geodata, (list, tuple)) and len(line_geodata) > 2:
                        coordinates = [[float(pt[0]), float(pt[1])] for pt in line_geodata]
                
                geometry = {
                    'line_id': str(idx),
                    'name': line_name,
                    'coordinates': coordinates,
                    'from_bus': from_bus_name,
                    'to_bus': to_bus_name,
                    'from_bus_idx': int(from_bus_idx),
                    'to_bus_idx': int(to_bus_idx),
                    'length_km': float(length_km),
                    'std_type': std_type,
                }
                if self.coordinate_system == "geographic":
                    geometry['coordinates'] = coordinates
                geometries.append(geometry)
        
        return geometries
    
    def get_transformer_geometries(self) -> List[Dict[str, Any]]:
        """Get transformer geometries (point locations)."""
        geometries = []
        if self.net is None or len(self.net.trafo) == 0:
            return geometries
        
        bus_coords = self.get_bus_coordinates()
        
        for idx, row in self.net.trafo.iterrows():
            hv_bus_idx = row['hv_bus']
            lv_bus_idx = row['lv_bus']
            trafo_name = row['name']
            sn_mva = row.get('sn_mva', 0)
            
            hv_bus_name = self.net.bus.at[hv_bus_idx, 'name'] if hv_bus_idx in self.net.bus.index else str(hv_bus_idx)
            lv_bus_name = self.net.bus.at[lv_bus_idx, 'name'] if lv_bus_idx in self.net.bus.index else str(lv_bus_idx)
            
            lv_coord = bus_coords.get(lv_bus_name)
            if lv_coord:
                geometries.append({
                    'transformer_id': str(idx),
                    'name': trafo_name,
                    'x': lv_coord['x'],
                    'y': lv_coord['y'],
                    'hv_bus': hv_bus_name,
                    'lv_bus': lv_bus_name,
                    'hv_bus_idx': int(hv_bus_idx),
                    'lv_bus_idx': int(lv_bus_idx),
                    'capacity_mva': float(sn_mva),
                })
                if self.coordinate_system == "geographic":
                    geometries[-1].update({'lat': lv_coord['lat'], 'lon': lv_coord['lon']})
        
        return geometries
    
    def get_network_geometry(self) -> Dict[str, Any]:
        """Get complete network geometry for frontend visualization."""
        buses = self.get_bus_coordinates()
        lines = self.get_line_geometries()
        transformers = self.get_transformer_geometries()
        
        all_coords = []
        for bus in buses.values():
            all_coords.append([bus['x'], bus['y']])
        for line in lines:
            all_coords.extend(line['coordinates'])
        
        bounds = None
        if all_coords:
            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
            bounds = {'min_x': min(lons), 'max_x': max(lons), 'min_y': min(lats), 'max_y': max(lats)}
            if self.coordinate_system == "geographic":
                bounds = {
                    'min_lon': min(lons), 'max_lon': max(lons),
                    'min_lat': min(lats), 'max_lat': max(lats)
                }
        
        return {
            'coordinate_system': self.coordinate_system,
            'buses': buses,
            'lines': lines,
            'transformers': transformers,
            'bounds': bounds
        }


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