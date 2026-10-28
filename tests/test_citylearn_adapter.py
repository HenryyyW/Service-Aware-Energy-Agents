"""Tests for CityLearn adapter - comprehensive regression tests for step convention."""
import pytest
import os
import tempfile
import shutil
import json
import pandas as pd
import numpy as np

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
                building_id="test_building_0",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",  # 1 week
            ),
            BuildingConfig(
                building_id="test_building_1",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",
            ),
            BuildingConfig(
                building_id="test_building_2",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",
            ),
        ],
        pandapower=PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=[
                GridBusMapping(building_id="test_building_0", bus_idx=1),
                GridBusMapping(building_id="test_building_1", bus_idx=2),
                GridBusMapping(building_id="test_building_2", bus_idx=3),
            ]
        )
    )


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


# ============================================================================
# Basic functionality tests (original tests)
# ============================================================================

def test_citylearn_adapter_creation(minimal_scenario, temp_data_dir):
    """Test CityLearn adapter can be created."""
    adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
    assert adapter is not None
    assert adapter.scenario_config == minimal_scenario
    assert "test_building_0" in adapter.building_ids
    adapter.close()


def test_citylearn_adapter_reset(minimal_scenario, temp_data_dir):
    """Test CityLearn adapter reset."""
    adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
    observations = adapter.reset(random_seed=42)
    assert observations is not None
    assert isinstance(observations, dict)
    # Check for at least one flattened observation key (e.g., building_0_month)
    assert any(key.startswith("test_building_0_") for key in observations.keys())
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
            Action(asset_id="test_building_0_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=2.0, timestep=0),
            Action(asset_id="test_building_1_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0),
            Action(asset_id="test_building_2_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=0.5, timestep=0),
        ]
    )
    
    observations, step_result = adapter.step(requested)
    assert observations is not None
    assert step_result is not None
    assert step_result.timestep == 0
    assert isinstance(step_result.rewards, dict)
    assert "test_building_0" in step_result.rewards
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


# ============================================================================
# REGRESSION TESTS: Step Convention Protection
# ============================================================================

class TestStepConventionRegression:
    """Regression tests to protect the time step convention.
    
    These tests ensure:
    1. All schema time step values are integers (not floats)
    2. CSV data length matches episode_time_steps exactly
    3. Both int (3600) and float (3600.0) seconds_per_time_step work correctly
    4. No non-integer slice indexing errors occur
    """

    @pytest.mark.parametrize("seconds_per_timestep", [3600, 3600.0, 1800, 1800.0, 900, 900.0])
    def test_schema_time_steps_are_integers(self, seconds_per_timestep, minimal_scenario, temp_data_dir):
        """Test that all schema time step fields are integers regardless of input type.
        
        This is a REGRESSION TEST for the TypeError: slice indices must be integers
        that occurred when seconds_per_time_step was a float (e.g., 3600.0).
        """
        # Create a mock dataset schema with the given seconds_per_timestep
        # We'll monkey-patch the dataset loading to inject our test value
        from citylearn.data import DataSet
        original_get_schema = DataSet.get_schema
        
        def mock_get_schema(self, name):
            schema = original_get_schema(self, name)
            schema['seconds_per_time_step'] = seconds_per_timestep
            return schema
        
        DataSet.get_schema = mock_get_schema
        try:
            adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
            
            # Load the generated schema and verify all time step fields are integers
            schema_dir = os.path.join(temp_data_dir, "schemas", "test_scenario")
            schema_path = os.path.join(schema_dir, "schema.json")
            
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            # These fields MUST be integers (not floats)
            time_step_fields = [
                'simulation_start_time_step',
                'simulation_end_time_step',
                'episode_time_steps',
                'seconds_per_time_step',
            ]
            
            for field in time_step_fields:
                assert field in schema, f"Missing field: {field}"
                value = schema[field]
                assert isinstance(value, int), f"Field {field} = {value} is {type(value).__name__}, expected int"
                assert value == int(value), f"Field {field} = {value} is not a whole number"
            
            # Verify the +1 safety margin convention
            assert schema['simulation_end_time_step'] == schema['episode_time_steps'] - 1
            assert schema['simulation_start_time_step'] == 0
            
            adapter.close()
        finally:
            DataSet.get_schema = original_get_schema

    @pytest.mark.parametrize("seconds_per_timestep", [3600, 3600.0, 1800, 1800.0])
    def test_csv_length_matches_episode_time_steps(self, seconds_per_timestep, minimal_scenario, temp_data_dir):
        """Test that dummy energy CSV files have exactly episode_time_steps rows.
        
        This is a REGRESSION TEST for the ValueError: operands could not be broadcast
        together with shapes (168,) (169,) that occurred when CSV had 168 rows
        but CityLearn expected 169 (episode_time_steps).
        """
        from citylearn.data import DataSet
        original_get_schema = DataSet.get_schema
        
        def mock_get_schema(self, name):
            schema = original_get_schema(self, name)
            schema['seconds_per_time_step'] = seconds_per_timestep
            return schema
        
        DataSet.get_schema = mock_get_schema
        try:
            adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
            
            # Load the generated schema
            schema_dir = os.path.join(temp_data_dir, "schemas", "test_scenario")
            schema_path = os.path.join(schema_dir, "schema.json")
            
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            expected_rows = schema['episode_time_steps']
            
            # Check each building's energy CSV
            for bid in adapter.building_ids:
                energy_file = os.path.join(schema_dir, f"{bid}.csv")
                assert os.path.exists(energy_file), f"Missing energy file for {bid}"
                
                df = pd.read_csv(energy_file)
                actual_rows = len(df)
                
                assert actual_rows == expected_rows, (
                    f"CSV row count mismatch for {bid}: "
                    f"got {actual_rows}, expected {expected_rows} (episode_time_steps)"
                )
            
            adapter.close()
        finally:
            DataSet.get_schema = original_get_schema

    @pytest.mark.parametrize("seconds_per_timestep", [3600, 3600.0, 1800, 1800.0])
    def test_no_float_slice_indexing_error(self, seconds_per_timestep, minimal_scenario, temp_data_dir):
        """Test that no TypeError occurs from float slice indices.
        
        This directly tests the original failure: TypeError: slice indices must be integers
        """
        from citylearn.data import DataSet
        original_get_schema = DataSet.get_schema
        
        def mock_get_schema(self, name):
            schema = original_get_schema(self, name)
            schema['seconds_per_time_step'] = seconds_per_timestep
            return schema
        
        DataSet.get_schema = mock_get_schema
        try:
            # This should not raise TypeError about slice indices
            adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
            observations = adapter.reset(random_seed=42)
            assert observations is not None
            
            # Do a few steps to ensure no slicing errors during simulation
            from src.schemas.action import RequestedActions, Action, ActionType
            for step in range(3):
                requested = RequestedActions(
                    timestep=step,
                    actions=[
                        Action(asset_id="test_building_0_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=step),
                        Action(asset_id="test_building_1_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=step),
                        Action(asset_id="test_building_2_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=step),
                    ]
                )
                observations, step_result = adapter.step(requested)
                assert step_result is not None
                assert step_result.timestep == step
            
            adapter.close()
        finally:
            DataSet.get_schema = original_get_schema

    def test_episode_time_steps_calculation_consistency(self, minimal_scenario, temp_data_dir):
        """Test that episode_time_steps is calculated consistently across schema and CSV.
        
        Verifies: episode_time_steps = 7 * timesteps_per_day + 1
        Where timesteps_per_day = 24 * 60 / (seconds_per_time_step / 60)
        """
        from citylearn.data import DataSet
        original_get_schema = DataSet.get_schema
        
        # Test with hourly data (3600 seconds)
        def mock_get_schema(self, name):
            schema = original_get_schema(self, name)
            schema['seconds_per_time_step'] = 3600  # 1 hour
            return schema
        
        DataSet.get_schema = mock_get_schema
        try:
            adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
            
            schema_dir = os.path.join(temp_data_dir, "schemas", "test_scenario")
            schema_path = os.path.join(schema_dir, "schema.json")
            
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            # For hourly data: 24 steps/day * 7 days + 1 = 169
            dataset_timestep_minutes = schema['seconds_per_time_step'] // 60
            timesteps_per_day = 24 * 60 // dataset_timestep_minutes
            expected_episode_steps = 7 * timesteps_per_day + 1
            
            assert schema['episode_time_steps'] == expected_episode_steps
            assert schema['simulation_end_time_step'] == expected_episode_steps - 1
            
            # Verify CSV matches
            for bid in adapter.building_ids:
                df = pd.read_csv(os.path.join(schema_dir, f"{bid}.csv"))
                assert len(df) == expected_episode_steps
            
            adapter.close()
        finally:
            DataSet.get_schema = original_get_schema

    def test_dataset_seconds_per_step_stored_as_int(self, minimal_scenario, temp_data_dir):
        """Test that adapter stores dataset_seconds_per_step as integer."""
        from citylearn.data import DataSet
        original_get_schema = DataSet.get_schema
        
        def mock_get_schema(self, name):
            schema = original_get_schema(self, name)
            schema['seconds_per_time_step'] = 3600.0  # float input
            return schema
        
        DataSet.get_schema = mock_get_schema
        try:
            adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
            
            # The adapter should store it as int
            assert isinstance(adapter.dataset_seconds_per_step, int)
            assert adapter.dataset_seconds_per_step == 3600
            
            adapter.close()
        finally:
            DataSet.get_schema = original_get_schema


class TestMultiStepSimulation:
    """Test multi-step simulation to catch off-by-one errors."""

    def test_full_episode_simulation(self, minimal_scenario, temp_data_dir):
        """Run a full episode simulation to verify no off-by-one errors."""
        adapter = create_citylearn_adapter(minimal_scenario, data_dir=temp_data_dir)
        adapter.reset(random_seed=42)
        
        from src.schemas.action import RequestedActions, Action, ActionType
        
        # Run until termination
        max_steps = 200  # Safety limit
        for step in range(max_steps):
            requested = RequestedActions(
                timestep=step,
                actions=[
                    Action(asset_id="test_building_0_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=step),
                    Action(asset_id="test_building_1_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=step),
                    Action(asset_id="test_building_2_electrical_storage", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=step),
                ]
            )
            observations, step_result = adapter.step(requested)
            
            if step_result.terminated:
                # Episode ended correctly
                assert step_result.timestep == step
                break
        else:
            pytest.fail(f"Episode did not terminate within {max_steps} steps")
        
        adapter.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_dummy_energy_file_is_reproducible_for_a_seed(tmp_path):
    """Synthetic building data must not change between runs of the same seed."""
    from types import SimpleNamespace

    def write(seed, path):
        adapter = CityLearnAdapter.__new__(CityLearnAdapter)
        adapter.data_dir = str(tmp_path)
        adapter.dataset_seconds_per_step = 3600
        adapter.scenario_config = SimpleNamespace(timestep_minutes=60, random_seed=seed)
        adapter._create_dummy_energy_file(path)
        return path.read_bytes()

    first = write(42, tmp_path / "a.csv")
    second = write(42, tmp_path / "b.csv")
    other = write(123, tmp_path / "c.csv")

    assert first == second
    assert first != other
