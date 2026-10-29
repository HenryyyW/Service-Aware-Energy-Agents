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
    
    # Helper function to get tariff price based on hour of day and tariff config
    def _get_tariff_price(tariff_config, hour_of_day, is_import):
        if tariff_config is None:
            return 0.0
        # tariff_config is a dict with keys "import_prices" and "export_prices"
        import_prices = tariff_config.get("import_prices", {})
        export_prices = tariff_config.get("export_prices", {})
        # Determine period based on hour of day
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
    
    for step in history:
        # Grid import/export from observations (sum of building net demands)
        obs = step.observations
        step_import = 0.0
        step_export = 0.0
        step_cost = 0.0  # Initialize step cost
        
        for building in scenario_config.get('buildings', []):
            bid = building['building_id']
            net_demand_key = f"{bid}_net_electricity_consumption"
            if net_demand_key in obs:
                net_demand_kw = float(obs[net_demand_key])
                if net_demand_kw > 0:
                    step_import += net_demand_kw
                elif net_demand_kw < 0:
                    step_export += -net_demand_kw
                
                # Calculate cost for this building at this step
                timestep_hours = scenario_config.get('timestep_minutes', 15) / 60.0
                energy_kwh = net_demand_kw * timestep_hours
                current_hour = (step.timestep * scenario_config.get('timestep_minutes', 15)) / 60.0
                hour_of_day = current_hour % 24.0
                # Determine period
                if hour_of_day < 7 or hour_of_day >= 23:
                    period = "off_peak"
                elif hour_of_day < 12 or (hour_of_day >= 18 and hour_of_day < 21):
                    period = "mid_peak"
                else:
                    period = "on_peak"
                tariff_config = building.get('tariff')
                if tariff_config is not None:
                    if energy_kwh > 0:
                        # importing
                        price = _get_tariff_price(tariff_config, hour_of_day, True)
                    else:
                        # exporting
                        price = _get_tariff_price(tariff_config, hour_of_day, False)
                    building_cost = energy_kwh * price
                    step_cost += building_cost
                else:
                    # Fall back to step.costs for this building
                    building_cost = step.costs.get(bid, 0.0)
                    step_cost += building_cost
            else:
                # If we don't have the net demand observation, we fall back to step.costs for this building
                building_cost = step.costs.get(bid, 0.0)
                step_cost += building_cost
        
        # Accumulate step cost to total cost
        total_cost += step_cost
        
        grid_import += step_import
        grid_export += step_export
        
        # Peak demand (community level)
        peak_demand = max(peak_demand, step_import)
        demand_values.append(step_import)
        
        # PV generation and self-consumption (from observations)
        for key, value in obs.items():
            if 'solar_generation' in key:
                pv_gen_total += value
            # Net electricity consumption negative means exporting (excess PV)
            # But we need to be careful not to double count
            # Self-consumed PV = PV generation - exported PV
            # Exported PV = max(0, -net_electricity_consumption - non_shiftable_load - battery_charge - EV_charge - flexible_load)
            # This is complex, so we'll use a simpler approach for now
            # In a more complete implementation, we'd track this from actions
        
        # For PV self-consumption, we'll calculate from actions when possible
        # Fallback to observation-based calculation
        pv_export = 0.0
        pv_import = 0.0  # This would be from grid when PV insufficient
        
        # Look for explicit PV curtailment
        if 'solar_curtailment' in obs:
            pv_curtailed += float(obs['solar_curtailment'])
        
        # Better approach: calculate from energy balance
        # This is simplified - a production system would need more detailed tracking
    
    # Battery throughput from actions
    for step in history:
        for action in step.applied_actions.actions:
            if action.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE]:
                battery_throughput += abs(action.value_kw)
    
    # Convert to kWh (assuming timestep in minutes)
    timestep_hours = scenario_config.get('timestep_minutes', 15) / 60
    grid_import *= timestep_hours
    grid_export *= timestep_hours
    pv_gen_total *= timestep_hours
    # Note: pv_self_consumed needs proper calculation
    pv_curtailed *= timestep_hours
    
    # Estimate PV self-consumed: PV generation minus what's exported to grid
    # This is approximate but better than zero
    pv_self_consumed = max(0, pv_gen_total - grid_export)
    
    # Battery cycles (rough estimate)
    # Use average battery capacity from scenario
    total_battery_capacity = 0.0
    building_count = 0
    for building in scenario_config.get('buildings', []):
        if building.get('battery'):
            total_battery_capacity += building['battery'].get('capacity_kwh', 0)
            building_count += 1
    avg_battery_capacity = total_battery_capacity / max(building_count, 1)
    battery_cycles = battery_throughput / (2 * avg_battery_capacity) if avg_battery_capacity > 0 else 0
    
    # Load factor
    avg_demand = np.mean(demand_values) if demand_values else 0
    load_factor = avg_demand / peak_demand if peak_demand > 0 else 0
    
    # Carbon emissions
    carbon_emissions = 0.0
    if carbon_intensity:
        for i, step in enumerate(history):
            obs = step.observations
            step_import = 0.0
            for building in scenario_config.get('buildings', []):
                bid = building['building_id']
                net_demand_key = f"{bid}_net_electricity_consumption"
                if net_demand_key in obs:
                    net_demand = float(obs[net_demand_key])
                    if net_demand > 0:
                        step_import += net_demand
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
def _compute_observed_ev_metrics(history: List[SimulationStepResult]):
    """EV service metrics from the adapter's explicit EV observations.

    Returns ``(completion_rate, avg_soc, worst_soc)``, or ``None`` when the
    history predates the ``{building}_ev_{i}_*`` observation keys. A departure is
    the step where ``*_connected`` changes from 1 to 0; SOC and the required SOC
    are taken from the last connected step.
    """
    soc: Dict[str, float] = {}
    required: Dict[str, float] = {}
    connected_prev: Dict[str, bool] = {}
    departures: List[tuple] = []
    saw_ev_observation = False

    for step in history:
        observations = step.observations
        prefixes = {
            key[: -len("_connected")]
            for key in observations
            if key.endswith("_connected") and "_ev_" in key
        }
        if prefixes:
            saw_ev_observation = True
        for prefix in prefixes:
            is_connected = bool(observations.get(f"{prefix}_connected"))
            if is_connected:
                if f"{prefix}_soc" in observations:
                    soc[prefix] = float(observations[f"{prefix}_soc"])
                if f"{prefix}_required_soc" in observations:
                    required[prefix] = float(observations[f"{prefix}_required_soc"])
            elif connected_prev.get(prefix, False):
                if prefix in soc:
                    departures.append((soc[prefix], required.get(prefix, 0.8)))
            connected_prev[prefix] = is_connected

    if not saw_ev_observation:
        return None
    if not departures:
        return (0.0, 0.0, 0.0)

    completed = sum(1 for value, target in departures if value >= target)
    values = [value for value, _ in departures]
    return (
        completed / len(values),
        float(np.mean(values)),
        float(np.min(values)),
    )


def compute_service_metrics(
    history: List[SimulationStepResult],
    scenario_config: Dict[str, Any]
) -> ServiceMetrics:
    """Compute service and fairness metrics from simulation history."""
    metrics = ServiceMetrics()

    observed_ev = _compute_observed_ev_metrics(history)
    if observed_ev is not None:
        (
            metrics.ev_completion_rate,
            metrics.ev_avg_soc_at_departure,
            metrics.ev_worst_soc_at_departure,
        ) = observed_ev

    # EV metrics
    ev_departures = {}
    ev_target_soc = {}
    building_evs = {}
    ev_soc_tracking = {}  # Track SOC over time for each EV
    ev_departure_soc = {}  # SOC at departure time
    ev_departed = {}       # Track which EVs have departed
    
    # Extract EV configs from scenario
    ev_arrivals = {}
    for building in scenario_config.get('buildings', []):
        for i, ev in enumerate(building.get('evs') or []):
            ev_id = f"{building['building_id']}_ev_{i}"
            ev_target_soc[ev_id] = ev.get('target_soc', 0.8)
            arrival_hour = _time_to_hour(ev.get('arrival_time', '00:00'))
            departure_hour = _time_to_hour(ev.get('departure_time', '07:00'))
            # Convert to timestep
            timestep_minutes = scenario_config.get('timestep_minutes', 15)
            arrival_timestep = int(arrival_hour * 60 / timestep_minutes)
            departure_timestep = int(departure_hour * 60 / timestep_minutes)
            ev_departures[ev_id] = departure_timestep
            ev_arrivals[ev_id] = arrival_timestep
            building_evs[ev_id] = building['building_id']
            ev_soc_tracking[ev_id] = ev.get('initial_soc', 0.3)
            ev_departed[ev_id] = False
    
    # Process history to track EV SOC and departures
    for step in history:
        timestep = step.timestep
        obs = step.observations
        
        # Update EV SOC from observations if available
        for ev_id in ev_soc_tracking.keys():
            # Extract building_id from ev_id (format: "{building_id}_ev_{i}")
            building_id = ev_id.split('_ev_')[0]
            soc_key = f"{building_id}_connected_electric_vehicle_at_charger_soc"
            if soc_key in obs:
                ev_soc_tracking[ev_id] = float(obs[soc_key])
        
        # Check for departures
        for ev_id, departure_timestep in ev_departures.items():
            if timestep >= departure_timestep and not ev_departed.get(ev_id, False):
                ev_departed[ev_id] = True
                if ev_id in ev_soc_tracking:
                    ev_departure_soc[ev_id] = ev_soc_tracking[ev_id]
    
    # Fallback for histories that predate the explicit EV observation keys.
    if observed_ev is None:
        if ev_departure_soc:
            departed_socs = list(ev_departure_soc.values())
            metrics.ev_avg_soc_at_departure = np.mean(departed_socs)
            metrics.ev_worst_soc_at_departure = np.min(departed_socs)

            # Completion rate: percentage of EVs that reached target SOC at departure
            completed_count = sum(1 for ev_id, soc in ev_departure_soc.items()
                                 if soc >= ev_target_soc.get(ev_id, 0.8))
            metrics.ev_completion_rate = completed_count / len(ev_departure_soc) if ev_departure_soc else 0.0
        else:
            metrics.ev_completion_rate = 0.0
            metrics.ev_avg_soc_at_departure = 0.0
            metrics.ev_worst_soc_at_departure = 0.0
    
    # Comfort violations: use indoor dry bulb temperature per building
    comfort_violations = 0.0
    timestep_hours = scenario_config.get('timestep_minutes', 15) / 60.0
    for step in history:
        obs = step.observations
        for building in scenario_config.get('buildings', []):
            bid = building['building_id']
            temp_key = f"{bid}_indoor_dry_bulb_temperature"
            if temp_key in obs:
                temp_value = float(obs[temp_key])
                if temp_value < 20.0:
                    comfort_violations += (20.0 - temp_value) * timestep_hours
                elif temp_value > 25.0:
                    comfort_violations += (temp_value - 25.0) * timestep_hours
    metrics.comfort_violation_degree_hours = comfort_violations
    
    # Flexible load completion
    fl_progress = {}  # Track progress for each flexible load
    fl_target = {}    # Track target energy for each flexible load
    fl_completed = {} # Track which flexible loads have completed
    
    # Initialize flexible load tracking
    for building in scenario_config.get('buildings', []):
        for i, fl in enumerate(building.get('flexible_loads') or []):
            fl_id = f"{building['building_id']}_flex_{i}"
            fl_target[fl_id] = fl.get('energy_kwh', 0.0)
            fl_progress[fl_id] = 0.0
            fl_completed[fl_id] = False
    
    # Process history to track flexible load progress
    for step in history:
        obs = step.observations
        # Update progress from observations if available
        for fl_id in fl_progress.keys():
            progress_key = f"{fl_id}_progress"
            if progress_key in obs:
                fl_progress[fl_id] = float(obs[progress_key])
        
        # Also try to infer from actions
        for action in step.applied_actions.actions:
            if action.action_type == ActionType.FLEXIBLE_LOAD:
                fl_id = action.asset_id
                if fl_id in fl_progress:
                    # Energy added this timestep
                    energy_added = abs(action.value_kw) * scenario_config.get('timestep_minutes', 15) / 60
                    fl_progress[fl_id] = min(fl_progress.get(fl_id, 0.0) + energy_added, fl_target.get(fl_id, 0.0))
    
    # Calculate completion
    completed_fl_count = sum(1 for fl_id, progress in fl_progress.items() 
                            if progress >= fl_target.get(fl_id, 0.0) * 0.95)  # Allow 5% tolerance
    total_fl_count = len(fl_target)
    metrics.flexible_load_completion_rate = completed_fl_count / total_fl_count if total_fl_count > 0 else 0.0
    
    # Average delay (simplified)
    metrics.flexible_load_avg_delay_hours = 0.0  # Would need more detailed tracking
    
    # DR delivery (simplified)
    metrics.dr_requested_kw = 0.0
    metrics.dr_delivered_kw = 0.0
    metrics.dr_credited_kw = 0.0
    
    # Per-member costs (will be computed in fairness analysis)
    metrics.per_member_costs = {}
    metrics.per_member_savings = {}
    
    # Fairness metrics will be computed separately
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