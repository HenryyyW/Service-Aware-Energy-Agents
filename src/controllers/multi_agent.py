"""Multi-agent controller for energy community coordination."""

from typing import List, Dict, Any, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.coordination.coordinator import CoordinationResult

from src.controllers import BaseController, RuleBasedController
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import ScenarioConfig
from src.coordination import create_coordinator


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
        max_iterations: int = 3,
    ):
        super().__init__(scenario_config)
        self.coordinator = create_coordinator(
            scenario_config=scenario_config,
            pandapower_network=pandapower_network,
            max_iterations=max_iterations,
        )
        self.last_coordination_result: Optional["CoordinationResult"] = None
        # For semantic fallback detection (run_experiment.py + API/UI): if this
        # controller produces battery actions identical to rule_based, it will be
        # marked as fallback. Both run_experiment and the API route check
        # hasattr(controller, "fallback_steps") and fallback_steps > 0.
        self._rule_based = RuleBasedController(scenario_config)
        self.fallback_steps: int = 0
        self.fallback_reason: Optional[str] = None

    def get_actions(
        self, observations: Dict[str, Any], timestep: int
    ) -> RequestedActions:
        """Get coordinated actions for the current timestep."""
        # Run coordination protocol
        self.last_coordination_result = self.coordinator.coordinate(
            observations, timestep
        )

        # Get actions from coordinator
        actions = self.coordinator.get_actions()

        # Set timestep on all actions
        for action in actions:
            action.timestep = timestep

        # Apply community grid limits as final safety check
        actions = self._apply_grid_limits(actions)

        # Apply grid violation re-dispatch based on previous step pandapower diagnostics
        actions = self._apply_grid_violation_redispatch(actions)

        requested_actions = self._create_requested_actions(actions)

        # Semantic fallback detection (mirrors run_experiment.py): if battery
        # actions match rule_based exactly, count as fallback step. Both the
        # benchmark and the API route check hasattr(controller, "fallback_steps")
        # and fallback_steps > 0.
        rule_based_actions = self._rule_based.get_actions(observations, timestep)
        if self._battery_actions_equal(requested_actions, rule_based_actions):
            self.fallback_steps += 1
            if self.fallback_reason is None:
                self.fallback_reason = "fallback_to_rule_based"

        return requested_actions

    @staticmethod
    def _battery_actions_equal(
        actions_a: RequestedActions, actions_b: RequestedActions
    ) -> bool:
        """Check if two RequestedActions have the same battery actions.

        Mirrors run_experiment.py's _actions_equal: compare only battery actions
        by (asset_id, action_type) -> value_kw mapping.
        """
        actions_a_dict = {
            (a.asset_id, a.action_type): a.value_kw for a in actions_a.actions
        }
        actions_b_dict = {
            (a.asset_id, a.action_type): a.value_kw for a in actions_b.actions
        }

        # Compare battery actions only
        battery_keys_a = {
            k: v for k, v in actions_a_dict.items() if "battery" in k[0].lower()
        }
        battery_keys_b = {
            k: v for k, v in actions_b_dict.items() if "battery" in k[0].lower()
        }

        if battery_keys_a.keys() != battery_keys_b.keys():
            return False

        for key in battery_keys_a:
            if abs(battery_keys_a[key] - battery_keys_b[key]) > 1e-6:
                return False

        return True

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
                scale = 0.8  # Reduce power to fix line loading
            else:  # transformer_loading
                scale = 0.9

            # Apply scaling to controllable actions (battery, EV, flexible load)
            for a in actions:
                if a.action_type in [
                    ActionType.BATTERY_CHARGE,
                    ActionType.BATTERY_DISCHARGE,
                    ActionType.EV_CHARGE,
                    ActionType.FLEXIBLE_LOAD,
                ]:
                    a.value_kw *= scale

        return actions

    def _apply_grid_limits(self, actions: List[Action]) -> List[Action]:
        """Apply community-level grid import/export limits."""
        if (
            not self.scenario_config.community_import_limit_kw
            and not self.scenario_config.community_export_limit_kw
        ):
            return actions

        total_import = sum(a.value_kw for a in actions if a.value_kw > 0)
        total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)

        import_limit = self.scenario_config.community_import_limit_kw or float("inf")
        export_limit = self.scenario_config.community_export_limit_kw or float("inf")

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
            ),
        }

    def reset(self):
        super().reset()
        self.coordinator.reset()
        self._rule_based.reset()
        self.fallback_steps = 0
        self.fallback_reason = None
        self.last_coordination_result = None
