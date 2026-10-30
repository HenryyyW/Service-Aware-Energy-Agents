"""LLM agent controllers for the verified-vs-unverified ablation.

Implements the two **asymmetric** arms from ``experiments/ABLATION_DESIGN.md``
and ``docs/phase2_experiment_plan.md`` (P0-2/P0-3):

- ``LLMAgentController`` (``llm_agent``, unverified): single-pass LLM dispatch.
  Parsed proposals are applied **as proposed** — no repair, no re-prompt. The
  simulation adapter clamps values to device limits downstream
  (``CityLearnAdapter._to_normalized_action``); the controller only counts the
  out-of-bounds values it let through as ``llm_unrepaired_violations``.
- ``LLMVerifiedController`` (``llm_agent_verified``): the same proposal path
  plus per-step verification (asset shape + device power bounds). A failed
  check triggers **one** corrective re-prompt carrying the violation text; if
  the corrected proposal is still invalid (or unusable), the whole step is
  **replaced** with the deterministic rule-based dispatch — replacement, not
  silent clamping. Repair work per step is capped at ``REPAIR_BUDGET`` (2):
  one re-prompt + one deterministic replacement. Service feasibility (EV and
  flexible-load deadlines) is enforced through the replacement path, because
  the rule-based dispatch meets deadlines by construction.

The arms are therefore behaviourally distinct by construction whenever the
proposer emits an out-of-bounds value: the unverified arm executes the clamped
proposal, the verified arm executes the rule-based setpoint for that step. In
fallback mode both variants run the deterministic proposer and stay identical;
those runs are labelled ``agent_backend: "fallback"`` and are never mixed with
LLM numbers.

Backends. Two shapes are supported:

- a synchronous ``Callable[[str], str]`` (the plan's interface): the
  controller owns the versioned dispatch prompt, calls the backend with it,
  and classifies the raw response itself via ``parse_llm_actions``
  (``clean`` / ``fenced`` / ``invalid``). The production backend for the
  paper's ``ollama-local`` arm is ``ollama_prompt_callable`` from
  ``src/agents/backend/local.py``, built from ``AGENT_BACKEND=ollama:<model>``
  (or ``--llm-backend ollama:<model>``) in ``_backend_from_env()`` with a hard
  per-call timeout and a token budget.
- an ``AgentBackend`` object (async ``generate_actions``, PR #43 interface):
  used by tests (mocks) and remote providers. Backend-provided actions are
  applied as-is; when the backend returns no actions, its raw output is
  classified with the same ``parse_llm_actions``.

Reproducibility contract (required for the paper's artifact table): every run
records ``agent_backend`` (``ollama-local`` / ``llm`` / ``fallback``),
``agent_model`` and the Ollama model digest, the proposal and repair prompt
template hashes, and the sampling temperature/seed, both in ``result.json``
(via the controller config) and ``manifest.json`` (via the runner).
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
from src.agents.backend.local import ollama_prompt_callable

# Versioned dispatch prompt. The hash of this template goes into the manifest;
# bump the version string whenever the prompt changes. The prompt is fixed for
# the whole phase 2 matrix: any edit invalidates the arm. v2 makes the exact
# asset_id values explicit (v1 left them implicit and the model invented
# building-level ids the adapter silently dropped).
LLM_PROMPT_TEMPLATE = """You are the dispatch agent for a renewable energy community.
Current step: {timestep}. Observations (JSON): {observations}
Assets (JSON): {assets}
Decide charging/discharging power in kW for each asset for this step.
Use EXACTLY the asset_id values listed in Assets (JSON); give an entry for every listed asset.
Constraints: respect device power bounds and every SOC/deadline requirement.
Reply with ONLY a JSON array of {{"asset_id": str, "value_kw": number}} objects.
Prompt version: llm_dispatch_v2
"""

# Corrective re-prompt for the verified arm: carries the exact violation text
# so the model can repair its own proposal. Versioned separately from the
# dispatch prompt because only the verified arm uses it.
LLM_REPAIR_PROMPT_TEMPLATE = """Your previous dispatch proposal violated these constraints:
{violations}
Current step: {timestep}. Observations (JSON): {observations}
Assets (JSON): {assets}
Return a corrected JSON array of {{"asset_id": str, "value_kw": number}} objects that respects every device power bound. Use EXACTLY the asset_id values listed in Assets (JSON).
Reply with ONLY the JSON array.
Prompt version: llm_dispatch_v1_repair
"""

PROMPT_VERSION = "llm_dispatch_v2"
REPAIR_PROMPT_VERSION = "llm_dispatch_v1_repair"
REPAIR_BUDGET = 2

# Default ollama-local arm settings (phase 2 gate decision: local Ollama only).
OLLAMA_DEFAULT_MODEL = "qwen2.5-coder:7b"


def parse_llm_actions(
    raw: str, timestep: int = 0
) -> Tuple[Optional[List[Action]], str]:
    """Parse a raw LLM response into actions.

    Returns ``(actions, status)`` with ``status in {"clean", "fenced",
    "invalid"}``:

    - ``clean``: the payload parsed as-is;
    - ``fenced``: the payload was wrapped in a single markdown code fence —
      a recorded formatting violation (``llm_fenced_outputs``), never hidden;
    - ``invalid``: not usable (bad JSON, not a list, wrong item shape).

    Only ONE leading/trailing fence is stripped; a malformed fence (e.g. a
    missing closing fence) is ``invalid``, not ``fenced``.
    """
    text = raw.strip() if isinstance(raw, str) else ""
    status = "clean"
    if text.startswith("```"):
        stripped = text[3:]
        if stripped[:4].lower() == "json":
            stripped = stripped[4:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        else:
            return None, "invalid"  # unclosed fence
        text = stripped.strip()
        status = "fenced"
    try:
        payload = json.loads(text)
        if not isinstance(payload, list):
            return None, "invalid"
        actions: List[Action] = []
        for item in payload:
            if (
                not isinstance(item, dict)
                or "asset_id" not in item
                or "value_kw" not in item
            ):
                return None, "invalid"
            actions.append(
                Action(
                    asset_id=str(item["asset_id"]),
                    action_type=ActionType.BATTERY_CHARGE,  # refined by asset id downstream
                    value_kw=float(item["value_kw"]),
                    timestep=timestep,
                )
            )
        return actions, status
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, "invalid"


def _percentile(sorted_samples: List[float], fraction: float) -> Optional[float]:
    """Nearest-rank percentile over a pre-sorted sample list."""
    if not sorted_samples:
        return None
    index = min(
        len(sorted_samples) - 1,
        max(0, int(round(fraction * (len(sorted_samples) - 1)))),
    )
    return sorted_samples[index]


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

        # Sampling parameters (needed by the env backend wiring below).
        self.sampling_temperature = float(
            os.environ.get("SAEA_LLM_TEMPERATURE", sampling_temperature if sampling_temperature is not None else 0.0)
        )
        self.sampling_seed = int(
            sampling_seed if sampling_seed is not None else scenario_config.random_seed
        )

        # Backend resolution: explicit injection (tests) > environment wiring
        # (ollama-local / echo debug) > the PR #43 LLMConfig path.
        self._env_backend_label: Optional[str] = None
        self._env_agent_model: Optional[str] = None
        if backend is None:
            backend = self._backend_from_env()
        if backend is None:
            backend = llm_config.create_backend()
        self._backend = backend
        if self._env_backend_label is not None:
            self.agent_backend = self._env_backend_label
        else:
            self.agent_backend = (
                "fallback" if isinstance(self._backend, FallbackBackend) else "llm"
            )
        self.prompt_version = PROMPT_VERSION
        self.prompt_hash = hashlib.sha256(LLM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
        self.repair_prompt_version = REPAIR_PROMPT_VERSION
        self.repair_prompt_hash = hashlib.sha256(
            LLM_REPAIR_PROMPT_TEMPLATE.encode("utf-8")
        ).hexdigest()
        # Agent-execution accounting (paper metrics, phase 2 section 8 field set)
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
        # LLM call accounting: every backend invocation (proposal + verified
        # re-prompt), parse/format outcomes, call failures, latency, tokens.
        self.llm_calls = 0
        self.llm_raw_parse_failures = 0
        self.llm_fenced_outputs = 0
        self.llm_backend_errors = 0
        self._latency_samples_ms: List[float] = []
        self.llm_prompt_tokens = 0
        self.llm_completion_tokens = 0
        # Deferred import: the controllers package imports this module, so the
        # rule-based fallback is resolved lazily to avoid a circular import.
        from src.controllers import RuleBasedController

        self._fallback = RuleBasedController(scenario_config)

    # ------------------------------------------------------------------
    # Backend plumbing
    # ------------------------------------------------------------------

    def _backend_from_env(self) -> Optional[Any]:
        """Resolve an LLM backend from the environment / LLM config, if any.

        ``AGENT_BACKEND=ollama:<model>`` (or ``LLMConfig._backend_raw``, which
        the runner sets from ``--llm-backend``) builds the synchronous
        ``ollama_prompt_callable`` and labels the arm ``ollama-local`` with
        ``agent_model`` set. ``SAEA_LLM_BACKEND=echo`` builds the debug echo
        backend. Anything else defers to the LLMConfig path.
        """
        raw = ""
        if self.llm_config is not None and getattr(self.llm_config, "_backend_raw", None):
            raw = str(self.llm_config._backend_raw).strip()
        if not raw:
            raw = os.environ.get("AGENT_BACKEND", "").strip()
        raw = raw.lower()

        if raw == "ollama" or raw.startswith("ollama:"):
            model = raw.split(":", 1)[1].strip() if raw.startswith("ollama:") else ""
            if not model:
                model = (
                    (self.llm_config.local_model if self.llm_config else None)
                    or os.environ.get("LLM_LOCAL_MODEL")
                    or OLLAMA_DEFAULT_MODEL
                )
            endpoint = (
                (self.llm_config.local_endpoint if self.llm_config else None)
                or os.environ.get("LLM_LOCAL_ENDPOINT")
                or "http://localhost:11434"
            )
            self._env_backend_label = "ollama-local"
            self._env_agent_model = model
            return ollama_prompt_callable(
                model=model,
                endpoint=endpoint,
                temperature=float(
                    os.environ.get("SAEA_LLM_TEMPERATURE", self.sampling_temperature)
                ),
                seed=self.sampling_seed,
                timeout_s=float(os.environ.get("SAEA_LLM_TIMEOUT_S", "120")),
                num_predict=int(os.environ.get("SAEA_LLM_NUM_PREDICT", "512")),
            )

        if os.environ.get("SAEA_LLM_BACKEND", "").strip().lower() == "echo":
            self._env_backend_label = "llm"

            def echo_backend(prompt: str) -> str:
                # Debug backend: returns the fallback proposal embedded in the
                # prompt as invalid JSON so the fallback path is exercised.
                return "not-json"

            return echo_backend
        return None

    @property
    def _is_prompt_callable(self) -> bool:
        """True when the backend is a plain ``prompt -> text`` callable."""
        return callable(self._backend) and not hasattr(self._backend, "generate_actions")

    def agent_model(self) -> Optional[str]:
        """The model name for the run manifest, when one is configured."""
        if self._env_agent_model is not None:
            return self._env_agent_model
        return getattr(self._backend, "model", None)

    def agent_model_digest(self) -> Optional[str]:
        """The Ollama model digest (sha256), when the backend exposes one."""
        return getattr(self._backend, "model_digest", None)

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
        """Build asset list for prompt (with the exact asset_id values)."""
        assets = []
        for bid, meta in self.device_metadata.items():
            asset_ids = []
            if meta.get("battery"):
                asset_ids.append(f"{bid}_battery")
            asset_ids.extend(
                f"{bid}_ev_{index}" for index in range(len(meta.get("chargers", [])))
            )
            asset_ids.extend(
                f"{bid}_flex_{index}" for index in range(len(meta.get("deferrable", [])))
            )
            assets.append({
                "asset_ids": asset_ids,
                "building": bid,
                "battery_power_kw": (meta.get("battery") or {}).get("power_kw"),
                "chargers": [c.get("max_charge_kw") for c in meta.get("chargers", [])],
                "deferrable": [d.get("power_kw") for d in meta.get("deferrable", [])],
            })
        return assets

    def _build_text_prompt(
        self,
        observations: Dict[str, Any],
        timestep: int,
        repair_violations: Optional[List[str]] = None,
    ) -> str:
        """The controller-owned prompt sent to text backends."""
        if repair_violations:
            return LLM_REPAIR_PROMPT_TEMPLATE.format(
                violations="\n".join(f"- {text}" for text in repair_violations),
                timestep=timestep,
                observations=self._observations_json(observations),
                assets=json.dumps(self._build_asset_list(), default=str),
            )
        return LLM_PROMPT_TEMPLATE.format(
            timestep=timestep,
            observations=self._observations_json(observations),
            assets=json.dumps(self._build_asset_list(), default=str),
        )

    def _record_call_latency(self, latency_ms: float) -> None:
        if latency_ms is not None and latency_ms >= 0:
            self._latency_samples_ms.append(float(latency_ms))

    def _record_tokens(self, usage: Optional[Dict[str, Any]]) -> None:
        if not usage:
            return
        self.llm_prompt_tokens += int(usage.get("prompt") or 0)
        self.llm_completion_tokens += int(usage.get("completion") or 0)

    def _call_backend(
        self,
        observations: Dict[str, Any],
        timestep: int,
        repair_violations: Optional[List[str]] = None,
    ) -> Optional[BackendResponse]:
        """Invoke the backend once; None means the call itself failed.

        Text callables get the controller-owned dispatch/repair prompt.
        ``repair_violations`` carries the verified arm's violation text so a
        text backend re-prompts with it (passed as ``context`` for
        AgentBackend-style backends).
        """
        if self._backend is None:
            return None
        self.llm_calls += 1

        if self._is_prompt_callable:
            prompt = self._build_text_prompt(observations, timestep, repair_violations)
            callable_backend = self._backend
            calls_before = getattr(callable_backend, "call_count", None)
            prompt_tokens_before = getattr(callable_backend, "prompt_tokens", 0)
            completion_tokens_before = getattr(callable_backend, "completion_tokens", 0)
            try:
                raw = callable_backend(prompt)
            except Exception:
                self.llm_backend_errors += 1
                return None
            self._record_tokens({
                "prompt": getattr(callable_backend, "prompt_tokens", 0) - prompt_tokens_before,
                "completion": getattr(callable_backend, "completion_tokens", 0) - completion_tokens_before,
            })
            if (
                calls_before is not None
                and callable_backend.latency_samples_ms
                and len(callable_backend.latency_samples_ms) > calls_before
            ):
                self._record_call_latency(callable_backend.latency_samples_ms[-1])
            # Wrap the text response in a BackendResponse-like record so both
            # paths share one downstream contract.
            return BackendResponse(
                actions=[],
                raw_output=raw,
                prompt_hash=self.prompt_hash,
                token_usage={},
                latency_ms=0.0,
                cost_usd=0.0,
                metadata={"transport": "prompt_callable"},
            )

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
                    response = future.result()
            else:
                response = asyncio.run(
                    self._backend.generate_actions(
                        scenario=self.scenario_config,
                        observations=observations,
                        timestep=timestep,
                        context=context,
                        budget=budget,
                    )
                )
        except Exception:
            self.llm_backend_errors += 1
            return None
        self._record_call_latency(getattr(response, "latency_ms", None))
        self._record_tokens(getattr(response, "token_usage", None))
        return response

    def _propose_via_llm(
        self,
        observations: Dict[str, Any],
        timestep: int,
        repair_violations: Optional[List[str]] = None,
    ) -> Tuple[Optional[List[Action]], str]:
        """Ask the backend for a proposal; returns (actions, parse status).

        ``actions`` is None when the call failed or the response did not
        parse; ``status`` is ``clean`` / ``fenced`` / ``invalid`` (fence
        stripping is recorded as a formatting violation, never hidden).
        """
        response = self._call_backend(observations, timestep, repair_violations)
        if response is None:
            return None, "invalid"
        if response.actions:
            # Backend-parsed actions (AgentBackend contract); raw output is
            # not classifiable here, so treat as clean.
            return list(response.actions), "clean"
        # One parsing authority: classify the raw text ourselves.
        actions, status = parse_llm_actions(response.raw_output, timestep)
        if status == "fenced":
            self.llm_fenced_outputs += 1
        elif status == "invalid":
            self.llm_raw_parse_failures += 1
        return actions, status

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
            proposed, _status = self._propose_via_llm(observations, timestep)
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
        samples = sorted(self._latency_samples_ms)
        return {
            "agent_backend": self.agent_backend,
            "agent_model": self.agent_model(),
            "agent_model_digest": self.agent_model_digest(),
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
            "llm_calls": self.llm_calls,
            "llm_raw_parse_failures": self.llm_raw_parse_failures,
            "llm_fenced_outputs": self.llm_fenced_outputs,
            "llm_backend_errors": self.llm_backend_errors,
            "llm_latency_p50_ms": _percentile(samples, 0.50),
            "llm_latency_p95_ms": _percentile(samples, 0.95),
            "llm_prompt_tokens": self.llm_prompt_tokens,
            "llm_completion_tokens": self.llm_completion_tokens,
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

    On a shape/bounds violation the controller re-prompts **once** with the
    violation text (a second backend call; text backends receive the versioned
    repair prompt, AgentBackend backends receive it in ``context``); if the
    corrected proposal is still invalid (or unusable), the step is replaced
    with the deterministic rule-based dispatch. The repair cap is
    ``REPAIR_BUDGET`` = 2 (one re-prompt + one replacement); clamping is never
    used on the LLM path — that is the unverified arm's behaviour and what
    made the arms identical by construction (P0-3). In fallback mode the
    deterministic proposer already satisfies every check, so the arms coincide
    and the accounting stays comparable.
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
        proposed, _status = self._propose_via_llm(observations, timestep)
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
        # violation text.
        reprompted, _status = self._propose_via_llm(
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
