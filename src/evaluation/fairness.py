"""Fairness analysis for multi-member energy communities."""
from typing import List, Dict, Any, Optional
import math
import numpy as np
import pandas as pd

from src.schemas.report import PerMemberMetrics, ServiceMetrics
from src.schemas.action import SimulationStepResult, ActionType
from src.schemas.scenario import ScenarioConfig
from src.evaluation.metrics import _time_to_hour


class FairnessAnalyzer:
    """Analyzes fairness of energy community outcomes."""
    
    def __init__(self, scenario_config: ScenarioConfig):
        self.scenario_config = scenario_config
        self.member_ids = [b.building_id for b in scenario_config.buildings]
        self.baseline_costs = None  # Will be set if baseline provided
        self.settlement_savings = None  # Will be set from settlement engine
    
    def set_baseline(self, baseline_history: List[SimulationStepResult]):
        """Set baseline history for savings calculation."""
        self.baseline_costs = self._compute_member_costs(baseline_history)
    
    def set_settlement_savings(self, savings: Dict[str, float]):
        """Set settlement savings from settlement engine."""
        self.settlement_savings = savings
    
    def analyze(self, history: List[SimulationStepResult]) -> ServiceMetrics:
        """Analyze fairness metrics from simulation history."""
        metrics = ServiceMetrics()

        # Compute per-member costs. Members whose cost data is corrupted by an
        # injected failure (NaN in any step) get cost None — service
        # interrupted, cost undefined — never 0.0, which would score a failed
        # member as free. Economic aggregates use valid members only, and the
        # interruption is reported explicitly (paper Scenario E convention).
        member_costs = self._compute_member_costs(history)
        interrupted = [m for m, cost in member_costs.items() if cost is None]
        valid_costs = [cost for cost in member_costs.values() if cost is not None]
        metrics.per_member_costs = member_costs
        metrics.members_interrupted = interrupted
        metrics.member_cost_coverage = (
            len(valid_costs) / len(self.member_ids) if self.member_ids else 1.0
        )

        # Compute savings vs baseline (if baseline available)
        if self.baseline_costs:
            metrics.per_member_savings = {}
            for member_id in self.member_ids:
                current_cost = member_costs.get(member_id)
                baseline_cost = self.baseline_costs.get(member_id, 0.0)
                if current_cost is None:
                    # Interrupted member: savings undefined, not zero.
                    metrics.per_member_savings[member_id] = None
                elif baseline_cost > 0:
                    # Savings = baseline - current (positive = saved money)
                    metrics.per_member_savings[member_id] = baseline_cost - current_cost
                else:
                    metrics.per_member_savings[member_id] = 0.0
        else:
            # No baseline available
            metrics.per_member_savings = {m: 0.0 for m in self.member_ids}

        # Gini coefficient over valid members only
        metrics.gini_coefficient = self._gini(valid_costs)

        # Worst/best member over valid members only
        if valid_costs:
            metrics.worst_member_cost = max(valid_costs)
            metrics.best_member_cost = min(valid_costs)

        return metrics

    def _compute_member_costs(self, history: List[SimulationStepResult]) -> Dict[str, Optional[float]]:
        """Compute cost per member.

        A member whose cost is NaN in any step (e.g. an injected sensor or
        supply failure) is marked ``None`` for the whole run: the service was
        interrupted, so no meaningful economic total exists for it.
        """
        costs: Dict[str, Optional[float]] = {m: 0.0 for m in self.member_ids}
        interrupted: set = set()

        for step in history:
            for member, cost in step.costs.items():
                if member not in costs:
                    continue
                if member in interrupted:
                    continue
                if cost is None or math.isnan(cost):
                    interrupted.add(member)
                    costs[member] = None
                    continue
                costs[member] += cost

        return costs
    
    def _gini(self, values: List[float]) -> float:
        """Calculate Gini coefficient."""
        if not values or len(values) < 2:
            return 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n
    
    def compute_detailed_per_member(self, history: List[SimulationStepResult]) -> List[PerMemberMetrics]:
        """Compute detailed per-member metrics."""
        results = []
        
        # Pre-calculate timestep hours
        timestep_hours = self.scenario_config.timestep_minutes / 60.0
        
        # Helper function to get tariff price based on hour of day and tariff config
        def _get_tariff_price(tariff_config, hour_of_day, is_import):
            if tariff_config is None:
                return 0.0
            # tariff_config is a TariffConfig object
            import_prices = getattr(tariff_config, "import_prices", {})
            export_prices = getattr(tariff_config, "export_prices", {})
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
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            member = PerMemberMetrics(
                member_id=bid,
                building_id=bid
            )
            
            # Filter history for this building (we check if building_id appears in observations keys)
            member_history = [h for h in history if bid in str(h.observations)]
            
            # Cost
            member.total_cost = 0.0
            
            # Grid import/export
            member.grid_import_kwh = 0.0
            member.grid_export_kwh = 0.0
            
            # PV self-consumption
            member.pv_self_consumption_kwh = 0.0
            
            # Battery cycles
            member.battery_cycles = 0.0
            
            # EV completion rate
            member.ev_completion_rate = 0.0
            
            # Comfort violations
            member.comfort_violations_hours = 0.0
            
            # Settlement savings from settlement engine
            member.settlement_savings = self.settlement_savings.get(bid, 0.0) if self.settlement_savings else 0.0
            
            # Service score (placeholder)
            member.service_score = 0.0
            
            # Accumulate metrics from history for this member
            for h in member_history:
                obs = h.observations
                
                # Grid import (positive = importing from grid)
                import_key = f"{bid}_net_electricity_consumption"
                if import_key in obs:
                    net_demand = float(obs[import_key])
                    if net_demand > 0:  # Importing from grid
                        member.grid_import_kwh += net_demand
                    elif net_demand < 0:  # Exporting to grid
                        member.grid_export_kwh += -net_demand
                    
                    # Calculate cost for this building at this step
                    current_hour = (h.timestep * self.scenario_config.timestep_minutes) / 60.0
                    hour_of_day = current_hour % 24.0
                    # Determine period
                    if hour_of_day < 7 or hour_of_day >= 23:
                        period = "off_peak"
                    elif hour_of_day < 12 or (hour_of_day >= 18 and hour_of_day < 21):
                        period = "mid_peak"
                    else:
                        period = "on_peak"
                    tariff_config = building.tariff
                    if net_demand != 0:
                        energy_kwh = abs(net_demand) * timestep_hours
                        if net_demand > 0:  # Importing
                            price = _get_tariff_price(tariff_config, hour_of_day, True)
                        else:  # Exporting
                            price = _get_tariff_price(tariff_config, hour_of_day, False)
                        building_cost = energy_kwh * price
                        # If exporting, cost is negative (credit)
                        if net_demand < 0:
                            building_cost = -building_cost
                        member.total_cost += building_cost
                    # If net_demand is zero, no cost
                # If we don't have the net demand observation, we fall back to step.costs for this building
                else:
                    # Fall back to step.costs for this building
                    building_cost = h.costs.get(bid, 0.0)
                    member.total_cost += building_cost
                
                # PV self-consumption: simplified as min(PV generation, load)
                pv_gen_key = f"{bid}_solar_generation"
                load_key = f"{bid}_non_shiftable_load"
                if pv_gen_key in obs and load_key in obs:
                    pv_gen = float(obs[pv_gen_key])
                    load = float(obs[load_key])
                    # Self-consumed PV = min(PV generation, load) - simplified
                    # Note: This doesn't subtract battery/EV/flexible load, but is a reasonable approximation
                    member.pv_self_consumption_kwh += min(pv_gen, max(load, 0))
                
                # Battery cycles: sum of absolute charge/discharge power over time
                for action in h.applied_actions.actions:
                    if action.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE]:
                        # Convert power to energy for this timestep
                        energy_kwh = abs(action.value_kw) * timestep_hours
                        member.battery_cycles += energy_kwh
                
                # EV completion rate: we'll compute SOC at departure per EV
                # We'll do this per building, assuming one EV per building for simplicity
                # We'll track the EV SOC over time and check at departure
                # We'll do this after the loop over history for efficiency, but for simplicity we do it here
                # We'll reset tracking per building
                pass  # We'll handle EV completion after the history loop
                
                # Comfort violations: use indoor dry bulb temperature
                temp_key = f"{bid}_indoor_dry_bulb_temperature"
                if temp_key in obs:
                    temp_value = float(obs[temp_key])
                    if temp_value < 20.0:
                        member.comfort_violations_hours += (20.0 - temp_value) * timestep_hours
                    elif temp_value > 25.0:
                        member.comfort_violations_hours += (temp_value - 25.0) * timestep_hours
            
            # Post-process: convert battery_cycles from total energy to cycles
            # Battery cycles = total energy charged/discharged / (2 * battery capacity)
            if building.battery:
                battery_capacity_kwh = building.battery.capacity_kwh
                if battery_capacity_kwh > 0:
                    member.battery_cycles = member.battery_cycles / (2.0 * battery_capacity_kwh)
            
            # Post-process: compute EV completion rate per building
            # We'll track the EV SOC over time for this building's EV(s)
            # We'll assume one EV per building for simplicity
            if building.evs:
                # We'll take the first EV for simplicity
                ev = building.evs[0]
                ev_id = f"{bid}_ev_0"
                # We'll simulate tracking by scanning member_history again
                ev_soc = ev.initial_soc  # Start with initial SOC
                ev_departed = False
                ev_departure_soc = None
                departure_hour = _time_to_hour(ev.departure_time)
                departure_timestep = int(departure_hour * 60 / self.scenario_config.timestep_minutes)
                
                for h in member_history:
                    # Update EV SOC from observation if available
                    obs = h.observations
                    # Observation key for EV SOC: "{building_id}_connected_electric_vehicle_at_charger_soc"
                    soc_key = f"{bid}_connected_electric_vehicle_at_charger_soc"
                    if soc_key in obs:
                        ev_soc = float(obs[soc_key])
                    
                    # Check for departure
                    if h.timestep >= departure_timestep and not ev_departed:
                        ev_departed = True
                        ev_departure_soc = ev_soc
                
                if ev_departed and ev_departure_soc is not None:
                    member.ev_completion_rate = 1.0 if ev_departure_soc >= ev.target_soc else 0.0
                else:
                    # If we don't have departure data, we can't compute completion rate
                    member.ev_completion_rate = 0.0
            
            # Post-process: convert grid import/export to kWh
            member.grid_import_kwh *= timestep_hours
            member.grid_export_kwh *= timestep_hours
            member.pv_self_consumption_kwh *= timestep_hours
            
            # Post-process: service score (placeholder)
            member.service_score = 0.0  # Could be a combination of other metrics
            
            results.append(member)
        
        return results
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
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            member = PerMemberMetrics(
                member_id=bid,
                building_id=bid
            )
            
            # Filter history for this building (we check if building_id appears in observations keys)
            member_history = [h for h in history if bid in str(h.observations)]
            
            # Cost
            member.total_cost = 0.0
            
            # Grid import/export
            member.grid_import_kwh = 0.0
            member.grid_export_kwh = 0.0
            
            # PV self-consumption
            member.pv_self_consumption_kwh = 0.0
            
            # Battery cycles
            member.battery_cycles = 0.0
            
            # EV completion rate
            member.ev_completion_rate = 0.0
            
            # Comfort violations
            member.comfort_violations_hours = 0.0
            
            # Settlement savings (placeholder)
            member.settlement_savings = 0.0
            
            # Service score (placeholder)
            member.service_score = 0.0
            
            # Accumulate metrics from history for this member
            for h in member_history:
                obs = h.observations
                
                # Grid import (positive = importing from grid)
                import_key = f"{bid}_net_electricity_consumption"
                if import_key in obs:
                    net_demand = float(obs[import_key])
                    if net_demand > 0:  # Importing from grid
                        member.grid_import_kwh += net_demand
                    elif net_demand < 0:  # Exporting to grid
                        member.grid_export_kwh += -net_demand
                    
                    # Calculate cost for this building at this step
                    current_hour = (h.timestep * self.scenario_config.timestep_minutes) / 60.0
                    hour_of_day = current_hour % 24.0
                    # Determine period
                    if hour_of_day < 7 or hour_of_day >= 23:
                        period = "off_peak"
                    elif hour_of_day < 12 or (hour_of_day >= 18 and hour_of_day < 21):
                        period = "mid_peak"
                    else:
                        period = "on_peak"
                    tariff_config = building.tariff
                    if net_demand != 0:
                        energy_kwh = abs(net_demand) * timestep_hours
                        if net_demand > 0:  # Importing
                            price = _get_tariff_price(tariff_config, hour_of_day, True)
                        else:  # Exporting
                            price = _get_tariff_price(tariff_config, hour_of_day, False)
                        building_cost = energy_kwh * price
                        # If exporting, cost is negative (credit)
                        if net_demand < 0:
                            building_cost = -building_cost
                        member.total_cost += building_cost
                    # If net_demand is zero, no cost
                # If we don't have the net demand observation, we fall back to step.costs for this building
                else:
                    # Fall back to step.costs for this building
                    building_cost = h.costs.get(bid, 0.0)
                    member.total_cost += building_cost
                
                # PV self-consumption: simplified as min(PV generation, load)
                pv_gen_key = f"{bid}_solar_generation"
                load_key = f"{bid}_non_shiftable_load"
                if pv_gen_key in obs and load_key in obs:
                    pv_gen = float(obs[pv_gen_key])
                    load = float(obs[load_key])
                    # Self-consumed PV = min(PV generation, load) - simplified
                    # Note: This doesn't subtract battery/EV/flexible load, but is a reasonable approximation
                    member.pv_self_consumption_kwh += min(pv_gen, max(load, 0))
                
                # Battery cycles: sum of absolute charge/discharge power over time
                for action in h.applied_actions.actions:
                    if action.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE]:
                        # Convert power to energy for this timestep
                        energy_kwh = abs(action.value_kw) * timestep_hours
                        member.battery_cycles += energy_kwh
                
                # EV completion rate: we'll compute SOC at departure per EV
                # We'll do this per building, assuming one EV per building for simplicity
                # We'll track the EV SOC over time and check at departure
                # We'll do this after the loop over history for efficiency, but for simplicity we do it here
                # We'll reset tracking per building
                pass  # We'll handle EV completion after the history loop
                
                # Comfort violations: use indoor dry bulb temperature
                temp_key = f"{bid}_indoor_dry_bulb_temperature"
                if temp_key in obs:
                    temp_value = float(obs[temp_key])
                    if temp_value < 20.0:
                        member.comfort_violations_hours += (20.0 - temp_value) * timestep_hours
                    elif temp_value > 25.0:
                        member.comfort_violations_hours += (temp_value - 25.0) * timestep_hours
            
            # Post-process: convert battery_cycles from total energy to cycles
            # Battery cycles = total energy charged/discharged / (2 * battery capacity)
            if building.battery:
                battery_capacity_kwh = building.battery.capacity_kwh
                if battery_capacity_kwh > 0:
                    member.battery_cycles = member.battery_cycles / (2.0 * battery_capacity_kwh)
            
            # Post-process: compute EV completion rate per building
            # We'll track the EV SOC over time for this building's EV(s)
            # We'll assume one EV per building for simplicity
            if building.evs:
                # We'll take the first EV for simplicity
                ev = building.evs[0]
                ev_id = f"{bid}_ev_0"
                # We'll simulate tracking by scanning member_history again
                ev_soc = ev.initial_soc  # Start with initial SOC
                ev_departed = False
                ev_departure_soc = None
                departure_hour = _time_to_hour(ev.departure_time)
                departure_timestep = int(departure_hour * 60 / self.scenario_config.timestep_minutes)
                
                for h in member_history:
                    # Update EV SOC from observation if available
                    obs = h.observations
                    # Observation key for EV SOC: "{building_id}_connected_electric_vehicle_at_charger_soc"
                    soc_key = f"{bid}_connected_electric_vehicle_at_charger_soc"
                    if soc_key in obs:
                        ev_soc = float(obs[soc_key])
                    
                    # Check for departure
                    if h.timestep >= departure_timestep and not ev_departed:
                        ev_departed = True
                        ev_departure_soc = ev_soc
                
                if ev_departed and ev_departure_soc is not None:
                    member.ev_completion_rate = 1.0 if ev_departure_soc >= ev.target_soc else 0.0
                else:
                    # If we don't have departure data, we can't compute completion rate
                    member.ev_completion_rate = 0.0
            
            # Post-process: convert grid import/export to kWh
            member.grid_import_kwh *= timestep_hours
            member.grid_export_kwh *= timestep_hours
            member.pv_self_consumption_kwh *= timestep_hours
            
            # Post-process: service score (placeholder)
            member.service_score = 0.0  # Could be a combination of other metrics
            
            results.append(member)
        
        return results
def compute_fairness_metrics(
    history: List[SimulationStepResult],
    scenario_config: ScenarioConfig
) -> ServiceMetrics:
    """Compute fairness metrics."""
    analyzer = FairnessAnalyzer(scenario_config)
    return analyzer.analyze(history)


def compute_per_member_metrics(
    history: List[SimulationStepResult],
    scenario_config: ScenarioConfig
) -> List[PerMemberMetrics]:
    """Compute detailed per-member metrics."""
    analyzer = FairnessAnalyzer(scenario_config)
    return analyzer.compute_detailed_per_member(history)