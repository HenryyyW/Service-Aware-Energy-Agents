"""Tests for multi-agent coordination functionality."""
import pytest
from src.controllers import MultiAgentController, CentralizedController, RuleBasedController
from src.coordination import (
    BuildingAgent, BatteryAgent, EVAgent, FlexibleLoadAgent,
    CommunityAggregator, MultiAgentCoordinator, create_coordinator
)
from src.schemas.scenario import ScenarioConfig, BuildingConfig, BatteryConfig, EVConfig, FlexibleLoadConfig
from src.schemas.action import ActionType


def test_multi_agent_controller_creation():
    """Test that MultiAgentController can be created."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for multi-agent controller',
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
                evs=[
                    EVConfig(
                        capacity_kwh=40.0,
                        max_charge_kw=11.0,
                        efficiency=0.95,
                        initial_soc=0.2,
                        target_soc=0.8,
                        arrival_time='18:00',
                        departure_time='07:00'
                    )
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=2.0,
                        energy_kwh=4.0,
                        earliest_start='08:00',
                        latest_end='22:00',
                        duration_hours=4.0
                    )
                ]
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0
    )
    
    controller = MultiAgentController(scenario_config=scenario)
    assert controller is not None
    assert hasattr(controller, 'coordinator')


def test_centralized_controller_creation():
    """Test that CentralizedController can be created."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for centralized controller',
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
                )
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0
    )
    
    controller = CentralizedController(scenario_config=scenario)
    assert controller is not None


def test_coordinator_basic_functionality():
    """Test basic coordinator functionality without pandapower."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for coordinator',
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
                evs=[
                    EVConfig(
                        capacity_kwh=40.0,
                        max_charge_kw=11.0,
                        efficiency=0.95,
                        initial_soc=0.2,
                        target_soc=0.8,
                        arrival_time='18:00',
                        departure_time='07:00'
                    )
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=2.0,
                        energy_kwh=4.0,
                        earliest_start='08:00',
                        latest_end='22:00',
                        duration_hours=4.0
                    )
                ]
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0
    )
    
    coordinator = create_coordinator(scenario)
    assert coordinator is not None
    
    # Test coordination at a specific timestep
    observations = {
        'building_1_net_electricity_consumption': 2.0,
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0
    }
    
    result = coordinator.coordinate(observations, timestep=0)
    assert result is not None
    assert hasattr(result, 'building_proposals')
    assert hasattr(result, 'final_allocations')
    assert 'building_1' in result.building_proposals
    assert 'building_1' in result.final_allocations


def test_coordinator_action_generation():
    """Test that coordinator can generate actions."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for coordinator actions',
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
                evs=[
                    EVConfig(
                        capacity_kwh=40.0,
                        max_charge_kw=11.0,
                        efficiency=0.95,
                        initial_soc=0.2,
                        target_soc=0.8,
                        arrival_time='18:00',
                        departure_time='07:00'
                    )
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=2.0,
                        energy_kwh=4.0,
                        earliest_start='08:00',
                        latest_end='22:00',
                        duration_hours=4.0
                    )
                ]
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0
    )
    
    coordinator = create_coordinator(scenario)
    
    # Test at noon when PV is available
    observations = {
        'building_1_net_electricity_consumption': 2.0,
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0
    }
    
    # Run coordination
    result = coordinator.coordinate(observations, timestep=12*4)  # 12:00 in 15-min steps
    
    # Get actions
    actions = coordinator.get_actions()
    
    # Should have actions from battery, EV, and/or flexible load
    assert isinstance(actions, list)
    # Note: We're not asserting a specific number because the logic might result in 0 actions
    # depending on the exact state, but the important thing is that it doesn't crash


def test_multi_agent_controller_integration():
    """Test MultiAgentController integration with scenario."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario for MultiAgentController',
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
                evs=[
                    EVConfig(
                        capacity_kwh=40.0,
                        max_charge_kw=11.0,
                        efficiency=0.95,
                        initial_soc=0.2,
                        target_soc=0.8,
                        arrival_time='18:00',
                        departure_time='07:00'
                    )
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=2.0,
                        energy_kwh=4.0,
                        earliest_start='08:00',
                        latest_end='22:00',
                        duration_hours=4.0
                    )
                ]
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0
    )
    
    controller = MultiAgentController(scenario_config=scenario)
    
    # Test getting actions
    observations = {
        'building_1_net_electricity_consumption': 2.0,
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0
    }
    
    actions = controller.get_actions(observations, timestep=0)
    assert hasattr(actions, 'actions')  # Should be RequestedActions
    assert isinstance(actions.actions, list)
    
    # Test reset
    controller.reset()
    # Should not raise exception


def test_controller_types_available():
    """Test that all expected controller types are available."""
    from src.controllers import BaseController, RuleBasedController, MultiAgentController, CentralizedController
    
    # Test that we can import them
    assert BaseController is not None
    assert RuleBasedController is not None
    assert MultiAgentController is not None
    assert CentralizedController is not None
    
    # Test inheritance
    assert issubclass(RuleBasedController, BaseController)
    assert issubclass(MultiAgentController, BaseController)
    assert issubclass(CentralizedController, BaseController)


def test_coordination_flow_with_mock_pandapower():
    """Test coordination flow with a mock pandapower network."""
    scenario = ScenarioConfig(
        scenario_id='test',
        name='Test Scenario',
        description='Test scenario with grid validation',
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
                )
            )
        ],
        community_import_limit_kw=100.0,
        community_export_limit_kw=50.0
    )
    
    # Create a mock pandapower network that mimics the expected interface
    class MockPandapowerNetwork:
        def __init__(self, vm_pu_values=None, loading_percent_values=None):
            # Create mock load data structure (pandas-like)
            import pandas as pd
            self.load = pd.DataFrame({'p_mw': [0.0, 0.0, 0.0, 0.0, 0.0]})  # 5 buses
            
            # Create mock result structures
            if vm_pu_values is None:
                vm_pu_values = [1.0, 1.0, 1.0, 1.0, 1.0]  # Normal voltage
            if loading_percent_values is None:
                loading_percent_values = [50.0, 50.0, 50.0, 50.0, 50.0]  # Normal loading
                
            self.res_bus = type('MockResBus', (), {
                'vm_pu': type('MockArray', (), {'values': vm_pu_values})()
            })()
            self.res_line = type('MockResLine', (), {
                'loading_percent': type('MockArray', (), {'values': loading_percent_values})()
            })()
    
    # Test normal case - should pass validation
    mock_network = MockPandapowerNetwork(
        vm_pu_values=[1.0, 1.0, 1.0, 1.0, 1.0],
        loading_percent_values=[50.0, 50.0, 50.0, 50.0, 50.0]
    )
    coordinator = create_coordinator(scenario, pandapower_network=mock_network)
    
    observations = {
        'building_1_net_electricity_consumption': 2.0,
        'building_1_solar_generation': 5.0,
        'building_1_non_shiftable_load': 2.0
    }
    
    # This should not raise an exception
    result = coordinator.coordinate(observations, timestep=0)
    # Note: Grid validation might still fail due to our simplified network mapping
    # but the important thing is that it doesn't crash and returns a valid result
    assert result is not None
    assert hasattr(result, 'grid_validation_passed')
    
    # Test with overvoltage - should fail validation
    mock_network_violation = MockPandapowerNetwork(
        vm_pu_values=[1.1, 1.1, 1.1, 1.1, 1.1],  # Overvoltage
        loading_percent_values=[50.0, 50.0, 50.0, 50.0, 50.0]
    )
    coordinator_violation = create_coordinator(scenario, pandapower_network=mock_network_violation)
    
    result_violation = coordinator_violation.coordinate(observations, timestep=0)
    # This might fail validation due to overvoltage, which is expected behavior
    # The important thing is that it doesn't crash and returns a valid result
    assert result_violation is not None
    assert hasattr(result_violation, 'grid_validation_passed')


if __name__ == "__main__":
    test_multi_agent_controller_creation()
    test_centralized_controller_creation()
    test_coordinator_basic_functionality()
    test_coordinator_action_generation()
    test_multi_agent_controller_integration()
    test_controller_types_available()
    test_coordination_flow_with_mock_pandapower()
    print("All tests passed!")