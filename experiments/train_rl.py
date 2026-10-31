"""Train the tabular Q-learning baseline used by ``src/controllers/rl.py``.

Training runs against the CityLearn adapter only (no pandapower) to keep the
policy-learning cost bounded. Evaluation uses the full co-simulation.

Regen recipe (plan 4.3: per-LMP-scenario policies, 60 episodes, seed 0)::

    # base encoder (126-state) policies
    python -m experiments.train_rl --config configs/scenario_a.yaml \
        --out experiments/reference/rl_policy/scenario_a.json --encoder base --episodes 60 --seed 0
    # ... repeat for scenarios b-e

    # LMP encoder (138-state) policies
    python -m experiments.train_rl --config configs/scenario_a.yaml \
        --out experiments/reference/rl_policy/lmp_scenario_a.json --encoder lmp --episodes 60 --seed 0
    python -m experiments.train_rl --config configs/scenario_b.yaml \
        --out experiments/reference/rl_policy/lmp_scenario_b.json --encoder lmp --episodes 60 --seed 0
    python -m experiments.train_rl --config configs/scenario_c.yaml \
        --out experiments/reference/rl_policy/lmp_scenario_c.json --encoder lmp --episodes 60 --seed 0
    python -m experiments.train_rl --config configs/scenario_d.yaml \
        --out experiments/reference/rl_policy/lmp_scenario_d.json --encoder lmp --episodes 60 --seed 0
    python -m experiments.train_rl --config configs/scenario_e.yaml \
        --out experiments/reference/rl_policy/lmp_scenario_e.json --encoder lmp --episodes 60 --seed 0

Each policy takes roughly 10 minutes. The LMP encoder appends a 12-bucket LMP
price field to the base state key (see ``src/controllers/rl.encode_state_lmp``).
The trained policy's metadata records ``encoder``, ``episodes``, ``seed`` and
``n_states``; ``QLearningController`` resolves the encoder from policy metadata
so an LMP policy is always decoded with the LMP encoder.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

from src.controllers.rl import (
    BATTERY_LEVELS,
    EV_LEVELS,
    N_ACTIONS,
    decode_action,
    encode_state,
    encode_state_lmp,
)
from src.schemas.action import Action, ActionType, RequestedActions
from src.schemas.scenario import ScenarioConfig
from src.simulation.citylearn_adapter import CityLearnAdapter


def _build_actions(
    observations: Dict[str, Any],
    building_ids: List[str],
    action_index: int,
    timestep: int,
    device_metadata: Dict[str, Dict[str, Any]],
) -> RequestedActions:
    """Translate a discrete joint action into requested device powers (kW)."""
    battery_level, ev_level = decode_action(action_index)
    actions: List[Action] = []
    for building_id in building_ids:
        meta = device_metadata.get(building_id, {})
        battery = meta.get("battery") or {}
        power_kw = float(battery.get("power_kw") or 0.0)
        if power_kw > 0.0 and abs(battery_level) > 1e-6:
            action_type = ActionType.BATTERY_CHARGE if battery_level > 0 else ActionType.BATTERY_DISCHARGE
            actions.append(Action(
                asset_id=f"{building_id}_electrical_storage",
                action_type=action_type,
                value_kw=float(battery_level) * power_kw,
                timestep=timestep,
            ))
        if observations.get(f"{building_id}_ev_0_connected") and ev_level > 1e-6:
            chargers = meta.get("chargers") or []
            max_charge_kw = max(
                (float(c.get("max_charge_kw") or 0.0) for c in chargers), default=0.0
            )
            if max_charge_kw > 0.0:
                actions.append(Action(
                    asset_id=f"{building_id}_electric_vehicle_storage",
                    action_type=ActionType.EV_CHARGE,
                    value_kw=float(ev_level) * max_charge_kw,
                    timestep=timestep,
                ))
    return RequestedActions(timestep=timestep, actions=actions)


def _reward(observations: Dict[str, Any], building_ids: List[str], dt: float) -> float:
    cost = 0.0
    net_total = 0.0
    for bid in building_ids:
        price = float(observations.get(f"{bid}_electricity_pricing", 0.0) or 0.0)
        net = float(observations.get(f"{bid}_net_electricity_consumption", 0.0) or 0.0)
        cost += price * net * dt
        net_total += net

    peak = max(0.0, net_total)
    reward = -(cost / 10.0) - 0.02 * peak

    for bid in building_ids:
        prefix = f"{bid}_ev_0"
        if not observations.get(f"{prefix}_connected"):
            continue
        soc = float(observations.get(f"{prefix}_soc", 0.0) or 0.0)
        required = float(observations.get(f"{prefix}_required_soc", 0.0) or 0.0)
        hours = float(observations.get(f"{prefix}_hours_to_departure", 0.0) or 0.0)
        if hours <= dt and soc < required:
            reward -= 5.0 * (required - soc)

    return float(reward)


def train(
    scenario: ScenarioConfig,
    episodes: int = 40,
    alpha: float = 0.2,
    gamma: float = 0.95,
    epsilon_start: float = 0.9,
    epsilon_end: float = 0.05,
    seed: int = 0,
    encoder: str = "base",
) -> Dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    scenario.random_seed = seed
    # Keep the training schema separate from any concurrent experiment run.
    os.environ.setdefault("SAEA_RUN_ID", f"train_{scenario.scenario_id}_{seed}")
    adapter = CityLearnAdapter(scenario, data_dir="data")
    metadata = adapter.get_device_metadata()
    building_ids = list(metadata.keys())
    dt = float(metadata[building_ids[0]]["hours_per_step"]) if building_ids else 1.0

    encode = encode_state_lmp if encoder == "lmp" else encode_state

    q_table: Dict[str, List[float]] = {}
    episode_returns: List[float] = []

    for episode in range(episodes):
        epsilon = epsilon_start + (epsilon_end - epsilon_start) * episode / max(1, episodes - 1)
        observations = adapter.reset(seed)
        total_reward = 0.0
        terminated = False
        step = 0
        while not terminated:
            state = encode(observations, building_ids)
            values = q_table.setdefault(state, [0.0] * N_ACTIONS)
            if random.random() < epsilon:
                action_index = random.randrange(N_ACTIONS)
            else:
                action_index = int(np.argmax(values))

            actions = _build_actions(observations, building_ids, action_index, step, metadata)
            next_observations, result = adapter.step(actions)
            reward = _reward(next_observations, building_ids, dt)
            total_reward += reward

            next_state = encode(next_observations, building_ids)
            next_values = q_table.setdefault(next_state, [0.0] * N_ACTIONS)
            target = reward + (0.0 if result.terminated else gamma * max(next_values))
            values[action_index] += alpha * (target - values[action_index])

            observations = next_observations
            terminated = bool(result.terminated)
            step += 1

        episode_returns.append(total_reward)
        print(
            f"episode {episode + 1}/{episodes}: steps={step} return={total_reward:.3f} "
            f"states={len(q_table)} epsilon={epsilon:.2f}"
        )

    adapter.close()
    return {
        "q_table": q_table,
        "metadata": {
            "algorithm": "tabular_q_learning_single_agent",
            "scenario_id": scenario.scenario_id,
            "episodes": episodes,
            "alpha": alpha,
            "gamma": gamma,
            "epsilon_start": epsilon_start,
            "epsilon_end": epsilon_end,
            "seed": seed,
            "encoder": encoder,
            "battery_levels": list(BATTERY_LEVELS),
            "ev_levels": list(EV_LEVELS),
            "n_states": len(q_table),
            "episode_returns": episode_returns,
            "trained_at": datetime.now().isoformat(timespec="seconds"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the tabular Q-learning baseline")
    parser.add_argument("--config", required=True, help="Scenario YAML")
    parser.add_argument("--out", required=True, help="Output policy JSON")
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--alpha", type=float, default=0.2)
    parser.add_argument("--gamma", type=float, default=0.95)
    parser.add_argument(
        "--encoder",
        type=str,
        default="base",
        choices=["base", "lmp"],
        help="State encoder: 'base' (5-band) or 'lmp' (base + 12 LMP price buckets).",
    )
    args = parser.parse_args()

    with open(args.config) as handle:
        scenario = ScenarioConfig(**yaml.safe_load(handle))

    started = time.time()
    payload = train(
        scenario,
        episodes=args.episodes,
        alpha=args.alpha,
        gamma=args.gamma,
        seed=args.seed,
        encoder=args.encoder,
    )
    payload["metadata"]["wall_clock_seconds"] = round(time.time() - started, 1)

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))
    print(f"Saved policy with {payload['metadata']['n_states']} states to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
