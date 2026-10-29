"""Model predictive control baseline.

A deterministic, receding-horizon MPC over battery dispatch and EV charging.
The controller requests power in kW; the CityLearn adapter converts that to the
simulator's normalized device actions. It uses the live device ratings from
``CityLearnAdapter.get_device_metadata`` rather than the scenario YAML, because
the adapter derives its schema from a CityLearn dataset template.

Forecasts are causal: load and PV use the observed diurnal profile with the
current value as a fallback before a profile has been learned. Prices come from
the scenario tariff (the same schedule the cost metrics bill), not from the
CityLearn dataset's own pricing column. No future observations are consumed, so
this is a fair online baseline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from scipy.optimize import linprog

from src.controllers import BaseController, RuleBasedController
from src.schemas.action import Action, ActionType, RequestedActions
from src.schemas.scenario import ScenarioConfig


class MPCController(BaseController):
    """Receding-horizon linear MPC for batteries and EV chargers."""

    def __init__(
        self,
        scenario_config: ScenarioConfig,
        device_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        horizon_steps: int = 24,
    ):
        super().__init__(scenario_config)
        self.device_metadata = device_metadata or {}
        self.horizon_steps = max(1, int(horizon_steps))
        self._buildings = {b.building_id: b for b in scenario_config.buildings}
        self._rule_based = RuleBasedController(scenario_config)
        self._reset_state()

    def _reset_state(self) -> None:
        self.timestep = 0
        self._price_by_hour: Dict[int, float] = {}
        self._load_by_hour: Dict[int, List[float]] = {}
        self._pv_by_hour: Dict[int, List[float]] = {}
        self.fallback_steps = 0
        self._rule_based.reset()

    def reset(self) -> None:
        super().reset()
        self._reset_state()

    # ------------------------------------------------------------------ public
    def get_actions(self, observations: Dict[str, Any], timestep: int) -> RequestedActions:
        self.timestep = timestep
        self._record_observation(observations)

        if not self.device_metadata:
            self.fallback_steps += 1
            return self._rule_based.get_actions(observations, timestep)

        try:
            battery_actions, ev_actions = self._solve(observations, timestep)
        except Exception:  # pragma: no cover - numerical guard, exercised in tests
            self.fallback_steps += 1
            return self._rule_based.get_actions(observations, timestep)

        actions: List[Action] = []
        actions.extend(battery_actions)
        actions.extend(ev_actions)
        actions.extend(self._deferrable_actions(observations))
        return self._create_requested_actions(actions)

    # ------------------------------------------------------------- forecasting
    def _record_observation(self, observations: Dict[str, Any]) -> None:
        for building_id in self.device_metadata:
            hour = int(observations.get(f"{building_id}_hour", 0)) % 24
            price = observations.get(f"{building_id}_electricity_pricing")
            load = observations.get(f"{building_id}_non_shiftable_load")
            pv = observations.get(f"{building_id}_solar_generation")
            if price is not None:
                self._price_by_hour[hour] = float(price)
            if load is not None:
                self._load_by_hour.setdefault(hour, []).append(float(load))
            if pv is not None:
                self._pv_by_hour.setdefault(hour, []).append(float(pv))

    def _forecast(self, observations: Dict[str, Any], building_id: str, start_hour: int) -> Dict[str, np.ndarray]:
        price = np.empty(self.horizon_steps)
        export = np.empty(self.horizon_steps)
        load = np.empty(self.horizon_steps)
        pv = np.empty(self.horizon_steps)
        current_price = float(observations.get(f"{building_id}_electricity_pricing", 0.15))
        current_load = float(observations.get(f"{building_id}_non_shiftable_load", 0.0))
        current_pv = float(observations.get(f"{building_id}_solar_generation", 0.0))
        building = self._buildings.get(building_id)
        for k in range(self.horizon_steps):
            hour = (start_hour + k) % 24
            price[k] = self._price_by_hour.get(hour, current_price)
            load_hist = self._load_by_hour.get(hour, [])
            pv_hist = self._pv_by_hour.get(hour, [])
            load[k] = float(np.mean(load_hist)) if load_hist else current_load
            pv[k] = float(np.mean(pv_hist)) if pv_hist else current_pv
            export_price = self._tariff_price(building, hour, is_import=False) if building else None
            export[k] = export_price if export_price is not None else 0.0
        return {"price": price, "export": export, "load": load, "pv": pv}

    @staticmethod
    def _tariff_period(hour: int) -> str:
        if hour < 7 or hour >= 23:
            return "off_peak"
        if hour < 12 or (18 <= hour < 21):
            return "mid_peak"
        return "on_peak"

    def _tariff_price(self, building, hour: int, is_import: bool) -> Optional[float]:
        tariff = getattr(building, "tariff", None)
        if tariff is None:
            return None
        prices = getattr(tariff, "import_prices" if is_import else "export_prices", None) or {}
        if not prices:
            return None
        return float(prices.get(self._tariff_period(hour), 0.0))

    # ------------------------------------------------------------------- solve
    def _solve(self, observations: Dict[str, Any], timestep: int) -> tuple[List[Action], List[Action]]:
        horizon = self.horizon_steps
        dt = float(self.device_metadata[self.building_ids[0]].get("hours_per_step", 1.0)) or 1.0
        start_hour = int(observations.get(f"{self.building_ids[0]}_hour", 0)) % 24

        buildings = [b for b in self.building_ids if b in self.device_metadata]
        n_b = len(buildings)
        if n_b == 0:
            return [], []

        # Variable layout -------------------------------------------------
        # per building and step: charge, discharge, import, export
        i_c = 0
        i_d = i_c + n_b * horizon
        i_imp = i_d + n_b * horizon
        i_exp = i_imp + n_b * horizon
        n_flow = i_exp + n_b * horizon
        # battery state of charge, horizon + 1 points
        i_soc = n_flow
        n_soc = n_b * (horizon + 1)
        # EV charging per building and step
        i_ev = i_soc + n_soc
        n_ev = n_b * horizon
        # EV state of charge, horizon + 1 points
        i_evsoc = i_ev + n_ev
        n_evsoc = n_b * (horizon + 1)
        i_peak = i_evsoc + n_evsoc
        i_short = i_peak + 1
        n_vars = i_short + n_b

        def flow_idx(kind: int, bidx: int, step: int) -> int:
            return kind + bidx * horizon + step

        def soc_idx(bidx: int, step: int) -> int:
            return i_soc + bidx * (horizon + 1) + step

        def ev_idx(bidx: int, step: int) -> int:
            return i_ev + bidx * horizon + step

        def evsoc_idx(bidx: int, step: int) -> int:
            return i_evsoc + bidx * (horizon + 1) + step

        cost = np.zeros(n_vars)

        # Equality constraints: building power balance and storage dynamics.
        a_eq_rows: List[np.ndarray] = []
        b_eq: List[float] = []

        for bidx, building_id in enumerate(buildings):
            meta = self.device_metadata[building_id]
            battery = meta.get("battery") or {}
            capacity = float(battery.get("capacity_kwh") or 0.0)
            power = float(battery.get("power_kw") or 0.0)
            efficiency = float(battery.get("efficiency") or 0.9)
            soc0 = float(observations.get(f"{building_id}_electrical_storage_soc", 0.0))
            soc0 = min(max(soc0, 0.0), 1.0)
            forecast = self._forecast(observations, building_id, start_hour)
            has_battery = capacity > 0.0 and power > 0.0

            ev_info = self._connected_ev(observations, building_id, 0)
            ev_capacity = ev_info["capacity_kwh"] if ev_info else 0.0
            ev_soc0 = ev_info["soc"] if ev_info else 0.0
            ev_max = ev_info["max_charge_kw"] if ev_info else 0.0
            ev_required = ev_info["required_soc"] if ev_info else 0.0
            ev_departure = ev_info["departure_steps"] if ev_info else horizon

            for k in range(horizon):
                row = np.zeros(n_vars)
                row[flow_idx(i_imp, bidx, k)] = 1.0
                row[flow_idx(i_exp, bidx, k)] = -1.0
                row[flow_idx(i_c, bidx, k)] = -1.0
                row[flow_idx(i_d, bidx, k)] = 1.0
                row[ev_idx(bidx, k)] = -1.0
                a_eq_rows.append(row)
                b_eq.append(forecast["load"][k] - forecast["pv"][k])

                cost[flow_idx(i_imp, bidx, k)] = forecast["price"][k] * dt
                cost[flow_idx(i_exp, bidx, k)] = -forecast["export"][k] * dt
                cost[flow_idx(i_c, bidx, k)] = 1e-4 * dt
                cost[flow_idx(i_d, bidx, k)] = 1e-4 * dt
                cost[ev_idx(bidx, k)] = 1e-5 * dt

                if has_battery:
                    dyn = np.zeros(n_vars)
                    dyn[soc_idx(bidx, k)] = -1.0
                    dyn[soc_idx(bidx, k + 1)] = 1.0
                    dyn[flow_idx(i_c, bidx, k)] = -efficiency * dt / capacity
                    dyn[flow_idx(i_d, bidx, k)] = dt / (capacity * efficiency)
                    a_eq_rows.append(dyn)
                    b_eq.append(0.0)
                else:
                    dyn = np.zeros(n_vars)
                    dyn[flow_idx(i_c, bidx, k)] = 1.0
                    a_eq_rows.append(dyn)
                    b_eq.append(0.0)
                    dyn = np.zeros(n_vars)
                    dyn[flow_idx(i_d, bidx, k)] = 1.0
                    a_eq_rows.append(dyn)
                    b_eq.append(0.0)

                if ev_capacity > 0.0 and k < ev_departure:
                    evdyn = np.zeros(n_vars)
                    evdyn[evsoc_idx(bidx, k)] = -1.0
                    evdyn[evsoc_idx(bidx, k + 1)] = 1.0
                    evdyn[ev_idx(bidx, k)] = -float(ev_info["efficiency"]) * dt / ev_capacity
                    a_eq_rows.append(evdyn)
                    b_eq.append(0.0)
                else:
                    evdyn = np.zeros(n_vars)
                    evdyn[evsoc_idx(bidx, k)] = -1.0
                    evdyn[evsoc_idx(bidx, k + 1)] = 1.0
                    a_eq_rows.append(evdyn)
                    b_eq.append(0.0)

        # Battery and EV initial states.
        for bidx, building_id in enumerate(buildings):
            battery = self.device_metadata[building_id].get("battery") or {}
            soc0 = float(observations.get(f"{building_id}_electrical_storage_soc", 0.0))
            soc0 = min(max(soc0, 0.0), 1.0)
            row = np.zeros(n_vars)
            row[soc_idx(bidx, 0)] = 1.0
            a_eq_rows.append(row)
            b_eq.append(soc0)

            ev_info = self._connected_ev(observations, building_id, 0)
            row = np.zeros(n_vars)
            row[evsoc_idx(bidx, 0)] = 1.0
            a_eq_rows.append(row)
            b_eq.append(ev_info["soc"] * ev_info["capacity_kwh"] if ev_info else 0.0)

        a_eq = np.vstack(a_eq_rows)
        b_eq_arr = np.asarray(b_eq)

        # Inequality constraints -----------------------------------------
        a_ub_rows: List[np.ndarray] = []
        b_ub: List[float] = []

        import_limit = self.scenario_config.community_import_limit_kw
        export_limit = self.scenario_config.community_export_limit_kw
        for k in range(horizon):
            peak_row = np.zeros(n_vars)
            for bidx in range(n_b):
                peak_row[flow_idx(i_imp, bidx, k)] = 1.0
            peak_row[i_peak] = -1.0
            a_ub_rows.append(peak_row)
            b_ub.append(0.0)

            if import_limit:
                row = np.zeros(n_vars)
                for bidx in range(n_b):
                    row[flow_idx(i_imp, bidx, k)] = 1.0
                a_ub_rows.append(row)
                b_ub.append(float(import_limit))
            if export_limit:
                row = np.zeros(n_vars)
                for bidx in range(n_b):
                    row[flow_idx(i_exp, bidx, k)] = 1.0
                a_ub_rows.append(row)
                b_ub.append(float(export_limit))

        # EV service constraint: terminal SOC + shortfall >= required.
        for bidx, building_id in enumerate(buildings):
            ev_info = self._connected_ev(observations, building_id, 0)
            if ev_info is None:
                continue
            departure = min(max(ev_info["departure_steps"], 0), horizon)
            row = np.zeros(n_vars)
            row[evsoc_idx(bidx, departure)] = -1.0
            row[i_short + bidx] = -1.0
            a_ub_rows.append(row)
            b_ub.append(-ev_info["required_soc"] * ev_info["capacity_kwh"])
            cost[i_short + bidx] = 10.0  # $/kWh shortfall at departure

        a_ub = np.vstack(a_ub_rows)
        b_ub_arr = np.asarray(b_ub)

        # Bounds ----------------------------------------------------------
        bounds: List[tuple[float, Optional[float]]] = [(0.0, None)] * n_vars
        for bidx, building_id in enumerate(buildings):
            meta = self.device_metadata[building_id]
            battery = meta.get("battery") or {}
            power = float(battery.get("power_kw") or 0.0)
            for k in range(horizon):
                bounds[flow_idx(i_c, bidx, k)] = (0.0, power)
                bounds[flow_idx(i_d, bidx, k)] = (0.0, power)
            for k in range(horizon + 1):
                bounds[soc_idx(bidx, k)] = (0.0, 1.0)

            ev_info = self._connected_ev(observations, building_id, 0)
            ev_max = max(0.0, ev_info["max_charge_kw"] if ev_info else 0.0)
            ev_capacity = max(0.0, ev_info["capacity_kwh"] if ev_info else 0.0)
            for k in range(horizon):
                bounds[ev_idx(bidx, k)] = (0.0, ev_max)
            for k in range(horizon + 1):
                bounds[evsoc_idx(bidx, k)] = (0.0, max(ev_capacity, 1e-9))

        bounds[i_peak] = (0.0, None)
        for bidx in range(n_b):
            bounds[i_short + bidx] = (0.0, None)

        # Demand-charge proxy: scenario tariffs carry a demand charge, but the
        # energy metrics do not bill it, so use a small explicit peak penalty.
        cost[i_peak] = 0.1

        result = linprog(
            cost,
            A_ub=a_ub,
            b_ub=b_ub_arr,
            A_eq=a_eq,
            b_eq=b_eq_arr,
            bounds=bounds,
            method="highs",
        )
        if not result.success:
            raise RuntimeError(f"MPC LP failed: {result.message}")

        x = result.x
        battery_actions: List[Action] = []
        ev_actions: List[Action] = []
        for bidx, building_id in enumerate(buildings):
            meta = self.device_metadata[building_id]
            battery = meta.get("battery") or {}
            power = float(battery.get("power_kw") or 0.0)
            if power > 0.0:
                net_kw = float(x[flow_idx(i_c, bidx, 0)] - x[flow_idx(i_d, bidx, 0)])
                if abs(net_kw) > 1e-2:
                    action_type = ActionType.BATTERY_CHARGE if net_kw > 0 else ActionType.BATTERY_DISCHARGE
                    battery_actions.append(Action(
                        asset_id=f"{building_id}_electrical_storage",
                        action_type=action_type,
                        value_kw=net_kw,
                        timestep=timestep,
                    ))

            ev_info = self._connected_ev(observations, building_id, 0)
            if ev_info and ev_info["max_charge_kw"] > 0.0:
                charge_kw = float(x[ev_idx(bidx, 0)])
                if charge_kw >= ev_info["min_charge_kw"] and charge_kw > 1e-2:
                    ev_actions.append(Action(
                        asset_id=f"{building_id}_electric_vehicle_storage",
                        action_type=ActionType.EV_CHARGE,
                        value_kw=charge_kw,
                        timestep=timestep,
                    ))

        return battery_actions, ev_actions

    def _connected_ev(self, observations: Dict[str, Any], building_id: str, charger_index: int) -> Optional[Dict[str, Any]]:
        prefix = f"{building_id}_ev_{charger_index}"
        if not observations.get(f"{prefix}_connected"):
            return None
        capacity = float(observations.get(f"{prefix}_capacity_kwh", 0.0) or 0.0)
        if capacity <= 0.0:
            return None
        hours_to_departure = float(observations.get(f"{prefix}_hours_to_departure", 0.0) or 0.0)
        dt = float(self.device_metadata.get(building_id, {}).get("hours_per_step", 1.0)) or 1.0
        return {
            "soc": float(observations.get(f"{prefix}_soc", 0.0) or 0.0),
            "capacity_kwh": capacity,
            "required_soc": float(observations.get(f"{prefix}_required_soc", 0.0) or 0.0),
            "max_charge_kw": float(observations.get(f"{prefix}_max_charge_kw", 0.0) or 0.0),
            "min_charge_kw": float(observations.get(f"{prefix}_min_charge_kw", 0.0) or 0.0),
            "efficiency": 0.95,
            "departure_steps": int(np.ceil(hours_to_departure / dt)),
        }

    def _deferrable_actions(self, observations: Dict[str, Any]) -> List[Action]:
        """Run deferrable appliances when urgent or when PV would otherwise export."""
        actions: List[Action] = []
        for building_id in self.device_metadata:
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
