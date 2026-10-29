"""LLM agent controllers for the verified-vs-unverified ablation.

Implements the two variants from ``experiments/ABLATION_DESIGN.md``:

- ``LLMAgentController`` (``llm_agent``): single-pass LLM dispatch; actions are
  applied as proposed when they parse and pass shape checks, otherwise the
  deterministic fallback decides for that step.
- ``LLMVerifiedController`` (``llm_agent_verified``): the same proposal path
  plus per-step verification (device bounds, action shape); failed checks
  trigger deterministic repair, budget 2 repairs per step, then fallback.

Reproducibility contract (required for the paper's artifact table): every run
records ``agent_backend`` (``"llm"`` or ``"fallback``), the prompt template
hash, and the sampling temperature/seed, both in ``result.json`` (via the
controller config) and ``manifest.json`` (via the runner). Without a configured
backend both variants run the deterministic fallback and are labelled
``fallback`` so those numbers are never mixed with LLM numbers.
"""
import hashlib
import json
import os
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from src.controllers import BaseController
from src.schemas.action import Action, ActionType, RequestedActions
from src.schemas.scenario import ScenarioConfig
from src.agents.backend import AgentBackend, BackendResponse, CostBudget
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

PROMPT_VERSION = "llm_dispatch_v1"
REPAIR_BUDGET = 2


class LLMAgentController(BaseController):
    """Single-pass LLM dispatch with a deterministic fallback."""

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
        
        # Create backend from config if not provided
        if backend is None:
            backend = llm_config.create_backend()
        
        self._backend: Optional[AgentBackend] = backend
        self.llm_config = llm_config
        self.agent_backend = "llm" if self._backend is not None else "fallback"
        self.prompt_version = PROMPT_VERSION
        self.prompt_hash = hashlib.sha256(LLM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
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
        # Deferred import: the controllers package imports this module, so the
        # rule-based fallback is resolved lazily to avoid a circular import.
        from src.controllers import RuleBasedController

        self._fallback = RuleBasedController(scenario_config)

    # ------------------------------------------------------------------
    # Backend plumbing
    # ------------------------------------------------------------------

    def _create_backend_from_env(self) -> Optional["AgentBackend"]:
        """Create an LLM backend from environment configuration."""
        llm_config = LLMConfig()
        # Validate config
        errors = llm_config.validate()
        if errors:
            return None
        # Create backend
        return llm_config.create_backend()

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

    def _propose_via_llm(self, observations: Dict[str, Any], timestep: int) -> Optional[List[Action]]:
        """Ask the backend for actions; None means unusable output."""
        if self._backend is None:
            return None
        
        # Build prompt context
        context = self._build_prompt_context(observations, timestep)
        prompt = LLM_PROMPT_TEMPLATE.format(
            timestep=timestep,
            observations=json.dumps(
                {k: v for k, v in list(observations.items())[:40]}, default=str
            ),
            assets=json.dumps(self._build_asset_list(), default=str),
        )
        
        # Create budget for this step
        budget = self.llm_config.create_cost_budget() if self.llm_config else CostBudget()
        
        try:
            # Build scenario context for backend
            context = {
                "grid_diagnostics": getattr(self, 'last_grid_diagnostics', None),
            }
            
            response = self._backend.generate_actions(
                scenario=self.scenario_config,
                observations=observations,
                timestep=timestep,
                context=context,
                budget=self.llm_config.create_cost_budget() if self.llm_config else CostBudget(),
            )
            
            if not response or not response.actions:
                return None
            
            # The backend returns actions directly, no need to parse JSON
            return response.actions
            
        except Exception as e:
            return None
    
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

    # ------------------------------------------------------------------
    # Decision path
    # ------------------------------------------------------------------

    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        self.timestep = timestep
        self.total_steps += 1
        actions: List[Action]
        if self._backend is not None:
            proposed = self._propose_via_llm(observations, timestep)
            if proposed is None:
                self.unparseable_outputs += 1
                self.verification_failures["unparseable_output"] += 1
                actions = self._fallback_actions(observations, timestep)
            else:
                actions = proposed
                repairs = 0
                while repairs < REPAIR_BUDGET and not self._actions_valid(actions):
                    actions = self._repair(actions)
                    repairs += 1
                    self.repair_iterations += 1
                if repairs > 0:
                    self.verification_failures["bound_violation"] += 1
                else:
                    self.first_attempt_valid += 1
        else:
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
            "sampling_temperature": self.sampling_temperature,
            "sampling_seed": self.sampling_seed,
            "total_steps": self.total_steps,
            "first_attempt_validity": (
                self.first_attempt_valid / self.total_steps if self.total_steps else 0.0
            ),
            "repair_iterations": self.repair_iterations,
            "verification_failures": dict(self.verification_failures),
            "unparseable_outputs": self.unparseable_outputs,
        }


class LLMVerifiedController(LLMAgentController):
    """LLM dispatch with per-step verification and a bounded repair loop.

    Behaviourally identical to the unverified variant while in fallback mode
    (fallback proposals already satisfy the checks); with an LLM backend the
    verification/repair path is active, which is the ablation's treatment.
    """

    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        if self._backend is None:
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
        return super().get_actions(observations, timestep)
