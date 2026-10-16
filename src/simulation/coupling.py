"""Coupling module for CityLearn-pandapower co-simulation."""
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass

from src.schemas.scenario import ScenarioConfig
from src.schemas.action import (
    RequestedActions, LimitedActions, AppliedActions, SimulationStepResult, Action, ActionType
)
from src.schemas.diagnostics import DiagnosticReport, Diagnostic, DiagnosticCategory, Severity
from .citylearn_adapter import CityLearnAdapter, create_citylearn_adapter
from .pandapower_adapter import PandapowerAdapter, create_grid_from_scenario


def _convert_to_json_serializable(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_to_json_serializable(v) for v in obj)
    else:
        return obj


@dataclass
class CoSimulationStepResult:
    """Result of one co-simulation step."""
    timestep: int
    citylearn_result: SimulationStepResult
    grid_diagnostics: DiagnosticReport
    power_flow_converged: bool
    combined_violations: List[str]
    terminated: bool = False
    truncated: bool = False


class SimulationCoupler:
    """Couples CityLearn community simulation with pandapower grid validation."""
    
    def __init__(self, scenario_config: ScenarioConfig, data_dir: str = "data"):
        self.scenario_config = scenario_config
        self.data_dir = data_dir
        
        # Initialize adapters
        self.citylearn = create_citylearn_adapter(scenario_config, data_dir)
        self.pandapower = create_grid_from_scenario(scenario_config)
        
        # State tracking
        self.current_timestep = 0
        self.co_sim_history: List[CoSimulationStepResult] = []
        self.run_power_flow_every = scenario_config.pandapower.run_power_flow_every if scenario_config.pandapower else 1
    
    def reset(self, random_seed: Optional[int] = None) -> Dict[str, Any]:
        """Reset both simulators."""
        seed = random_seed or self.scenario_config.random_seed
        observations = self.citylearn.reset(seed)
        self.pandapower.reset()
        self.current_timestep = 0
        self.co_sim_history = []
        return observations
    
    def step(self, requested_actions: RequestedActions) -> CoSimulationStepResult:
        """Execute one co-simulation step."""
        # Step CityLearn
        observations, cl_result = self.citylearn.step(requested_actions)
        
        # Extract building powers for grid
        building_powers, building_pvs, building_battery_powers = self._extract_building_powers(cl_result)
        
        # Update grid loads
        self.pandapower.update_building_loads(building_powers, building_pvs, building_battery_powers)
        
        # Run power flow at specified intervals
        grid_diagnostics = DiagnosticReport(
            scenario_id=self.scenario_config.scenario_id,
            run_id=f"cosim_step_{self.current_timestep}",
            timestep=self.current_timestep
        )
        power_flow_converged = True
        
        if self.current_timestep % self.run_power_flow_every == 0:
            power_flow_converged, grid_diagnostics = self.pandapower.run_power_flow()
            
            # Check community grid limits
            if self.scenario_config.community_import_limit_kw or self.scenario_config.community_export_limit_kw:
                import_kw = sum(p for p in building_powers.values() if p > 0)
                export_kw = sum(-p for p in building_powers.values() if p < 0)
                
                import_limit = self.scenario_config.community_import_limit_kw or float('inf')
                export_limit = self.scenario_config.community_export_limit_kw or float('inf')
                
                grid_limit_diagnostics = self.pandapower.check_grid_limits(
                    import_kw, export_kw, import_limit, export_limit
                )
                for d in grid_limit_diagnostics:
                    grid_diagnostics.add_diagnostic(d)
            
            # Add per-building contributions and losses to diagnostics
            if power_flow_converged:
                building_contributions = self.pandapower.get_per_building_contributions()
                losses = self.pandapower.calculate_losses()
                grid_diagnostics.building_contributions = building_contributions
                grid_diagnostics.losses = losses
        
        # Combine violations
        combined_violations = cl_result.constraint_violations.copy()
        combined_violations.extend([str(d) for d in grid_diagnostics.diagnostics 
                                   if d.severity in [Severity.VIOLATION, Severity.CRITICAL]])
        
        # Create co-simulation result
        cosim_result = CoSimulationStepResult(
            timestep=self.current_timestep,
            citylearn_result=cl_result,
            grid_diagnostics=grid_diagnostics,
            power_flow_converged=power_flow_converged,
            combined_violations=combined_violations,
            terminated=cl_result.terminated,
            truncated=cl_result.truncated
        )
        
        # Attach grid diagnostics to CityLearn result
        grid_diag_dict = {
            "power_flow_converged": power_flow_converged,
            "diagnostics": [d.model_dump() for d in grid_diagnostics.diagnostics],
            "voltage_profile": self.pandapower.get_voltage_profile(),
            "loading_profile": self.pandapower.get_loading_profile()
        }
        
        # Add building contributions and losses if available
        if hasattr(grid_diagnostics, 'building_contributions'):
            grid_diag_dict["building_contributions"] = grid_diagnostics.building_contributions
        if hasattr(grid_diagnostics, 'losses'):
            grid_diag_dict["losses"] = grid_diagnostics.losses
        
        cl_result.grid_diagnostics = grid_diag_dict
        
        self.co_sim_history.append(cosim_result)
        self.current_timestep += 1
        
        return cosim_result
    
    def _extract_building_powers(
        self, 
        cl_result: SimulationStepResult
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Extract building net power demand, PV generation, and battery power from CityLearn result."""
        building_powers = {}
        building_pvs = {}
        building_battery_powers = {}
        
        # From observations
        obs = cl_result.observations
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            
            # Net electrical demand (positive = consumption)
            net_demand_key = f"{bid}_net_electricity_consumption"
            if net_demand_key in obs:
                building_powers[bid] = float(obs[net_demand_key])
            else:
                # Fallback: sum of loads - PV
                load_key = f"{bid}_non_shiftable_load"
                pv_key = f"{bid}_solar_generation"
                load = float(obs.get(load_key, 0))
                pv = float(obs.get(pv_key, 0))
                building_powers[bid] = load
                building_pvs[bid] = pv
            
            # PV generation
            pv_key = f"{bid}_solar_generation"
            if pv_key in obs:
                building_pvs[bid] = float(obs[pv_key])
            elif bid not in building_pvs:
                building_pvs[bid] = 0.0
            
            # Battery power (positive = discharge, negative = charge)
            # Check observations for battery power
            battery_power_key = f"{bid}_battery_power"
            if battery_power_key in obs:
                building_battery_powers[bid] = float(obs[battery_power_key])
            else:
                # Try to infer from applied actions
                for action in cl_result.applied_actions.actions:
                    # asset_id format: {building_id}_battery or {building_id}_ev_{i}
                    if action.asset_id.startswith(bid + "_battery"):
                        if action.action_type == ActionType.BATTERY_CHARGE:
                            building_battery_powers[bid] = -float(action.value_kw)  # Negative = charge
                        elif action.action_type == ActionType.BATTERY_DISCHARGE:
                            building_battery_powers[bid] = float(action.value_kw)  # Positive = discharge
                        break
                else:
                    building_battery_powers[bid] = 0.0
        
        return building_powers, building_pvs, building_battery_powers
    
    def get_kpis(self) -> Dict[str, Any]:
        """Get combined KPIs from both simulators."""
        cl_kpis = self.citylearn.get_kpis()
        
        # Get enhanced grid KPIs from pandapower adapter
        grid_kpis = self.pandapower.get_enhanced_kpis()
        
        return {
            **cl_kpis,
            **grid_kpis,
            "grid_voltage_violations": sum(1 for h in self.co_sim_history 
                                          for d in h.grid_diagnostics.diagnostics 
                                          if d.category == DiagnosticCategory.VOLTAGE),
            "grid_line_violations": sum(1 for h in self.co_sim_history 
                                       for d in h.grid_diagnostics.diagnostics 
                                       if d.category == DiagnosticCategory.LINE_LOADING),
            "grid_trafo_violations": sum(1 for h in self.co_sim_history 
                                        for d in h.grid_diagnostics.diagnostics 
                                        if d.category == DiagnosticCategory.TRANSFORMER_LOADING),
        }
    
    def get_per_building_contributions(self) -> List[Dict[str, Dict[str, float]]]:
        """Get per-building contributions for each timestep."""
        contributions_history = []
        for h in self.co_sim_history:
            # The pandapower adapter stores contributions per timestep in the grid_diagnostics
            if h.citylearn_result.grid_diagnostics and "building_contributions" in h.citylearn_result.grid_diagnostics:
                contributions_history.append(h.citylearn_result.grid_diagnostics["building_contributions"])
        return contributions_history
    
    def close(self):
        """Close both simulators."""
        self.citylearn.close()
    
    def export_results(self, output_dir: str):
        """Export all results to files."""
        import os
        import json
        os.makedirs(output_dir, exist_ok=True)
        
        # Export CityLearn trajectories
        trajectories = []
        for h in self.co_sim_history:
            traj = {
                "timestep": h.timestep,
                "requested_actions": [a.model_dump() for a in h.citylearn_result.requested_actions.actions],
                "limited_actions": [a.model_dump() for a in h.citylearn_result.limited_actions.actions],
                "applied_actions": [a.model_dump() for a in h.citylearn_result.applied_actions.actions],
                "observations": h.citylearn_result.observations,
                "rewards": h.citylearn_result.rewards,
                "costs": h.citylearn_result.costs,
                "constraint_violations": h.citylearn_result.constraint_violations,
                "grid_diagnostics": h.citylearn_result.grid_diagnostics
            }
            trajectories.append(_convert_to_json_serializable(traj))
        
        with open(os.path.join(output_dir, "trajectories.jsonl"), "w") as f:
            for t in trajectories:
                f.write(json.dumps(t) + "\n")
        
        # Export grid diagnostics
        grid_diags = []
        for h in self.co_sim_history:
            for d in h.grid_diagnostics.diagnostics:
                grid_diags.append(d.model_dump())
        
        with open(os.path.join(output_dir, "grid_diagnostics.jsonl"), "w") as f:
            for d in grid_diags:
                f.write(json.dumps(d) + "\n")
        
        # Export pandapower network
        self.pandapower.export_results(os.path.join(output_dir, "pandapower_network.json"))
        
        # Export KPIs
        kpis = self.get_kpis()
        with open(os.path.join(output_dir, "kpis.json"), "w") as f:
            json.dump(kpis, f, indent=2)


def run_co_simulation(
    scenario_config: ScenarioConfig,
    controller,
    data_dir: str = "data",
    max_steps: Optional[int] = None
) -> List[CoSimulationStepResult]:
    """Run a complete co-simulation with a given controller.
    
    Args:
        scenario_config: Scenario configuration
        controller: Controller object with `get_actions(observations, timestep)` method
        data_dir: Data directory
        max_steps: Maximum steps to run (None = full episode)
    
    Returns:
        List of co-simulation step results
    """
    coupler = SimulationCoupler(scenario_config, data_dir)
    observations = coupler.reset()
    
    results = []
    step = 0
    
    while True:
        # Get actions from controller
        requested_actions = controller.get_actions(observations, step)
        
        # Step co-simulation
        cosim_result = coupler.step(requested_actions)
        results.append(cosim_result)
        
        # Check termination
        observations = cosim_result.citylearn_result.observations
        step += 1
        
        if max_steps and step >= max_steps:
            break
        
        # Check if episode done (all buildings terminated)
        # This depends on CityLearn's termination criteria
        if all(v.get("terminated", False) for v in observations.values() if isinstance(v, dict)):
            break
    
    coupler.close()
    return results