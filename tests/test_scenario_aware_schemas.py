"""Scenario-aware schema customization tests (BENCHMARK_MATRIX.md caveat 1).

The scenario YAML's device parameters (battery, PV, EV schedules, flexible
loads) must reach the CityLearn schema; two scenarios that differ only in
device mix must produce different simulations.
"""
import json
import os
import shutil
import tempfile
from types import SimpleNamespace

import pytest

from src.schemas.scenario import (
    BatteryConfig,
    BuildingConfig,
    BuildingType,
    EVConfig,
    FlexibleLoadConfig,
    PVConfig,
    ScenarioConfig,
)
from src.simulation.citylearn_adapter import create_citylearn_adapter


@pytest.fixture()
def temp_data_dir():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _building(
    building_id,
    *,
    pv_kw=None,
    battery=None,
    evs=None,
    flexible_loads=None,
):
    return BuildingConfig(
        building_id=building_id,
        building_type=BuildingType.RESIDENTIAL,
        location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
        simulation_start="2023-01-01",
        simulation_end="2023-01-08",
        pv=PVConfig(capacity_kw=pv_kw) if pv_kw is not None else None,
        battery=battery,
        evs=evs or [],
        flexible_loads=flexible_loads or [],
    )


@pytest.fixture()
def mixed_scenario():
    """Two buildings with deliberately different device mixes."""
    return ScenarioConfig(
        scenario_id="schema_mix_test",
        name="Schema Mix",
        description="Device-mix differentiation test",
        random_seed=42,
        timestep_minutes=60,
        buildings=[
            _building(
                "mix_building_0",
                pv_kw=4.0,
                battery=BatteryConfig(capacity_kwh=10.0, power_kw=6.0),
                evs=[
                    EVConfig(
                        capacity_kwh=60.0,
                        max_charge_kw=11.0,
                        efficiency=0.90,
                        arrival_time="17:00",
                        departure_time="09:00",
                        target_soc=0.9,
                        initial_soc=0.2,
                    ),
                    EVConfig(
                        capacity_kwh=40.0,
                        max_charge_kw=7.0,
                        arrival_time="08:00",
                        departure_time="12:00",
                        target_soc=0.8,
                        initial_soc=0.3,
                    ),
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=5.0,
                        energy_kwh=10.0,
                        earliest_start="22:00",
                        latest_end="06:00",
                        duration_hours=2.0,
                    ),
                ],
            ),
            _building(
                "mix_building_1",
                pv_kw=0.0,  # explicitly no PV
                battery=BatteryConfig(capacity_kwh=20.0, power_kw=5.0),
                evs=[],
            ),
        ],
    )


def _read_schema(data_dir, scenario_id):
    with open(
        os.path.join(data_dir, "schemas", scenario_id, "schema.json"), encoding="utf-8"
    ) as handle:
        return json.load(handle)


def test_device_overrides_reach_the_schema(mixed_scenario, temp_data_dir):
    adapter = create_citylearn_adapter(mixed_scenario, data_dir=temp_data_dir)
    try:
        saved = _read_schema(temp_data_dir, mixed_scenario.scenario_id)
        first = saved["buildings"]["mix_building_0"]
        second = saved["buildings"]["mix_building_1"]

        # Battery capacity/power from YAML, not the dataset default (6.4/5.0)
        assert first["electrical_storage"]["attributes"]["capacity"] == 10.0
        assert first["electrical_storage"]["attributes"]["nominal_power"] == 6.0
        assert second["electrical_storage"]["attributes"]["capacity"] == 20.0

        # PV present with YAML size on one building, absent on the other
        assert first["pv"]["attributes"]["nominal_power"] == 4.0
        assert "pv" not in second

        # One charger per configured EV, none when the scenario has no EVs
        assert sorted(first.get("chargers", {})) == ["charger_0", "charger_1"]
        assert "chargers" not in second

        # Flexible load synthesized
        assert sorted(first.get("deferrable_appliances", {})) == ["deferrable_appliance_0"]
    finally:
        adapter.close()


def test_synthesized_charger_schedule_matches_yaml(mixed_scenario, temp_data_dir):
    adapter = create_citylearn_adapter(mixed_scenario, data_dir=temp_data_dir)
    try:
        import pandas as pd

        path = os.path.join(
            temp_data_dir,
            "schemas",
            mixed_scenario.scenario_id,
            "mix_building_0_charger_0.csv",
        )
        frame = pd.read_csv(path)
        # One row per episode step (7 days hourly + 1)
        assert len(frame) == 7 * 24 + 1
        # EV connected in the evening window has departure countdown and
        # required SOC from the YAML (target_soc 0.9 -> 90).
        connected = frame[frame["electric_vehicle_charger_state"] == 1]
        assert len(connected) > 0
        assert (connected["electric_vehicle_required_soc_departure"] == 90.0).all()
        # Away steps carry the arrival countdown and initial SOC (0.2 -> 20).
        away = frame[frame["electric_vehicle_charger_state"] == 0]
        assert (away["electric_vehicle_estimated_soc_arrival"] == 20.0).all()
    finally:
        adapter.close()


def test_overridden_environment_still_simulates(mixed_scenario, temp_data_dir):
    """CityLearn must accept the overridden schema (device attribute names, CSVs)."""
    adapter = create_citylearn_adapter(mixed_scenario, data_dir=temp_data_dir)
    try:
        from src.schemas.action import ActionType, Action, RequestedActions

        observations = adapter.reset(random_seed=42)
        assert observations is not None
        actions = RequestedActions(
            timestep=0,
            actions=[
                Action(
                    asset_id="mix_building_0_battery",
                    action_type=ActionType.BATTERY_CHARGE,
                    value_kw=1.0,
                    timestep=0,
                ),
                Action(
                    asset_id="mix_building_0_ev_0",
                    action_type=ActionType.EV_CHARGE,
                    value_kw=3.0,
                    timestep=0,
                ),
            ],
        )
        _obs, result = adapter.step(actions)
        assert result is not None
    finally:
        adapter.close()
