"""Tests for the verified-vs-unverified LLM agent ablation controllers.

Covers the traceability contract from experiments/ABLATION_DESIGN.md section 4
(agent_backend, prompt hash and sampling parameters recorded, fallback mode
labelled) and the arm-separation contract from docs/phase2_experiment_plan.md
P0-3: the unverified arm applies proposals as proposed (the adapter clamps,
violations are counted), the verified arm re-prompts once with the violation
text and then replaces the step with the deterministic rule-based dispatch —
the two arms must produce different action streams on an out-of-bounds
proposal.

Covers the P0-2 controller-side contract: AGENT_BACKEND=ollama:<model> wires
the ollama-local arm, parse_llm_actions classifies raw responses as
clean/fenced/invalid (a fence is a recorded formatting violation), and the
full phase 2 metric set (llm_calls, parse failures, fenced outputs, latency
p50/p95, token counts, fallback steps/share, model digest) reaches
result.json and manifest.json.
"""
import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import (
    ScenarioConfig,
    BuildingConfig,
    BatteryConfig,
    EVConfig,
    PVConfig,
    FlexibleLoadConfig,
    TariffConfig,
)
from src.controllers import LLMAgentController, LLMVerifiedController, RuleBasedController
from src.agents.backend import AgentBackend, BackendResponse, CostBudget
from src.agents.backend.fallback import FallbackBackend


@pytest.fixture
def scenario():
    """Create a test scenario configuration."""
    return ScenarioConfig(
        scenario_id="llm_ablation_test",
        name="LLM Ablation",
        description="Ablation controller test",
        random_seed=42,
        timestep_minutes=60,
        community_import_limit_kw=200.0,
        community_export_limit_kw=150.0,
        buildings=[
            BuildingConfig(
                building_id="ab",
                building_type="residential",
                location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-08",
                pv=PVConfig(capacity_kw=5.0),
                battery=BatteryConfig(
                    capacity_kwh=13.5,
                    power_kw=6.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
                evs=[
                    EVConfig(
                        capacity_kwh=60.0,
                        max_charge_kw=7.0,
                        efficiency=0.90,
                        initial_soc=0.3,
                        target_soc=0.8,
                        arrival_time="18:00",
                        departure_time="07:00",
                        connected_days=[0, 1, 2, 3, 4, 5, 6]
                    )
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=3.0,
                        energy_kwh=6.0,
                        earliest_start="20:00",
                        latest_end="06:00",
                        duration_hours=2.0
                    )
                ],
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"off_peak": 0.08, "mid_peak": 0.12, "on_peak": 0.20},
                    export_prices={"off_peak": 0.03, "mid_peak": 0.05, "on_peak": 0.08},
                    demand_charge=5.0
                ),
            )
        ],
    )


def _metadata() -> Dict[str, Dict[str, Any]]:
    return {
        "ab": {
            "battery": {"power_kw": 6.0},
            "chargers": [{"max_charge_kw": 7.0}],
            "deferrable": [{"power_kw": 3.0}],
        }
    }


def _metadata_5kw_battery() -> Dict[str, Dict[str, Any]]:
    """Same community with a 5 kW battery, for the P0-3 asymmetry test."""
    meta = _metadata()
    meta["ab"]["battery"]["power_kw"] = 5.0
    return meta


def _observations(timestep=0):
    return {
        "ab_net_electricity_consumption": 3.0,
        "ab_solar_generation": 1.0,
        "ab_non_shiftable_load": 2.0,
        "ab_electrical_storage_soc": 0.5,
    }


def _battery_action(value_kw: float) -> Action:
    return Action(
        asset_id="ab_battery",
        action_type=ActionType.BATTERY_CHARGE,
        value_kw=value_kw,
        timestep=0,
    )


def _action_set(actions: List[Action]) -> set:
    return {(a.asset_id, round(a.value_kw, 6)) for a in actions}


class MockBackend:
    """Mock backend that returns predefined actions."""

    def __init__(self, actions: List[Action]):
        self._actions = actions
        self._call_count = 0

    @property
    def backend_id(self) -> str:
        return "mock"

    @property
    def supports_streaming(self) -> bool:
        return False

    async def generate_actions(
        self,
        scenario,
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional[CostBudget] = None,
    ) -> BackendResponse:
        self._call_count += 1
        return BackendResponse(
            actions=self._actions,
            raw_output="mock",
            prompt_hash="test",
            token_usage={"prompt": 100, "completion": 50, "total": 150},
            latency_ms=10.0,
            cost_usd=0.0,
        )

    async def health_check(self) -> bool:
        return True

    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        return 0.0


class SequenceBackend:
    """Mock backend returning a queued BackendResponse per call.

    A queued exception is raised instead, to simulate a failed call.
    """

    def __init__(self, responses: List[Any]):
        self._responses = list(responses)
        self._call_count = 0

    @property
    def backend_id(self) -> str:
        return "sequence_mock"

    @property
    def supports_streaming(self) -> bool:
        return False

    async def generate_actions(
        self,
        scenario,
        observations: Dict[str, Any],
        timestep: int,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional[CostBudget] = None,
    ) -> BackendResponse:
        self._call_count += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def health_check(self) -> bool:
        return True

    def estimate_cost(self, prompt_tokens: int, max_completion_tokens: int) -> float:
        return 0.0


def _response(*actions: Action) -> BackendResponse:
    return BackendResponse(
        actions=list(actions),
        raw_output="mock",
        prompt_hash="test",
        token_usage={"prompt": 100, "completion": 50, "total": 150},
        latency_ms=10.0,
        cost_usd=0.0,
    )


def _ev_step(timestep, connected, soc, required=0.87):
    return SimpleNamespace(
        timestep=timestep,
        observations={
            "b0_ev_0_connected": 1.0 if connected else 0.0,
            "b0_ev_0_soc": soc,
            "b0_ev_0_required_soc": required,
        },
        applied_actions=RequestedActions(timestep=timestep, actions=[]),
        costs={},
        grid_diagnostics=None,
    )


def test_fallback_mode_is_labelled_and_matches_rule_based(scenario):
    from src.agents.backend.config import LLMConfig
    llm_config = LLMConfig()
    llm_config._backend_raw = "fallback"
    llm = LLMAgentController(scenario, device_metadata=_metadata(), llm_config=llm_config)
    rule = RuleBasedController(scenario)
    assert llm.agent_backend == "fallback"
    assert llm.prompt_hash
    assert llm.sampling_seed == 42

    obs = _observations()
    llm_actions = llm.get_actions(obs, 0)
    rule_actions = rule.get_actions(obs, 0)
    assert llm_actions.timestep == 0
    assert _action_set(llm_actions.actions) == _action_set(rule_actions.actions)
    stats = llm.agent_stats()
    assert stats["agent_backend"] == "fallback"
    assert stats["first_attempt_validity"] == 1.0


def test_llm_backend_proposals_are_parsed_and_applied(scenario):
    mock_backend = MockBackend(_make_mock_actions())
    llm = LLMAgentController(
        scenario, device_metadata=_metadata(), backend=mock_backend
    )
    assert llm.agent_backend == "llm"
    actions = llm.get_actions(_observations(), 0).actions
    by_id = {a.asset_id: a.value_kw for a in actions}
    assert by_id["ab_battery"] == 2.0
    assert by_id["ab_ev_0"] == 5.0
    stats = llm.agent_stats()
    assert stats["first_attempt_validity"] == 1.0
    assert stats["repair_iterations"] == 0
    assert stats["unparseable_outputs"] == 0
    assert stats["llm_unrepaired_violations"] == 0


def _make_mock_actions():
    """Create mock actions for testing."""
    return [
        Action(asset_id="ab_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
        Action(asset_id="ab_ev_0", action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=0),
    ]


def test_unverified_arm_applies_out_of_bounds_proposal_unclamped(scenario):
    """P0-3 unverified treatment: apply as proposed, count, never repair."""
    llm = LLMAgentController(
        scenario, device_metadata=_metadata(), backend=MockBackend([_battery_action(50.0)])
    )
    actions = llm.get_actions(_observations(), 0).actions
    assert actions[0].value_kw == 50.0  # passed through to the adapter
    # The adapter clamp is what bounds the value downstream: 50 kW on a 6 kW
    # battery normalizes to 8.33 and clamps to 1.0 == 6 kW.
    from src.simulation.citylearn_adapter import CityLearnAdapter

    adapter = CityLearnAdapter.__new__(CityLearnAdapter)
    normalized = adapter._to_normalized_action(
        "ab", "electrical_storage", actions[0].value_kw, _metadata()
    )
    assert normalized == 1.0
    stats = llm.agent_stats()
    assert stats["llm_unrepaired_violations"] == 1
    assert stats["repair_iterations"] == 0
    assert stats["first_attempt_validity"] == 0.0


def test_arms_diverge_on_synthetic_out_of_bounds_proposal(scenario):
    """P0-3 asymmetry: 50 kW proposal on a 5 kW battery.

    Unverified yields the proposal (adapter clamps to 5 kW); verified yields
    the deterministic rule-based setpoint for that step.
    """
    obs = _observations()
    rule = RuleBasedController(scenario)
    expected = _action_set(rule.get_actions(obs, 0).actions)

    unverified = LLMAgentController(
        scenario,
        device_metadata=_metadata_5kw_battery(),
        backend=MockBackend([_battery_action(50.0)]),
    )
    unv = unverified.get_actions(obs, 0).actions
    assert _action_set(unv) != expected
    assert next(a.value_kw for a in unv if a.asset_id == "ab_battery") == 50.0

    # The verified arm re-prompts; the mock always re-proposes 50 kW, so the
    # step is replaced with the rule-based dispatch.
    verified = LLMVerifiedController(
        scenario,
        device_metadata=_metadata_5kw_battery(),
        backend=MockBackend([_battery_action(50.0)]),
    )
    ver = verified.get_actions(obs, 0).actions
    assert _action_set(ver) == expected
    stats = verified.agent_stats()
    assert stats["repair_iterations"] == 2  # one re-prompt + deterministic replacement
    assert stats["llm_fallback_steps"] == 1
    assert stats["first_attempt_validity"] == 0.0
    assert stats["verification_failures"].get("bound_violation", 0) == 1


def test_out_of_bounds_proposal_is_verified_and_replaced(scenario):
    # 99 kW exceeds every device bound; the verified arm must replace the
    # step with the rule-based dispatch, never clamp silently.
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=MockBackend([_battery_action(99.0)])
    )
    obs = _observations()
    actions = verified.get_actions(obs, 0).actions
    rule = RuleBasedController(scenario)
    expected = _action_set(rule.get_actions(obs, 0).actions)
    assert _action_set(actions) == expected
    stats = verified.agent_stats()
    assert stats["repair_iterations"] == 2
    assert stats["verification_failures"].get("bound_violation", 0) == 1
    assert stats["first_attempt_validity"] == 0.0


def test_verified_reprompt_success_applies_corrected_proposal(scenario):
    """A corrected re-prompt is applied without falling back (repair 1 of 2)."""
    backend = SequenceBackend([
        _response(_battery_action(50.0)),
        _response(_battery_action(4.0)),
    ])
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=backend
    )
    actions = verified.get_actions(_observations(), 0).actions
    assert actions[0].value_kw == 4.0
    assert backend._call_count == 2
    stats = verified.agent_stats()
    assert stats["repair_iterations"] == 1
    assert stats["llm_fallback_steps"] == 0
    assert stats["first_attempt_validity"] == 0.0


def test_verified_reprompt_unusable_output_replaces_with_rule_based(scenario):
    backend = SequenceBackend([
        _response(_battery_action(99.0)),
        RuntimeError("backend down"),
    ])
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=backend
    )
    obs = _observations()
    actions = verified.get_actions(obs, 0).actions
    rule = RuleBasedController(scenario)
    expected = _action_set(rule.get_actions(obs, 0).actions)
    assert _action_set(actions) == expected
    stats = verified.agent_stats()
    assert stats["repair_iterations"] == 2
    assert stats["llm_fallback_steps"] == 1
    # The initial proposal parsed fine; the failed re-prompt is a call
    # failure, not a parse failure.
    assert stats["unparseable_outputs"] == 0


def test_verified_unknown_asset_is_a_shape_violation_and_is_replaced(scenario):
    bad = Action(
        asset_id="ab_foo", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0
    )
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=MockBackend([bad])
    )
    obs = _observations()
    actions = verified.get_actions(obs, 0).actions
    rule = RuleBasedController(scenario)
    expected = _action_set(rule.get_actions(obs, 0).actions)
    assert _action_set(actions) == expected
    stats = verified.agent_stats()
    assert stats["verification_failures"].get("action_shape", 0) == 1


def test_unparseable_llm_output_falls_back_and_runs_continue(scenario):
    # This test now uses a mock backend that returns invalid actions
    class BadMockBackend:
        @property
        def backend_id(self):
            return "bad_mock"
        @property
        def supports_streaming(self):
            return False
        async def generate_actions(self, scenario, observations, timestep, context=None, budget=None):
            from src.agents.backend.interface import BackendResponse
            # Return invalid actions (wrong asset_id format)
            from src.schemas.action import Action, ActionType
            return BackendResponse(
                actions=[Action(asset_id="invalid", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0)],
                raw_output="not-json",
                prompt_hash="test",
                token_usage={"prompt": 100, "completion": 50, "total": 150},
                latency_ms=10.0,
                cost_usd=0.0,
            )
        async def health_check(self):
            return True
        def estimate_cost(self, prompt_tokens, max_completion_tokens):
            return 0.0

    llm = LLMAgentController(
        scenario, device_metadata=_metadata(), backend=BadMockBackend()
    )
    actions = llm.get_actions(_observations(), 0).actions
    assert actions, "fallback must produce actions for the step"
    stats = llm.agent_stats()
    assert stats["unparseable_outputs"] == 1
    assert stats["verification_failures"].get("unparseable_output", 0) == 1
    assert stats["llm_fallback_steps"] == 1
    assert stats["llm_fallback_step_share"] == 1.0


def test_verified_fallback_mode_records_comparable_accounting(scenario):
    verified = LLMVerifiedController(scenario, device_metadata=_metadata())
    for step in range(3):
        verified.get_actions(_observations(), step)
    stats = verified.agent_stats()
    assert stats["total_steps"] == 3
    assert stats["first_attempt_validity"] == 1.0
    assert stats["agent_backend"] == "fallback"


class FakeTextBackend:
    """Prompt-callable with OllamaPromptCallable-like telemetry attributes."""

    def __init__(self, responses, digest="dae161e27b0e90dd"):
        self._responses = list(responses)
        self.prompts: List[str] = []
        self.call_count = 0
        self.latency_samples_ms: List[float] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model_digest = digest

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.call_count += 1
        self.latency_samples_ms.append(100.0 * self.call_count)
        self.prompt_tokens += 639
        self.completion_tokens += 327
        return self._responses.pop(0)


def _payload(value_kw: float) -> str:
    return json.dumps([{"asset_id": "ab_battery", "value_kw": value_kw}])


def test_parse_llm_actions_clean_fenced_invalid():
    from src.controllers.llm_agent import parse_llm_actions

    actions, status = parse_llm_actions('[{"asset_id": "ab_battery", "value_kw": 2.0}]', 3)
    assert status == "clean"
    assert [a.value_kw for a in actions] == [2.0]
    assert [a.timestep for a in actions] == [3]

    for fenced in (
        '```json\n[{"asset_id": "ab_battery", "value_kw": 2.0}]\n```',
        '```\n[{"asset_id": "ab_battery", "value_kw": 2.0}]\n```',
    ):
        actions, status = parse_llm_actions(fenced)
        assert status == "fenced", fenced
        assert [a.value_kw for a in actions] == [2.0]

    for raw in ("not-json", '{"a": 1}', '[{"asset": "x"}]', '["nope"]', "```json\n[oops", ""):
        actions, status = parse_llm_actions(raw)
        assert status == "invalid", raw
        assert actions is None, raw


def test_backend_from_env_builds_ollama_local_callable(scenario, monkeypatch):
    from src.agents.backend.config import LLMConfig

    monkeypatch.setenv("AGENT_BACKEND", "ollama:qwen2.5-coder:7b")
    llm = LLMAgentController(scenario, device_metadata=_metadata())
    assert llm.agent_backend == "ollama-local"
    assert llm.agent_model() == "qwen2.5-coder:7b"
    assert llm._is_prompt_callable
    assert isinstance(llm.agent_model_digest(), (str, type(None)))
    stats = llm.agent_stats()
    assert stats["agent_backend"] == "ollama-local"
    assert stats["agent_model"] == "qwen2.5-coder:7b"


def test_backend_from_env_bare_ollama_uses_default_model(scenario, monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "ollama")
    llm = LLMAgentController(scenario, device_metadata=_metadata())
    assert llm.agent_backend == "ollama-local"
    assert llm.agent_model() == "qwen2.5-coder:7b"


def test_fenced_output_is_recorded_and_still_applied(scenario):
    backend = FakeTextBackend([f"```json\n{_payload(2.0)}\n```"])
    llm = LLMAgentController(scenario, device_metadata=_metadata(), backend=backend)
    actions = llm.get_actions(_observations(), 0).actions
    assert [a.value_kw for a in actions] == [2.0]
    stats = llm.agent_stats()
    assert stats["llm_fenced_outputs"] == 1
    assert stats["llm_raw_parse_failures"] == 0
    assert stats["llm_calls"] == 1
    assert stats["first_attempt_validity"] == 1.0


def test_invalid_response_counts_parse_failure_and_falls_back(scenario):
    backend = FakeTextBackend(["not-json"])
    llm = LLMAgentController(scenario, device_metadata=_metadata(), backend=backend)
    actions = llm.get_actions(_observations(), 0).actions
    assert actions, "fallback must produce actions for the step"
    stats = llm.agent_stats()
    assert stats["llm_raw_parse_failures"] == 1
    assert stats["unparseable_outputs"] == 1
    assert stats["llm_fallback_steps"] == 1
    assert stats["llm_fallback_step_share"] == 1.0


def test_agent_stats_carries_full_phase2_metric_set(scenario):
    backend = FakeTextBackend([_payload(2.0)])
    llm = LLMAgentController(scenario, device_metadata=_metadata(), backend=backend)
    llm.get_actions(_observations(), 0)
    stats = llm.agent_stats()
    for key in (
        "agent_backend",
        "agent_model",
        "agent_model_digest",
        "prompt_version",
        "prompt_hash",
        "repair_prompt_version",
        "repair_prompt_hash",
        "llm_calls",
        "llm_raw_parse_failures",
        "llm_fenced_outputs",
        "llm_backend_errors",
        "llm_latency_p50_ms",
        "llm_latency_p95_ms",
        "llm_prompt_tokens",
        "llm_completion_tokens",
        "llm_unrepaired_violations",
        "llm_fallback_steps",
        "llm_fallback_step_share",
    ):
        assert key in stats, key
    assert stats["agent_backend"] == "llm"
    assert stats["llm_prompt_tokens"] == 639
    assert stats["llm_completion_tokens"] == 327
    assert stats["llm_latency_p50_ms"] == 100.0
    assert stats["llm_latency_p95_ms"] == 100.0


def test_verified_reprompt_sends_violation_text_to_text_backend(scenario):
    backend = FakeTextBackend([_payload(50.0), _payload(4.0)])
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=backend
    )
    actions = verified.get_actions(_observations(), 0).actions
    assert actions[0].value_kw == 4.0
    assert backend.call_count == 2
    assert "violated these constraints" in backend.prompts[1]
    assert "exceeds" in backend.prompts[1]  # the bound-violation text
    assert "dispatch agent for a renewable energy community" in backend.prompts[0]
    stats = verified.agent_stats()
    assert stats["repair_iterations"] == 1
    assert stats["llm_calls"] == 2
    assert stats["llm_fallback_steps"] == 0


def test_ollama_callable_talks_to_localhost_endpoint(monkeypatch):
    """The callable hits /api/generate with the right payload and telemetry."""
    import urllib.request
    from src.agents.backend.local import ollama_prompt_callable

    captured = {}

    class _FakeResponse:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        body = json.dumps({
            "response": "```json\n[{\"asset_id\": \"b0_battery\", \"value_kw\": 3.0}]\n```",
            "prompt_eval_count": 639,
            "eval_count": 327,
        }).encode("utf-8")
        return _FakeResponse(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    # /api/tags digest lookup fails silently offline (fake_urlopen returns a
    # generate-shaped body without "models"); the generate call must still work.
    backend = ollama_prompt_callable(
        model="qwen2.5-coder:7b", endpoint="http://localhost:11434",
        temperature=0.0, seed=42, timeout_s=60, num_predict=512,
    )
    text = backend("dispatch prompt")
    assert "qwen2.5-coder" in json.dumps(captured["payload"])
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["seed"] == 42
    assert captured["payload"]["options"]["num_predict"] == 512
    assert captured["timeout"] == 60
    assert "```json" in text  # raw text returned; fence handling is the controller's job
    assert backend.call_count == 1
    assert backend.prompt_tokens == 639
    assert backend.completion_tokens == 327
    assert len(backend.latency_samples_ms) == 1


def test_run_manifest_records_ollama_local_agent_fields(scenario, tmp_path, monkeypatch):
    """End-to-end: AGENT_BACKEND=ollama:<model> reaches manifest.json.

    The endpoint is pointed at a dead port so every call fails fast; the run
    must still complete, be labelled ollama-local, and show a 100% fallback
    share with the real backend errors accounted.
    """
    import subprocess
    import sys
    import yaml

    config_path = tmp_path / "scenario.yaml"
    config_path.write_text(yaml.safe_dump(json.loads(scenario.model_dump_json())))
    out_dir = tmp_path / "runs"
    env = dict(os.environ)
    env["AGENT_BACKEND"] = "ollama:qwen2.5-coder:7b"
    env["LLM_LOCAL_ENDPOINT"] = "http://localhost:9"
    env.pop("SAEA_LLM_BACKEND", None)
    result = subprocess.run(
        [
            sys.executable, "-m", "experiments.run_experiment",
            "--config", str(config_path),
            "--controller", "llm_agent",
            "--seed", "42",
            "--max-steps", "4",
            "--output-dir", str(out_dir),
            "--run-id", "llm_ollama_manifest_check",
        ],
        capture_output=True, text=True, timeout=600, env=env,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    run_dir = out_dir / "llm_ablation_test" / "llm_ollama_manifest_check"
    with open(run_dir / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    agent = manifest["agent"]
    assert agent["agent_backend"] == "ollama-local"
    assert agent["agent_model"] == "qwen2.5-coder:7b"
    assert agent["llm_fallback_step_share"] == 1.0
    assert agent["llm_backend_errors"] == agent["llm_calls"] == 4
    assert agent["prompt_hash"]
    with open(run_dir / "result.json", encoding="utf-8") as handle:
        result_data = json.load(handle)
    assert result_data["controller_config"]["type"] == "llm_agent"
    assert result_data["controller_config"]["agent_backend"] == "ollama-local"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
