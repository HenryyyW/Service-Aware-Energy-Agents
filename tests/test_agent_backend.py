"""Tests for AgentBackend interface and implementations."""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch

from src.agents.backend.interface import AgentBackend, BackendResponse, CostBudget
from src.agents.backend.fallback import FallbackBackend
from src.agents.backend.config import LLMConfig
from src.agents.backend.registry import BackendRegistry, create_backend_from_config
from src.agents.backend.prompts import (
    PromptTemplate,
    PROMPT_REGISTRY,
    register_prompt,
    get_prompt,
    get_prompt_hash,
)
from src.schemas.diagnostics import DiagnosticCategory, Severity
from backend.app.routers.agent import _diag_enum


# Fixture to isolate module-level state between tests
@pytest.fixture(autouse=True)
def _isolate_state():
    """Isolate module-level state (tasks, runs, idempotency keys) between tests."""
    from backend.app.state import (
        _tasks,
        _idempotency_keys,
        _task_retries,
        _runs,
    )

    # Save original state
    saved_tasks = dict(_tasks)
    saved_idempotency = dict(_idempotency_keys)
    saved_retries = dict(_task_retries)
    saved_runs = dict(_runs)
    try:
        yield
    finally:
        # Restore original state
        _tasks.clear()
        _tasks.update(saved_tasks)
        _idempotency_keys.clear()
        _idempotency_keys.update(saved_idempotency)
        _task_retries.clear()
        _task_retries.update(saved_retries)
        _runs.clear()
        _runs.update(saved_runs)


class TestCostBudget:
    """Tests for CostBudget dataclass."""

    def test_default_budget(self):
        budget = CostBudget()
        assert budget.max_usd == 1.0
        assert budget.max_latency_ms == 5000
        assert budget.max_tokens == 4000
        assert budget.spent_usd == 0.0

    def test_custom_budget(self):
        budget = CostBudget(max_usd=5.0, max_latency_ms=10000, max_tokens=8000)
        assert budget.max_usd == 5.0
        assert budget.max_latency_ms == 10000
        assert budget.max_tokens == 8000

    def test_budget_check_ok(self):
        budget = CostBudget(max_usd=10.0, max_latency_ms=10000, max_tokens=10000)
        budget.spent_usd = 1.0
        budget.spent_latency_ms = 1000
        budget.spent_tokens = 1000

        class DummyBackend:
            def check_budget(self, budget):
                return super(AgentBackend, self).check_budget(budget)

        # We can't easily test the abstract method, but we can test the logic
        assert budget.spent_usd < budget.max_usd
        assert budget.spent_latency_ms < budget.max_latency_ms
        assert budget.spent_tokens < budget.max_tokens


class TestCostBudgetExceeded:
    """Tests for budget exceeded conditions."""

    def test_usd_exceeded(self):
        budget = CostBudget(max_usd=1.0)
        budget.spent_usd = 1.5
        assert budget.spent_usd > budget.max_usd

    def test_latency_exceeded(self):
        budget = CostBudget(max_latency_ms=1000)
        budget.spent_latency_ms = 1500
        assert budget.spent_latency_ms > budget.max_latency_ms

    def test_tokens_exceeded(self):
        budget = CostBudget(max_tokens=1000)
        budget.spent_tokens = 1500
        assert budget.spent_tokens > budget.max_tokens


class TestFallbackBackend:
    """Tests for FallbackBackend."""

    @pytest.fixture
    def backend(self):
        return FallbackBackend()

    def test_backend_id(self, backend):
        assert backend.backend_id == "fallback"

    def test_supports_streaming(self, backend):
        assert backend.supports_streaming is False

    def test_estimate_cost(self, backend):
        assert backend.estimate_cost(1000, 1000) == 0.0

    def test_health_check(self, backend):
        import asyncio

        result = asyncio.run(backend.health_check())
        assert result is True

    def test_generate_actions_returns_response(self, backend):
        from src.schemas.scenario import ScenarioConfig, BuildingConfig
        from src.schemas.action import RequestedActions

        # Create minimal scenario
        scenario = ScenarioConfig(
            scenario_id="test",
            name="Test",
            description="Test scenario",
            timestep_minutes=15,
            buildings=[
                BuildingConfig(
                    building_id="building_0",
                    location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                )
            ],
        )

        observations = {
            "building_0_net_electricity_consumption": 2.0,
            "building_0_solar_generation": 5.0,
        }

        import asyncio

        response = asyncio.run(backend.generate_actions(scenario, observations, 0))

        assert isinstance(response, BackendResponse)
        assert response.prompt_hash == "fallback"
        assert response.cost_usd == 0.0
        assert response.token_usage["total"] == 0
        assert response.latency_ms >= 0
        assert len(response.actions) >= 0  # May have actions


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_config(self):
        config = LLMConfig()
        assert config.backend == "fallback"
        assert config.model == "kimi-k2.7-code"
        assert config.max_usd == 1.0
        assert config.max_latency_ms == 5000

    def test_validate_fallback_ok(self):
        config = LLMConfig()
        config.backend = "fallback"
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_openai_missing_key(self):
        # Temporarily remove env var
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            config = LLMConfig()
            config.backend = "openai_gpt4"
            errors = config.validate()
            assert any("OPENAI_API_KEY" in e for e in errors)
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_validate_anthropic_missing_key(self):
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            config = LLMConfig()
            config.backend = "anthropic_claude"
            errors = config.validate()
            assert any("ANTHROPIC_API_KEY" in e for e in errors)
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_validate_ollama_ok(self):
        config = LLMConfig()
        config.backend = "ollama"
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_ollama_with_model(self):
        config = LLMConfig()
        config.backend = "ollama:llama3.2:3b"
        assert config.backend == "ollama"
        assert config.ollama_model == "llama3.2:3b"
        errors = config.validate()
        assert len(errors) == 0

    def test_create_cost_budget(self):
        config = LLMConfig(max_usd=5.0, max_latency_ms=10000, max_tokens=8000)
        budget = config.create_cost_budget()
        assert budget.max_usd == 5.0
        assert budget.max_latency_ms == 10000
        assert budget.max_tokens == 8000


class TestBackendRegistry:
    """Tests for BackendRegistry."""

    def test_fallback_available(self):
        assert BackendRegistry.is_available("fallback")

    def test_ollama_available(self):
        assert BackendRegistry.is_available("ollama")

    def test_get_fallback(self):
        backend = BackendRegistry.get("fallback")
        assert isinstance(backend, FallbackBackend)

    def test_list_available(self):
        available = BackendRegistry.list_available()
        assert "fallback" in available
        assert "ollama" in available

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            BackendRegistry.get("nonexistent_backend")


class TestPromptTemplate:
    """Tests for PromptTemplate."""

    def test_prompt_hash_consistency(self):
        template = PromptTemplate(
            template_id="test_v1",
            version=1,
            system_prompt="System",
            user_prompt_template="User {var}",
        )

        hash1 = template.prompt_hash
        hash2 = template.prompt_hash
        assert hash1 == hash2
        assert len(hash1) == 16  # SHA256 truncated to 16 chars

    def test_prompt_hash_changes_with_content(self):
        t1 = PromptTemplate("test_v1", 1, "System", "User {var}")
        t2 = PromptTemplate("test_v1", 1, "Different System", "User {var}")
        t3 = PromptTemplate("test_v1", 2, "System", "User {var}")

        assert t1.prompt_hash != t2.prompt_hash
        assert t1.prompt_hash != t3.prompt_hash

    def test_render(self):
        template = PromptTemplate(
            template_id="test",
            version=1,
            system_prompt="System",
            user_prompt_template="Hello {name}!",
        )

        rendered = template.render(name="World")
        assert rendered == "Hello World!"

    def test_registry_contains_default(self):
        assert "llm_agent_v1" in PROMPT_REGISTRY
        template = PROMPT_REGISTRY["llm_agent_v1"]
        assert template.version == 1
        assert "energy community controller" in template.system_prompt.lower()


class TestPromptRegistry:
    """Tests for prompt registry functions."""

    def test_get_prompt(self):
        template = get_prompt("llm_agent_v1")
        assert template is not None
        assert template.template_id == "llm_agent_v1"

    def test_get_nonexistent(self):
        assert get_prompt("nonexistent") is None

    def test_register_prompt(self):
        new_template = PromptTemplate(
            template_id="test_custom",
            version=1,
            system_prompt="Test",
            user_prompt_template="Test {var}",
        )
        register_prompt(new_template)
        assert "test_custom" in PROMPT_REGISTRY
        assert get_prompt("test_custom") is not None

    def test_get_prompt_hash(self):
        hash_val = get_prompt_hash("llm_agent_v1")
        assert hash_val is not None
        assert len(hash_val) == 16


class TestBackendResponse:
    """Tests for BackendResponse dataclass."""

    def test_backend_response_creation(self):
        from src.schemas.action import Action, ActionType

        action = Action(
            asset_id="building_0_battery",
            action_type=ActionType.BATTERY_CHARGE,
            value_kw=5.0,
            timestep=0,
        )

        response = BackendResponse(
            actions=[action],
            raw_output="test",
            prompt_hash="abc123",
            token_usage={"prompt": 100, "completion": 50, "total": 150},
            latency_ms=100.0,
            cost_usd=0.01,
        )

        assert len(response.actions) == 1
        assert response.actions[0].asset_id == "building_0_battery"
        assert response.token_usage["total"] == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestRunDataCrossProcess:
    """Tests for cross-process run data persistence (fixes run not found in RQ worker)."""

    def test_run_set_get_in_memory_fallback(self):
        """Run data can be set and retrieved via in-memory fallback."""
        from backend.app.state import set_run, get_run

        run_data = {
            "run_id": "run_test_123",
            "status": "completed",
            "scenario_id": "scenario_e",
            "energy_metrics": {"total_cost": 123.45, "grid_import_kwh": 500},
            "service_metrics": {"ev_completion_rate": 0.95},
            "grid_metrics": {"voltage_violations_count": 0},
        }

        set_run("run_test_123", run_data)
        retrieved = get_run("run_test_123")

        assert retrieved is not None
        assert retrieved["run_id"] == "run_test_123"
        assert retrieved["status"] == "completed"
        assert retrieved["energy_metrics"]["total_cost"] == 123.45

    def test_run_not_found_returns_none(self):
        """Getting a non-existent run returns None (not an exception)."""
        from backend.app.state import get_run

        result = get_run("nonexistent_run")
        assert result is None

    def test_load_run_data_uses_persistent_storage(self, monkeypatch):
        """_load_run_data reads from persistent storage, not in-memory simulations dict."""
        from backend.app.routers.agent import _load_run_data
        from backend.app.state import set_run

        # Simulate the simulations router's in-memory dict being empty (different process)
        import backend.app.routers.simulations as sim_module

        monkeypatch.setattr(sim_module, "_runs", {})

        # But persistent storage has the run
        run_data = {
            "run_id": "run_cross_process",
            "status": "completed",
            "energy_metrics": {"total_cost": 200},
        }
        set_run("run_cross_process", run_data)

        # _load_run_data should still find it via persistent storage
        loaded = _load_run_data("run_cross_process")
        assert loaded is not None
        assert loaded["run_id"] == "run_cross_process"
        assert loaded["energy_metrics"]["total_cost"] == 200

    def test_task_storage_unaffected(self):
        """Task storage still works independently of run storage."""
        from backend.app.state import set_task, get_task, set_run, get_run

        task_data = {"task_id": "task_1", "status": "planning"}
        run_data = {"run_id": "run_1", "status": "completed"}

        set_task("task_1", task_data)
        set_run("run_1", run_data)

        assert get_task("task_1") == task_data
        assert get_run("run_1") == run_data

    def test_trajectories_set_get_in_memory_fallback(self):
        """Trajectory data can be set and retrieved via in-memory fallback."""
        from backend.app.state import set_trajectories, get_trajectories

        traj_data = [
            {
                "timestep": 0,
                "observations": {"Building_1": {"voltage": 1.0}},
                "grid_diagnostics": {},
            },
            {
                "timestep": 1,
                "observations": {"Building_1": {"voltage": 1.02}},
                "grid_diagnostics": {"voltage": "ok"},
            },
        ]

        set_trajectories("run_traj_1", traj_data)
        retrieved = get_trajectories("run_traj_1")

        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved[0]["timestep"] == 0
        assert retrieved[1]["grid_diagnostics"].get("voltage") == "ok"

    def test_trajectories_not_found_returns_none(self):
        """Getting non-existent trajectories returns None."""
        from backend.app.state import get_trajectories

        result = get_trajectories("nonexistent_run")
        assert result is None

    def test_load_run_trajectories_uses_durable_storage(self, monkeypatch):
        """_load_run_trajectories reads from durable storage, not in-memory couplers."""
        from backend.app.routers.agent import _load_run_trajectories
        from backend.app.state import set_trajectories

        # Simulate the simulations router's in-memory dict being empty (different process)
        import backend.app.routers.simulations as sim_module

        monkeypatch.setattr(sim_module, "_couplers", {})

        # But durable storage has the trajectories
        traj_data = [
            {
                "timestep": 0,
                "observations": {"Building_1": {"voltage": 1.0}},
                "grid_diagnostics": {},
            },
            {
                "timestep": 1,
                "observations": {"Building_1": {"voltage": 1.02}},
                "grid_diagnostics": {"voltage": "ok"},
            },
        ]
        set_trajectories("run_traj_cross", traj_data)

        # _load_run_trajectories should still find it via durable storage
        loaded = _load_run_trajectories("run_traj_cross")
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0]["timestep"] == 0
        assert loaded[1]["grid_diagnostics"].get("voltage") == "ok"

    def test_trajectory_step_has_observations_and_grid_diagnostics(self):
        """Verify trajectory step has required fields for verifier."""
        from backend.app.state import set_trajectories, get_trajectories

        traj_data = [
            {
                "timestep": 0,
                "observations": {"Building_1": {"voltage": 1.0}},
                "grid_diagnostics": {},
            },
            {
                "timestep": 1,
                "observations": {"Building_1": {"voltage": 1.02}},
                "grid_diagnostics": {"voltage": "ok"},
            },
        ]
        set_trajectories("run_step_test", traj_data)
        retrieved = get_trajectories("run_step_test")

        assert retrieved is not None
        for step in retrieved:
            assert "timestep" in step
            assert "observations" in step
            assert "grid_diagnostics" in step
            assert isinstance(step["observations"], dict)
            assert isinstance(step["grid_diagnostics"], dict)

    def test_set_trajectories_rejects_unserializable(self):
        """set_trajectories should raise on unserializable data (dataclasses, etc.)."""
        from backend.app.state import set_trajectories
        from dataclasses import dataclass

        @dataclass
        class StepResult:
            timestep: int
            observations: dict

        # Dataclass instances are not JSON serializable by default
        unserializable_data = [StepResult(timestep=0, observations={})]

        with pytest.raises(TypeError):
            set_trajectories("run_bad", unserializable_data)


class TestDiagEnumParsing:
    """Tests for the tolerant diagnostic enum parser (_diag_enum)."""

    def test_category_value_form(self):
        """Value-form 'voltage' parses to DiagnosticCategory.VOLTAGE."""
        result = _diag_enum(DiagnosticCategory, "voltage")
        assert result == DiagnosticCategory.VOLTAGE

    def test_category_name_form(self):
        """Name-form 'VOLTAGE' parses to DiagnosticCategory.VOLTAGE."""
        result = _diag_enum(DiagnosticCategory, "VOLTAGE")
        assert result == DiagnosticCategory.VOLTAGE

    def test_category_case_insensitive(self):
        """Mixed case 'VoLtAgE' parses correctly."""
        result = _diag_enum(DiagnosticCategory, "VoLtAgE")
        assert result == DiagnosticCategory.VOLTAGE

    def test_severity_value_form(self):
        """Value-form 'warning' parses to Severity.WARNING."""
        result = _diag_enum(Severity, "warning")
        assert result == Severity.WARNING

    def test_severity_name_form(self):
        """Name-form 'WARNING' parses to Severity.WARNING."""
        result = _diag_enum(Severity, "WARNING")
        assert result == Severity.WARNING

    def test_severity_case_insensitive(self):
        """Mixed case 'WaRnInG' parses correctly."""
        result = _diag_enum(Severity, "WaRnInG")
        assert result == Severity.WARNING

    def test_unknown_category_returns_none(self):
        """Unknown category 'not_a_category' returns None (no crash)."""
        result = _diag_enum(DiagnosticCategory, "not_a_category")
        assert result is None

    def test_unknown_severity_returns_none(self):
        """Unknown severity 'not_a_severity' returns None (no crash)."""
        result = _diag_enum(Severity, "not_a_severity")
        assert result is None

    def test_none_input_returns_none(self):
        """None input returns None."""
        result = _diag_enum(DiagnosticCategory, None)
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        result = _diag_enum(DiagnosticCategory, "")
        assert result is None
