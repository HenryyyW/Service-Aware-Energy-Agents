"""Tests for the MPC baseline controller (no simulator required)."""

import pytest

from src.controllers.mpc import MPCController
from src.schemas.action import ActionType
from src.schemas.scenario import ScenarioConfig


def make_scenario(buildings=("b0",)):
    return ScenarioConfig(
        scenario_id="test_mpc",
        name="MPC test",
        description="unit test",
        random_seed=42,
        timestep_minutes=60,
        community_import_limit_kw=200,
        community_export_limit_kw=150,
        buildings=[
            {
                "building_id": building_id,
                "building_type": "residential",
                "location": {"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                "simulation_start": "2023-07-01",
                "simulation_end": "2023-07-08",
            }
            for building_id in buildings
        ],
    )


def base_observations(price=0.30, load=10.0, pv=0.0, soc=1.0):
    return {
        "b0_hour": 18,
        "b0_electricity_pricing": price,
        "b0_non_shiftable_load": load,
        "b0_solar_generation": pv,
        "b0_electrical_storage_soc": soc,
        "b0_ev_0_connected": 0.0,
        "b0_deferrable_appliance_can_start": 0.0,
    }


def metadata(battery=True, chargers=None):
    return {
        "b0": {
            "battery": (
                {"capacity_kwh": 10.0, "power_kw": 5.0, "efficiency": 0.9}
                if battery else None
            ),
            "chargers": chargers or [],
            "deferrable": [],
            "pv_kw": 8.0,
            "hours_per_step": 1.0,
        }
    }


def test_battery_discharges_when_price_is_high_and_soc_is_full():
    controller = MPCController(make_scenario(), device_metadata=metadata(), horizon_steps=6)
    actions = controller.get_actions(base_observations(price=0.35, soc=1.0), timestep=0)

    battery = [a for a in actions.actions if a.asset_id == "b0_electrical_storage"]
    assert battery, "MPC should dispatch the battery at a high price"
    assert battery[0].action_type == ActionType.BATTERY_DISCHARGE
    assert battery[0].value_kw < 0.0
    assert abs(battery[0].value_kw) <= 5.0


def test_battery_charges_when_future_prices_are_higher():
    controller = MPCController(make_scenario(), device_metadata=metadata(), horizon_steps=6)
    # Learned diurnal profile: every hour is expensive and has evening load
    # except the current (cheap, PV-surplus) one.
    controller._price_by_hour = {hour: 0.40 for hour in range(24)}
    controller._load_by_hour = {hour: [10.0] for hour in range(24)}
    controller._pv_by_hour = {hour: [0.0] for hour in range(24)}
    actions = controller.get_actions(
        base_observations(price=0.05, load=0.0, pv=8.0, soc=0.0), timestep=0
    )

    battery = [a for a in actions.actions if a.asset_id == "b0_electrical_storage"]
    assert battery, "MPC should charge when later prices are much higher"
    assert battery[0].action_type == ActionType.BATTERY_CHARGE
    assert 0.0 < battery[0].value_kw <= 5.0


def test_ev_charges_to_meet_departure_requirement():
    chargers = [{"charger_id": "c0", "max_charge_kw": 11.0, "min_charge_kw": 1.4,
                 "max_discharge_kw": 7.2, "efficiency": 0.95}]
    observations = base_observations(price=0.10, load=5.0, pv=0.0, soc=0.2)
    observations.update({
        "b0_ev_0_connected": 1.0,
        "b0_ev_0_soc": 0.2,
        "b0_ev_0_capacity_kwh": 60.0,
        "b0_ev_0_required_soc": 1.0,
        "b0_ev_0_hours_to_departure": 2.0,
        "b0_ev_0_max_charge_kw": 11.0,
        "b0_ev_0_min_charge_kw": 1.4,
    })
    controller = MPCController(
        make_scenario(), device_metadata=metadata(chargers=chargers), horizon_steps=4
    )
    actions = controller.get_actions(observations, timestep=0)

    ev = [a for a in actions.actions if a.asset_id == "b0_electric_vehicle_storage"]
    assert ev, "MPC must charge an EV that is short of its departure target"
    assert ev[0].action_type == ActionType.EV_CHARGE
    assert 0.0 < ev[0].value_kw <= 11.0


def test_actions_respect_device_power_limits():
    controller = MPCController(make_scenario(), device_metadata=metadata(), horizon_steps=8)
    observations = base_observations(price=0.5, load=40.0, soc=1.0)
    actions = controller.get_actions(observations, timestep=3)

    for action in actions.actions:
        assert -5.0 <= action.value_kw <= 5.0
        assert action.timestep == 3


def test_falls_back_to_rule_based_without_device_metadata():
    controller = MPCController(make_scenario(), device_metadata=None, horizon_steps=4)
    actions = controller.get_actions(base_observations(), timestep=0)

    assert controller.fallback_steps == 1
    assert actions.timestep == 0


def test_reset_clears_forecast_state():
    controller = MPCController(make_scenario(), device_metadata=metadata(), horizon_steps=2)
    controller.get_actions(base_observations(), timestep=0)
    controller.reset()

    assert controller.fallback_steps == 0
    assert controller.timestep == 0
