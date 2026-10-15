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
from src.schemas.action import SimulationStepResult, RequestedActions, LimitedActions, AppliedActions, Action, ActionType
from src.schemas.diagnostics import Diagnostic, DiagnosticCategory, Severity, DiagnosticReport


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])