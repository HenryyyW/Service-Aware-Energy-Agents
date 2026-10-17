"""Tests for evaluation metrics."""
import pytest
import numpy as np

from src.evaluation.metrics import (
    compute_energy_metrics,
    compute_service_metrics,
    compute_grid_metrics,
    compute_agent_metrics,
    compute_all_metrics,
    calculate_gini_coefficient
)
from src.evaluation.fairness import FairnessAnalyzer
from src.schemas.action import SimulationStepResult, RequestedActions, LimitedActions, AppliedActions, Action, ActionType
from src.schemas.diagnostics import Diagnostic, DiagnosticCategory, Severity, DiagnosticReport
from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BatteryConfig, EVConfig,
    FlexibleLoadConfig, TariffConfig
)


@pytest.fixture
def sample_history():
    """Create sample simulation history."""
    history = []
    for i in range(10):
        requested = RequestedActions(timestep=i, actions=[
            Action(asset_id="b0_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=i),
            Action(asset_id="b0_ev_0", action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=i),
            Action(asset_id="grid", action_type=ActionType.GRID_IMPORT, value_kw=10.0, timestep=i),
        ])
        limited = LimitedActions(timestep=i, actions=[])
        applied = AppliedActions(timestep=i, actions=[
            Action(asset_id="b0_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=i),
            Action(asset_id="b0_ev_0", action_type=ActionType.EV_CHARGE, value_kw=5.0, timestep=i),
            Action(asset_id="grid", action_type=ActionType.GRID_IMPORT, value_kw=10.0, timestep=i),
        ])
        
        step = SimulationStepResult(
            timestep=i,
            requested_actions=requested,
            limited_actions=limited,
            applied_actions=applied,
            observations={
                "building_0_net_electricity_consumption": 8.0,
                "building_0_solar_generation": 5.0,
                "building_0_non_shiftable_load": 10.0,
            },
            rewards={"building_0": -1.0},
            costs={"building_0": 0.5},
            grid_diagnostics={
                "power_flow_converged": True,
                "diagnostics": [],
                "voltage_profile": {0: 1.0, 1: 0.98},
                "loading_profile": {"lines": {0: 0.5}, "trafos": {0: 0.3}}
            }
        )
        history.append(step)
    return history


@pytest.fixture
def sample_scenario_config():
    """Create sample scenario config dict."""
    return {
        "timestep_minutes": 15,
        "battery_capacity_kwh": 100,
        "buildings": [
            {"building_id": "building_0", "evs": [{"target_soc": 0.8, "departure_time": "07:00"}]}
        ]
    }


def test_calculate_gini_coefficient():
    """Test Gini coefficient calculation."""
    # Perfect equality
    assert calculate_gini_coefficient([10, 10, 10, 10]) == 0.0
    
    # Perfect inequality (one has everything)
    gini = calculate_gini_coefficient([0, 0, 0, 100])
    assert gini > 0.5
    
    # Empty list
    assert calculate_gini_coefficient([]) == 0.0
    assert calculate_gini_coefficient([100]) == 0.0


def test_compute_energy_metrics(sample_history, sample_scenario_config):
    """Test energy metrics computation."""
    metrics = compute_energy_metrics(sample_history, sample_scenario_config)
    
    assert metrics.total_cost > 0
    assert metrics.grid_import_kwh > 0
    assert metrics.peak_demand_kw > 0
    assert metrics.load_factor >= 0
    assert metrics.load_factor <= 1
    assert metrics.carbon_emissions_kg >= 0


def test_compute_service_metrics(sample_history, sample_scenario_config):
    """Test service metrics computation."""
    metrics = compute_service_metrics(sample_history, sample_scenario_config)
    
    assert 0 <= metrics.ev_completion_rate <= 1
    assert 0 <= metrics.ev_avg_soc_at_departure <= 1
    assert metrics.comfort_violation_degree_hours >= 0
    assert 0 <= metrics.flexible_load_completion_rate <= 1


def test_compute_grid_metrics(sample_history):
    """Test grid metrics computation."""
    metrics = compute_grid_metrics(sample_history)
    
    assert 0 <= metrics.power_flow_convergence_rate <= 1
    assert metrics.voltage_violations_count >= 0
    assert metrics.max_voltage_pu >= metrics.min_voltage_pu


def test_compute_agent_metrics(sample_history):
    """Test agent metrics computation."""
    metrics = compute_agent_metrics(sample_history, [], 1000, 60.0)
    
    assert 0 <= metrics.task_success_rate <= 1
    assert 0 <= metrics.simulation_success_rate <= 1
    assert metrics.token_consumption == 1000
    assert metrics.wall_clock_seconds == 60.0


def test_compute_all_metrics(sample_history, sample_scenario_config):
    """Test computing all metrics at once."""
    all_metrics = compute_all_metrics(
        history=sample_history,
        scenario_config=sample_scenario_config,
        repair_history=[],
        token_usage=500,
        wall_clock_seconds=30.0
    )
    
    assert 'energy' in all_metrics
    assert 'service' in all_metrics
    assert 'grid' in all_metrics
    assert 'agent' in all_metrics


def test_two_step_reference_case_matches_hand_calculated_metrics():
    """Check metric outputs against a tiny, independently hand-calculated case."""
    off_peak_tariff = TariffConfig(
        import_prices={"off_peak": 0.10},
        export_prices={"off_peak": 0.04},
    )
    scenario = ScenarioConfig(
        scenario_id="reference_case",
        name="Two-step KPI reference",
        description="Deterministic inputs with hand-calculated expected metrics.",
        timestep_minutes=60,
        buildings=[
            BuildingConfig(
                building_id="building_0",
                tariff=off_peak_tariff,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=2.0,
                    initial_soc=0.5,
                ),
                evs=[EVConfig(
                    capacity_kwh=20.0,
                    max_charge_kw=7.0,
                    arrival_time="00:00",
                    departure_time="01:00",
                    initial_soc=0.5,
                    target_soc=0.8,
                )],
                flexible_loads=[FlexibleLoadConfig(
                    power_kw=1.0,
                    energy_kwh=2.0,
                    earliest_start="00:00",
                    latest_end="02:00",
                    duration_hours=2.0,
                )],
            ),
            BuildingConfig(
                building_id="building_1",
                tariff=off_peak_tariff,
            ),
        ],
    )

    def make_step(timestep, observations, costs, actions):
        requested = RequestedActions(timestep=timestep, actions=actions)
        applied = AppliedActions(timestep=timestep, actions=actions)
        return SimulationStepResult(
            timestep=timestep,
            requested_actions=requested,
            limited_actions=LimitedActions(timestep=timestep),
            applied_actions=applied,
            observations=observations,
            costs=costs,
        )

    history = [
        make_step(
            0,
            {
                "building_0_net_electricity_consumption": 2.0,
                "building_1_net_electricity_consumption": 3.0,
                "building_0_solar_generation": 3.0,
                "building_1_solar_generation": 0.0,
                "building_0_connected_electric_vehicle_at_charger_soc": 0.5,
                "building_0_indoor_dry_bulb_temperature": 26.0,
            },
            {"building_0": 0.20, "building_1": 0.30},
            [
                Action(asset_id="building_0_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0),
                Action(asset_id="building_0_ev_0", action_type=ActionType.EV_CHARGE, value_kw=0.3, timestep=0),
                Action(asset_id="building_0_flex_0", action_type=ActionType.FLEXIBLE_LOAD, value_kw=1.0, timestep=0),
            ],
        ),
        make_step(
            1,
            {
                "building_0_net_electricity_consumption": -1.0,
                "building_1_net_electricity_consumption": 0.0,
                "building_0_solar_generation": 1.0,
                "building_1_solar_generation": 0.0,
                "building_0_connected_electric_vehicle_at_charger_soc": 0.8,
                "building_0_indoor_dry_bulb_temperature": 22.0,
            },
            {"building_0": -0.04, "building_1": 0.0},
            [
                Action(asset_id="building_0_battery", action_type=ActionType.BATTERY_DISCHARGE, value_kw=-0.5, timestep=1),
                Action(asset_id="building_0_flex_0", action_type=ActionType.FLEXIBLE_LOAD, value_kw=1.0, timestep=1),
            ],
        ),
    ]

    energy = compute_energy_metrics(
        history,
        scenario.model_dump(),
        carbon_intensity=[0.5, 0.4],
    )
    service = compute_service_metrics(history, scenario.model_dump())
    fairness = FairnessAnalyzer(scenario).analyze(history)

    # Hand calculations: cost=.20 + .30 - .04; import=2+3 kWh;
    # export=1 kWh; peak=5 kW; load factor=(5+0)/2/5=.5.
    assert energy.total_cost == pytest.approx(0.46)
    assert energy.grid_import_kwh == pytest.approx(5.0)
    assert energy.grid_export_kwh == pytest.approx(1.0)
    assert energy.peak_demand_kw == pytest.approx(5.0)
    assert energy.load_factor == pytest.approx(0.5)
    assert energy.pv_generation_kwh == pytest.approx(4.0)
    assert energy.pv_self_consumption_kwh == pytest.approx(3.0)
    assert energy.battery_throughput_kwh == pytest.approx(1.5)
    assert energy.battery_cycles == pytest.approx(0.075)
    assert energy.carbon_emissions_kg == pytest.approx(2.5)

    # EV reaches its 0.8 target at departure (step 1); temperature is 1 C
    # above the 25 C upper bound for one hour; flexible load receives 2 kWh.
    assert service.ev_completion_rate == pytest.approx(1.0)
    assert service.ev_avg_soc_at_departure == pytest.approx(0.8)
    assert service.ev_worst_soc_at_departure == pytest.approx(0.8)
    assert service.comfort_violation_degree_hours == pytest.approx(1.0)
    assert service.flexible_load_completion_rate == pytest.approx(1.0)

    # Member costs are .16 and .30; their two-member Gini coefficient is
    # (0.30 - 0.16) / (2 * 0.46).
    assert fairness.per_member_costs == pytest.approx({"building_0": 0.16, "building_1": 0.30})
    assert fairness.gini_coefficient == pytest.approx(0.14 / 0.92)
    assert fairness.worst_member_cost == pytest.approx(0.30)
    assert fairness.best_member_cost == pytest.approx(0.16)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])