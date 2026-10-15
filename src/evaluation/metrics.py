"""Metrics computation for energy, service, grid, and agent performance."""
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from src.schemas.action import SimulationStepResult, ActionType
from src.schemas.diagnostics import Diagnostic, DiagnosticCategory, Severity
from src.schemas.report import EnergyMetrics, ServiceMetrics, GridMetrics, AgentMetrics, PerMemberMetrics


def _time_to_hour(time_str: str) -> float:
    """Convert HH:MM to hour float."""
    h, m = map(int, time_str.split(':'))
    return h + m / 60


def compute_energy_metrics(
    history: List[SimulationStepResult],
    scenario_config: Dict[str, Any],
    carbon_intensity: Optional[List[float]] = None
) -> EnergyMetrics:
    """Compute energy and cost metrics from simulation history."""
    metrics = EnergyMetrics()
    
    total_cost = 0.0
    grid_import = 0.0
    grid_export = 0.0
    peak_demand = 0.0
    pv_gen_total = 0.0
    pv_self_consumed = 0.0
    pv_curtailed = 0.0
    battery_throughput = 0.0
    battery_cycles = 0.0
    
    demand_values = []
    
    for step in history:
        # Costs
        step_cost = sum(step.costs.values())
        total_cost += step_cost
        
        # Grid import/export from actions
        for action in step.applied_actions.actions:
            if action.action_type == ActionType.GRID_IMPORT and action.value_kw > 0:
                grid_import += action.value_kw
            elif action.action_type == ActionType.GRID_EXPORT and action.value_kw < 0:
                grid_export += -action.value_kw
        
        # Peak demand (community level)
        step_import = sum(a.value_kw for a in step.applied_actions.actions 
                         if a.action_type == ActionType.GRID_IMPORT and a.value_kw > 0)
        peak_demand = max(peak_demand, step_import)
        demand_values.append(step_import)
        
        # PV generation and self-consumption (from observations)
        obs = step.observations
        for key, value in obs.items():
            if 'solar_generation' in key:
                pv_gen_total += value
            if 'net_electricity_consumption' in key and value < 0:
                # Negative net consumption means exporting
                pv_self_consumed += min(abs(value), pv_gen_total)
            elif 'solar_curtailment' in key:
                pv_curtailed += value
        
        # Battery throughput
        for action in step.applied_actions.actions:
            if action.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE]:
                battery_throughput += abs(action.value_kw)
    
    # Convert to kWh (assuming timestep in minutes)
    timestep_hours = scenario_config.get('timestep_minutes', 15) / 60
    grid_import *= timestep_hours
    grid_export *= timestep_hours
    pv_gen_total *= timestep_hours
    pv_self_consumed *= timestep_hours
    pv_curtailed *= timestep_hours
    battery_throughput *= timestep_hours
    
    # Battery cycles (rough estimate)
    battery_cycles = battery_throughput / (2 * scenario_config.get('battery_capacity_kwh', 100))
    
    # Load factor
    avg_demand = np.mean(demand_values) if demand_values else 0
    load_factor = avg_demand / peak_demand if peak_demand > 0 else 0
    
    # Carbon emissions
    carbon_emissions = 0.0
    if carbon_intensity:
        for i, step in enumerate(history):
            step_import = sum(a.value_kw for a in step.applied_actions.actions 
                            if a.action_type == ActionType.GRID_IMPORT and a.value_kw > 0)
            if i < len(carbon_intensity):
                carbon_emissions += step_import * timestep_hours * carbon_intensity[i]
    else:
        # Default carbon intensity
        carbon_emissions = grid_import * 0.5  # kg CO2/kWh
    
    metrics.total_cost = total_cost
    metrics.grid_import_kwh = grid_import
    metrics.grid_export_kwh = grid_export
    metrics.peak_demand_kw = peak_demand
    metrics.load_factor = load_factor
    metrics.pv_self_consumption_kwh = pv_self_consumed
    metrics.pv_curtailment_kwh = pv_curtailed
    metrics.pv_generation_kwh = pv_gen_total
    metrics.battery_throughput_kwh = battery_throughput
    metrics.battery_cycles = battery_cycles
    metrics.carbon_emissions_kg = carbon_emissions
    metrics.carbon_intensity_weighted_kg = carbon_emissions
    
    return metrics


def compute_service_metrics(
    history: List[SimulationStepResult],
    scenario_config: Dict[str, Any]
) -> ServiceMetrics:
    """Compute service and fairness metrics."""
    metrics = ServiceMetrics()
    
    # EV metrics
    ev_departures = {}
    ev_target_soc = {}
    building_evs = {}
    
    # Extract EV configs from scenario
    for building in scenario_config.get('buildings', []):
        for i, ev in enumerate(building.get('evs', [])):
            ev_id = f"{building['building_id']}_ev_{i}"
            ev_target_soc[ev_id] = ev.get('target_soc', 0.8)
            departure_hour = _time_to_hour(ev.get('departure_time', '07:00'))
            # Convert to timestep
            timestep = int(departure_hour * 60 / scenario_config.get('timestep_minutes', 15))
            ev_departures[ev_id] = timestep
            building_evs[ev_id] = building['building_id']
    
    # Track EV SOC at departure
    ev_soc_at_departure = {}
    for step in history:
        for action in step.applied_actions.actions:
            if action.action_type == ActionType.EV_CHARGE and action.asset_id in ev_departures:
                # This is simplified - in reality we'd track SOC from observations
                pass
    
    # For now, return defaults - would need SOC tracking from observations
    metrics.ev_completion_rate = 1.0
    metrics.ev_avg_soc_at_departure = 0.8
    metrics.ev_worst_soc_at_departure = 0.8
    
    # Comfort violations (would need temperature observations)
    metrics.comfort_violation_degree_hours = 0.0
    
    # Flexible load completion
    metrics.flexible_load_completion_rate = 1.0
    metrics.flexible_load_avg_delay_hours = 0.0
    
    # DR delivery
    metrics.dr_requested_kw = 0.0
    metrics.dr_delivered_kw = 0.0
    metrics.dr_credited_kw = 0.0
    
    # Per-member costs (placeholder)
    metrics.per_member_costs = {}
    metrics.per_member_savings = {}
    
    # Fairness
    metrics.gini_coefficient = 0.0
    metrics.worst_member_cost = 0.0
    metrics.best_member_cost = 0.0
    
    return metrics


def compute_grid_metrics(
    history: List[SimulationStepResult],
    timestep_minutes: int = 15
) -> GridMetrics:
    """Compute grid feasibility metrics."""
    metrics = GridMetrics()
    
    total_steps = len(history)
    converged_steps = 0
    voltage_violations = 0
    voltage_violation_duration = 0.0
    max_voltage = -float('inf')
    min_voltage = float('inf')
    line_violations = 0
    trafo_violations = 0
    max_line_loading = 0.0
    max_trafo_loading = 0.0
    
    for step in history:
        if step.grid_diagnostics:
            converged = step.grid_diagnostics.get('power_flow_converged', True)
            if converged:
                converged_steps += 1
            
            # Process diagnostics
            for diag in step.grid_diagnostics.get('diagnostics', []):
                if diag.get('category') == 'voltage':
                    voltage_violations += 1
                    voltage_violation_duration += timestep_minutes / 60
                    v = diag.get('values', {}).get('voltage_pu', 1.0)
                    max_voltage = max(max_voltage, v)
                    min_voltage = min(min_voltage, v)
                elif diag.get('category') == 'line_loading':
                    line_violations += 1
                    ld = diag.get('values', {}).get('loading_pct', 0)
                    max_line_loading = max(max_line_loading, ld)
                elif diag.get('category') == 'transformer_loading':
                    trafo_violations += 1
                    ld = diag.get('values', {}).get('loading_pct', 0)
                    max_trafo_loading = max(max_trafo_loading, ld)
    
    metrics.power_flow_convergence_rate = converged_steps / total_steps if total_steps > 0 else 1.0
    metrics.voltage_violations_count = voltage_violations
    metrics.voltage_violation_duration_hours = voltage_violation_duration
    metrics.max_voltage_pu = max_voltage if max_voltage != -float('inf') else 1.0
    metrics.min_voltage_pu = min_voltage if min_voltage != float('inf') else 1.0
    metrics.line_loading_violations = line_violations
    metrics.transformer_loading_violations = trafo_violations
    metrics.max_line_loading_pct = max_line_loading
    metrics.max_transformer_loading_pct = max_trafo_loading
    metrics.nodal_power_balance_violations = 0
    
    return metrics


def compute_agent_metrics(
    history: List[SimulationStepResult],
    repair_history: List[Dict[str, Any]],
    token_usage: int,
    wall_clock_seconds: float
) -> AgentMetrics:
    """Compute code agent performance metrics."""
    metrics = AgentMetrics()
    
    total_steps = len(history)
    valid_steps = sum(1 for h in history if len(h.constraint_violations) == 0)
    sim_success = sum(1 for h in history if h.grid_diagnostics and h.grid_diagnostics.get('power_flow_converged', True))
    
    metrics.task_success_rate = 1.0 if valid_steps == total_steps else 0.0
    metrics.first_attempt_validity = 1.0 if valid_steps == total_steps else 0.0
    metrics.simulation_success_rate = sim_success / total_steps if total_steps > 0 else 1.0
    metrics.repair_success_rate = 1.0 if len(repair_history) == 0 else 0.5  # placeholder
    metrics.repair_iterations = len(repair_history)
    metrics.token_consumption = token_usage
    metrics.wall_clock_seconds = wall_clock_seconds
    metrics.constraint_violation_rate = 1.0 - (valid_steps / total_steps) if total_steps > 0 else 0.0
    metrics.report_completeness = 1.0
    
    return metrics


def calculate_gini_coefficient(values: List[float]) -> float:
    """Calculate Gini coefficient for fairness measurement."""
    if not values or len(values) < 2:
        return 0.0
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n


def compute_all_metrics(
    history: List[SimulationStepResult],
    scenario_config: Dict[str, Any],
    carbon_intensity: Optional[List[float]] = None,
    repair_history: Optional[List[Dict[str, Any]]] = None,
    token_usage: int = 0,
    wall_clock_seconds: float = 0.0
) -> Dict[str, Any]:
    """Compute all metrics at once."""
    return {
        'energy': compute_energy_metrics(history, scenario_config, carbon_intensity),
        'service': compute_service_metrics(history, scenario_config),
        'grid': compute_grid_metrics(history, scenario_config.get('timestep_minutes', 15)),
        'agent': compute_agent_metrics(history, repair_history or [], token_usage, wall_clock_seconds)
    }