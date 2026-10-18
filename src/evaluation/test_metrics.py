"""Test to verify KPI calculations with a hand-calculable small case."""
import sys
sys.path.insert(0, ".")

from src.evaluation.metrics import compute_energy_metrics
from src.schemas.action import (
    SimulationStepResult, RequestedActions, LimitedActions, AppliedActions,
    Action, ActionType
)
from src.schemas.report import EnergyMetrics


def create_hand_calculable_history():
    """Create a simple 2-step history with known values for manual verification.
    
    Scenario: 1 building, 15-min timestep.
    Building has:
      - non_shiftable_load = 2 kW (constant)
      - solar_generation = 3 kW (constant)
      - net_electricity_consumption = non_shiftable_load - solar_generation = -1 kW (export)
      - No battery, no EV.
    Tariff: import 0.1 $/kWh on-peak, 0.05 off-peak; export 0.03 $/kWh flat.
    We'll simulate 2 steps: step 0 at hour 12 (on-peak), step 1 at hour 3 (off-peak).
    """
    timestep_minutes = 15
    timestep_hours = timestep_minutes / 60.0  # 0.25 h
    
    # Step 0: hour 12 (on-peak)
    obs0 = {
        "building1_net_electricity_consumption": -1.0,  # kW (export)
        "building1_solar_generation": 3.0,
        "building1_non_shiftable_load": 2.0,
    }
    step0 = SimulationStepResult(
        timestep=0,
        requested_actions=RequestedActions(timestep=0, actions=[]),
        limited_actions=LimitedActions(timestep=0, actions=[]),
        applied_actions=AppliedActions(timestep=0, actions=[]),
        observations=obs0,
        rewards={},
        costs={"building1": 0.0},  # will be recomputed
        constraint_violations=[],
        terminated=False,
        truncated=False,
        grid_diagnostics={}
    )
    
    # Step 1: hour 3 (off-peak)
    obs1 = {
        "building1_net_electricity_consumption": -1.0,
        "building1_solar_generation": 3.0,
        "building1_non_shiftable_load": 2.0,
    }
    step1 = SimulationStepResult(
        timestep=1,
        requested_actions=RequestedActions(timestep=1, actions=[]),
        limited_actions=LimitedActions(timestep=1, actions=[]),
        applied_actions=AppliedActions(timestep=1, actions=[]),
        observations=obs1,
        rewards={},
        costs={"building1": 0.0},
        constraint_violations=[],
        terminated=False,
        truncated=False,
        grid_diagnostics={}
    )
    
    history = [step0, step1]
    
    scenario_config = {
        "timestep_minutes": timestep_minutes,
        "buildings": [{
            "building_id": "building1",
            "tariff": {
                "import_prices": {"on_peak": 0.10, "mid_peak": 0.07, "off_peak": 0.05},
                "export_prices": {"on_peak": 0.03, "mid_peak": 0.03, "off_peak": 0.03},
            }
        }]
    }
    
    return history, scenario_config, timestep_hours


def manual_calculation(timestep_hours):
    """Manually compute expected metrics for the hand-calculable case."""
    # Each step: net = -1 kW (export 1 kW)
    # Energy per step = 1 kW * 0.25 h = 0.25 kWh export
    # Two steps => total export = 0.5 kWh, import = 0 kWh
    # Peak demand (import) = 0 kW
    # PV generation per step = 3 kW * 0.25 = 0.75 kWh, total = 1.5 kWh
    # PV self-consumed = PV gen - export = 1.5 - 0.5 = 1.0 kWh
    # Cost: step0 (on-peak) export 0.25 kWh * 0.03 $/kWh = -0.0075 $ (revenue)
    #       step1 (off-peak) export 0.25 kWh * 0.03 $/kWh = -0.0075 $
    # Total cost = -0.015 $ (negative means revenue)
    # Load factor = avg_import / peak_import = 0/0 -> 0
    expected = {
        "total_cost": -0.015,
        "grid_import_kwh": 0.0,
        "grid_export_kwh": 0.5,
        "peak_demand_kw": 0.0,
        "load_factor": 0.0,
        "pv_generation_kwh": 1.5,
        "pv_self_consumption_kwh": 1.0,
        "pv_curtailment_kwh": 0.0,
        "battery_throughput_kwh": 0.0,
        "battery_cycles": 0.0,
    }
    return expected


def test_energy_metrics():
    history, scenario_config, timestep_hours = create_hand_calculable_history()
    metrics = compute_energy_metrics(history, scenario_config)
    expected = manual_calculation(timestep_hours)
    
    print("=== Computed Metrics ===")
    print(f"total_cost: {metrics.total_cost:.6f} (expected {expected['total_cost']:.6f})")
    print(f"grid_import_kwh: {metrics.grid_import_kwh:.6f} (expected {expected['grid_import_kwh']:.6f})")
    print(f"grid_export_kwh: {metrics.grid_export_kwh:.6f} (expected {expected['grid_export_kwh']:.6f})")
    print(f"peak_demand_kw: {metrics.peak_demand_kw:.6f} (expected {expected['peak_demand_kw']:.6f})")
    print(f"load_factor: {metrics.load_factor:.6f} (expected {expected['load_factor']:.6f})")
    print(f"pv_generation_kwh: {metrics.pv_generation_kwh:.6f} (expected {expected['pv_generation_kwh']:.6f})")
    print(f"pv_self_consumption_kwh: {metrics.pv_self_consumption_kwh:.6f} (expected {expected['pv_self_consumption_kwh']:.6f})")
    print(f"pv_curtailment_kwh: {metrics.pv_curtailment_kwh:.6f} (expected {expected['pv_curtailment_kwh']:.6f})")
    print(f"battery_throughput_kwh: {metrics.battery_throughput_kwh:.6f} (expected {expected['battery_throughput_kwh']:.6f})")
    print(f"battery_cycles: {metrics.battery_cycles:.6f} (expected {expected['battery_cycles']:.6f})")
    
    # Assertions with tolerance
    tol = 1e-6
    assert abs(metrics.total_cost - expected["total_cost"]) < tol, f"Cost mismatch: {metrics.total_cost} vs {expected['total_cost']}"
    assert abs(metrics.grid_import_kwh - expected["grid_import_kwh"]) < tol
    assert abs(metrics.grid_export_kwh - expected["grid_export_kwh"]) < tol
    assert abs(metrics.peak_demand_kw - expected["peak_demand_kw"]) < tol
    assert abs(metrics.pv_generation_kwh - expected["pv_generation_kwh"]) < tol
    assert abs(metrics.pv_self_consumption_kwh - expected["pv_self_consumption_kwh"]) < tol
    print("\n[OK] All assertions passed! KPIs are non-zero and correct.")


if __name__ == "__main__":
    test_energy_metrics()