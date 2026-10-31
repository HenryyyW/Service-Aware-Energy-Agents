"""Single-agent reinforcement-learning baseline.

A tabular Q-learning controller over a discretized community state. The agent
controls all batteries and EV chargers with one joint action, i.e. the
"single centralized agent" baseline required by the research brief. The policy
is trained offline with ``experiments/train_rl.py`` and loaded from JSON so that
evaluation runs are deterministic and free of training cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.controllers import BaseController, RuleBasedController
from src.schemas.action import Action, ActionType, RequestedActions
from src.schemas.scenario import ScenarioConfig

BATTERY_LEVELS = (-1.0, -0.5, 0.0, 0.5, 1.0)
EV_LEVELS = (0.0, 0.5, 1.0)
N_ACTIONS = len(BATTERY_LEVELS) * len(EV_LEVELS)


def decode_action(index: int) -> Tuple[float, float]:
    """Map a joint action index to (battery level, EV level)."""
    battery_index, ev_index = divmod(index, len(EV_LEVELS))
    return BATTERY_LEVELS[battery_index], EV_LEVELS[ev_index]


def _bin(value: float, thresholds: Tuple[float, ...]) -> int:
    for index, threshold in enumerate(thresholds):
        if value < threshold:
            return index
    return len(thresholds)


def encode_state(
    observations: Dict[str, Any],
    building_ids: List[str],
) -> str:
    """Discretize the community state into a compact key.

    Components: hour of day, price band, community net-load band, mean battery
    SOC band, and EV urgency band.
    """
    return _encode_state_core(observations, building_ids, lmp_bucket=None)


# LMP price buckets (plan 4.3: 12 LMP price buckets added to the 126-state
# base encoder). Thresholds are $/kWh import price; the final bucket catches
# everything above the last threshold.
LMP_PRICE_BUCKETS = (0.05, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.23, 0.26, 0.30)
N_LMP_BUCKETS = len(LMP_PRICE_BUCKETS) + 1  # 12


def _encode_state_core(
    observations: Dict[str, Any],
    building_ids: List[str],
    lmp_bucket: Optional[int],
) -> str:
    """Shared state core; appends ``|<lmp_bucket>`` when ``lmp_bucket`` is set."""
    hour = int(observations.get(f"{building_ids[0]}_hour", 0)) % 24
    hour_bin = hour // 6

    prices = [
        float(observations.get(f"{bid}_electricity_pricing", 0.0) or 0.0)
        for bid in building_ids
        if f"{bid}_electricity_pricing" in observations
    ]
    price = float(np.mean(prices)) if prices else 0.15
    price_bin = _bin(price, (0.12, 0.20))

    net = 0.0
    socs: List[float] = []
    for bid in building_ids:
        load = float(observations.get(f"{bid}_non_shiftable_load", 0.0) or 0.0)
        pv = float(observations.get(f"{bid}_solar_generation", 0.0) or 0.0)
        net += load - pv
        soc = observations.get(f"{bid}_electrical_storage_soc")
        if soc is not None:
            socs.append(float(soc))
    net_bin = _bin(net, (0.0, 5.0, 15.0))

    mean_soc = float(np.mean(socs)) if socs else 0.0
    soc_bin = _bin(mean_soc, (0.25, 0.5, 0.75))

    ev_bin = 0
    for bid in building_ids:
        prefix = f"{bid}_ev_0"
        if not observations.get(f"{prefix}_connected"):
            continue
        soc = float(observations.get(f"{prefix}_soc", 0.0) or 0.0)
        required = float(observations.get(f"{prefix}_required_soc", 0.0) or 0.0)
        hours = float(observations.get(f"{prefix}_hours_to_departure", 0.0) or 0.0)
        if soc >= required:
            ev_bin = max(ev_bin, 1)
        elif hours <= 6.0:
            ev_bin = 3
        else:
            ev_bin = max(ev_bin, 2)

    key = f"{hour_bin}|{price_bin}|{net_bin}|{soc_bin}|{ev_bin}"
    if lmp_bucket is not None:
        key = f"{key}|{lmp_bucket}"
    return key


def encode_state_lmp(
    observations: Dict[str, Any],
    building_ids: List[str],
) -> str:
    """Discretize the community state with an added LMP price bucket.

    Mirrors :func:`encode_state` and appends a sixth component, the LMP price
    bucket (12 buckets over import price in $/kWh), so the LMP arm can
    differentiate states that the base encoder collapses on price.
    """
    prices = [
        float(observations.get(f"{bid}_electricity_pricing", 0.0) or 0.0)
        for bid in building_ids
        if f"{bid}_electricity_pricing" in observations
    ]
    price = float(np.mean(prices)) if prices else 0.15
    lmp_bucket = _bin(price, LMP_PRICE_BUCKETS)
    return _encode_state_core(observations, building_ids, lmp_bucket=lmp_bucket)


class QLearningController(BaseController):
    """Greedy policy from a trained tabular Q-function."""

    def __init__(
        self,
        scenario_config: ScenarioConfig,
        policy_path: str,
        device_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        encoder: str = "base",
    ):
        super().__init__(scenario_config)
        self.device_metadata = device_metadata or {}
        self.policy_path = Path(policy_path)
        if not self.policy_path.exists():
            raise FileNotFoundError(
                f"RL policy not found: {self.policy_path}. "
                f"Train it with: python -m experiments.train_rl --config <scenario> --out {self.policy_path}"
            )
        payload = json.loads(self.policy_path.read_text())
        self.q_table: Dict[str, List[float]] = payload["q_table"]
        self.metadata: Dict[str, Any] = payload.get("metadata", {})
        self._rule_based = RuleBasedController(scenario_config)
        self._known_states = set(self.q_table)
        self.unseen_states = 0
        self.timestep = 0
        # The encoder used at training time is recorded in policy metadata; fall
        # back to the explicit argument (default ``base``) so an LMP policy is
        # always decoded with the LMP encoder.
        resolved_encoder = encoder
        if encoder == "base" and self.metadata.get("encoder") == "lmp":
            resolved_encoder = "lmp"
        self.encoder = resolved_encoder
        self._encode = encode_state_lmp if resolved_encoder == "lmp" else encode_state

    def reset(self) -> None:
        super().reset()
        self._rule_based.reset()
        self.unseen_states = 0

    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        self.timestep = timestep
        buildings = [b for b in self.building_ids if b in self.device_metadata] or list(self.building_ids)
        state = self._encode(observations, buildings)

        if state in self.q_table:
            action_index = int(np.argmax(self.q_table[state]))
        else:
            self.unseen_states += 1
            return self._rule_based.get_actions(observations, timestep)

        battery_level, ev_level = decode_action(action_index)
        actions: List[Action] = []

        for building_id in buildings:
            meta = self.device_metadata.get(building_id, {})
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

        actions.extend(self._deferrable_actions(observations))
        return self._create_requested_actions(actions)

    def _deferrable_actions(self, observations: Dict[str, Any]) -> List[Action]:
        actions: List[Action] = []
        for building_id in self.building_ids:
            if not observations.get(f"{building_id}_deferrable_appliance_can_start"):
                continue
            urgency = float(observations.get(f"{building_id}_deferrable_appliance_urgency_ratio", 0.0) or 0.0)
            pv = float(observations.get(f"{building_id}_solar_generation", 0.0) or 0.0)
            load = float(observations.get(f"{building_id}_non_shiftable_load", 0.0) or 0.0)
            if urgency >= 0.5 or pv > load:
                actions.append(Action(
                    asset_id=f"{building_id}_deferrable_appliance",
                    action_type=ActionType.FLEXIBLE_LOAD,
                    value_kw=1.0,
                    timestep=self.timestep,
                ))
        return actions
