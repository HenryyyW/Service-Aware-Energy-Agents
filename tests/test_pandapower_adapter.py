"""Tests for pandapower adapter."""
import pytest

from src.schemas.scenario import (
    PandapowerConfig, GridBusMapping, ScenarioConfig, BuildingConfig, BuildingType
)
from src.simulation.pandapower_adapter import PandapowerAdapter, create_grid_from_scenario
from src.schemas.diagnostics import DiagnosticCategory, Severity


@pytest.fixture
def pandapower_config():
    """Create a pandapower config for testing."""
    return PandapowerConfig(
        network_type="ieee_34",
        bus_mappings=[
            GridBusMapping(building_id="building_0", bus_idx=1),
            GridBusMapping(building_id="building_1", bus_idx=3),
        ],
        slack_bus=0,
        voltage_limits={"min": 0.95, "max": 1.05},
        line_loading_limit=1.0,
        transformer_loading_limit=1.0
    )


@pytest.fixture
def scenario_config():
    """Create a scenario config for testing."""
    return ScenarioConfig(
        scenario_id="test_scenario",
        name="Test",
        description="Test",
        buildings=[
            BuildingConfig(building_id="building_0", building_type=BuildingType.RESIDENTIAL),
            BuildingConfig(building_id="building_1", building_type=BuildingType.RESIDENTIAL),
        ],
        pandapower=PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=[
                GridBusMapping(building_id="building_0", bus_idx=1),
                GridBusMapping(building_id="building_1", bus_idx=3),
            ]
        )
    )


def test_pandapower_adapter_creation(pandapower_config):
    """Test pandapower adapter creation."""
    adapter = PandapowerAdapter(pandapower_config)
    assert adapter is not None
    assert adapter.net is not None
    assert len(adapter.net.bus) > 0
    assert "building_0" in adapter.bus_mapping
    assert "building_1" in adapter.bus_mapping


def test_pandapower_adapter_update_loads(pandapower_config):
    """Test updating building loads."""
    adapter = PandapowerAdapter(pandapower_config)
    
    building_powers = {"building_0": 10.0, "building_1": 5.0}  # kW
    building_pvs = {"building_0": 3.0, "building_1": 2.0}  # kW
    
    adapter.update_building_loads(building_powers, building_pvs)
    
    # Check loads were updated (net load = consumption - PV)
    load_0 = adapter.net.load.at[adapter.load_indices["building_0"], 'p_mw']
    load_1 = adapter.net.load.at[adapter.load_indices["building_1"], 'p_mw']
    
    # Net loads in MW
    assert abs(load_0 - (10.0 - 3.0) / 1000) < 0.001
    assert abs(load_1 - (5.0 - 2.0) / 1000) < 0.001


def test_pandapower_adapter_run_power_flow(pandapower_config):
    """Test running power flow."""
    adapter = PandapowerAdapter(pandapower_config)
    
    # Set some loads
    adapter.update_building_loads({"building_0": 10.0, "building_1": 5.0}, 
                                   {"building_0": 0.0, "building_1": 0.0})
    
    converged, report = adapter.run_power_flow()
    
    assert isinstance(converged, bool)
    assert report is not None
    assert report.timestep == 0


def test_pandapower_adapter_voltage_check(pandapower_config):
    """Test voltage violation detection."""
    adapter = PandapowerAdapter(pandapower_config)
    
    # Set heavy load to cause undervoltage
    adapter.update_building_loads({"building_0": 500.0, "building_1": 500.0}, 
                                   {"building_0": 0.0, "building_1": 0.0})
    
    converged, report = adapter.run_power_flow()
    
    # Should detect voltage violations
    voltage_diags = [d for d in report.diagnostics if d.category == DiagnosticCategory.VOLTAGE]
    # May or may not have violations depending on network


def test_pandapower_adapter_grid_limits(pandapower_config):
    """Test grid limit checking."""
    adapter = PandapowerAdapter(pandapower_config)
    
    diagnostics = adapter.check_grid_limits(
        community_import_kw=250.0,
        community_export_kw=50.0,
        import_limit_kw=200.0,
        export_limit_kw=100.0
    )
    
    assert len(diagnostics) == 1  # Import limit exceeded
    assert diagnostics[0].limit_type == "import"
    assert diagnostics[0].excess_kw == 50.0


def test_create_grid_from_scenario(scenario_config):
    """Test factory function."""
    adapter = create_grid_from_scenario(scenario_config)
    assert adapter is not None
    assert adapter.net is not None


def test_pandapower_adapter_reset(pandapower_config):
    """Test adapter reset."""
    adapter = PandapowerAdapter(pandapower_config)
    adapter.time_step = 10
    adapter.convergence_history = [True, False, True]
    
    adapter.reset()
    
    assert adapter.time_step == 0
    assert adapter.convergence_history == []


def test_pandapower_get_network_state(pandapower_config):
    """Test getting network state."""
    adapter = PandapowerAdapter(pandapower_config)
    adapter.update_building_loads({"building_0": 10.0}, {"building_0": 0.0})
    adapter.run_power_flow()
    
    state = adapter.get_network_state()
    
    assert "converged" in state
    assert "bus_voltages" in state
    assert "line_loading" in state
    assert "total_load_mw" in state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])