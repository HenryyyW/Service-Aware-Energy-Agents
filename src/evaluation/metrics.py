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


def _get_tariff_price(tariff_config, hour_of_day, is_import):
    """Get tariff price for given hour and import/export direction."""
    if tariff_config is None:
        return 0.0
    # tariff_config is a dict with keys "import_prices" and "export_prices"
    import_prices = tariff_config.get("import_prices", {})
    export_prices = tariff_config.get("export_prices", {})

    # Determine period
    if hour_of_day < 7 or hour_of_day >= 23:
        period = "off_peak"
    elif hour_of_day < 12 or (hour_of_day >= 18 and hour_of_day < 21):
        period = "mid_peak"
    else:
        period = "on_peak"
    if is_import:
        return import_prices.get(period, 0.0)
    else:
        return export_prices.get(period, 0.0)


def compute_energy_metrics(
    history: List[SimulationStepResult],
    scenario_config: Dict[str, Any],
    carbon_intensity: Optional[List[float]] = None,
    timestep_hours: Optional[float] = None
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
    valid_building_steps = 0
    total_building_steps = 0

    # Determine actual timestep in hours
    # Priority: explicit parameter > scenario config default > history-derived
    if timestep_hours is not None:
        pass  # Use provided value
    else:
        timestep_hours = scenario_config.get("timestep_minutes", 15) / 60.0
        # Only fall back to history-derived if scenario config doesn't have timestep
        if "timestep_minutes" not in scenario_config and len(history) >= 2:
            timestep_hours = (history[1].timestep - history[0].timestep) * 1.0  # hours per step

    # Build PV nominal power lookup from scenario config (in kW)
    pv_nominal_power = {}
    buildings = scenario_config.get("buildings", [])
    if not isinstance(buildings, list):
        buildings = list(buildings)
    for building in buildings:
        if isinstance(building, dict):
            bid = building.get("building_id")
            pv = building.get("pv")
            if pv:
                pv_nominal_power[bid] = pv.get("capacity_kw", 0.0)
            else:
                pv_nominal_power[bid] = 0.0
        else:
            bid = getattr(building, "building_id", None)
            pv = getattr(building, "pv", None)
            if pv:
                pv_nominal_power[bid] = getattr(pv, "capacity_kw", 0.0)
            else:
                pv_nominal_power[bid] = 0.0

    # Build tariff lookup for cost calculation from observations
    building_tariffs = {}
    for building in buildings:
        if isinstance(building, dict):
            bid = building.get("building_id")
            tariff = building.get("tariff")
            if tariff:
                building_tariffs[bid] = tariff
        else:
            bid = getattr(building, "building_id", None)
            tariff = getattr(building, "tariff", None)
            if tariff:
                building_tariffs[bid] = tariff

    for step in history:
        # Costs - prefer step.costs, fallback to calculating from observations
        step_cost = sum(step.costs.values())
        if step_cost == 0.0 and building_tariffs:
            # Calculate costs from net_electricity_consumption and tariff
            obs = step.observations
            hour_of_day = (step.timestep * timestep_hours) % 24.0
            for bid, tariff in building_tariffs.items():
                net_key = f"{bid}_net_electricity_consumption"
                if net_key in obs:
                    net_val = obs[net_key]
                    if isinstance(net_val, (int, float)) and np.isfinite(net_val):
                        net_kw = float(net_val)
                        energy_kwh = net_kw * timestep_hours
                        price = _get_tariff_price(tariff, hour_of_day, energy_kwh > 0)
                        step_cost += energy_kwh * price
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
        # Observations are a flat dict with keys like "building_0_solar_generation"
        # CityLearn solar_generation is in p.u. (per unit of PV capacity)
        # Convert to kW by multiplying by capacity_kw
        for bid in pv_nominal_power:
            key = f"{bid}_solar_generation"
            if key in obs:
                value = obs[key]
                pv_gen_total += float(value) * pv_nominal_power[bid]  # p.u. * kW = kW
            
            # Self-consumption: min(PV generation, load) per building
            if f"{bid}_solar_generation" in obs and f"{bid}_non_shiftable_load" in obs:
                pv_gen = float(obs[f"{bid}_solar_generation"]) * pv_nominal_power[bid]  # p.u. * kW = kW
                load = float(obs[f"{bid}_non_shiftable_load"])
                pv_self_consumed += min(pv_gen, max(load, 0))
        
        # Track cost coverage: count building-steps with valid net_electricity_consumption
        for bid in pv_nominal_power:
            net_key = f"{bid}_net_electricity_consumption"
            total_building_steps += 1
            if net_key in obs:
                net_val = obs[net_key]
                if isinstance(net_val, (int, float)) and np.isfinite(net_val):
                    valid_building_steps += 1
        
        # Battery throughput
        for action in step.applied_actions.actions:
            if action.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE]:
                battery_throughput += abs(action.value_kw)
    
    # Convert to kWh (using actual timestep from history)
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
    metrics.cost_coverage = valid_building_steps / total_building_steps if total_building_steps > 0 else 1.0
    metrics.invalid_cost_steps = total_building_steps - valid_building_steps
    
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
    buildings = scenario_config.get('buildings', [])
    if not isinstance(buildings, list):
        buildings = list(buildings)
    for building in buildings:
        if isinstance(building, dict):
            bid = building.get('building_id')
            evs = building.get('evs', [])
        else:
            bid = getattr(building, 'building_id', None)
            evs = getattr(building, 'evs', [])
        if not evs:
            continue
        for i, ev in enumerate(evs):
            if isinstance(ev, dict):
                ev_id = f"{bid}_ev_{i}"
                ev_target_soc[ev_id] = ev.get('target_soc', 0.8)
                departure_hour = _time_to_hour(ev.get('departure_time', '07:00'))
            else:
                ev_id = f"{bid}_ev_{i}"
                ev_target_soc[ev_id] = getattr(ev, 'target_soc', 0.8)
                departure_hour = _time_to_hour(getattr(ev, 'departure_time', '07:00'))
            # Convert to timestep
            timestep = int(departure_hour * 60 / scenario_config.get('timestep_minutes', 15))
            ev_departures[ev_id] = timestep
            building_evs[ev_id] = bid
    
    # Track EV SOC at departure from observations
    # Observations use keys like "b0_ev_0_connected", "b0_ev_0_soc", "b0_ev_0_required_soc"
    ev_soc_at_departure = {}
    ev_was_connected = {}  # Track previous connection state
    ev_last_soc = {}  # Track last known SOC while connected
    
    for step in history:
        obs = step.observations
        for key, value in obs.items():
            if key.endswith('_connected') and 'ev_' in key:
                # Extract EV ID from key (e.g., "b0_ev_0_connected" -> "b0_ev_0")
                ev_id = key.rsplit('_', 1)[0]
                connected = float(value) > 0.5
                was_connected = ev_was_connected.get(ev_id, False)
                
                if was_connected and not connected:
                    # Departure detected - use last known SOC while connected
                    req_key = f"{ev_id}_required_soc"
                    last_soc = ev_last_soc.get(ev_id, 0.0)
                    target = float(obs.get(req_key, 0.8))
                    ev_soc_at_departure[ev_id] = (last_soc, target)
                
                ev_was_connected[ev_id] = connected
            
            # Track last known SOC while connected
            if key.endswith('_soc') and 'ev_' in key and not key.endswith('_required_soc'):
                ev_id = key.rsplit('_', 1)[0]
                # Only update if currently connected
                connected_key = f"{ev_id}_connected"
                if obs.get(connected_key, 0) > 0.5:
                    ev_last_soc[ev_id] = float(value)
    
    # Calculate EV metrics
    if ev_soc_at_departure:
        completed = sum(1 for soc, target in ev_soc_at_departure.values() if soc >= target)
        total = len(ev_soc_at_departure)
        metrics.ev_completion_rate = completed / total
        metrics.ev_avg_soc_at_departure = np.mean([soc for soc, _ in ev_soc_at_departure.values()])
        metrics.ev_worst_soc_at_departure = min(soc for soc, _ in ev_soc_at_departure.values())
    else:
        # No departures observed
        metrics.ev_completion_rate = 1.0
        metrics.ev_avg_soc_at_departure = 0.8
        metrics.ev_worst_soc_at_departure = 0.8
    
    # Comfort violations - calculate from indoor temperature observations
    # Assume comfort band 20-25°C
    comfort_violation = 0.0
    timestep_h = scenario_config.get('timestep_minutes', 15) / 60.0
    for step in history:
        obs = step.observations
        for key, value in obs.items():
            if 'indoor_dry_bulb_temperature' in key:
                temp = float(value)
                if temp < 20.0:
                    comfort_violation += (20.0 - temp) * timestep_h
                elif temp > 25.0:
                    comfort_violation += (temp - 25.0) * timestep_h
    metrics.comfort_violation_degree_hours = comfort_violation
    
    # Flexible load completion
    metrics.flexible_load_completion_rate = 1.0
    metrics.flexible_load_avg_delay_hours = 0.0
    
    # DR delivery
    metrics.dr_requested_kw = 0.0
    metrics.dr_delivered_kw = 0.0
    metrics.dr_credited_kw = 0.0
    
    # Per-member costs - calculate from observations and tariff
    member_ids = []
    building_tariffs = {}
    for building in buildings:
        if isinstance(building, dict):
            bid = building.get("building_id")
            tariff = building.get("tariff")
            if bid:
                member_ids.append(bid)
            if tariff:
                building_tariffs[bid] = tariff
        else:
            bid = getattr(building, "building_id", None)
            tariff = getattr(building, "tariff", None)
            if bid:
                member_ids.append(bid)
            if tariff:
                building_tariffs[bid] = tariff
    
    member_costs = {m: 0.0 for m in member_ids}
    interrupted = set()
    timestep_h = scenario_config.get('timestep_minutes', 15) / 60.0
    
    for step in history:
        obs = step.observations
        hour_of_day = (step.timestep * timestep_h) % 24.0
        for member in member_ids:
            if member in interrupted:
                continue
            net_key = f"{member}_net_electricity_consumption"
            tariff = building_tariffs.get(member)
            if net_key in obs and tariff is not None:
                net_val = obs[net_key]
                if isinstance(net_val, (int, float)) and np.isfinite(net_val):
                    net_kw = float(net_val)
                    energy_kwh = net_kw * timestep_h
                    price = _get_tariff_price(tariff, hour_of_day, energy_kwh > 0)
                    member_costs[member] += energy_kwh * price
                    continue
                else:
                    # Observation exists but is NaN/inf - mark as interrupted
                    interrupted.add(member)
                    member_costs[member] = None
                    continue
            # No observation/tariff: fall back to step.costs
            step_cost = step.costs.get(member, 0.0)
            if step_cost is None or (isinstance(step_cost, float) and not np.isfinite(step_cost)):
                interrupted.add(member)
                member_costs[member] = None
                continue
            member_costs[member] += float(step_cost)
    
    valid_costs = [c for c in member_costs.values() if c is not None]
    metrics.per_member_costs = member_costs
    metrics.members_interrupted = list(interrupted)
    metrics.member_cost_coverage = len(valid_costs) / len(member_ids) if member_ids else 1.0
    
    # Fairness
    metrics.gini_coefficient = calculate_gini_coefficient(valid_costs) if valid_costs else 0.0
    metrics.worst_member_cost = max(valid_costs) if valid_costs else 0.0
    metrics.best_member_cost = min(valid_costs) if valid_costs else 0.0
    
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
    wall_clock_seconds: float = 0.0,
    timestep_hours: Optional[float] = None
) -> Dict[str, Any]:
    """Compute all metrics at once."""
    return {
        'energy': compute_energy_metrics(history, scenario_config, carbon_intensity, timestep_hours),
        'service': compute_service_metrics(history, scenario_config),
        'grid': compute_grid_metrics(history, scenario_config.get('timestep_minutes', 15)),
        'agent': compute_agent_metrics(history, repair_history or [], token_usage, wall_clock_seconds)
    }