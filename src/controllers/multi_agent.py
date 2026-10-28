"""Multi-agent controller for energy community coordination."""
from typing import Optional, List, Dict, Any

from src.controllers import BaseController
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import ScenarioConfig
from src.coordination import MultiAgentCoordinator, create_coordinator


class MultiAgentController(BaseController):
    """Controller using multi-agent hierarchical coordination.
    
    This controller orchestrates building, battery, EV, and flexible load agents
    through a community aggregator to produce coordinated actions that respect
    both local constraints and grid limits.
    """
    
    def __init__(
        self, 
        scenario_config: ScenarioConfig,
        pandapower_network=None,
        max_iterations: int = 3
    ):
        super().__init__(scenario_config)
        self.coordinator = create_coordinator(
            scenario_config=scenario_config,
            pandapower_network=pandapower_network,
            max_iterations=max_iterations
        )
        self.last_coordination_result = None
    
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        """Get coordinated actions for the current timestep."""
        # Run coordination protocol
        self.last_coordination_result = self.coordinator.coordinate(observations, timestep)
        
        # Get actions from coordinator
        actions = self.coordinator.get_actions()
        
        # Set timestep on all actions
        for action in actions:
            action.timestep = timestep
        
        # Apply community grid limits as final safety check
        actions = self._apply_grid_limits(actions)
        
        # Apply grid violation re-dispatch based on previous step pandapower diagnostics
        actions = self._apply_grid_violation_redispatch(actions)
        
        return self._create_requested_actions(actions)
    
    def _apply_grid_violation_redispatch(self, actions: List[Action]) -> List[Action]:
        """Re-dispatch actions based on actual grid violations from previous step.
        
        Uses the actual pandapower diagnostics (not the coordinator's internal validation)
        to adjust actions when real violations occurred.
        """
        if not self.last_grid_diagnostics:
            return actions
        
        diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
        voltage_violated = False
        line_loading_violated = False
        transformer_loading_violated = False
        
        for d in diagnostics:
            category = d.get("category", "")
            severity = d.get("severity", "")
            if severity in ["violation", "critical"]:
                if category == "voltage":
                    voltage_violated = True
                elif category == "line_loading":
                    line_loading_violated = True
                elif category == "transformer_loading":
                    transformer_loading_violated = True
        
        # If violations detected, apply re-dispatch scaling
        if voltage_violated or line_loading_violated or transformer_loading_violated:
            # Determine scaling factor based on violation type
            if voltage_violated:
                scale = 0.85  # Reduce export/charging to raise voltage
            elif line_loading_violated:
                scale = 0.8   # Reduce power to fix line loading
            else:  # transformer_loading
                scale = 0.9
            
            # Apply scaling to controllable actions (battery, EV, flexible load)
            for a in actions:
                if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                                     ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                    a.value_kw *= scale
        
        return actions
    
    def _apply_grid_limits(self, actions: List[Action]) -> List[Action]:
        """Apply community-level grid import/export limits."""
        if not self.scenario_config.community_import_limit_kw and \
           not self.scenario_config.community_export_limit_kw:
            return actions
        
        total_import = sum(a.value_kw for a in actions if a.value_kw > 0)
        total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)
        
        import_limit = self.scenario_config.community_import_limit_kw or float('inf')
        export_limit = self.scenario_config.community_export_limit_kw or float('inf')
        
        if total_import > import_limit:
            scale = import_limit / total_import
            for a in actions:
                if a.value_kw > 0:
                    a.value_kw *= scale
        
        if total_export > export_limit:
            scale = export_limit / total_export
            for a in actions:
                if a.value_kw < 0:
                    a.value_kw *= scale
        
        return actions
    
    def update_from_simulation(self, observations: Dict[str, Any]):
        """Update internal state from simulation observations."""
        self.coordinator.update_state(observations)
    
    def get_coordination_info(self) -> Dict[str, Any]:
        """Get information about last coordination round."""
        if self.last_coordination_result is None:
            return {}
        
        return {
            "iterations": self.last_coordination_result.iterations,
            "converged": self.last_coordination_result.converged,
            "grid_validation_passed": self.last_coordination_result.grid_validation_passed,
            "grid_violations": self.last_coordination_result.grid_violations,
            "total_import_kw": sum(
                max(0, a.requested_power_kw) 
                for a in self.last_coordination_result.final_allocations.values()
            ),
            "total_export_kw": sum(
                -min(0, a.requested_power_kw) 
                for a in self.last_coordination_result.final_allocations.values()
            )
        }
    
    def reset(self):
        super().reset()
        self.coordinator.reset()
        self.last_coordination_result = None