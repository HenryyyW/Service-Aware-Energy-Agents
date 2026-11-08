"""Deterministic safety baseline controller.

Implements a pure code-path safety layer that bounds-checks and projects/clamps
proposals with NO LLM re-prompt. This provides the reviewer's requested
comparison: a simple deterministic safety layer vs. the LLM verification arm.

Records the 5-level stratification the reviewer demands:
(1) raw proposal bound violations
(2) accepted by agent layer
(3) adapter interventions (clamping by CityLearnAdapter)
(4) final applied-action violations
(5) post-execution grid/service violations
"""

from typing import Optional, List, Dict, Any, Tuple
from collections import Counter

from src.schemas.action import (
    RequestedActions,
    Action,
    LimitedActions,
    AppliedActions,
)
from src.schemas.scenario import ScenarioConfig
from src.controllers import BaseController


class DeterministicSafetyController(BaseController):
    """Deterministic safety baseline: bounds-check + projection/clamping.

    Wraps any proposer (LLM, rule-based, etc.) and applies a pure code-path
    safety layer with NO LLM re-prompt. The proposer's raw output is clamped
    to device power bounds before being sent to the simulation adapter.

    This is the "simple deterministic safety layer" the reviewer asked for
    as a comparison against the LLM verification arm.
    """

    def __init__(
        self,
        scenario_config: ScenarioConfig,
        proposer: Optional[BaseController] = None,
        device_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        super().__init__(scenario_config)
        self.proposer = proposer
        self.device_metadata = device_metadata or {}

        # 5-level stratification counters
        self._level1_raw_proposal_violations: Counter = (
            Counter()
        )  # raw proposal bound violations
        self._level2_accepted_by_agent: Counter = Counter()  # accepted by agent layer
        self._level3_adapter_interventions: Counter = (
            Counter()
        )  # adapter interventions (clamping)
        self._level4_final_applied_violations: Counter = (
            Counter()
        )  # final applied-action violations
        self._level5_post_execution_violations: Counter = (
            Counter()
        )  # post-execution grid/service violations

        # Detailed per-step records for analysis
        self._stratification_history: List[Dict[str, Any]] = []

        # Expose adapter for clamping inspection
        self._adapter = None

    def set_adapter(self, adapter):
        """Set the CityLearn adapter reference for clamping inspection."""
        self._adapter = adapter
        # Also set on proposer if it has the method
        if self.proposer and hasattr(self.proposer, "set_adapter"):
            self.proposer.set_adapter(adapter)

    def set_proposer(self, proposer: BaseController):
        """Set the proposer after initialization."""
        self.proposer = proposer

    def _asset_power_limit(self, asset_id: str) -> Optional[float]:
        """Get the device power limit for an asset from live metadata."""
        for bid, meta in self.device_metadata.items():
            battery = meta.get("battery")
            if battery and asset_id == f"{bid}_battery":
                return float(battery.get("power_kw") or 0.0) or None
            for index, charger in enumerate(meta.get("chargers", [])):
                if asset_id == f"{bid}_ev_{index}":
                    return float(charger.get("max_charge_kw") or 0.0) or None
            for index, flex in enumerate(meta.get("deferrable", [])):
                if asset_id == f"{bid}_flex_{index}":
                    return float(flex.get("power_kw") or 0.0) or None
        return None

    def _clamp_to_bounds(
        self, actions: List[Action]
    ) -> Tuple[List[Action], Dict[str, int]]:
        """Clamp actions to device power bounds.

        Returns (clamped_actions, stats_dict) where stats_dict contains:
        - total_clamped: number of actions clamped
        - clamped_by_asset: Counter of clamped assets
        """
        clamped: List[Action] = []
        clamped_by_asset = Counter()
        total_clamped = 0

        for action in actions:
            limit = self._asset_power_limit(action.asset_id)
            value = action.value_kw
            was_clamped = False

            if limit is not None and abs(value) > limit + 1e-9:
                value = max(-limit, min(limit, value))
                was_clamped = True
                total_clamped += 1
                clamped_by_asset[action.asset_id] += 1

            clamped.append(
                Action(
                    asset_id=action.asset_id,
                    action_type=action.action_type,
                    value_kw=value,
                    timestep=action.timestep,
                )
            )

        return clamped, {
            "total_clamped": total_clamped,
            "clamped_by_asset": clamped_by_asset,
        }

    def _count_raw_violations(self, actions: List[Action]) -> Dict[str, int]:
        """Count bound violations in raw proposal."""
        violations = Counter()
        for action in actions:
            limit = self._asset_power_limit(action.asset_id)
            if limit is not None and abs(action.value_kw) > limit + 1e-9:
                violations[action.asset_id] += 1
        return {
            "total_violations": sum(violations.values()),
            "by_asset": dict(violations),
        }

    def get_actions(
        self, observations: Dict[str, Any], timestep: int
    ) -> RequestedActions:
        """Get actions with deterministic safety clamping applied."""
        self.timestep = timestep

        # 1. Get raw proposal from proposer (or use fallback if no proposer)
        if self.proposer:
            self.proposer.timestep = timestep
            self.proposer.last_grid_diagnostics = self.last_grid_diagnostics
            raw_proposed = self.proposer.get_actions(observations, timestep)
            raw_actions = list(raw_proposed.actions)
        else:
            # No proposer - return empty actions
            raw_actions = []

        # LEVEL 1: Raw proposal bound violations
        level1_stats = self._count_raw_violations(raw_actions)
        self._level1_raw_proposal_violations.update(
            {k: v for k, v in level1_stats["by_asset"].items()}
        )

        # 2. Apply deterministic clamping at agent layer
        clamped_actions, level2_stats = self._clamp_to_bounds(raw_actions)

        # LEVEL 2: Accepted by agent layer (after clamping)
        # These are the actions that pass our bounds check and go to the adapter
        for action in clamped_actions:
            self._level2_accepted_by_agent[action.asset_id] += 1

        # Create requested actions with clamped values
        requested = RequestedActions(timestep=timestep, actions=clamped_actions)

        # Record stratification for this step
        step_record = {
            "timestep": timestep,
            "level1_raw_violations": level1_stats,
            "level2_accepted_by_agent": {
                "total": len(clamped_actions),
                "clamped_by_agent": level2_stats["total_clamped"],
                "clamped_by_asset": dict(level2_stats["clamped_by_asset"]),
            },
            "level3_adapter_interventions": None,  # Filled in after adapter step
            "level4_final_applied_violations": None,  # Filled in after adapter step
            "level5_post_execution_violations": None,  # Filled in after simulation
        }
        self._stratification_history.append(step_record)

        return requested

    def record_adapter_interventions(
        self,
        requested: RequestedActions,
        limited: LimitedActions,
        applied: AppliedActions,
    ):
        """Record adapter-level clamping (LEVEL 3) and final applied violations (LEVEL 4).

        Called after the simulation adapter step to capture what the adapter did.
        """
        if not self._stratification_history:
            return

        step_record = self._stratification_history[-1]

        # LEVEL 3: Adapter interventions
        adapter_interventions = Counter()
        for req_action in requested.actions:
            for lim_action in limited.actions:
                if req_action.asset_id == lim_action.asset_id:
                    if abs(req_action.value_kw - lim_action.value_kw) > 1e-9:
                        adapter_interventions[req_action.asset_id] += 1
                        self._level3_adapter_interventions[req_action.asset_id] += 1
                    break

        step_record["level3_adapter_interventions"] = {
            "total": sum(adapter_interventions.values()),
            "by_asset": dict(adapter_interventions),
        }

        # LEVEL 4: Final applied-action violations
        # Check if applied actions still violate bounds (shouldn't happen if adapter works)
        final_violations = Counter()
        for app_action in applied.actions:
            limit = self._asset_power_limit(app_action.asset_id)
            if limit is not None and abs(app_action.value_kw) > limit + 1e-9:
                final_violations[app_action.asset_id] += 1
                self._level4_final_applied_violations[app_action.asset_id] += 1

        step_record["level4_final_applied_violations"] = {
            "total": sum(final_violations.values()),
            "by_asset": dict(final_violations),
        }

    def record_post_execution_violations(
        self,
        grid_diagnostics: Optional[Dict[str, Any]],
        observations: Optional[Dict[str, Any]] = None,
    ):
        """Record post-execution grid/service violations (LEVEL 5).

        Called after the simulation step with grid diagnostics to capture
        voltage, line loading, transformer loading, and service violations.
        """
        if not self._stratification_history:
            return

        step_record = self._stratification_history[-1]

        # LEVEL 5: Post-execution grid/service violations
        grid_violations = Counter()
        service_violations = Counter()

        if grid_diagnostics:
            diagnostics = grid_diagnostics.get("diagnostics", [])
            for d in diagnostics:
                category = d.get("category", "")
                severity = d.get("severity", "")
                if severity in ["violation", "critical"]:
                    # Extract asset/location info if available
                    location = d.get("location", category)
                    grid_violations[location] += 1
                    self._level5_post_execution_violations[location] += 1

        # Check EV deadline violations from observations
        if observations:
            for bid in self.building_ids:
                for ev_idx in range(10):  # reasonable upper bound
                    connected_key = f"{bid}_ev_{ev_idx}_connected"
                    if observations.get(connected_key, 0) == 1:
                        # Check if SOC is below target at departure
                        hours_to_depart = observations.get(
                            f"{bid}_ev_{ev_idx}_hours_to_departure"
                        )
                        required_soc = observations.get(
                            f"{bid}_ev_{ev_idx}_required_soc"
                        )
                        current_soc = observations.get(f"{bid}_ev_{ev_idx}_soc")
                        if (
                            hours_to_depart is not None
                            and hours_to_depart <= 1.0  # within 1 hour of departure
                            and required_soc is not None
                            and current_soc is not None
                            and current_soc < required_soc * 0.95
                        ):
                            service_violations[f"{bid}_ev_{ev_idx}_deadline"] += 1
                            self._level5_post_execution_violations[
                                f"{bid}_ev_{ev_idx}_deadline"
                            ] += 1

        step_record["level5_post_execution_violations"] = {
            "grid": dict(grid_violations),
            "service": dict(service_violations),
            "total": sum(grid_violations.values()) + sum(service_violations.values()),
        }

    def get_stratification_summary(self) -> Dict[str, Any]:
        """Get summary of all 5 stratification levels."""
        return {
            "level1_raw_proposal_violations": {
                "total": sum(self._level1_raw_proposal_violations.values()),
                "by_asset": dict(self._level1_raw_proposal_violations),
            },
            "level2_accepted_by_agent": {
                "total": sum(self._level2_accepted_by_agent.values()),
                "by_asset": dict(self._level2_accepted_by_agent),
            },
            "level3_adapter_interventions": {
                "total": sum(self._level3_adapter_interventions.values()),
                "by_asset": dict(self._level3_adapter_interventions),
            },
            "level4_final_applied_violations": {
                "total": sum(self._level4_final_applied_violations.values()),
                "by_asset": dict(self._level4_final_applied_violations),
            },
            "level5_post_execution_violations": {
                "total": sum(self._level5_post_execution_violations.values()),
                "by_asset": dict(self._level5_post_execution_violations),
            },
        }

    def get_stratification_history(self) -> List[Dict[str, Any]]:
        """Get detailed per-step stratification history."""
        return self._stratification_history

    def agent_stats(self) -> Dict[str, Any]:
        """Runtime accounting for result.json / manifest.json."""
        return {
            "controller_type": "deterministic_safety",
            "proposer_type": type(self.proposer).__name__ if self.proposer else "none",
            "stratification": self.get_stratification_summary(),
        }

    def reset(self):
        super().reset()
        self._level1_raw_proposal_violations.clear()
        self._level2_accepted_by_agent.clear()
        self._level3_adapter_interventions.clear()
        self._level4_final_applied_violations.clear()
        self._level5_post_execution_violations.clear()
        self._stratification_history.clear()
        if self.proposer:
            self.proposer.reset()
