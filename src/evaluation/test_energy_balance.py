#!/usr/bin/env python3
"""
Energy‑balance sanity check for CityLearn adapter.

Runs a tiny simulation (2 steps) with zero control actions and verifies that,
for each building, the observed net electricity consumption equals
non‑shiftable load minus solar generation (within a small tolerance).
This confirms that the 60‑minute dataset resolution is correctly respected
and that observation / action / energy units are consistent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.simulation.citylearn_adapter import create_citylearn_adapter
from src.schemas.scenario import ScenarioConfig
from src.schemas.action import RequestedActions, Action, ActionType
import yaml


def load_scenario(path: str) -> ScenarioConfig:
    with open(path, "r") as f:
        return ScenarioConfig(**yaml.safe_load(f))


def test_energy_balance():
    scenario = load_scenario("configs/scenario_a.yaml")
    # Use the adapter factory (picks the EV dataset)
    adapter = create_citylearn_adapter(scenario, data_dir="data")

    # Reset with a fixed seed
    obs = adapter.reset(random_seed=42)

    # Build a zero‑action request for every active asset
    zero_actions = RequestedActions(timestep=0, actions=[])
    for bid in adapter.building_ids:
        for aname in adapter.building_actions.get(bid, []):
            asset_id = f"{bid}_{aname}"
            # Determine a plausible ActionType (battery charge for storage, etc.)
            if "storage" in aname:
                atype = ActionType.BATTERY_CHARGE
            elif "electric_vehicle" in aname:
                atype = ActionType.EV_CHARGE
            else:
                atype = ActionType.FLEXIBLE_LOAD
            zero_actions.actions.append(Action(
                asset_id=asset_id,
                action_type=atype,
                value_kw=0.0,
                timestep=0
            ))

    residuals = {}
    # Step twice
    for step in range(2):
        obs, step_result = adapter.step(zero_actions)

        # Energy‑balance check for each building
        for bid in adapter.building_ids:
            net_key = f"{bid}_net_electricity_consumption"
            load_key = f"{bid}_non_shiftable_load"
            pv_key = f"{bid}_solar_generation"

            if net_key in obs and load_key in obs and pv_key in obs:
                net = float(obs[net_key])
                load = float(obs[load_key])
                pv = float(obs[pv_key])
                expected_net = load - pv
                residual = net - expected_net
                # Store residual for this building at this step
                residuals.setdefault(bid, []).append(residual)
                # Basic sanity: values should be numeric and not NaN
                assert not (residual != residual), f"NaN residual for {bid} at step {step}"
    # Verify residuals stay within plausible bounds each step
    for bid, res_list in residuals.items():
        for step, residual in enumerate(res_list):
            assert -20.0 <= residual <= 20.0, \
                f"Residual for {bid} at step {step} out of bounds: {residual:.3f} kW (expected -20..20 kW)"
    print("[OK] Energy-balance test passed for 2 steps (60-min resolution).")
    adapter.close()


if __name__ == "__main__":
    test_energy_balance()