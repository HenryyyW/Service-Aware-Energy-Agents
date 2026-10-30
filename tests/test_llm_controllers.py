"""Tests for LLM agent controllers."""
import json
from types import SimpleNamespace
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

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


def _observations(timestep=0):
    return {
        "ab_building_0_net_electricity_consumption": 3.0,
        "ab_building_0_solar_generation": 1.0,
        "ab_building_0_non_shiftable_load": 2.0,
        "ab_building_0_electrical_storage_soc": 0.5,
    }


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
    ) -> 'BackendResponse':
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


def _make_mock_actions():
    """Create mock actions for testing."""
    return [
        Action(asset_id="ab_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
        Action(asset_id="ab_ev_0", action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=0),
    ]


def _observations(timestep=0):
    return {
        "ab_building_0_net_electricity_consumption": 3.0,
        "ab_building_0_solar_generation": 1.0,
        "ab_building_0_non_shiftable_load": 2.0,
        "ab_building_0_electrical_storage_soc": 0.5,
    }


def _metadata() -> Dict[str, Dict[str, Any]]:
    return {
        "ab": {
            "battery": {"power_kw": 6.0},
            "chargers": [{"max_charge_kw": 7.0}],
            "deferrable": [{"power_kw": 3.0}],
        }
    }


def _make_mock_actions():
    """Create mock actions for testing."""
    return [
        Action(asset_id="ab_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
        Action(asset_id="ab_ev_0", action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=0),
    ]


def _observations(timestep=0):
    return {
        "ab_building_0_net_electricity_consumption": 3.0,
        "ab_building_0_solar_generation": 1.0,
        "ab_building_0_non_shiftable_load": 2.0,
        "ab_building_0_electrical_storage_soc": 0.5,
    }


def _metadata() -> Dict[str, Dict[str, Any]]:
    return {
        "ab": {
            "battery": {"power_kw": 6.0},
            "chargers": [{"max_charge_kw": 7.0}],
            "deferrable": [{"power_kw": 3.0}],
        }
    }


def _make_mock_actions():
    """Create mock actions for testing."""
    return [
        Action(asset_id="ab_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
        Action(asset_id="ab_ev_0", action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=0),
    ]


def _observations(timestep=0):
    return {
        "ab_building_0_net_electricity_consumption": 3.0,
        "ab_building_0_solar_generation": 1.0,
        "ab_building_0_non_shiftable_load": 2.0,
        "ab_building_0_electrical_storage_soc": 0.5,
    }


def _metadata() -> Dict[str, Dict[str, Any]]:
    return {
        "ab": {
            "battery": {"power_kw": 6.0},
            "chargers": [{"max_charge_kw": 7.0}],
            "deferrable": [{"power_kw": 3.0}],
        }
    }


def _ev_step(timestep, connected, soc, required=0.87):
    from types import SimpleNamespace
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
    rule_actions = RuleBasedController(scenario).get_actions(obs, 0)
    assert llm_actions.timestep == 0
    assert {(a.asset_id, round(a.value_kw, 6)) for a in llm_actions.actions} == {
        (a.asset_id, round(a.value_kw, 6)) for a in rule_actions.actions
    }
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


def test_out_of_bounds_proposal_is_verified_and_repaired(scenario):
    mock_backend = MockBackend([
        Action(asset_id="ab_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=99.0, timestep=0),
    ])
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=MockBackend([
            Action(asset_id="ab_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=99.0, timestep=0),
        ])
    )
    actions = verified.get_actions(_observations(), 0).actions
    assert actions[0].value_kw == 6.0  # battery power bound
    stats = verified.agent_stats()
    assert stats["repair_iterations"] >= 1
    assert stats["verification_failures"].get("bound_violation", 0) >= 1
    assert stats["first_attempt_validity"] == 0.0


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


def test_verified_fallback_mode_records_comparable_accounting(scenario):
    verified = LLMVerifiedController(scenario, device_metadata=_metadata())
    for step in range(3):
        verified.get_actions(_observations(), step)
    stats = verified.agent_stats()
    assert stats["total_steps"] == 3
    assert stats["first_attempt_validity"] == 1.0
    assert stats["agent_backend"] == "fallback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])