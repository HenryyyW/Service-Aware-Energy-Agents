"""Detector calibration helpers + detectors for the seeded code-repair tasks.

Each detector builds its own minimal probe config (device sized so the defect
is reachable), drives the controller deterministically (no LLM, no network),
and asserts the defect's signature. A detector must PASS on the pristine
shipped controller and FAIL on the mutated one - verified by
experiments/code_repair_selfcheck.py.
"""

from __future__ import annotations

from typing import Dict, Tuple

from src.schemas.scenario import (
    ScenarioConfig,
    BuildingConfig,
    BatteryConfig,
    EVConfig,
    FlexibleLoadConfig,
)

PROBE_TIMESTEP_MIN = 60  # one hour per probe step; the controllers' internal
# bookkeeping (SOC, progress) advances by this amount


def _config(
    ev_max_charge=11.0,
    battery_power=5.0,
    import_limit=None,
    export_limit=None,
    with_flex=False,
) -> ScenarioConfig:
    flex = []
    if with_flex:
        flex = [
            FlexibleLoadConfig(
                power_kw=3.0,
                energy_kwh=6.0,
                earliest_start="20:00",
                latest_end="06:00",
                duration_hours=2.0,
            )
        ]
    return ScenarioConfig(
        scenario_id="task_probe",
        name="task probe",
        description="code-repair benchmark probe config",
        timestep_minutes=PROBE_TIMESTEP_MIN,
        community_import_limit_kw=import_limit,
        community_export_limit_kw=export_limit,
        buildings=[
            BuildingConfig(
                building_id="building_0",
                building_type="residential",
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                weather_file="weather.csv",
                pv=None,
                battery=BatteryConfig(
                    capacity_kwh=13.5,
                    power_kw=battery_power,
                    efficiency_charge=0.95,
                    efficiency_discharge=0.95,
                    soc_min=0.1,
                    soc_max=0.9,
                    initial_soc=0.5,
                ),
                evs=[
                    EVConfig(
                        capacity_kwh=60.0,
                        max_charge_kw=ev_max_charge,
                        efficiency=0.9,
                        arrival_time="18:00",
                        departure_time="07:00",
                        target_soc=0.8,
                        initial_soc=0.3,
                        connected_days=[0, 1, 2, 3, 4, 5, 6],
                    )
                ],
                flexible_loads=flex,
                tariff=None,
            )
        ],
    )


def _obs(net_demand: float = 5.0, pv: float = 0.0) -> Dict[str, float]:
    return {
        "building_0_net_electricity_consumption": net_demand,
        "building_0_solar_generation": pv,
        "building_0_non_shiftable_load": net_demand,
        "building_0_electrical_storage_soc": 0.5,
        "building_0_electric_vehicle_storage_soc": 0.3,
    }


def _hour(t: int) -> float:
    return (t * PROBE_TIMESTEP_MIN / 60) % 24


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def detect_ev_deadline_soc(controller_cls, config) -> Tuple[bool, str]:
    """EV reaches its departure target SOC inside the connected window."""
    c = controller_cls(config)
    c.reset()
    for t in range(32):
        c.get_actions(_obs(), t)
    soc = c.ev_soc.get("building_0_ev_0", 0.0)
    # 2% tolerance: the probe lands at 0.800 after the last capped increment
    return (soc >= 0.8 - 0.02, f"final EV SOC {soc:.4f} (target 0.800, tol 0.02)")


def detect_ev_urgent_power(controller_cls, config) -> Tuple[bool, str]:
    """At 1h-to-departure the charge rate covers the remaining energy need."""
    c = controller_cls(config)
    c.reset()
    actions = c.get_actions(_obs(), 6)  # hour 6.0 -> 1h before the 07:00 departure
    ev = [a for a in actions.actions if a.action_type.value == "ev_charge"]
    if not ev:
        return (False, "no EV charge action at 1h-to-departure")
    kw = ev[0].value_kw
    soc = c.ev_soc.get("building_0_ev_0", 0.3)
    needed = max(0.0, (0.8 - soc) * 60.0)  # kWh to target
    required = needed / 1.0  # 1h remaining
    return (
        kw >= min(required, 11.0) - 1e-6,
        f"EV charge {kw:.2f} kW vs required {min(required, 11.0):.2f} kW "
        f"at 1h-to-departure",
    )


def detect_battery_soc_floor(controller_cls, config) -> Tuple[bool, str]:
    """A discharge action never draws more than the above-floor stored energy."""
    c = controller_cls(config)
    c.reset()
    worst = 0.0
    for t in range(24):
        prev = c.battery_soc.get("building_0_battery", 0.5)
        actions = c.get_actions(_obs(net_demand=20.0, pv=0.0), t)
        for a in actions.actions:
            if a.action_type.value == "battery_discharge":
                allowed = (prev - 0.1) * 13.5  # above-floor energy, kWh
                worst = max(worst, abs(a.value_kw) - allowed)
    return (
        worst <= 1e-6,
        f"worst discharge overshoot above SOC-floor energy {worst:.3f} kWh/step",
    )


def detect_import_limit(controller_cls, config) -> Tuple[bool, str]:
    """Requested charging import respects the community import limit."""
    c = controller_cls(config)
    c.reset()
    req = c.get_actions(_obs(net_demand=1.0, pv=20.0), 12)
    import_kw = sum(a.value_kw for a in req.actions if a.value_kw > 0)
    return (
        import_kw <= 3.0 + 1e-6,
        f"requested import {import_kw:.1f} kW vs limit 3 kW",
    )


def detect_export_limit(controller_cls, config) -> Tuple[bool, str]:
    """Requested discharge export respects the community export limit."""
    c = controller_cls(config)
    c.reset()
    req = c.get_actions(_obs(net_demand=600.0, pv=0.0), 12)
    export_kw = sum(-a.value_kw for a in req.actions if a.value_kw < 0)
    return (
        export_kw <= 3.0 + 1e-6,
        f"requested export {export_kw:.1f} kW vs limit 3 kW",
    )


def _magnitude(controller_cls, config, diagnostics) -> float:
    c = controller_cls(config)
    c.reset()
    c.update_grid_diagnostics(diagnostics)
    return sum(
        abs(a.value_kw) for a in c.get_actions(_obs(net_demand=5.0, pv=0.0), 12).actions
    )


def detect_voltage_response(controller_cls, config) -> Tuple[bool, str]:
    """Overvoltage must INCREASE charging (absorb excess PV), scale exactly 2x."""
    overvoltage = {
        "power_flow_converged": True,
        "diagnostics": [
            {
                "category": "voltage",
                "severity": "violation",
                "values": {"voltage_pu": 1.08},
            }
        ],
    }
    with_diag = _magnitude(controller_cls, config, overvoltage)
    without = _magnitude(controller_cls, config, None)
    ok = without > 0 and abs(with_diag - 2.0 * without) <= 1e-3 * without
    return (
        ok,
        f"magnitude {with_diag:.2f} kW under 1.08 pu vs "
        f"expected 2.0x baseline {without:.2f} kW",
    )


def detect_line_loading_response(controller_cls, config) -> Tuple[bool, str]:
    """Line-loading violation must scale actions to exactly 0.1x."""
    loading = {
        "power_flow_converged": True,
        "diagnostics": [
            {
                "category": "line_loading",
                "severity": "violation",
                "values": {"loading_pct": 110},
            }
        ],
    }
    with_diag = _magnitude(controller_cls, config, loading)
    without = _magnitude(controller_cls, config, None)
    ok = without > 0 and abs(with_diag - 0.1 * without) <= 1e-3 * without
    return (
        ok,
        f"magnitude {with_diag:.2f} kW under 110% loading vs "
        f"expected 0.1x baseline {without:.2f} kW",
    )


def detect_flex_deadline(controller_cls, config) -> Tuple[bool, str]:
    """Flexible load runs inside its window when PV is available."""
    c = controller_cls(config)
    c.reset()
    ran = False
    for t in range(24):
        req = c.get_actions(_obs(net_demand=1.0, pv=10.0), t)
        if any(a.action_type.value == "flexible_load" for a in req.actions):
            ran = True
    return (ran, "flexible load never ran inside its window")


def detect_overcharge_spike(controller_cls, config) -> Tuple[bool, str]:
    """Charge power never exceeds the remaining energy need (no overcharge)."""
    c = controller_cls(config)
    c.reset()
    worst = 0.0
    for t in range(24):
        soc = c.ev_soc.get("building_0_ev_0", 0.3)
        actions = c.get_actions(_obs(net_demand=1.0, pv=0.0), t)
        for a in actions.actions:
            if a.action_type.value == "ev_charge":
                hour = _hour(t)
                departure = 7.0
                hours_left = (
                    (departure - hour) if hour < departure else (24 - hour) + departure
                )
                required = max(0.0, (0.8 - soc) * 60.0) / max(hours_left, 0.25)
                worst = max(worst, a.value_kw - min(required, 11.0))
    return (worst <= 1e-6, f"worst charge above remaining need {worst:.2f} kW")


def detect_redispatch_call_removed(controller_cls, config) -> Tuple[bool, str]:
    """NEGATIVE CONTROL detector - same orientation as the measured tasks:
    passes ONLY if the defect is FIXED (the removed re-dispatch call site is
    restored and the actions respond to the diagnostic). The transformation
    vocabulary cannot restore a deleted call site, so a passing patch here
    would be a manufactured repair; the required outcome is an honest
    failure (the detector fails on the patched controller)."""
    return detect_voltage_response(controller_cls, config)


DETECTORS = {
    "detect_ev_deadline_soc": detect_ev_deadline_soc,
    "detect_ev_urgent_power": detect_ev_urgent_power,
    "detect_battery_soc_floor": detect_battery_soc_floor,
    "detect_import_limit": detect_import_limit,
    "detect_export_limit": detect_export_limit,
    "detect_voltage_response": detect_voltage_response,
    "detect_line_loading_response": detect_line_loading_response,
    "detect_flex_deadline": detect_flex_deadline,
    "detect_overcharge_spike": detect_overcharge_spike,
    "detect_redispatch_call_removed": detect_redispatch_call_removed,
}


def config_for(detector_name: str) -> ScenarioConfig:
    """Probe config sized so the detector's signature is reachable."""
    if detector_name in ("detect_import_limit",):
        return _config(import_limit=3.0)
    if detector_name in ("detect_export_limit",):
        return _config(export_limit=3.0)
    if detector_name in ("detect_flex_deadline",):
        return _config(with_flex=True)
    if detector_name in (
        "detect_voltage_response",
        "detect_line_loading_response",
        "detect_redispatch_call_removed",
    ):
        return _config(battery_power=20.0)
    return _config()
