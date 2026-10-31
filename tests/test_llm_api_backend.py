"""Tests for the hosted-API LLM transport (P0-2 resume, feature/llm-api-controller).

The transport swaps Ollama-local for an OpenAI-compatible
``POST {LLM_BASE_URL}/chat/completions`` with a Bearer key from
``LLM_API_KEY``. Everything downstream (``parse_llm_actions`` clean/fenced/
invalid classification, the full phase 2 metric set, the ``llm_dispatch_v2``
prompt, the verified arm's re-prompt) is unchanged and stays covered by
``tests/test_llm_controllers.py``.

Every test here mocks the HTTP layer (monkeypatched ``urllib.request.urlopen``):
no network, no real key. The key never appears in code or fixtures beyond a
dummy ``Bearer`` value that the transport is expected to forward.
"""
import io
import json
import os
import time
from typing import Any, Dict, List, Optional

import pytest
import urllib.error
import urllib.request

from src.schemas.action import Action, ActionType
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
from src.agents.backend.config import LLMConfig
from src.agents.backend.api import ApiPromptCallable, api_prompt_callable


DUMMY_KEY = "dummy-key-for-tests-only"
MODEL_ID = "gpt-4o-mini-2024-07-18"
CLEAN_ACTIONS = '[{"asset_id": "ab_battery", "value_kw": 2.0}, {"asset_id": "ab_ev_0", "value_kw": 5.0}]'


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


def _observations(timestep=0):
    return {
        "ab_net_electricity_consumption": 3.0,
        "ab_solar_generation": 1.0,
        "ab_non_shiftable_load": 2.0,
        "ab_electrical_storage_soc": 0.5,
    }


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _http_error(status: int, detail: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.test/v1/chat/completions",
        code=status,
        msg="mocked",
        hdrs=None,
        fp=io.BytesIO(json.dumps({"error": {"message": detail}}).encode("utf-8")),
    )


def _chat_body(content: str, prompt_tokens: int = 639, completion_tokens: int = 327) -> bytes:
    return json.dumps({
        "id": "chatcmpl-mock",
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }).encode("utf-8")


def _install_fake_urlopen(monkeypatch, script: List[Any]) -> Dict[str, Any]:
    """Queue per-attempt outcomes (bytes body or Exception) and record requests.

    Returns ``captured`` with ``requests`` (url/headers/payload/timeout per
    attempt) and ``sleeps`` (the retry backoff calls).
    """
    captured: Dict[str, Any] = {"requests": [], "sleeps": []}
    queue = list(script)

    def fake_urlopen(request, timeout=None):
        captured["requests"].append({
            "url": request.full_url,
            "headers": dict(request.header_items()),
            "payload": json.loads(request.data.decode("utf-8")),
            "timeout": timeout,
        })
        outcome = queue.pop(0) if queue else RuntimeError("no scripted response left")
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeResponse(outcome)

    def fake_sleep(seconds):
        captured["sleeps"].append(seconds)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(time, "sleep", fake_sleep)
    return captured


def _make_callable(**overrides) -> ApiPromptCallable:
    kwargs = dict(
        model="gpt-4o-mini",
        base_url="https://api.test/v1",
        api_key=DUMMY_KEY,
        temperature=0.0,
        seed=42,
        timeout_s=60,
        max_tokens=512,
    )
    kwargs.update(overrides)
    return api_prompt_callable(**kwargs)


# ---------------------------------------------------------------------------
# Transport: happy paths
# ---------------------------------------------------------------------------

def test_api_callable_posts_chat_completions_with_auth(monkeypatch):
    captured = _install_fake_urlopen(monkeypatch, [_chat_body(CLEAN_ACTIONS)])
    backend = _make_callable()
    text = backend("dispatch prompt")

    assert len(captured["requests"]) == 1
    req = captured["requests"][0]
    assert req["url"] == "https://api.test/v1/chat/completions"
    auth = next(v for k, v in req["headers"].items() if k.lower() == "authorization")
    assert auth == f"Bearer {DUMMY_KEY}"
    assert req["payload"]["model"] == "gpt-4o-mini"
    assert req["payload"]["messages"] == [{"role": "user", "content": "dispatch prompt"}]
    assert req["payload"]["temperature"] == 0.0
    assert req["payload"]["seed"] == 42
    assert req["payload"]["max_tokens"] == 512
    assert req["payload"]["stream"] is False
    assert req["timeout"] == 60

    assert text == CLEAN_ACTIONS  # raw text returned; fence handling is the controller's job
    assert backend.prompt_tokens == 639
    assert backend.completion_tokens == 327
    assert backend.model_digest == MODEL_ID  # the API model id fills the digest field
    assert backend.call_count == 1
    assert len(backend.latency_samples_ms) == 1
    assert backend.last_error is None


def test_api_callable_returns_fenced_text_raw(monkeypatch):
    fenced = '```json\n[{"asset_id": "ab_battery", "value_kw": 3.0}]\n```'
    captured = _install_fake_urlopen(monkeypatch, [_chat_body(fenced)])
    backend = _make_callable()
    text = backend("prompt")
    assert text == fenced  # passthrough; parse_llm_actions classifies it downstream


def test_api_callable_model_digest_updates_from_each_response(monkeypatch):
    captured = _install_fake_urlopen(
        monkeypatch, [_chat_body(CLEAN_ACTIONS), _chat_body(CLEAN_ACTIONS)]
    )
    backend = _make_callable()
    backend("one")
    assert backend.model_digest == MODEL_ID
    backend("two")
    assert backend.model_digest == MODEL_ID
    assert backend.call_count == 2
    assert backend.prompt_tokens == 1278  # 2 x 639, cumulative for agent_stats deltas


# ---------------------------------------------------------------------------
# Transport: retries and failures
# ---------------------------------------------------------------------------

def test_api_callable_retries_429_and_5xx_then_succeeds(monkeypatch):
    captured = _install_fake_urlopen(
        monkeypatch,
        [_http_error(429, "rate limited"), _http_error(503, "unavailable"), _chat_body(CLEAN_ACTIONS)],
    )
    backend = _make_callable(retry_backoff_s=0.5)
    text = backend("prompt")

    assert text == CLEAN_ACTIONS
    assert len(captured["requests"]) == 3  # 1 initial + 2 retries
    assert captured["sleeps"] == [0.5, 1.0]  # short linear backoff
    assert backend.call_count == 1  # one logical call, like the controller's llm_calls


def test_api_callable_401_fails_fast_without_retry(monkeypatch):
    captured = _install_fake_urlopen(monkeypatch, [_http_error(401, "bad key")])
    backend = _make_callable()
    with pytest.raises(RuntimeError, match="401"):
        backend("prompt")
    assert len(captured["requests"]) == 1  # auth errors are never retried
    assert captured["sleeps"] == []
    assert "401" in backend.last_error


def test_api_callable_5xx_exhausts_retries(monkeypatch):
    captured = _install_fake_urlopen(
        monkeypatch, [_http_error(503), _http_error(503), _http_error(503)]
    )
    backend = _make_callable(retry_backoff_s=0.5)
    with pytest.raises(RuntimeError, match="503"):
        backend("prompt")
    assert len(captured["requests"]) == 3  # 2 retries spent, then give up
    assert captured["sleeps"] == [0.5, 1.0]


def test_api_callable_timeout_fails_without_retry(monkeypatch):
    captured = _install_fake_urlopen(monkeypatch, [TimeoutError("hung generation")])
    backend = _make_callable()
    with pytest.raises(RuntimeError, match="LLM API request failed"):
        backend("prompt")
    assert len(captured["requests"]) == 1  # timeouts are not retried
    assert "hung generation" in backend.last_error


def test_api_callable_missing_key_refuses_before_any_http(monkeypatch):
    captured = _install_fake_urlopen(monkeypatch, [])
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    backend = _make_callable(api_key=None)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        backend("prompt")
    assert captured["requests"] == []  # never hit the wire without credentials
    assert backend.call_count == 1  # still accounted as a backend invocation
    assert backend.prompt_tokens == 0


def test_api_callable_key_read_from_env_at_call_time(monkeypatch):
    """The key is picked up from the env when not passed to the constructor."""
    captured = _install_fake_urlopen(monkeypatch, [_chat_body(CLEAN_ACTIONS)])
    monkeypatch.setenv("LLM_API_KEY", "env-supplied-key")
    backend = _make_callable(api_key=None)
    backend("prompt")
    auth = next(v for k, v in captured["requests"][0]["headers"].items() if k.lower() == "authorization")
    assert auth == "Bearer env-supplied-key"


def test_api_callable_unexpected_response_shape(monkeypatch):
    body = json.dumps({"object": "error", "choices": []}).encode("utf-8")
    _install_fake_urlopen(monkeypatch, [body])
    backend = _make_callable()
    with pytest.raises(RuntimeError, match="unexpected response shape"):
        backend("prompt")


def test_api_callable_reasoning_content_fallback(monkeypatch):
    """Reasoning models: content null, JSON inside reasoning_content.

    The reasoning text is returned raw so parse_llm_actions classifies it —
    a fenced JSON inside reasoning counts as a formatting violation, never
    an empty response.
    """
    fenced = '```json\n[{"asset_id": "ab_battery", "value_kw": 2.0}]\n```'
    body = json.dumps({
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": None, "reasoning_content": fenced},
        }],
        "usage": {"prompt_tokens": 900, "completion_tokens": 200},
    }).encode("utf-8")
    _install_fake_urlopen(monkeypatch, [body])
    backend = _make_callable()
    text = backend("prompt")
    assert text == fenced
    assert backend.prompt_tokens == 900  # usage captured even on the reasoning path
    assert backend.model_digest == MODEL_ID


def test_api_callable_empty_content_falls_back_to_reasoning(monkeypatch):
    body = json.dumps({
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": "  ", "reasoning_content": CLEAN_ACTIONS},
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }).encode("utf-8")
    _install_fake_urlopen(monkeypatch, [body])
    backend = _make_callable()
    assert backend("prompt") == CLEAN_ACTIONS


def test_api_callable_no_content_no_reasoning_raises(monkeypatch):
    body = json.dumps({
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": None}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }).encode("utf-8")
    _install_fake_urlopen(monkeypatch, [body])
    backend = _make_callable()
    with pytest.raises(RuntimeError, match="neither content nor reasoning_content"):
        backend("prompt")


def test_api_callable_default_base_url(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    captured = _install_fake_urlopen(monkeypatch, [_chat_body(CLEAN_ACTIONS)])
    backend = ApiPromptCallable(model="gpt-4o-mini", api_key=DUMMY_KEY)
    backend("prompt")
    assert captured["requests"][0]["url"] == "https://api.openai.com/v1/chat/completions"


def test_api_callable_base_url_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://proxy.test/v2/")
    captured = _install_fake_urlopen(monkeypatch, [_chat_body(CLEAN_ACTIONS)])
    backend = ApiPromptCallable(model="gpt-4o-mini", api_key=DUMMY_KEY)
    backend("prompt")
    assert captured["requests"][0]["url"] == "https://proxy.test/v2/chat/completions"  # trailing slash stripped


# ---------------------------------------------------------------------------
# Controller wiring: AGENT_BACKEND=api:<model>
# ---------------------------------------------------------------------------

def _env_api_controller(monkeypatch, scenario, controller_cls=LLMAgentController, **env):
    monkeypatch.setenv("AGENT_BACKEND", env.pop("agent_backend", "api:gpt-4o-mini"))
    monkeypatch.setenv("LLM_API_KEY", env.pop("llm_api_key", DUMMY_KEY))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return controller_cls(scenario, device_metadata=_metadata())


def test_backend_from_env_builds_api_callable(monkeypatch, scenario):
    monkeypatch.setenv("AGENT_BACKEND", "api:gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", DUMMY_KEY)
    monkeypatch.setenv("SAEA_LLM_TIMEOUT_S", "900")
    llm = LLMAgentController(scenario, device_metadata=_metadata())
    backend = llm._backend
    assert isinstance(backend, ApiPromptCallable)
    assert backend.model == "gpt-4o-mini"
    assert backend.timeout_s == 900.0
    assert llm.agent_backend == "api"
    assert llm.agent_model() == "gpt-4o-mini"
    assert llm.agent_model_digest() is None  # filled from the first response


def test_backend_from_env_bare_api_uses_env_model(monkeypatch, scenario):
    monkeypatch.setenv("AGENT_BACKEND", "api")
    monkeypatch.setenv("LLM_API_MODEL", "claude-x")
    monkeypatch.setenv("LLM_API_KEY", DUMMY_KEY)
    llm = LLMAgentController(scenario, device_metadata=_metadata())
    assert llm.agent_model() == "claude-x"
    assert llm.agent_backend == "api"


def test_backend_from_env_freeform_llm_backend_raw(monkeypatch, scenario):
    """The runner's --llm-backend path (LLMConfig._backend_raw) also selects api."""
    monkeypatch.delenv("AGENT_BACKEND", raising=False)
    monkeypatch.setenv("LLM_API_KEY", DUMMY_KEY)
    llm = LLMAgentController(
        scenario,
        device_metadata=_metadata(),
        llm_config=LLMConfig(_backend_raw="api:model-x"),
    )
    assert llm.agent_backend == "api"
    assert llm.agent_model() == "model-x"


def test_backend_from_env_still_parses_ollama(monkeypatch, scenario):
    """The ollama selector stays parseable (no local server is ever started)."""
    monkeypatch.setenv("AGENT_BACKEND", "ollama:qwen2.5-coder:7b")
    llm = LLMAgentController(scenario, device_metadata=_metadata())
    from src.agents.backend.local import OllamaPromptCallable

    assert isinstance(llm._backend, OllamaPromptCallable)
    assert llm.agent_backend == "ollama-local"


# ---------------------------------------------------------------------------
# Controller integration over the API transport (faked HTTP, real parse path)
# ---------------------------------------------------------------------------

def test_api_backend_clean_json_applied_with_tokens(monkeypatch, scenario):
    captured = _install_fake_urlopen(monkeypatch, [_chat_body(CLEAN_ACTIONS)])
    llm = _env_api_controller(monkeypatch, scenario)
    actions = llm.get_actions(_observations(), 0).actions
    by_id = {a.asset_id: a.value_kw for a in actions}
    assert by_id["ab_battery"] == 2.0
    assert by_id["ab_ev_0"] == 5.0
    stats = llm.agent_stats()
    assert stats["llm_calls"] == 1
    assert stats["llm_backend_errors"] == 0
    assert stats["llm_prompt_tokens"] == 639
    assert stats["llm_completion_tokens"] == 327
    assert stats["agent_model_digest"] == MODEL_ID
    assert len(llm._latency_samples_ms) == 1
    assert captured["requests"][0]["payload"]["model"] == "gpt-4o-mini"


def test_api_backend_fenced_output_recorded_and_applied(monkeypatch, scenario):
    fenced = f"```json\n{CLEAN_ACTIONS}\n```"
    _install_fake_urlopen(monkeypatch, [_chat_body(fenced)])
    llm = _env_api_controller(monkeypatch, scenario)
    actions = llm.get_actions(_observations(), 0).actions
    by_id = {a.asset_id: a.value_kw for a in actions}
    assert by_id["ab_battery"] == 2.0
    stats = llm.agent_stats()
    assert stats["llm_fenced_outputs"] == 1  # formatting violation recorded, never hidden
    assert stats["llm_calls"] == 1
    assert stats["llm_backend_errors"] == 0


def test_api_backend_invalid_json_counts_parse_failure_and_falls_back(monkeypatch, scenario):
    _install_fake_urlopen(monkeypatch, [_chat_body("not-json")])
    llm = _env_api_controller(monkeypatch, scenario)
    actions = llm.get_actions(_observations(), 0).actions
    expected = _action_set(RuleBasedController(scenario).get_actions(_observations(), 0).actions)
    assert _action_set(actions) == expected
    stats = llm.agent_stats()
    assert stats["llm_raw_parse_failures"] == 1
    assert stats["llm_fallback_steps"] == 1
    assert stats["llm_fallback_step_share"] == 1.0


def test_api_backend_401_counts_backend_error_and_falls_back(monkeypatch, scenario):
    _install_fake_urlopen(monkeypatch, [_http_error(401, "bad key")])
    llm = _env_api_controller(monkeypatch, scenario)
    actions = llm.get_actions(_observations(), 0).actions
    expected = _action_set(RuleBasedController(scenario).get_actions(_observations(), 0).actions)
    assert _action_set(actions) == expected
    stats = llm.agent_stats()
    assert stats["llm_backend_errors"] == 1
    assert stats["llm_calls"] == 1
    assert stats["llm_fallback_steps"] == 1


def test_api_backend_verified_arm_reprompt_over_api(monkeypatch, scenario):
    """Verified arm: out-of-bounds proposal re-prompts over the API and the
    corrected proposal (4 kW within the 6 kW bound) is applied without fallback."""
    _install_fake_urlopen(
        monkeypatch,
        [
            _chat_body('[{"asset_id": "ab_battery", "value_kw": 50.0}]'),
            _chat_body('[{"asset_id": "ab_battery", "value_kw": 4.0}]'),
        ],
    )
    llm = _env_api_controller(monkeypatch, scenario, controller_cls=LLMVerifiedController)
    actions = llm.get_actions(_observations(), 0).actions
    assert actions[0].value_kw == 4.0
    stats = llm.agent_stats()
    assert stats["repair_iterations"] == 1
    assert stats["llm_calls"] == 2  # proposal + corrective re-prompt
    assert stats["llm_fallback_steps"] == 0
    assert stats["first_attempt_validity"] == 0.0


def _action_set(actions: List[Action]) -> set:
    return {(a.asset_id, round(a.value_kw, 6)) for a in actions}


# ---------------------------------------------------------------------------
# End-to-end manifest wiring (subprocess, dead endpoint: no network, no key use)
# ---------------------------------------------------------------------------

def test_run_manifest_records_api_agent_fields(scenario, tmp_path, monkeypatch):
    """End-to-end: AGENT_BACKEND=api:<model> reaches manifest.json.

    The endpoint is pointed at a dead port so every call fails fast (no
    retries on connection errors); the run must still complete, be labelled
    ``api``, and show a 100% fallback share with the backend errors accounted.
    """
    import subprocess
    import sys
    import yaml

    config_path = tmp_path / "scenario.yaml"
    config_path.write_text(yaml.safe_dump(json.loads(scenario.model_dump_json())))
    out_dir = tmp_path / "runs"
    env = dict(os.environ)
    env["AGENT_BACKEND"] = "api:api-test-model"
    env["LLM_BASE_URL"] = "http://localhost:9"
    env["LLM_API_KEY"] = DUMMY_KEY
    env.pop("SAEA_LLM_BACKEND", None)
    result = subprocess.run(
        [
            sys.executable, "-m", "experiments.run_experiment",
            "--config", str(config_path),
            "--controller", "llm_agent",
            "--seed", "42",
            "--max-steps", "4",
            "--output-dir", str(out_dir),
            "--run-id", "llm_api_manifest_check",
        ],
        capture_output=True, text=True, timeout=600, env=env,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    run_dir = out_dir / "llm_ablation_test" / "llm_api_manifest_check"
    with open(run_dir / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    agent = manifest["agent"]
    assert agent["agent_backend"] == "api"
    assert agent["agent_model"] == "api-test-model"
    assert agent["llm_fallback_step_share"] == 1.0
    assert agent["llm_backend_errors"] == agent["llm_calls"] == 4
    assert agent["prompt_hash"]
    with open(run_dir / "result.json", encoding="utf-8") as handle:
        result_data = json.load(handle)
    assert result_data["controller_config"]["type"] == "llm_agent"
    assert result_data["controller_config"]["agent_backend"] == "api"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
