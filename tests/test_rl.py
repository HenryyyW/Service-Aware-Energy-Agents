"""Tests for the tabular Q-learning baseline controller."""

import json

import pytest

import json
from pathlib import Path

from src.controllers.rl import (
    BATTERY_LEVELS,
    EV_LEVELS,
    N_ACTIONS,
    N_LMP_BUCKETS,
    QLearningController,
    decode_action,
    encode_state,
    encode_state_lmp,
)
from src.schemas.action import ActionType
from src.schemas.scenario import ScenarioConfig

LMP_POLICY_DIR = Path("experiments/reference/rl_policy")


def make_scenario():
    return ScenarioConfig(
        scenario_id="test_rl",
        name="RL test",
        description="unit test",
        random_seed=42,
        timestep_minutes=60,
        buildings=[
            {
                "building_id": "b0",
                "building_type": "residential",
                "location": {"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                "simulation_start": "2023-07-01",
                "simulation_end": "2023-07-08",
            }
        ],
    )


def metadata():
    return {
        "b0": {
            "battery": {"capacity_kwh": 10.0, "power_kw": 5.0, "efficiency": 0.9},
            "chargers": [{"charger_id": "c0", "max_charge_kw": 11.0,
                          "min_charge_kw": 1.4, "max_discharge_kw": 7.2,
                          "efficiency": 0.95}],
            "deferrable": [],
            "pv_kw": 8.0,
            "hours_per_step": 1.0,
        }
    }


def observations(price=0.30, load=10.0, pv=0.0, soc=0.5):
    return {
        "b0_hour": 18,
        "b0_electricity_pricing": price,
        "b0_non_shiftable_load": load,
        "b0_solar_generation": pv,
        "b0_electrical_storage_soc": soc,
        "b0_ev_0_connected": 0.0,
        "b0_deferrable_appliance_can_start": 0.0,
    }


def write_policy(path, q_table):
    path.write_text(json.dumps({"q_table": q_table, "metadata": {"algorithm": "test"}}))
    return str(path)


def test_action_space_is_complete_and_bijective():
    decoded = [decode_action(index) for index in range(N_ACTIONS)]
    assert len(set(decoded)) == N_ACTIONS == len(BATTERY_LEVELS) * len(EV_LEVELS)
    assert decoded[0] == (BATTERY_LEVELS[0], EV_LEVELS[0])


def test_encode_state_is_stable_and_includes_all_bands():
    state = encode_state(observations(), ["b0"])
    assert state.count("|") == 4
    assert encode_state(observations(), ["b0"]) == state


def test_encode_state_distinguishes_price_and_soc():
    cheap = encode_state(observations(price=0.05, soc=0.1), ["b0"])
    expensive = encode_state(observations(price=0.35, soc=0.9), ["b0"])
    assert cheap != expensive


def test_policy_drives_battery_and_ev_actions(tmp_path):
    observations_with_ev = observations()
    observations_with_ev.update({
        "b0_ev_0_connected": 1.0,
        "b0_ev_0_soc": 0.2,
        "b0_ev_0_required_soc": 0.87,
        "b0_ev_0_hours_to_departure": 12.0,
    })
    state = encode_state(observations_with_ev, ["b0"])
    q_values = [0.0] * N_ACTIONS
    q_values[N_ACTIONS - 1] = 1.0  # battery +1, EV +1
    policy = write_policy(tmp_path / "policy.json", {state: q_values})

    controller = QLearningController(make_scenario(), policy, device_metadata=metadata())
    actions = controller.get_actions(observations_with_ev, timestep=1)

    battery = [a for a in actions.actions if a.asset_id == "b0_electrical_storage"]
    ev = [a for a in actions.actions if a.asset_id == "b0_electric_vehicle_storage"]
    assert battery and battery[0].action_type == ActionType.BATTERY_CHARGE
    assert battery[0].value_kw == pytest.approx(5.0)
    assert ev and ev[0].value_kw == pytest.approx(11.0)
    assert ev[0].action_type == ActionType.EV_CHARGE
    assert controller.unseen_states == 0


def test_unseen_state_falls_back_to_rule_based(tmp_path):
    policy = write_policy(tmp_path / "policy.json", {})
    controller = QLearningController(make_scenario(), policy, device_metadata=metadata())
    actions = controller.get_actions(observations(), timestep=0)

    assert controller.unseen_states == 1
    assert actions.timestep == 0


def test_missing_policy_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        QLearningController(make_scenario(), str(tmp_path / "missing.json"))


def test_lmp_encoder_has_twelve_buckets_and_six_fields():
    """The LMP encoder appends a 12-bucket price field as a sixth component."""
    base = {
        "b0_hour": 18,
        "b0_electricity_pricing": 0.15,
        "b0_non_shiftable_load": 10.0,
        "b0_solar_generation": 0.0,
        "b0_electrical_storage_soc": 0.5,
        "b0_ev_0_connected": 0.0,
        "b0_deferrable_appliance_can_start": 0.0,
    }
    buckets = set()
    for price in [0.04, 0.07, 0.09, 0.11, 0.13, 0.15, 0.17, 0.19, 0.21, 0.24, 0.27, 0.31, 0.40]:
        obs = dict(base, b0_electricity_pricing=price)
        key = encode_state_lmp(obs, ["b0"])
        assert key.count("|") == 5  # six |-separated components
        buckets.add(int(key.split("|")[-1]))
    assert buckets == set(range(N_LMP_BUCKETS))  # all 12 LMP buckets reachable


def test_lmp_policy_has_138_states():
    """The regenerated LMP policy for scenario A uses the 138-state encoder (plan 4.3)."""
    path = LMP_POLICY_DIR / "lmp_scenario_a.json"
    assert path.exists(), f"Run the regen recipe to produce {path}"
    payload = json.loads(path.read_text())
    assert payload["metadata"]["encoder"] == "lmp"
    assert payload["metadata"]["episodes"] == 60
    assert payload["metadata"]["seed"] == 0
    assert payload["metadata"]["n_states"] == 138
    assert len(payload["q_table"]) == 138


def test_policy_json_round_trip(tmp_path):
    """A policy JSON written by the trainer round-trips through the controller."""
    state = encode_state(observations(), ["b0"])
    q_values = [0.0] * N_ACTIONS
    q_values[0] = 1.0
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"q_table": {state: q_values}, "metadata": {"encoder": "base"}}))

    controller = QLearningController(make_scenario(), str(path), device_metadata=metadata())
    actions = controller.get_actions(observations(), timestep=0)
    assert controller.unseen_states == 0


def test_ql_controller_loads_lmp_policy():
    """QLearningController resolves the LMP encoder from an lmp_scenario_*.json policy."""
    path = LMP_POLICY_DIR / "lmp_scenario_a.json"
    assert path.exists(), f"Run the regen recipe to produce {path}"
    controller = QLearningController(make_scenario(), str(path), device_metadata=metadata())
    assert controller.encoder == "lmp"
    assert controller._encode is encode_state_lmp
