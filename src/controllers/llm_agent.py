"""LLM agent controllers for the verified-vs-unverified ablation.

Implements the two **asymmetric** arms from ``experiments/ABLATION_DESIGN.md``
and ``docs/phase2_experiment_plan.md`` (P0-3):

- ``LLMAgentController`` (``llm_agent``, unverified): single-pass LLM dispatch.
  Parsed proposals are applied **as proposed** — no repair, no re-prompt. The
  simulation adapter clamps values to device limits downstream
  (``CityLearnAdapter._to_normalized_action``); the controller only counts the
  out-of-bounds values it let through as ``llm_unrepaired_violations``.
- ``LLMVerifiedController`` (``llm_agent_verified``): the same proposal path
  plus per-step verification (asset shape + device power bounds). A failed
  check triggers **one** corrective re-prompt (a second backend call, with the
  violation text passed in ``context["repair_violations"]``); if the corrected
  proposal is still invalid (or unusable), the whole step is **replaced** with
  the deterministic rule-based dispatch — replacement, not silent clamping.
  Repair work per step is capped at ``REPAIR_BUDGET`` (2): one re-prompt + one
  deterministic replacement. Service feasibility (EV and flexible-load
  deadlines) is enforced through the replacement path, because the rule-based
  dispatch meets deadlines by construction.

The arms are therefore behaviourally distinct by construction whenever the
proposer emits an out-of-bounds value: the unverified arm executes the clamped
proposal, the verified arm executes the rule-based setpoint for that step. In
fallback mode both variants run the deterministic proposer and stay identical;
those runs are labelled ``agent_backend: "fallback"`` and are never mixed with
LLM numbers.

Reproducibility contract (required for the paper's artifact table): every run
records ``agent_backend``, the proposal and repair prompt template hashes, and
the sampling temperature/seed, both in ``result.json`` (via the controller
config) and ``manifest.json`` (via the runner).
"""
import asyncio
import concurrent.futures
import hashlib
import json
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from src.controllers import BaseController
from src.schemas.action import Action, ActionType, RequestedActions
from src.schemas.scenario import ScenarioConfig
from src.agents.backend import AgentBackend, BackendResponse, CostBudget, FallbackBackend
from src.agents.backend.config import LLMConfig

# Versioned dispatch prompt. The hash of this template goes into the manifest;
# bump the version string whenever the prompt changes.
LLM_PROMPT_TEMPLATE = """You are the dispatch agent for a renewable energy community.
Current step: {timestep}. Observations (JSON): {observations}
Assets (JSON): {assets}
Decide charging/discharging power in kW for each asset for this step.
Constraints: respect device power bounds and every SOC/deadline requirement.
Reply with ONLY a JSON array of {{"asset_id": str, "value_kw": number}} objects.
Prompt version: llm_dispatch_v1
"""

# Corrective re-prompt for the verified arm: carries the exact violation text
# so the model can repair its own proposal. Versioned separately from the
# dispatch prompt because only the verified arm uses it.
LLM_REPAIR_PROMPT_TEMPLATE = """Your previous dispatch proposal violated these constraints:
{violations}
Current step: {timestep}. Observations (JSON): {observations}
Assets (JSON): {assets}
Return a corrected JSON array of {{"asset_id": str, "value_kw": number}} objects that respects every device power bound.
Reply with ONLY the JSON array.
Prompt version: llm_dispatch_v1_repair
"""

PROMPT_VERSION = "llm_dispatch_v1"
REPAIR_PROMPT_VERSION = "llm_dispatch_v1_repair"
REPAIR_BUDGET = 2


class LLMAgentController(BaseController):
    """Unverified single-pass LLM dispatch (the ``llm_agent`` arm).

    Parsed proposals are applied as proposed; the adapter clamps to device
    limits downstream and the controller counts the out-of-bounds values as
    ``llm_unrepaired_violations``. There is no repair and no re-prompt: sharing
    the repair loop with the verified arm is what made the two arms identical
    by construction (P0-3).
    """

    def __init__(
        self,
        scenario_config: ScenarioConfig,
        device_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        backend: Optional[AgentBackend] = None,
        llm_config: Optional[LLMConfig] = None,
        sampling_temperature: Optional[float] = None,
        sampling_seed: Optional[int] = None,
    ):
        super().__init__(scenario_config)
        self.device_metadata = device_metadata or {}

        # Create LLM config from environment if not provided
        if llm_config is None:
            llm_config = LLMConfig()
        self.llm_config = llm_config

        # Backend injection (tests) or environment configuration. Without one,
        # the LLMConfig path decides (FallbackBackend => fallback mode).
        if backend is None:
            backend = llm_config.create_backend()
        self._backend: Optional[AgentBackend] = backend
        self.agent_backend = "fallback" if isinstance(self._backend, FallbackBackend) else "llm"
        self.prompt_version = PROMPT_VERSION
        self.prompt_hash = hashlib.sha256(LLM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
        self.repair_prompt_version = REPAIR_PROMPT_VERSION
        self.repair_prompt_hash = hashlib.sha256(
            LLM_REPAIR_PROMPT_TEMPLATE.encode("utf-8")
        ).hexdigest()
        self.sampling_temperature = float(
            os.environ.get("SAEA_LLM_TEMPERATURE", sampling_temperature if sampling_temperature is not None else 0.0)
        )
        self.sampling_seed = int(
            sampling_seed if sampling_seed is not None else scenario_config.random_seed
        )
        # Agent-execution accounting (paper metrics)
        self.total_steps = 0
        self.first_attempt_valid = 0
        self.repair_iterations = 0
        self.verification_failures: Counter = Counter()
        self.unparseable_outputs = 0
        # Out-of-bounds actions applied as proposed and left to the adapter's
        # clamp (unverified arm); steps decided by the deterministic fallback
        # instead of the LLM (both arms).
        self.unrepaired_violations = 0
        self.fallback_steps = 0
        # Deferred import: the controllers package imports this module, so the
        # rule-based fallback is resolved lazily to avoid a circular import.
        from src.controllers import RuleBasedController

        self._fallback = RuleBasedController(scenario_config)

    # ------------------------------------------------------------------
    # Backend plumbing
    # ------------------------------------------------------------------

    def _build_prompt_context(self, observations: Dict[str, Any], timestep: int) -> Dict[str, Any]:
        """Build context for prompt template."""
        assets = self._build_asset_list()

        # Grid diagnostics if available
        grid_diag = None
        if hasattr(self, 'last_grid_diagnostics') and self.last_grid_diagnostics:
            grid_diag = self.last_grid_diagnostics

        return {
            "scenario_id": self.scenario_config.scenario_id,
            "timestep": timestep,
            "buildings": assets,
            "grid_diagnostics": grid_diag,
            "community_import_limit_kw": self.scenario_config.community_import_limit_kw,
            "community_export_limit_kw": self.scenario_config.community_export_limit_kw,
        }

    def _observations_json(self, observations: Dict[str, Any]) -> str:
        return json.dumps(
            {k: v for k, v in list(observations.items())[:40]}, default=str
        )

    def _build_asset_list(self) -> List[Dict[str, Any]]:
        """Build asset list for prompt."""
        assets = []
        for bid, meta in self.device_metadata.items():
            assets.append({
                "building": bid,
                "battery_power_kw": (meta.get("battery") or {}).get("power_kw"),
                "chargers": [c.get("max_charge_kw") for c in meta.get("chargers", [])],
                "deferrable": [d.get("power_kw") for d in meta.get("deferrable", [])],
            })
        return assets

    def _call_backend(
        self,
        observations: Dict[str, Any],
        timestep: int,
        repair_violations: Optional[List[str]] = None,
    ) -> Optional[BackendResponse]:
        """Invoke the backend once; None means the call itself failed.

        ``repair_violations`` carries the verified arm's violation text so a
        text backend can re-prompt with it (passed as ``context`` for
        AgentBackend-style backends).
        """
        if self._backend is None:
            return None
        context: Dict[str, Any] = {
            "grid_diagnostics": getattr(self, 'last_grid_diagnostics', None),
        }
        if repair_violations:
            context["repair_violations"] = repair_violations
        budget = self.llm_config.create_cost_budget() if self.llm_config else CostBudget()
        try:
            # Run async backend call, handling existing event loops
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # If there's already a running loop, we can't use asyncio.run
                # Create a new thread with its own event loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._backend.generate_actions(
                            scenario=self.scenario_config,
                            observations=observations,
                            timestep=timestep,
                            context=context,
                            budget=budget,
                        ),
                    )
                    return future.result()
            return asyncio.run(
                self._backend.generate_actions(
                    scenario=self.scenario_config,
                    observations=observations,
                    timestep=timestep,
                    context=context,
                    budget=budget,
                )
            )
        except Exception:
            return None

    def _propose_via_llm(
        self,
        observations: Dict[str, Any],
        timestep: int,
        repair_violations: Optional[List[str]] = None,
    ) -> Optional[List[Action]]:
        """Ask the backend for actions; None means unusable output."""
        response = self._call_backend(observations, timestep, repair_violations)
        if not response or not response.actions:
            return None
        # The backend returns actions directly, no need to parse JSON
        return response.actions

    # ------------------------------------------------------------------
    # Decision path
    # ------------------------------------------------------------------

    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        self.timestep = timestep
        self.total_steps += 1
        actions: List[Action]

        # Check if we have a real LLM backend (not fallback)
        use_llm = self._backend is not None and not isinstance(self._backend, FallbackBackend)

        if use_llm:
            proposed = self._propose_via_llm(observations, timestep)
            if proposed is None:
                self.unparseable_outputs += 1
                self.verification_failures["unparseable_output"] += 1
                self.fallback_steps += 1
                actions = self._fallback_actions(observations, timestep)
            else:
                # Unverified arm: apply the proposal as proposed — no repair,
                # no re-prompt. The adapter clamps to device limits downstream;
                # out-of-bounds values are only counted, never corrected here.
                actions = proposed
                violations = 0
                for action in actions:
                    limit = self._asset_power_limit(action.asset_id)
                    if limit is not None and abs(action.value_kw) > limit + 1e-9:
                        violations += 1
                if violations:
                    self.unrepaired_violations += violations
                else:
                    self.first_attempt_valid += 1
        else:
            # Using FallbackBackend or no backend - use fallback actions
            actions = self._fallback_actions(observations, timestep)
            self.first_attempt_valid += 1

        return self._create_requested_actions(actions)

    def _fallback_actions(self, observations: Dict[str, Any], timestep: int) -> List[Action]:
        requested = self._fallback.get_actions(observations, timestep)
        for action in requested.actions:
            action.timestep = timestep
        return requested.actions

    def _actions_valid(self, actions: List[Action]) -> bool:
        """Per-step verification: shape + device power bounds from live metadata."""
        for action in actions:
            limit = self._asset_power_limit(action.asset_id)
            if limit is not None and abs(action.value_kw) > limit + 1e-9:
                return False
        return True

    def _asset_power_limit(self, asset_id: str) -> Optional[float]:
        for bid, meta in self.device_metadata.items():
            battery = meta.get("battery")
            if battery and asset_id == f"{bid}_battery":
                return float(battery.get("power_kw") or 0.0) or None
            for index, charger in enumerate(meta.get("chargers", [])):
                if asset_id == f"{bid}_ev_{index}":
                    return float(charger.get("max_charge_kw") or 0.0) or None
        return None

    def _repair(self, actions: List[Action]) -> List[Action]:
        """Deterministic repair: clamp each action into its device bounds."""
        repaired: List[Action] = []
        for action in actions:
            limit = self._asset_power_limit(action.asset_id)
            value = action.value_kw
            if limit is not None:
                value = max(-limit, min(limit, value))
            repaired.append(
                Action(
                    asset_id=action.asset_id,
                    action_type=action.action_type,
                    value_kw=value,
                    timestep=action.timestep,
                )
            )
        return repaired

    def agent_stats(self) -> Dict[str, Any]:
        """Runtime accounting for result.json / manifest.json."""
        return {
            "agent_backend": self.agent_backend,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "repair_prompt_version": self.repair_prompt_version,
            "repair_prompt_hash": self.repair_prompt_hash,
            "sampling_temperature": self.sampling_temperature,
            "sampling_seed": self.sampling_seed,
            "total_steps": self.total_steps,
            "first_attempt_validity": (
                self.first_attempt_valid / self.total_steps if self.total_steps else 0.0
            ),
            "repair_iterations": self.repair_iterations,
            "llm_unrepaired_violations": self.unrepaired_violations,
            "llm_fallback_steps": self.fallback_steps,
            "llm_fallback_step_share": (
                self.fallback_steps / self.total_steps if self.total_steps else 0.0
            ),
            "verification_failures": dict(self.verification_failures),
            "unparseable_outputs": self.unparseable_outputs,
        }


class LLMVerifiedController(LLMAgentController):
    """LLM dispatch with per-step verification and a bounded repair loop
    (the ``llm_agent_verified`` arm).

    On a shape/bounds violation the controller re-prompts **once** (a second
    backend call carrying the violation text in ``context``); if the corrected
    proposal is still invalid (or unusable), the step is replaced with the
    deterministic rule-based dispatch. The repair cap is ``REPAIR_BUDGET`` = 2
    (one re-prompt + one replacement); clamping is never used on the LLM path —
    that is the unverified arm's behaviour and what made the arms identical by
    construction (P0-3). In fallback mode the deterministic proposer already
    satisfies every check, so the arms coincide and the accounting stays
    comparable.
    """

    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        if self._backend is None or isinstance(self._backend, FallbackBackend):
            # Fallback proposals are deterministic and in-bounds; run the same
            # accounting so both variants produce comparable traces.
            self.timestep = timestep
            self.total_steps += 1
            actions = self._fallback_actions(observations, timestep)
            repairs = 0
            while repairs < REPAIR_BUDGET and not self._actions_valid(actions):
                actions = self._repair(actions)
                repairs += 1
                self.repair_iterations += 1
            if repairs == 0:
                self.first_attempt_valid += 1
            return self._create_requested_actions(actions)
        return self._verified_llm_actions(observations, timestep)

    def _verified_llm_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        """Verified backend path: verify -> one re-prompt -> deterministic replacement."""
        self.timestep = timestep
        self.total_steps += 1
        proposed = self._propose_via_llm(observations, timestep)
        if proposed is None:
            self.unparseable_outputs += 1
            self.verification_failures["unparseable_output"] += 1
            self.fallback_steps += 1
            return self._create_requested_actions(
                self._fallback_actions(observations, timestep)
            )
        actions = proposed
        issues = self._validation_issues(actions)
        if not issues:
            self.first_attempt_valid += 1
            return self._create_requested_actions(actions)
        for category in {category for category, _ in issues}:
            self.verification_failures[category] += 1
        # Repair 1 of REPAIR_BUDGET: one corrective re-prompt with the exact
        # violation text (carried in the backend call's context).
        reprompted = self._propose_via_llm(
            observations, timestep, repair_violations=[text for _, text in issues]
        )
        self.repair_iterations += 1
        if reprompted is not None:
            actions = reprompted
            issues = self._validation_issues(actions)
        if issues:
            # Repair 2 of REPAIR_BUDGET: still invalid (or the correction was
            # unusable) -> replace the whole step with the deterministic
            # rule-based dispatch. Replacement, not silent clamping.
            self.repair_iterations += 1
            self.fallback_steps += 1
            actions = self._fallback_actions(observations, timestep)
        return self._create_requested_actions(actions)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def _validation_issues(self, actions: List[Action]) -> List[Tuple[str, str]]:
        """Shape/bounds verification; returns (category, violation text) pairs.

        Shape: the proposal must reference assets this community owns. Bounds:
        every battery/EV value must respect the device power limit. Service
        feasibility (EV/flexible-load deadlines) is not a standalone check: it
        is enforced by the deterministic replacement, which meets deadlines by
        construction.
        """
        issues: List[Tuple[str, str]] = []
        for action in actions:
            if not self._asset_known(action.asset_id):
                issues.append((
                    "action_shape",
                    f"{action.asset_id}: not a known asset of this community",
                ))
                continue
            limit = self._asset_power_limit(action.asset_id)
            if limit is not None and abs(action.value_kw) > limit + 1e-9:
                issues.append((
                    "bound_violation",
                    (
                        f"{action.asset_id}: |{action.value_kw:.3f}| kW exceeds "
                        f"the device power limit of {limit:.3f} kW"
                    ),
                ))
        return issues

    def _asset_known(self, asset_id: str) -> bool:
        """True if the id matches a battery, EV charger or deferrable load."""
        for bid, meta in self.device_metadata.items():
            if asset_id == f"{bid}_battery":
                return True
            if any(
                asset_id == f"{bid}_ev_{index}"
                for index in range(len(meta.get("chargers", [])))
            ):
                return True
            if any(
                asset_id == f"{bid}_flex_{index}"
                for index in range(len(meta.get("deferrable", [])))
            ):
                return True
        return False
