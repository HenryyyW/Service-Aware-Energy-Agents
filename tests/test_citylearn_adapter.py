"""Tests for CityLearn adapter."""
import pytest
import os
import tempfile
import shutil

from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BuildingType, PVConfig, BatteryConfig,
    EVConfig, FlexibleLoadConfig, TariffConfig, PandapowerConfig, GridBusMapping
)
from src.simulation.citylearn_adapter import CityLearnAdapter, create_citylearn_adapter


@pytest.fixture
def minimal_scenario():
    """Create a minimal scenario for testing that matches the basic dataset."""
    return ScenarioConfig(
        scenario_id="test_scenario",
        name="Test Scenario",
        description="Minimal test scenario",
        random_seed=42,
        timestep_minutes=60,  # Hourly to match dataset
        buildings=[
            BuildingConfig(
                building_id="building_0",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",  # 1 week
            ),
            BuildingConfig(
                building_id="building_1",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",
            ),
            BuildingConfig(
                building_id="building_2",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",
            ),
        ],
        pandapower=PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=[
                GridBusMapping(building_id="building_0", bus_idx=1),
                GridBusMapping(building_id="building_1", bus_idx=2),
                GridBusMapping(building_id="building_2", bus_idx=3),
            ]
        )
    )


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


def test_citylearn_adapter_creation(minimal_scenario, temp_data_dir):
    """Test CityLearn adapter can be created."""
    adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
    assert adapter is not None
    assert adapter.scenario_config == minimal_scenario
    assert "building_0" in adapter.building_ids
    adapter.close()


def test_citylearn_adapter_reset(minimal_scenario, temp_data_dir):
    """Test CityLearn adapter reset."""
    adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
    observations = adapter.reset(random_seed=42)
    assert observations is not None
    assert isinstance(observations, dict)
    # Check for at least one flattened observation key (e.g., building_0_month)
    assert any(key.startswith("building_0_") for key in observations.keys())
    adapter.close()


def test_citylearn_adapter_step(minimal_scenario, temp_data_dir):
    """Test CityLearn adapter step with electrical_storage action."""
    adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
    adapter.reset(random_seed=42)
    
    # Create requested actions for electrical_storage (all buildings have this)
    from src.schemas.action import RequestedActions, Action, ActionType
    requested = RequestedActions(
        timestep=0,
        actions=[
            Action(asset_id="building_0_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
            Action(asset_id="building_1_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0),
            Action(asset_id="building_2_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=0.5, timestep=0),
        ]
    )
    
    observations, step_result = adapter.step(requested)
    assert observations is not None
    assert step_result is not None
    assert step_result.timestep == 0
    assert isinstance(step_result.rewards, dict)
    assert "building_0" in step_result.rewards
    adapter.close()


def test_citylearn_dummy_data_generation(minimal_scenario, temp_data_dir):
    """Test that dataset files are copied to schema directory."""
    adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
    
    # Check that schema directory was created with copied files
    schema_dir = os.path.join(temp_data_dir, "schemas", "test_scenario")
    assert os.path.exists(schema_dir)
    assert os.path.exists(os.path.join(schema_dir, "schema.json"))
    assert os.path.exists(os.path.join(schema_dir, "weather.csv"))
    # Building energy files should be copied
    for bid in adapter.building_ids:
        energy_file = f"{bid}.csv"
        assert os.path.exists(os.path.join(schema_dir, energy_file)), f"Missing {energy_file}"
    
    adapter.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])