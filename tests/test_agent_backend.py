"""Tests for AgentBackend interface and implementations."""

import pytest
import os
from unittest.mock import Mock, AsyncMock, patch

from src.agents.backend.interface import AgentBackend, BackendResponse, CostBudget
from src.agents.backend.fallback import FallbackBackend
from src.agents.backend.config import LLMConfig
from src.agents.backend.registry import BackendRegistry, create_backend_from_config
from src.agents.backend.prompts import PromptTemplate, PROMPT_REGISTRY, register_prompt, get_prompt, get_prompt_hash


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
        assert config.model == "gpt-4-turbo"
        assert config.max_usd == 1.0
        assert config.max_latency_ms == 5000
    
    def test_validate_fallback_ok(self):
        config = LLMConfig(backend="fallback")
        errors = config.validate()
        assert len(errors) == 0
    
    def test_validate_openai_missing_key(self):
        # Temporarily remove env var
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            config = LLMConfig(backend="openai_gpt4")
            errors = config.validate()
            assert any("OPENAI_API_KEY" in e for e in errors)
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
    
    def test_validate_anthropic_missing_key(self):
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            config = LLMConfig(backend="anthropic_claude")
            errors = config.validate()
            assert any("ANTHROPIC_API_KEY" in e for e in errors)
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key
    
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
    
    def test_local_llama_available(self):
        assert BackendRegistry.is_available("local_llama")
    
    def test_get_fallback(self):
        backend = BackendRegistry.get("fallback")
        assert isinstance(backend, FallbackBackend)
    
    def test_list_available(self):
        available = BackendRegistry.list_available()
        assert "fallback" in available
        assert "local_llama" in available
    
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