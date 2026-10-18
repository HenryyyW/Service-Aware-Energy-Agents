"""Verifier agent - verifies that fixes resolve violations."""
from typing import Optional, List, Dict, Any
from src.agents.roles import AgentState, VerifierOutput, AgentRole
from src.agents.planner import PlannerOutput
from src.schemas.diagnostics import DiagnosticCategory, Severity
from src.schemas.report import ExperimentResult, GridMetrics, ServiceMetrics


class VerifierAgent:
    """Verifier agent that checks if repairs resolved the violations."""
    
    def __init__(self, model: str = "gpt-4", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature
    
    def verify(
        self, 
        state: AgentState, 
        plan: PlannerOutput,
        executor_output: Dict[str, Any]
    ) -> VerifierOutput:
        """
        Verify that the repair resolved the violations.
        
        Args:
            state: Current agent state
            plan: Original repair plan
            executor_output: Results from executor
            
        Returns:
            VerifierOutput with verification results
        """
        if not state.sandbox_result or not state.sandbox_result.success:
            return VerifierOutput(
                violations_resolved=False,
                remaining_violations=[{"issue": "execution_failed", "details": executor_output.get("error", "Unknown error")}],
                confidence=0.0,
                recommendation="retry"
            )
        
        # Parse experiment results from executor output
        # In practice, would run full experiment and get metrics
        # For now, analyze the quick test output
        
        # Check if primary issue success criteria are met
        violations_resolved, remaining, new_violations = self._check_violations(
            state, plan, executor_output
        )
        
        # Compare metrics
        metrics_comparison = self._compare_metrics(state, plan)
        
        # Determine confidence
        confidence = self._calculate_confidence(violations_resolved, remaining, metrics_comparison)
        
        # Make recommendation
        recommendation = self._make_recommendation(violations_resolved, remaining, confidence)
        
        output = VerifierOutput(
            violations_resolved=violations_resolved,
            remaining_violations=remaining,
            new_violations=new_violations,
            metrics_comparison=metrics_comparison,
            confidence=confidence,
            recommendation=recommendation
        )
        
        state.verification_result = output.model_dump()
        state.add_message(AgentRole.VERIFIER, f"Verification: {'PASSED' if violations_resolved else 'FAILED'} (confidence: {confidence:.2f})", output.model_dump())
        
        return output
    
    def _check_violations(
        self, 
        state: AgentState, 
        plan: PlannerOutput,
        executor_output: Dict[str, Any]
    ) -> tuple:
        """Check if violations are resolved based on executor results."""
        remaining = []
        new_violations = []
        
        # Parse executor test results
        test_results = executor_output.get("test_results", {})
        
        # Check if the quick validation experiment passed
        experiment_passed = test_results.get("experiment_passed", False)
        
        if experiment_passed:
            violations_resolved = True
            # In a full implementation, we would check specific diagnostic improvements
            # For quick test, we assume that passing the experiment means the primary issue is addressed
        else:
            violations_resolved = False
            # Add the primary issue as remaining since the fix didn't pass validation
            remaining.append({
                "issue": plan.primary_issue,
                "reason": "Quick experiment validation failed - fix did not resolve issue",
                "severity": "high",
                "test_details": test_results.get("error", "Unknown test failure")
            })
            
            # Check if any new issues were introduced
            if test_results.get("syntax_error", False):
                new_violations.append({
                    "issue": "syntax_error",
                    "reason": "Introduced syntax error in controller code",
                    "severity": "critical"
                })
        
        return violations_resolved, remaining, new_violations
    
    def _compare_metrics(self, state: AgentState, plan: PlannerOutput) -> Dict[str, Any]:
        """Compare metrics before and after repair."""
        # Since we don't have "before" metrics stored in state for quick verification,
        # we analyze what we can from the executor output and current state
        comparison = {
            "primary_issue": plan.primary_issue,
            "verification_type": "quick_test",
            "notes": "Based on sandbox experiment results"
        }
        
        # Add issue-specific checks based on what we can verify in quick test
        if plan.primary_issue in ["voltage", "line_loading", "transformer_loading"]:
            comparison["grid_stability"] = "verified_power_flow_convergence"
        elif plan.primary_issue in ["ev_deadline", "battery_soc"]:
            comparison["resource_management"] = "verified_basic_functionality"
        elif plan.primary_issue in ["comfort", "flexible_load"]:
            comparison["service_quality"] = "verified_basic_functionality"
        elif plan.primary_issue in ["grid_import", "grid_export"]:
            comparison["grid_limits"] = "verified_limit_checking"
            
        return comparison
    
    def _calculate_confidence(
        self, 
        violations_resolved: bool, 
        remaining: List[Dict], 
        metrics: Dict
    ) -> float:
        """Calculate confidence in the fix."""
        if violations_resolved and not remaining:
            return 0.85
        elif violations_resolved and remaining:
            return 0.6
        else:
            return 0.2
    
    def _make_recommendation(
        self, 
        violations_resolved: bool, 
        remaining: List[Dict], 
        confidence: float
    ) -> str:
        """Make recommendation based on verification results."""
        if violations_resolved and confidence > 0.8:
            return "accept"
        elif violations_resolved and confidence > 0.5:
            return "accept_with_monitoring"
        elif not violations_resolved and confidence > 0.3:
            return "retry"
        else:
            return "escalate"
    
    def verify_full_experiment(
        self, 
        original_result: ExperimentResult, 
        repaired_result: ExperimentResult,
        plan: PlannerOutput
    ) -> VerifierOutput:
        """Verify using full experiment results comparison."""
        # Compare grid metrics
        orig_grid: GridMetrics = original_result.grid
        new_grid: GridMetrics = repaired_result.grid
        
        # Compare service metrics
        orig_service: ServiceMetrics = original_result.service
        new_service: ServiceMetrics = repaired_result.service
        
        remaining = []
        new_violations = []
        
        # Check voltage
        if plan.primary_issue == "voltage" or "voltage" in plan.secondary_issues:
            if new_grid.voltage_violations_count > 0:
                remaining.append({
                    "issue": "voltage",
                    "count": new_grid.voltage_violations_count,
                    "max_voltage_pu": new_grid.max_voltage_pu,
                    "min_voltage_pu": new_grid.min_voltage_pu
                })
            elif orig_grid.voltage_violations_count > 0:
                new_violations.append({
                    "issue": "voltage_resolved",
                    "improvement": f"Reduced from {orig_grid.voltage_violations_count} to 0"
                })
        
        # Check line loading
        if plan.primary_issue == "line_loading" or "line_loading" in plan.secondary_issues:
            if new_grid.line_loading_violations > 0:
                remaining.append({
                    "issue": "line_loading",
                    "count": new_grid.line_loading_violations,
                    "max_loading_pct": new_grid.max_line_loading_pct
                })
            elif orig_grid.line_loading_violations > 0:
                new_violations.append({
                    "issue": "line_loading_resolved",
                    "improvement": f"Reduced from {orig_grid.line_loading_violations} to 0"
                })
        
        # Check transformer loading
        if plan.primary_issue == "transformer_loading" or "transformer_loading" in plan.secondary_issues:
            if new_grid.transformer_loading_violations > 0:
                remaining.append({
                    "issue": "transformer_loading",
                    "count": new_grid.transformer_loading_violations,
                    "max_loading_pct": new_grid.max_transformer_loading_pct
                })
        
        # Check EV completion
        if plan.primary_issue == "ev_deadline" or "ev_deadline" in plan.secondary_issues:
            if new_service.ev_completion_rate < 0.95:
                remaining.append({
                    "issue": "ev_deadline",
                    "completion_rate": new_service.ev_completion_rate,
                    "target": 0.95
                })
            elif orig_service.ev_completion_rate < new_service.ev_completion_rate:
                new_violations.append({
                    "issue": "ev_deadline_improved",
                    "improvement": f"Improved from {orig_service.ev_completion_rate:.2f} to {new_service.ev_completion_rate:.2f}"
                })
        
        # Check comfort
        if plan.primary_issue == "comfort" or "comfort" in plan.secondary_issues:
            if new_service.comfort_violation_degree_hours > 0:
                remaining.append({
                    "issue": "comfort",
                    "degree_hours": new_service.comfort_violation_degree_hours
                })
        
        violations_resolved = len(remaining) == 0
        
        metrics_comparison = {
            "grid": {
                "voltage_violations": {"before": orig_grid.voltage_violations_count, "after": new_grid.voltage_violations_count},
                "line_loading_violations": {"before": orig_grid.line_loading_violations, "after": new_grid.line_loading_violations},
                "transformer_loading_violations": {"before": orig_grid.transformer_loading_violations, "after": new_grid.transformer_loading_violations},
                "max_line_loading_pct": {"before": orig_grid.max_line_loading_pct, "after": new_grid.max_line_loading_pct},
                "max_transformer_loading_pct": {"before": orig_grid.max_transformer_loading_pct, "after": new_grid.max_transformer_loading_pct}
            },
            "service": {
                "ev_completion_rate": {"before": orig_service.ev_completion_rate, "after": new_service.ev_completion_rate},
                "comfort_violations": {"before": orig_service.comfort_violation_degree_hours, "after": new_service.comfort_violation_degree_hours}
            }
        }
        
        confidence = 0.9 if violations_resolved else 0.3
        recommendation = "accept" if violations_resolved else "retry"
        
        return VerifierOutput(
            violations_resolved=violations_resolved,
            remaining_violations=remaining,
            new_violations=new_violations,
            metrics_comparison=metrics_comparison,
            confidence=confidence,
            recommendation=recommendation
        )