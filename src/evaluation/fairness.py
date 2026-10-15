"""Fairness analysis for multi-member energy communities."""
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from src.schemas.report import PerMemberMetrics, ServiceMetrics
from src.schemas.action import SimulationStepResult
from src.schemas.scenario import ScenarioConfig


class FairnessAnalyzer:
    """Analyzes fairness of energy community outcomes."""
    
    def __init__(self, scenario_config: ScenarioConfig):
        self.scenario_config = scenario_config
        self.member_ids = [b.building_id for b in scenario_config.buildings]
    
    def analyze(self, history: List[SimulationStepResult]) -> ServiceMetrics:
        """Analyze fairness metrics from simulation history."""
        metrics = ServiceMetrics()
        
        # Compute per-member costs
        member_costs = self._compute_member_costs(history)
        metrics.per_member_costs = member_costs
        
        # Compute savings vs baseline (placeholder)
        metrics.per_member_savings = {m: 0.0 for m in self.member_ids}
        
        # Gini coefficient
        cost_values = list(member_costs.values())
        metrics.gini_coefficient = self._gini(cost_values)
        
        # Worst/best member
        if cost_values:
            metrics.worst_member_cost = max(cost_values)
            metrics.best_member_cost = min(cost_values)
        
        return metrics
    
    def _compute_member_costs(self, history: List[SimulationStepResult]) -> Dict[str, float]:
        """Compute cost per member."""
        costs = {m: 0.0 for m in self.member_ids}
        
        for step in history:
            for member, cost in step.costs.items():
                if member in costs:
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
        
        for building in self.scenario_config.buildings:
            bid = building.building_id
            member = PerMemberMetrics(
                member_id=bid,
                building_id=bid
            )
            
            # Aggregate metrics for this member
            member_history = [h for h in history if bid in str(h.observations)]
            
            # Cost
            member.total_cost = sum(h.costs.get(bid, 0) for h in history)
            
            # Grid import/export
            member.grid_import_kwh = 0.0
            member.grid_export_kwh = 0.0
            
            # PV self-consumption
            member.pv_self_consumption_kwh = 0.0
            
            # Battery cycles
            member.battery_cycles = 0.0
            
            # EV completion
            member.ev_completion_rate = 1.0
            
            # Comfort
            member.comfort_violations_hours = 0.0
            
            # Settlement
            member.settlement_savings = 0.0
            
            # Service score (composite)
            member.service_score = 1.0
            
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