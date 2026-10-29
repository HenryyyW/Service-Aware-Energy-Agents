"""Regression tests for device action routing and EV observation enrichment.

These tests use lightweight stubs so they run without building a CityLearn
environment. They guard two defects that silently invalidated earlier results:
every controller action was dropped before reaching CityLearn, and the stock
EV observation columns were populated from mismatched sources.
"""

from types import SimpleNamespace

import numpy as np

from src.schemas.action import Action, ActionType, RequestedActions
from src.simulation.citylearn_adapter import CityLearnAdapter


def make_action_adapter(building_actions, device_metadata):
    adapter = CityLearnAdapter.__new__(CityLearnAdapter)
    adapter.building_ids = ["b0"]
    adapter.building_actions = {"b0": building_actions}
    adapter.device_metadata = device_metadata
    return adapter


def test_actions_are_forwarded_by_asset_id_without_action_type():
    adapter = make_action_adapter(
        ["electrical_storage", "deferrable_appliance"], {}
    )
    requested = RequestedActions(
        timestep=0,
        actions=[
            Action(
                asset_id="b0_electrical_storage",
                action_type=ActionType.BATTERY_DISCHARGE,
                value_kw=-0.6,
                timestep=0,
            )
        ],
    )

    converted = CityLearnAdapter._actions_to_citylearn(adapter, requested)

    assert converted == [[-0.6, 0.0]]


def _action_adapter():
    return make_action_adapter(
        ["electrical_storage", "electric_vehicle_storage", "deferrable_appliance"],
        {
            "b0": {
                "battery": {"capacity_kwh": 10.0, "power_kw": 5.0, "efficiency": 0.9},
                "chargers": [{"charger_id": "c0", "max_charge_kw": 11.0,
                              "min_charge_kw": 1.4, "max_discharge_kw": 7.2,
                              "efficiency": 0.95}],
            }
        },
    )


def test_configured_asset_ids_and_kw_are_normalized_for_citylearn():
    adapter = _action_adapter()
    requested = RequestedActions(
        timestep=0,
        actions=[
            Action(asset_id="b0_battery", action_type=ActionType.BATTERY_CHARGE,
                   value_kw=2.5, timestep=0),
            Action(asset_id="b0_ev_0", action_type=ActionType.EV_CHARGE,
                   value_kw=5.5, timestep=0),
            Action(asset_id="b0_flex_0", action_type=ActionType.FLEXIBLE_LOAD,
                   value_kw=2.0, timestep=0),
        ],
    )

    converted = CityLearnAdapter._actions_to_citylearn(adapter, requested)

    assert converted == [[2.5 / 5.0, 5.5 / 11.0, 1.0]]


def test_grid_charge_and_discharge_are_clamped_and_signed():
    adapter = _action_adapter()
    requested = RequestedActions(
        timestep=0,
        actions=[
            Action(asset_id="b0_battery", action_type=ActionType.BATTERY_CHARGE,
                   value_kw=500.0, timestep=0),
            Action(asset_id="b0_ev_0", action_type=ActionType.EV_CHARGE,
                   value_kw=-7.2, timestep=0),
        ],
    )

    converted = CityLearnAdapter._actions_to_citylearn(adapter, requested)

    assert converted[0][0] == 1.0
    assert converted[0][1] == -1.0


def _battery(capacity=60.0, soc=0.25):
    soc_series = np.zeros(12)
    soc_series[0] = soc
    return SimpleNamespace(soc=soc_series, capacity=capacity)


def _charger(soc=0.25, hours_to_departure=12, required_soc=0.87):
    simulation = SimpleNamespace(
        electric_vehicle_departure_time=np.full(12, hours_to_departure),
        electric_vehicle_required_soc_departure=np.full(12, required_soc),
    )
    return SimpleNamespace(
        charger_id="c0",
        max_charging_power=11.0,
        min_charging_power=1.4,
        max_discharging_power=7.2,
        efficiency=0.95,
        charger_simulation=simulation,
        connected_electric_vehicle=SimpleNamespace(battery=_battery(soc=soc)),
    )


def test_ev_observations_use_the_right_sources():
    charger = _charger(soc=0.25, hours_to_departure=12, required_soc=0.87)
    building = SimpleNamespace(
        time_step=0,
        electric_vehicle_chargers=[charger],
        electrical_storage=SimpleNamespace(capacity=6.4, nominal_power=5.0, efficiency=0.9),
        deferrable_appliances=[],
        pv=SimpleNamespace(nominal_power=8.0),
    )
    adapter = SimpleNamespace(env=SimpleNamespace(buildings=[building]), building_ids=["b0"])

    observations = CityLearnAdapter._enrich_electric_vehicle_observations(adapter, {})

    assert observations["b0_ev_0_connected"] == 1.0
    assert observations["b0_ev_0_soc"] == 0.25
    assert observations["b0_ev_0_capacity_kwh"] == 60.0
    assert observations["b0_ev_0_energy_kwh"] == 15.0
    assert observations["b0_ev_0_hours_to_departure"] == 12.0
    assert observations["b0_ev_0_required_soc"] == 0.87
    assert observations["b0_ev_0_max_charge_kw"] == 11.0
    assert observations["b0_ev_0_min_charge_kw"] == 1.4


def test_device_metadata_reports_live_ratings():
    charger = _charger()
    building = SimpleNamespace(
        time_step=0,
        electric_vehicle_chargers=[charger],
        electrical_storage=SimpleNamespace(capacity=6.4, nominal_power=5.0, efficiency=0.9),
        deferrable_appliances=[SimpleNamespace(nominal_power=2.0)],
        pv=SimpleNamespace(nominal_power=8.0),
    )
    adapter = SimpleNamespace(
        env=SimpleNamespace(buildings=[building]),
        building_ids=["b0"],
        dataset_seconds_per_step=3600,
    )

    metadata = CityLearnAdapter.get_device_metadata(adapter)

    assert metadata["b0"]["battery"]["capacity_kwh"] == 6.4
    assert metadata["b0"]["battery"]["power_kw"] == 5.0
    assert metadata["b0"]["chargers"][0]["max_charge_kw"] == 11.0
    assert metadata["b0"]["deferrable"][0]["power_kw"] == 2.0
    assert metadata["b0"]["hours_per_step"] == 1.0
