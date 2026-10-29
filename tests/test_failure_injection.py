"""Tests for failure injection in Scenario E."""
import pytest
from datetime import datetime

from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BuildingType, EnergySharingConfig,
    TariffConfig, PVConfig, BatteryConfig, PandapowerConfig, GridBusMapping,
    FailureConfig
)
from src.simulation.failure_injector import FailureInjector, create_failure_injector, FailureType
from src.simulation.coupling import SimulationCoupler


@pytest.fixture
def scenario_config_with_failures():
    """Create a scenario config with failure injections like scenario_e.yaml."""
    return ScenarioConfig(
        scenario_id="test_scenario_e",
        name="Test Failure Scenario",
        description="Scenario for failure injection tests",
        random_seed=42,
        timestep_minutes=15,
        community_import_limit_kw=200,
        community_export_limit_kw=150,
        buildings=[
            BuildingConfig(
                building_id="building_0",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-08",
                pv=PVConfig(capacity_kw=8.0),
                battery=BatteryConfig(capacity_kwh=13.5, power_kw=5.0),
            ),
            BuildingConfig(
                building_id="building_1",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-08",
                pv=PVConfig(capacity_kw=6.0),
                battery=BatteryConfig(capacity_kwh=10.0, power_kw=4.0),
            ),
            BuildingConfig(
                building_id="building_2",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-08",
                pv=PVConfig(capacity_kw=10.0),
                battery=BatteryConfig(capacity_kwh=15.0, power_kw=7.0),
            ),
            BuildingConfig(
                building_id="building_3",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-08",
                pv=PVConfig(capacity_kw=5.0),
                battery=BatteryConfig(capacity_kwh=8.0, power_kw=3.0),
            ),
        ],
        pandapower=PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=[
                GridBusMapping(building_id="building_0", bus_idx=1),
                GridBusMapping(building_id="building_1", bus_idx=3),
                GridBusMapping(building_id="building_2", bus_idx=5),
                GridBusMapping(building_id="building_3", bus_idx=7),
            ]
        ),
        failures=[
            # PV inverter failure on building_2 during peak production hours (Day 2, 10:00-14:00)
            FailureConfig(
                failure_id="pv_failure_building_2",
                asset_id="building_2_pv",
                failure_type="pv_inverter",
                start_time="2023-07-02T10:00:00",
                end_time="2023-07-02T14:00:00",
                severity=1.0,
            ),
            # Battery unavailability in building_0 during evening peak (Day 3, 17:00-21:00)
            FailureConfig(
                failure_id="battery_failure_building_0",
                asset_id="building_0_battery",
                failure_type="battery",
                start_time="2023-07-03T17:00:00",
                end_time="2023-07-03T21:00:00",
                severity=1.0,
            ),
            # EV-charger failure in building_1 during morning charging (Day 4, 06:00-09:00)
            FailureConfig(
                failure_id="ev_charger_failure_building_1",
                asset_id="building_1_ev_0",
                failure_type="ev_charger",
                start_time="2023-07-04T06:00:00",
                end_time="2023-07-04T09:00:00",
                severity=0.8,
            ),
            # Sensor/observation failure in building_3 (Day 5, entire day)
            FailureConfig(
                failure_id="sensor_failure_building_3",
                asset_id="building_3_net_electricity_consumption",
                failure_type="sensor",
                start_time="2023-07-05T00:00:00",
                end_time="2023-07-05T23:59:59",
                severity=1.0,
            ),
            # Temporary grid-service limit reduction (Day 6, afternoon peak)
            FailureConfig(
                failure_id="grid_limit_reduction",
                asset_id="community_grid",
                failure_type="grid_limit",
                start_time="2023-07-06T12:00:00",
                end_time="2023-07-06T18:00:00",
                severity=0.5,
            ),
        ],
    )


class TestFailureInjector:
    """Tests for the FailureInjector class."""
    
    def test_failure_injector_creation(self, scenario_config_with_failures):
        """Test failure injector creates correctly from scenario config."""
        injector = create_failure_injector(scenario_config_with_failures)
        
        assert injector is not None
        assert len(injector.parsed_failures) == 5
        assert injector.timestep_minutes == 15
    
    def test_failure_time_parsing(self, scenario_config_with_failures):
        """Test failure times are parsed to correct timesteps."""
        injector = create_failure_injector(scenario_config_with_failures)
        injector.set_simulation_start(datetime(2023, 7, 1, 0, 0))
        
        # Check PV failure: Day 2 (2023-07-02), 10:00-14:00
        # Day 2 starts at timestep 96 (24*60/15), 10:00 = 40 timesteps into day = 96 + 40 = 136
        # 14:00 = 56 timesteps into day = 96 + 56 = 152
        pv_failure = next(f for f in injector.parsed_failures if f['config'].failure_id == 'pv_failure_building_2')
        assert pv_failure['start_timestep'] == 136  # Day 2, 10:00
        assert pv_failure['end_timestep'] == 152    # Day 2, 14:00
        
        # Check battery failure: Day 3 (2023-07-03), 17:00-21:00
        battery_failure = next(f for f in injector.parsed_failures if f['config'].failure_id == 'battery_failure_building_0')
        assert battery_failure['start_timestep'] == 260  # Day 3, 17:00 (192 + 68)
        assert battery_failure['end_timestep'] == 276    # Day 3, 21:00 (192 + 84)
        
        # Check grid limit failure: Day 6 (2023-07-06), 12:00-18:00
        grid_failure = next(f for f in injector.parsed_failures if f['config'].failure_id == 'grid_limit_reduction')
        assert grid_failure['start_timestep'] == 528  # Day 6, 12:00 (480 + 48)
        assert grid_failure['end_timestep'] == 552    # Day 6, 18:00 (480 + 72)
    
    def test_failure_activation_deactivation(self, scenario_config_with_failures):
        """Test failures activate and deactivate at correct timesteps."""
        injector = create_failure_injector(scenario_config_with_failures)
        injector.set_simulation_start(datetime(2023, 7, 1, 0, 0))
        injector.reset()
        
        # Before PV failure (Day 2, 10:00 = timestep 136)
        result = injector.step(135)
        assert len(result['activated']) == 0
        assert len(result['deactivated']) == 0
        assert len(injector.get_active_failures()) == 0
        
        # At PV failure start (timestep 136)
        result = injector.step(136)
        assert len(result['activated']) == 1
        assert result['activated'][0].failure_id == 'pv_failure_building_2'
        assert len(injector.get_active_failures()) == 1
        
        # During PV failure (timestep 140)
        result = injector.step(140)
        assert len(result['activated']) == 0
        assert len(injector.get_active_failures()) == 1
        
        # At PV failure end (timestep 152)
        result = injector.step(152)
        assert len(result['activated']) == 0
        assert len(result['deactivated']) == 1
        assert result['deactivated'][0].failure_id == 'pv_failure_building_2'
        assert len(injector.get_active_failures()) == 0
    
    def test_pv_failure_application(self, scenario_config_with_failures):
        """Test PV failure reduces PV generation."""
        injector = create_failure_injector(scenario_config_with_failures)
        injector.set_simulation_start(datetime(2023, 7, 1, 0, 0))
        injector.reset()
        
        building_pvs = {"building_0": 5.0, "building_1": 3.0, "building_2": 8.0, "building_3": 2.0}
        
        # Before failure
        injector.step(135)
        result = injector.apply_pv_failure(building_pvs, "building_2")
        assert result == 8.0  # No failure yet
        
        # During failure (100% severity = 0 output)
        injector.step(136)
        result = injector.apply_pv_failure(building_pvs, "building_2")
        assert result == 0.0  # Complete failure
        
        # Other buildings unaffected
        result = injector.apply_pv_failure(building_pvs, "building_0")
        assert result == 5.0
        
        # After failure ends
        injector.step(152)
        result = injector.apply_pv_failure(building_pvs, "building_2")
        assert result == 8.0
    
    def test_battery_failure_application(self, scenario_config_with_failures):
        """Test battery failure makes battery unavailable."""
        injector = create_failure_injector(scenario_config_with_failures)
        injector.set_simulation_start(datetime(2023, 7, 1, 0, 0))
        injector.reset()
        
        building_battery = {"building_0": 2.0, "building_1": -1.0}
        
        # Before failure
        injector.step(259)
        result = injector.apply_battery_failure(building_battery, "building_0")
        assert result == 2.0
        
        # During failure
        injector.step(260)
        result = injector.apply_battery_failure(building_battery, "building_0")
        assert result == 0.0  # Battery unavailable
        
        # After failure
        injector.step(276)
        result = injector.apply_battery_failure(building_battery, "building_0")
        assert result == 2.0
    
    def test_grid_limit_failure_application(self, scenario_config_with_failures):
        """Test grid limit failure reduces import/export limits."""
        injector = create_failure_injector(scenario_config_with_failures)
        injector.set_simulation_start(datetime(2023, 7, 1, 0, 0))
        injector.reset()
        
        import_limit = 200.0
        export_limit = 150.0
        
        # Before failure
        injector.step(527)
        imp, exp = injector.apply_grid_limit_failure(import_limit, export_limit)
        assert imp == 200.0
        assert exp == 150.0
        
        # During failure (50% severity)
        injector.step(528)
        imp, exp = injector.apply_grid_limit_failure(import_limit, export_limit)
        assert imp == 100.0  # 50% reduction
        assert exp == 75.0   # 50% reduction
        
        # After failure
        injector.step(552)
        imp, exp = injector.apply_grid_limit_failure(import_limit, export_limit)
        assert imp == 200.0
        assert exp == 150.0
    
    def test_failure_history_tracking(self, scenario_config_with_failures):
        """Test failure history is tracked correctly."""
        injector = create_failure_injector(scenario_config_with_failures)
        injector.set_simulation_start(datetime(2023, 7, 1, 0, 0))
        injector.reset()
        
        # Activate PV failure
        injector.step(136)
        # Deactivate PV failure
        injector.step(152)
        
        summary = injector.get_failure_summary()
        assert summary['total_failures_configured'] == 5
        assert summary['failures_activated'] == 1
        assert summary['failures_deactivated'] == 1
        assert summary['currently_active'] == 0
        
        # Activate another failure
        injector.step(260)  # battery failure
        summary = injector.get_failure_summary()
        assert summary['failures_activated'] == 2
        assert summary['currently_active'] == 1


class TestFailureInjectionIntegration:
    """Integration tests with SimulationCoupler."""
    
    def test_coupler_initializes_failure_injector(self, scenario_config_with_failures, tmp_path):
        """Test coupler initializes failure injector when failures configured."""
        coupler = SimulationCoupler(scenario_config_with_failures, data_dir=str(tmp_path))
        
        assert coupler.failure_injector is not None
        assert len(coupler.failure_injector.parsed_failures) == 5
    
    def test_coupler_step_activates_failures(self, scenario_config_with_failures, tmp_path):
        """Test coupler step activates failures at correct timestep."""
        # Note: CityLearn adapter overrides timestep_minutes to dataset resolution (60 min)
        # So timesteps are different: Day 2, 10:00 = 34 (not 136)
        coupler = SimulationCoupler(scenario_config_with_failures, data_dir=str(tmp_path))
        coupler.reset()
        
        # Step to just before PV failure (with 60-min timesteps: Day 2, 10:00 = timestep 34)
        for _ in range(34):
            from src.schemas.action import RequestedActions
            requested = RequestedActions(timestep=_, actions=[])
            coupler.step(requested)
        
        # Next step should activate PV failure (timestep 34)
        requested = RequestedActions(timestep=34, actions=[])
        result = coupler.step(requested)
        
        # Check failure was activated
        active = coupler.failure_injector.get_active_failures()
        assert len(active) == 1
        assert active[0].failure_id == 'pv_failure_building_2'
    
    def test_pv_failure_affects_power_flow(self, scenario_config_with_failures, tmp_path):
        """Test PV failure actually reduces PV generation in power flow."""
        # Note: CityLearn adapter overrides timestep_minutes to dataset resolution (60 min)
        # PV failure at Day 2, 10:00 = timestep 34
        coupler = SimulationCoupler(scenario_config_with_failures, data_dir=str(tmp_path))
        coupler.reset()
        
        # Advance to PV failure timestep (34 with 60-min timesteps)
        for t in range(35):
            from src.schemas.action import RequestedActions
            requested = RequestedActions(timestep=t, actions=[])
            result = coupler.step(requested)
        
        # Check that PV failure is active
        active = coupler.failure_injector.get_active_failures()
        assert any(f.failure_id == 'pv_failure_building_2' for f in active)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])