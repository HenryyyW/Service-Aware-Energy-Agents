"""Verification harness for proving repairs fix real violations."""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging
from src.schemas.report import ExperimentResult

logger = logging.getLogger(__name__)


@dataclass
class ViolationTarget:
    category: str
    metric_key: str
    threshold: Optional[float] = None
    is_upper_bound: bool = True


@dataclass
class VerificationResult:
    target: ViolationTarget
    before_value: float
    after_value: float
    threshold: Optional[float]
    improved: bool
    fixed: bool
    improvement_pct: float
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def repaired(self) -> bool:
        return self.fixed or self.improved


@dataclass
class HarnessReport:
    run_id_before: str
    run_id_after: str
    verification_results: List[VerificationResult]
    all_fixed: bool
    any_regression: bool
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.all_fixed and not self.any_regression


class VerificationHarness:
    def __init__(self):
        self.targets = []

    def add_target(self, target: ViolationTarget):
        self.targets.append(target)

    def verify_repair(self, before_result: ExperimentResult, after_result: ExperimentResult, targets: Optional[List[ViolationTarget]] = None) -> HarnessReport:
        targets = targets or self.targets
        results = []
        for t in targets:
            results.append(self._verify_target(before_result, after_result, t))
        all_fixed = all(r.fixed for r in results) if results else True
        any_reg = any((not r.improved) and r.before_value > 0 for r in results)
        fixed_count = sum(1 for r in results if r.fixed)
        total = len(results)
        summary = f"Verified {fixed_count}/{total} targeted violations fixed."
        if all_fixed:
            summary += " All targeted violations resolved."
        else:
            summary += " Some violations remain."
        if any_reg:
            summary += " WARNING: potential regressions detected."
        return HarnessReport(run_id_before=before_result.run_id, run_id_after=after_result.run_id, verification_results=results, all_fixed=all_fixed, any_regression=any_reg, summary=summary)

    def _verify_target(self, before_result: ExperimentResult, after_result: ExperimentResult, target: ViolationTarget) -> VerificationResult:
        bv = self._extract_metric(before_result, target)
        av = self._extract_metric(after_result, target)
        th = target.threshold
        was_v = False
        if th is not None:
            was_v = bv > th if target.is_upper_bound else bv < th
        now_v = False
        if th is not None:
            now_v = av > th if target.is_upper_bound else av < th
        fixed = was_v and not now_v
        improved = av < bv if target.is_upper_bound else av > bv
        if bv == 0:
            imp = 100.0 if av == 0 else -float('inf')
        else:
            imp = ((bv - av) / abs(bv)) * 100
            if not target.is_upper_bound:
                imp = -imp
        return VerificationResult(target=target, before_value=bv, after_value=av, threshold=th, improved=improved, fixed=fixed, improvement_pct=imp, details={'was_violating': was_v, 'now_violating': now_v})

    def _extract_metric(self, result: ExperimentResult, target: ViolationTarget) -> float:
        g = result.grid
        s = result.service
        k = target.metric_key
        if k == 'voltage_violations_count':
            return float(g.voltage_violations_count)
        if k == 'max_voltage_pu':
            return float(g.max_voltage_pu)
        if k == 'min_voltage_pu':
            return float(g.min_voltage_pu)
        if k == 'line_loading_violations':
            return float(g.line_loading_violations)
        if k == 'max_line_loading_pct':
            return float(g.max_line_loading_pct)
        if k == 'transformer_loading_violations':
            return float(g.transformer_loading_violations)
        if k == 'max_transformer_loading_pct':
            return float(g.max_transformer_loading_pct)
        if k == 'power_flow_convergence_rate':
            return float(g.power_flow_convergence_rate)
        if k == 'ev_completion_rate':
            return float(s.ev_completion_rate)
        if k == 'comfort_violation_degree_hours':
            return float(s.comfort_violation_degree_hours)
        if k == 'load_shedding_total_kw':
            return float(s.load_shedding_total_kw)
        logger.warning('Unknown metric key: %s', k)
        return 0.0


def create_harness_for_grid_violation(violation_type: str) -> VerificationHarness:
    h = VerificationHarness()
    if violation_type == 'voltage':
        h.add_target(ViolationTarget(category='voltage', metric_key='voltage_violations_count', threshold=0, is_upper_bound=True))
    elif violation_type == 'line_loading':
        h.add_target(ViolationTarget(category='line_loading', metric_key='line_loading_violations', threshold=0, is_upper_bound=True))
    elif violation_type == 'transformer_loading':
        h.add_target(ViolationTarget(category='transformer_loading', metric_key='transformer_loading_violations', threshold=0, is_upper_bound=True))
    elif violation_type == 'ev_deadline':
        h.add_target(ViolationTarget(category='ev_deadline', metric_key='ev_completion_rate', threshold=0.95, is_upper_bound=False))
    elif violation_type == 'comfort':
        h.add_target(ViolationTarget(category='comfort', metric_key='comfort_violation_degree_hours', threshold=0, is_upper_bound=True))
    return h
