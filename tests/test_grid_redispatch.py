"""Tests for closed-loop grid re-dispatch functionality."""
import pytest
from src.controllers import RuleBasedController, MultiAgentController
from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BatteryConfig, EVConfig, 
    FlexibleLoadConfig, PandapowerConfig
)
from src.schemas.action import ActionType


def test_rule_based_controller_grid_diagnostics_update():
    """Test that RuleBasedController can receive and store grid diagnostics."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for grid diagnostics',
        timestep_minutes=15,
        buildings=[
            BuildingConfig(
                building_id='building_1',
                solar_generation_kw=5.0,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=5.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0,
        pandapower=PandapowerConfig(run_power_flow_every=1)
    )
    
    controller = RuleBasedController(scenario_config=scenario)
    
    # Initially no grid diagnostics
    assert controller.last_grid_diagnostics is None
    
    # Update with mock grid diagnostics (voltage violation)
    mock_diagnostics = {
        "diagnostics": [
            {
                "category": "voltage",
                "severity": "violation",
                "message": "Overvoltage at bus 3",
                "timestep": 0,
                "values": {"voltage_pu": 1.08},
                "limits": {"max_pu": 1.05}
            }
        ],
        "power_flow_converged": True
    }
    
    controller.update_grid_diagnostics(mock_diagnostics)
    assert controller.last_grid_diagnostics is not None
    assert controller.last_grid_diagnostics == mock_diagnostics


def test_rule_based_controller_redispatch_on_voltage_violation():
    """Test that RuleBasedController scales down actions on voltage violation."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for voltage re-dispatch',
        timestep_minutes=15,
        buildings=[
            BuildingConfig(
                building_id='building_1',
                solar_generation_kw=5.0,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=5.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0,
        pandapower=PandapowerConfig(run_power_flow_every=1)
    )
    
    controller = RuleBasedController(scenario_config=scenario)
    
    # Simulate observations with excess PV (should trigger battery charge)
    observations = {
        'building_1_net_electricity_consumption': -3.0,  # Net export (negative demand)
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0
    }
    
    # First step - no violations yet
    actions_step1 = controller.get_actions(observations, timestep=0)
    battery_charge_original = None
    for a in actions_step1.actions:
        if a.action_type == ActionType.BATTERY_CHARGE:
            battery_charge_original = a.value_kw
            break
    
    assert battery_charge_original is not None and battery_charge_original > 0
    
    # Capture the SOC after first step
    soc_after_step1 = controller.battery_soc.get("building_1_battery", 0.5)
    
    # Simulate voltage violation from previous step
    mock_diagnostics = {
        "diagnostics": [
            {
                "category": "voltage",
                "severity": "violation",
                "message": "Overvoltage at bus 3",
                "timestep": 0,
                "values": {"voltage_pu": 1.08},
                "limits": {"max_pu": 1.05}
            }
        ],
        "power_flow_converged": True
    }
    controller.update_grid_diagnostics(mock_diagnostics)
    
    # Create a fresh controller with same SOC to compute baseline without violation
    controller_baseline = RuleBasedController(scenario_config=scenario)
    controller_baseline.battery_soc["building_1_battery"] = soc_after_step1
    actions_baseline = controller_baseline.get_actions(observations, timestep=1)
    battery_charge_baseline = None
    for a in actions_baseline.actions:
        if a.action_type == ActionType.BATTERY_CHARGE:
            battery_charge_baseline = a.value_kw
            break
    
    # Second step with violation - should scale down battery charge due to voltage violation
    actions_step2 = controller.get_actions(observations, timestep=1)
    battery_charge_redispatched = None
    for a in actions_step2.actions:
        if a.action_type == ActionType.BATTERY_CHARGE:
            battery_charge_redispatched = a.value_kw
            break
    
    assert battery_charge_redispatched is not None
    assert battery_charge_baseline is not None
    # Should be scaled by 0.85 for voltage violation (compared to baseline without violation)
    expected_scaled = battery_charge_baseline * 0.85
    assert abs(battery_charge_redispatched - expected_scaled) < 0.01, f"Expected {expected_scaled}, got {battery_charge_redispatched}"


def test_rule_based_controller_redispatch_on_line_loading_violation():
    """Test that RuleBasedController scales down actions on line loading violation."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for line loading re-dispatch',
        timestep_minutes=15,
        buildings=[
            BuildingConfig(
                building_id='building_1',
                solar_generation_kw=5.0,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=5.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0,
        pandapower=PandapowerConfig(run_power_flow_every=1)
    )
    
    controller = RuleBasedController(scenario_config=scenario)
    
    # Get baseline actions
    observations = {
        'building_1_net_electricity_consumption': -3.0,
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0
    }
    
    actions_step1 = controller.get_actions(observations, timestep=0)
    battery_charge_original = None
    for a in actions_step1.actions:
        if a.action_type == ActionType.BATTERY_CHARGE:
            battery_charge_original = a.value_kw
            break
    
    assert battery_charge_original is not None and battery_charge_original > 0
    
    # Capture the SOC after first step
    soc_after_step1 = controller.battery_soc.get("building_1_battery", 0.5)
    
    # Simulate line loading violation
    mock_diagnostics = {
        "diagnostics": [
            {
                "category": "line_loading",
                "severity": "violation",
                "message": "Line 1 overloaded",
                "timestep": 0,
                "values": {"loading_pct": 110.0},
                "limits": {"max_pct": 100.0}
            }
        ],
        "power_flow_converged": True
    }
    controller.update_grid_diagnostics(mock_diagnostics)
    
    # Create a fresh controller with same SOC to compute baseline without violation
    controller_baseline = RuleBasedController(scenario_config=scenario)
    controller_baseline.battery_soc["building_1_battery"] = soc_after_step1
    actions_baseline = controller_baseline.get_actions(observations, timestep=1)
    battery_charge_baseline = None
    for a in actions_baseline.actions:
        if a.action_type == ActionType.BATTERY_CHARGE:
            battery_charge_baseline = a.value_kw
            break
    
    # Next step - should scale down by 0.8 for line loading
    actions_step2 = controller.get_actions(observations, timestep=1)
    battery_charge_redispatched = None
    for a in actions_step2.actions:
        if a.action_type == ActionType.BATTERY_CHARGE:
            battery_charge_redispatched = a.value_kw
            break
    
    assert battery_charge_redispatched is not None
    assert battery_charge_baseline is not None
    # Should be scaled by 0.8 for line loading (compared to baseline without violation)
    expected_scaled = battery_charge_baseline * 0.8
    assert abs(battery_charge_redispatched - expected_scaled) < 0.01, f"Expected {expected_scaled}, got {battery_charge_redispatched}"


def test_multi_agent_controller_grid_diagnostics_update():
    """Test that MultiAgentController can receive and store grid diagnostics."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for multi-agent grid diagnostics',
        timestep_minutes=15,
        buildings=[
            BuildingConfig(
                building_id='building_1',
                solar_generation_kw=5.0,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=5.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0,
        pandapower=PandapowerConfig(run_power_flow_every=1)
    )
    
    controller = MultiAgentController(scenario_config=scenario)
    
    # Initially no grid diagnostics
    assert controller.last_grid_diagnostics is None
    
    # Update with mock grid diagnostics
    mock_diagnostics = {
        "diagnostics": [
            {
                "category": "voltage",
                "severity": "violation",
                "message": "Overvoltage at bus 3",
                "timestep": 0,
                "values": {"voltage_pu": 1.08},
                "limits": {"max_pu": 1.05}
            }
        ],
        "power_flow_converged": True
    }
    
    controller.update_grid_diagnostics(mock_diagnostics)
    assert controller.last_grid_diagnostics is not None
    assert controller.last_grid_diagnostics == mock_diagnostics


def test_multi_agent_controller_redispatch_on_violation():
    """Test that MultiAgentController applies re-dispatch on grid violations."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for multi-agent re-dispatch',
        timestep_minutes=15,
        buildings=[
            BuildingConfig(
                building_id='building_1',
                solar_generation_kw=5.0,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=5.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0,
        pandapower=PandapowerConfig(run_power_flow_every=1)
    )
    
    controller = MultiAgentController(scenario_config=scenario)
    
    # Get baseline actions (no violations)
    observations = {
        'building_1_net_electricity_consumption': -3.0,
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0,
        'building_1_electrical_storage_soc': 0.5
    }
    
    actions_step1 = controller.get_actions(observations, timestep=0)
    # Store original action values for comparison
    original_values = {}
    for a in actions_step1.actions:
        if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                             ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
            original_values[a.asset_id] = a.value_kw
    
    # Simulate voltage violation
    mock_diagnostics = {
        "diagnostics": [
            {
                "category": "voltage",
                "severity": "violation",
                "message": "Overvoltage at bus 3",
                "timestep": 0,
                "values": {"voltage_pu": 1.08},
                "limits": {"max_pu": 1.05}
            }
        ],
        "power_flow_converged": True
    }
    controller.update_grid_diagnostics(mock_diagnostics)
    
    # Next step - actions should be scaled
    actions_step2 = controller.get_actions(observations, timestep=1)
    
    # Check that controllable actions were scaled
    for a in actions_step2.actions:
        if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                             ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
            if a.asset_id in original_values:
                expected = original_values[a.asset_id] * 0.85
                assert abs(a.value_kw - expected) < 0.01, f"Action {a.asset_id} not scaled correctly"


def test_experiment_runner_passes_grid_diagnostics():
    """Test that ExperimentRunner passes grid diagnostics to controller."""
    from experiments.run_experiment import ExperimentRunner
    
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for experiment runner grid diagnostics',
        timestep_minutes=15,
        buildings=[
            BuildingConfig(
                building_id='building_1',
                solar_generation_kw=5.0,
                battery=BatteryConfig(
                    capacity_kwh=10.0,
                    power_kw=5.0,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5
                ),
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0,
        pandapower=PandapowerConfig(run_power_flow_every=1)
    )
    
    runner = ExperimentRunner(scenario)
    runner.setup(controller_type="rule_based")
    
    # Check that controller has the update_grid_diagnostics method
    assert hasattr(runner.controller, 'update_grid_diagnostics')


if __name__ == "__main__":
    test_rule_based_controller_grid_diagnostics_update()
    test_rule_based_controller_redispatch_on_voltage_violation()
    test_rule_based_controller_redispatch_on_line_loading_violation()
    test_multi_agent_controller_grid_diagnostics_update()
    test_multi_agent_controller_redispatch_on_violation()
    test_experiment_runner_passes_grid_diagnostics()
    print("All grid re-dispatch tests passed!")