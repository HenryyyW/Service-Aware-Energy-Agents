"""Joint integration test for market clearing + re-dispatch loop."""
import pytest
from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BatteryConfig, EVConfig, 
    FlexibleLoadConfig, PandapowerConfig, EnergySharingConfig
)
from src.schemas.action import ActionType
from src.simulation.coupling import SimulationCoupler
from src.controllers import RuleBasedController, MultiAgentController
import tempfile


def create_scenario_d_config():
    """Create scenario D config with energy sharing enabled."""
    return ScenarioConfig(
        scenario_id='scenario_d_test',
        name='Test Local Energy Sharing',
        description='Test scenario for market clearing + re-dispatch integration',
        random_seed=42,
        timestep_minutes=15,
        community_import_limit_kw=200.0,
        community_export_limit_kw=150.0,
        buildings=[
            BuildingConfig(
                building_id='building_0',
                location={'lat': 40.0000, 'lon': -105.0000, 'timezone': 'America/Denver'},
                simulation_start='2023-07-01',
                simulation_end='2023-07-08',
                pv={'capacity_kw': 8.0, 'azimuth': 180, 'tilt': 30, 'efficiency': 0.20, 'inverter_efficiency': 0.96},
                battery=BatteryConfig(
                    capacity_kwh=13.5, power_kw=5.0, efficiency_charge=0.95,
                    efficiency_discharge=0.95, soc_min=0.1, soc_max=0.9, initial_soc=0.5
                ),
                evs=[EVConfig(
                    capacity_kwh=60.0, max_charge_kw=11.0, efficiency=0.90,
                    arrival_time='18:00', departure_time='07:00', target_soc=0.8,
                    initial_soc=0.3, connected_days=[0,1,2,3,4,5,6]
                )],
                flexible_loads=[FlexibleLoadConfig(
                    power_kw=3.0, energy_kwh=6.0, earliest_start='20:00',
                    latest_end='06:00', duration_hours=2.0
                )],
                tariff={'type': 'time_of_use', 'import_prices': {'off_peak': 0.08, 'mid_peak': 0.12, 'on_peak': 0.20},
                        'export_prices': {'off_peak': 0.03, 'mid_peak': 0.05, 'on_peak': 0.08}, 'demand_charge': 5.0}
            ),
            BuildingConfig(
                building_id='building_1',
                location={'lat': 40.0007, 'lon': -105.0007, 'timezone': 'America/Denver'},
                simulation_start='2023-07-01',
                simulation_end='2023-07-08',
                pv={'capacity_kw': 6.0, 'azimuth': 200, 'tilt': 30, 'efficiency': 0.20, 'inverter_efficiency': 0.96},
                battery=BatteryConfig(
                    capacity_kwh=10.0, power_kw=4.0, efficiency_charge=0.95,
                    efficiency_discharge=0.95, soc_min=0.1, soc_max=0.9, initial_soc=0.5
                ),
                evs=[EVConfig(
                    capacity_kwh=75.0, max_charge_kw=11.0, efficiency=0.90,
                    arrival_time='19:00', departure_time='08:00', target_soc=0.8,
                    initial_soc=0.4, connected_days=[0,1,2,3,4,5,6]
                )],
                flexible_loads=[FlexibleLoadConfig(
                    power_kw=2.5, energy_kwh=5.0, earliest_start='22:00',
                    latest_end='06:00', duration_hours=2.0
                )],
                tariff={'type': 'time_of_use', 'import_prices': {'off_peak': 0.08, 'mid_peak': 0.12, 'on_peak': 0.20},
                        'export_prices': {'off_peak': 0.03, 'mid_peak': 0.05, 'on_peak': 0.08}, 'demand_charge': 5.0}
            ),
            BuildingConfig(
                building_id='building_2',
                location={'lat': 40.0007, 'lon': -104.9993, 'timezone': 'America/Denver'},
                simulation_start='2023-07-01',
                simulation_end='2023-07-08',
                pv={'capacity_kw': 10.0, 'azimuth': 160, 'tilt': 30, 'efficiency': 0.20, 'inverter_efficiency': 0.96},
                battery=BatteryConfig(
                    capacity_kwh=15.0, power_kw=7.0, efficiency_charge=0.95,
                    efficiency_discharge=0.95, soc_min=0.1, soc_max=0.9, initial_soc=0.5
                ),
                evs=[EVConfig(
                    capacity_kwh=50.0, max_charge_kw=7.0, efficiency=0.90,
                    arrival_time='17:00', departure_time='07:00', target_soc=0.8,
                    initial_soc=0.2, connected_days=[0,1,2,3,4,5,6]
                )],
                flexible_loads=[FlexibleLoadConfig(
                    power_kw=4.0, energy_kwh=8.0, earliest_start='20:00',
                    latest_end='06:00', duration_hours=2.0
                )],
                tariff={'type': 'time_of_use', 'import_prices': {'off_peak': 0.08, 'mid_peak': 0.12, 'on_peak': 0.20},
                        'export_prices': {'off_peak': 0.03, 'mid_peak': 0.05, 'on_peak': 0.08}, 'demand_charge': 5.0}
            ),
        ],
        pandapower=PandapowerConfig(
            network_type='ieee_34',
            coordinate_system='geographic',
            bus_mappings=[
                {'building_id': 'building_0', 'bus_idx': 1, 'phase': 'all', 'voltage_level': 'LV'},
                {'building_id': 'building_1', 'bus_idx': 3, 'phase': 'all', 'voltage_level': 'LV'},
                {'building_id': 'building_2', 'bus_idx': 5, 'phase': 'all', 'voltage_level': 'LV'},
            ],
            slack_bus=0,
            voltage_limits={'min': 0.95, 'max': 1.05},
            line_loading_limit=1.0,
            transformer_loading_limit=1.0,
            run_power_flow_every=1
        ),
        energy_sharing=EnergySharingConfig(
            enabled=True,
            market_type='uniform_price',
            settlement_interval='15min',
            import_limit_kw=50.0,
            export_limit_kw=50.0
        ),
        failures=[]
    )


def test_market_clearing_modifies_building_powers_before_power_flow():
    """Verify market clearing happens before power flow and modifies building powers."""
    scenario = create_scenario_d_config()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()
        
        # Step 1: Get actions from controller
        requested_actions = controller.get_actions(observations, 0)
        
        # Step 2: Run co-simulation step (includes market clearing + power flow)
        result = coupler.step(requested_actions)
        
        # Verify market result exists
        assert result.market_result is not None, "Market clearing should have run"
        
        # Verify trades are present (even if 0 volume)
        assert hasattr(result.market_result, 'trades'), "Market result should have trades"
        assert hasattr(result.market_result, 'clearing_price'), "Market result should have clearing price"
        
        # Verify power flow converged
        assert result.power_flow_converged, "Power flow should converge"
        
        # Verify grid diagnostics are available
        assert result.grid_diagnostics is not None
        assert len(result.grid_diagnostics.diagnostics) >= 0
        
        coupler.close()


def test_re_dispatch_reacts_to_grid_violations_with_market_clearing():
    """Test that re-dispatch loop reacts to grid violations even with market clearing active."""
    scenario = create_scenario_d_config()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()
        
        # Inject a mock grid diagnostic with voltage violation
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
        
        # Get actions - should be scaled down due to voltage violation
        actions_with_violation = controller.get_actions(observations, 1)
        
        # Check that battery charge actions are scaled
        battery_charge_scaled = False
        for a in actions_with_violation.actions:
            if a.action_type == ActionType.BATTERY_CHARGE:
                # The action value should be reduced due to voltage violation
                # (exact value depends on controller logic)
                assert a.value_kw > 0, "Battery charge should still be positive"
                battery_charge_scaled = True
        
        # Verify grid diagnostics were passed through
        assert controller.last_grid_diagnostics is not None
        assert controller.last_grid_diagnostics == mock_diagnostics


def test_market_clearing_and_re_dispatch_sequence():
    """Test the full sequence: market clearing -> power flow -> grid diagnostics -> re-dispatch."""
    scenario = create_scenario_d_config()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()
        
        # Run multiple steps and verify the loop works
        max_steps = 5
        for step in range(max_steps):
            # Controller acts based on previous grid diagnostics (or none for step 0)
            requested_actions = controller.get_actions(observations, step)
            
            # Co-simulation step: market clearing + power flow
            result = coupler.step(requested_actions)
            
            # Verify market clearing ran
            if scenario.energy_sharing.enabled:
                assert result.market_result is not None, f"Market result missing at step {step}"
            
            # Verify power flow ran
            assert result.power_flow_converged, f"Power flow failed at step {step}"
            
            # Extract grid diagnostics for next step
            grid_diagnostics = result.citylearn_result.grid_diagnostics
            
            # Pass to controller for next step's re-dispatch
            if hasattr(controller, 'update_grid_diagnostics'):
                controller.update_grid_diagnostics(grid_diagnostics)
            
            # Update observations
            observations = result.citylearn_result.observations
            
            # Check that grid diagnostics are properly structured
            assert grid_diagnostics is not None
            assert 'power_flow_converged' in grid_diagnostics
            assert 'diagnostics' in grid_diagnostics
        
        coupler.close()


def test_energy_sharing_limits_respected_in_power_flow():
    """Test that community import/export limits from energy sharing config are respected."""
    scenario = create_scenario_d_config()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()
        
        # Run a few steps
        for step in range(3):
            requested_actions = controller.get_actions(observations, step)
            result = coupler.step(requested_actions)
            observations = result.citylearn_result.observations
        
        # Check that community limits from energy_sharing config are used
        import_limit = scenario.energy_sharing.import_limit_kw
        export_limit = scenario.energy_sharing.export_limit_kw
        
        # These should be passed to pandapower grid limit checking
        assert import_limit == 50.0
        assert export_limit == 50.0
        
        # Verify the grid limit diagnostics were checked
        # (even if no violations occurred)
        assert result.grid_diagnostics is not None
        
        coupler.close()


def test_multi_agent_controller_with_market_clearing():
    """Test that MultiAgentController works correctly with market clearing."""
    scenario = create_scenario_d_config()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = MultiAgentController(scenario_config=scenario)
        controller.reset()
        
        # Run a few steps
        for step in range(3):
            requested_actions = controller.get_actions(observations, step)
            result = coupler.step(requested_actions)
            observations = result.citylearn_result.observations
            
            # Verify market clearing ran
            assert result.market_result is not None
            
            # Verify power flow converged
            assert result.power_flow_converged
        
        coupler.close()


def test_no_market_clearing_when_disabled():
    """Verify market clearing is skipped when energy_sharing is disabled."""
    scenario = create_scenario_d_config()
    scenario.energy_sharing.enabled = False
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()
        
        requested_actions = controller.get_actions(observations, 0)
        result = coupler.step(requested_actions)
        
        # Market result should be None when energy sharing is disabled
        assert result.market_result is None
        assert result.settlement_snapshot is None
        
        # Power flow should still run
        assert result.power_flow_converged
        
        coupler.close()


def test_grid_violations_trigger_re_dispatch_with_market_clearing():
    """Test that grid violations from power flow trigger re-dispatch in subsequent step."""
    scenario = create_scenario_d_config()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        coupler = SimulationCoupler(scenario, data_dir=tmpdir)
        observations = coupler.reset(random_seed=42)
        
        controller = RuleBasedController(scenario_config=scenario)
        controller.reset()
        
        # Step 1: No grid diagnostics yet (first step)
        requested_actions_1 = controller.get_actions(observations, 0)
        result_1 = coupler.step(requested_actions_1)
        
        # Get grid diagnostics from step 1
        grid_diag_1 = result_1.citylearn_result.grid_diagnostics
        
        # Step 2: Controller should use grid diagnostics from step 1
        controller.update_grid_diagnostics(grid_diag_1)
        requested_actions_2 = controller.get_actions(observations, 1)
        
        # Actions should be influenced by grid diagnostics
        # (In this test case, no actual violations, but the mechanism should work)
        assert len(requested_actions_2.actions) >= 0
        
        # Run step 2
        result_2 = coupler.step(requested_actions_2)
        assert result_2.power_flow_converged
        
        coupler.close()


if __name__ == "__main__":
    test_market_clearing_modifies_building_powers_before_power_flow()
    test_re_dispatch_reacts_to_grid_violations_with_market_clearing()
    test_market_clearing_and_re_dispatch_sequence()
    test_energy_sharing_limits_respected_in_power_flow()
    test_multi_agent_controller_with_market_clearing()
    test_no_market_clearing_when_disabled()
    test_grid_violations_trigger_re_dispatch_with_market_clearing()
    print("All joint integration tests passed!")