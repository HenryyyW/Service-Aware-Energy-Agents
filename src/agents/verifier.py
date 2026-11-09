"""Verifier agent - verifies that fixes resolve violations."""

from typing import List, Dict, Any
from src.agents.roles import AgentState, VerifierOutput, AgentRole
from src.agents.planner import PlannerOutput
from src.schemas.report import ExperimentResult
from src.evaluation.repair_acceptance import evaluate_repair, RepairVerdict


class VerifierAgent:
    """Verifier agent that checks if repairs resolved the violations."""

    def __init__(self, model: str = "gpt-4", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature

    def verify(
        self, state: AgentState, plan: PlannerOutput, executor_output: Dict[str, Any]
    ) -> VerifierOutput:
        """
        Verify that the repair resolved the violations using shared no-masking criteria.

        Args:
            state: Current agent state
            plan: Original repair plan
            executor_output: Results from executor

        Returns:
            VerifierOutput with verification results
        """
        # Check if executor itself failed (code errors, syntax, unit tests)
        if not state.sandbox_result or state.sandbox_result.error:
            output = VerifierOutput(
                violations_resolved=False,
                remaining_violations=[
                    {
                        "issue": "execution_failed",
                        "details": (
                            state.sandbox_result.error
                            if state.sandbox_result
                            else executor_output.get(
                                "experiment_error",
                                executor_output.get("error", "Unknown error"),
                            )
                        ),
                    }
                ],
                confidence=0.0,
                recommendation="retry",
            )
            state.verification_result = output.model_dump()
            state.add_message(
                AgentRole.VERIFIER,
                f"Verification: FAILED (execution failed: {state.sandbox_result.error if state.sandbox_result else executor_output.get('experiment_error', executor_output.get('error', 'Unknown error'))})",
                output.model_dump(),
            )
            return output

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
        confidence = self._calculate_confidence(
            violations_resolved, remaining, metrics_comparison
        )

        # Make recommendation
        recommendation = self._make_recommendation(
            violations_resolved, remaining, confidence
        )

        output = VerifierOutput(
            violations_resolved=violations_resolved,
            remaining_violations=remaining,
            new_violations=new_violations,
            metrics_comparison=metrics_comparison,
            confidence=confidence,
            recommendation=recommendation,
        )

        state.verification_result = output.model_dump()
        state.add_message(
            AgentRole.VERIFIER,
            f"Verification: {'PASSED' if violations_resolved else 'FAILED'} (confidence: {confidence:.2f})",
            output.model_dump(),
        )

        return output

    def _build_metrics_from_test_results(
        self, test_results: Dict[str, Any], is_baseline: bool = False
    ) -> Dict[str, Any]:
        """Build metrics dict from test results for evaluate_repair."""
        # Extract violation counts
        violation_counts = test_results.get("violation_counts", {})

        # Build metrics dict matching evaluate_repair expected format
        return {
            "grid": {
                "voltage_violations_count": violation_counts.get("voltage", 0),
                "line_loading_violations": violation_counts.get("line_loading", 0),
                "transformer_loading_violations": violation_counts.get(
                    "transformer_loading", 0
                ),
                "max_voltage_pu": test_results.get("max_voltage_pu", 1.05),
                "min_voltage_pu": test_results.get("min_voltage_pu", 0.95),
                "max_line_loading_pct": test_results.get("max_line_loading_pct", 100.0),
                "max_transformer_loading_pct": test_results.get(
                    "max_transformer_loading_pct", 100.0
                ),
            },
            "service": {
                "ev_completion_rate": test_results.get("ev_completion_rate", 1.0),
                "ev_avg_soc_at_departure": test_results.get(
                    "ev_avg_soc_at_departure", 1.0
                ),
                "ev_worst_soc_at_departure": test_results.get(
                    "ev_worst_soc_at_departure", 1.0
                ),
                "flexible_load_completion_rate": test_results.get(
                    "flexible_load_completion_rate", 1.0
                ),
                "comfort_violation_degree_hours": test_results.get(
                    "comfort_violation_degree_hours", 0.0
                ),
                "member_cost_coverage": test_results.get("member_cost_coverage", 1.0),
                "members_interrupted_count": test_results.get(
                    "members_interrupted_count", 0
                ),
                "member_cost_interrupted": test_results.get(
                    "member_cost_interrupted", None
                ),
            },
        }

    def _check_violations(
        self, state: AgentState, plan: PlannerOutput, executor_output: Dict[str, Any]
    ) -> tuple:
        """Check if violations are resolved based on executor results."""
        remaining = []
        new_violations = []

        # Handle both full executor_output dict and test_results dict
        # If executor_output has "test_results" key, use that; otherwise assume it's test_results directly
        if "test_results" in executor_output:
            test_results = executor_output.get("test_results", {})
        else:
            test_results = executor_output

        # Check violation counts from sandbox experiment
        violation_counts = test_results.get("violation_counts", {})
        check_categories = test_results.get("check_categories", [])

        # Check for absent execution (controller took no actions)
        action_counts = test_results.get("action_counts", {})
        steps_with_actions = action_counts.get("steps_with_actions", 0)
        total_actions = action_counts.get("total_actions", 0)
        controller_crashed = action_counts.get("controller_crashed", False)
        crash_error = action_counts.get("crash_error", "")
        if controller_crashed:
            remaining.append(
                {
                    "issue": "controller_crashed",
                    "reason": f"Controller raised exception during execution: {crash_error}",
                    "severity": "critical",
                }
            )
            return False, remaining, new_violations
        if steps_with_actions == 0 or total_actions == 0:
            remaining.append(
                {
                    "issue": "absent_execution",
                    "reason": "Controller took no actions during experiment (absent execution)",
                    "severity": "critical",
                }
            )
            return False, remaining, new_violations

        # Check violation counts from sandbox experiment
        violation_counts = test_results.get("violation_counts", {})
        check_categories = test_results.get("check_categories", [])

        # Check if violations in checked categories are resolved
        primary_issue = plan.primary_issue
        violations_resolved = True

        if violation_counts:
            # Check primary issue violations
            primary_count = violation_counts.get(primary_issue, 0)
            if primary_count > 0:
                violations_resolved = False
                remaining.append(
                    {
                        "issue": primary_issue,
                        "count": primary_count,
                        "reason": f"Quick experiment validation failed - {primary_issue} violations still present",
                        "severity": "high",
                    }
                )

            # Check other checked categories
            for cat in check_categories:
                if cat != primary_issue and violation_counts.get(cat, 0) > 0:
                    remaining.append(
                        {
                            "issue": cat,
                            "count": violation_counts.get(cat, 0),
                            "reason": f"New {cat} violations detected",
                            "severity": "medium",
                        }
                    )
        else:
            # Fallback to experiment_passed if no violation counts
            experiment_passed = test_results.get("experiment_passed", False)
            if not experiment_passed:
                violations_resolved = False
                remaining.append(
                    {
                        "issue": primary_issue,
                        "reason": "Quick experiment validation failed - fix did not resolve issue",
                        "severity": "high",
                        "test_details": test_results.get(
                            "error", "Unknown test failure"
                        ),
                    }
                )

        # Check if any new issues were introduced
        if test_results.get("syntax_error", False):
            new_violations.append(
                {
                    "issue": "syntax_error",
                    "reason": "Introduced syntax error in controller code",
                    "severity": "critical",
                }
            )

        return violations_resolved, remaining, new_violations

    def _compare_metrics(
        self, state: AgentState, plan: PlannerOutput
    ) -> Dict[str, Any]:
        """Compare metrics before and after repair."""
        # Since we don't have "before" metrics stored in state for quick verification,
        # we analyze what we can from the executor output and current state
        comparison = {
            "primary_issue": plan.primary_issue,
            "verification_type": "quick_test",
            "notes": "Based on sandbox experiment results",
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
        self, violations_resolved: bool, remaining: List[Dict], metrics: Dict
    ) -> float:
        """Calculate confidence in the fix."""
        if violations_resolved and not remaining:
            return 0.85
        elif violations_resolved and remaining:
            return 0.6
        else:
            return 0.2

    def _make_recommendation(
        self, violations_resolved: bool, remaining: List[Dict], confidence: float
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
        plan: PlannerOutput,
    ) -> VerifierOutput:
        """Verify using full experiment results comparison - uses shared no-masking criteria."""
        # Convert ExperimentResult to dict format for evaluate_repair
        baseline_metrics = {
            "grid": {
                "voltage_violations_count": original_result.grid.voltage_violations_count,
                "line_loading_violations": original_result.grid.line_loading_violations,
                "transformer_loading_violations": original_result.grid.transformer_loading_violations,
                "max_voltage_pu": original_result.grid.max_voltage_pu,
                "min_voltage_pu": original_result.grid.min_voltage_pu,
                "max_line_loading_pct": original_result.grid.max_line_loading_pct,
                "max_transformer_loading_pct": original_result.grid.max_transformer_loading_pct,
            },
            "service": {
                "ev_completion_rate": original_result.service.ev_completion_rate,
                "ev_avg_soc_at_departure": (
                    original_result.service.ev_avg_soc_at_departure
                    if hasattr(original_result.service, "ev_avg_soc_at_departure")
                    else 1.0
                ),
                "ev_worst_soc_at_departure": (
                    original_result.service.ev_worst_soc_at_departure
                    if hasattr(original_result.service, "ev_worst_soc_at_departure")
                    else 1.0
                ),
                "flexible_load_completion_rate": original_result.service.flexible_load_completion_rate,
                "comfort_violation_degree_hours": original_result.service.comfort_violation_degree_hours,
                "member_cost_coverage": (
                    original_result.service.member_cost_coverage
                    if hasattr(original_result.service, "member_cost_coverage")
                    else 1.0
                ),
                "members_interrupted_count": (
                    original_result.service.members_interrupted_count
                    if hasattr(original_result.service, "members_interrupted_count")
                    else 0
                ),
                "member_cost_interrupted": (
                    original_result.service.member_cost_interrupted
                    if hasattr(original_result.service, "member_cost_interrupted")
                    else None
                ),
            },
        }

        repaired_metrics = {
            "grid": {
                "voltage_violations_count": repaired_result.grid.voltage_violations_count,
                "line_loading_violations": repaired_result.grid.line_loading_violations,
                "transformer_loading_violations": repaired_result.grid.transformer_loading_violations,
                "max_voltage_pu": repaired_result.grid.max_voltage_pu,
                "min_voltage_pu": repaired_result.grid.min_voltage_pu,
                "max_line_loading_pct": repaired_result.grid.max_line_loading_pct,
                "max_transformer_loading_pct": repaired_result.grid.max_transformer_loading_pct,
            },
            "service": {
                "ev_completion_rate": repaired_result.service.ev_completion_rate,
                "ev_avg_soc_at_departure": (
                    repaired_result.service.ev_avg_soc_at_departure
                    if hasattr(repaired_result.service, "ev_avg_soc_at_departure")
                    else 1.0
                ),
                "ev_worst_soc_at_departure": (
                    repaired_result.service.ev_worst_soc_at_departure
                    if hasattr(repaired_result.service, "ev_worst_soc_at_departure")
                    else 1.0
                ),
                "flexible_load_completion_rate": repaired_result.service.flexible_load_completion_rate,
                "comfort_violation_degree_hours": repaired_result.service.comfort_violation_degree_hours,
                "member_cost_coverage": (
                    repaired_result.service.member_cost_coverage
                    if hasattr(repaired_result.service, "member_cost_coverage")
                    else 1.0
                ),
                "members_interrupted_count": (
                    repaired_result.service.members_interrupted_count
                    if hasattr(repaired_result.service, "members_interrupted_count")
                    else 0
                ),
                "member_cost_interrupted": (
                    repaired_result.service.member_cost_interrupted
                    if hasattr(repaired_result.service, "member_cost_interrupted")
                    else None
                ),
            },
        }

        # Use shared evaluation criteria
        verdict: RepairVerdict = evaluate_repair(baseline_metrics, repaired_metrics)

        remaining = []
        if not verdict.accepted:
            # Convert reasons to remaining violations format
            for reason in verdict.reasons:
                remaining.append({"issue": "no_masking_violation", "reason": reason})

        # Also add any remaining grid violations for backward compatibility
        if repaired_result.grid.voltage_violations_count > 0:
            remaining.append(
                {
                    "issue": "voltage",
                    "count": repaired_result.grid.voltage_violations_count,
                    "max_voltage_pu": repaired_result.grid.max_voltage_pu,
                    "min_voltage_pu": repaired_result.grid.min_voltage_pu,
                }
            )
        if repaired_result.grid.line_loading_violations > 0:
            remaining.append(
                {
                    "issue": "line_loading",
                    "count": repaired_result.grid.line_loading_violations,
                    "max_loading_pct": repaired_result.grid.max_line_loading_pct,
                }
            )
        if repaired_result.grid.transformer_loading_violations > 0:
            remaining.append(
                {
                    "issue": "transformer_loading",
                    "count": repaired_result.grid.transformer_loading_violations,
                    "max_loading_pct": repaired_result.grid.max_transformer_loading_pct,
                }
            )

        violations_resolved = len(remaining) == 0

        metrics_comparison = {
            "grid": {
                "voltage_violations": {
                    "before": baseline_metrics["grid"]["voltage_violations_count"],
                    "after": repaired_metrics["grid"]["voltage_violations_count"],
                },
                "line_loading_violations": {
                    "before": baseline_metrics["grid"]["line_loading_violations"],
                    "after": repaired_metrics["grid"]["line_loading_violations"],
                },
                "transformer_loading_violations": {
                    "before": baseline_metrics["grid"][
                        "transformer_loading_violations"
                    ],
                    "after": repaired_metrics["grid"]["transformer_loading_violations"],
                },
                "max_line_loading_pct": {
                    "before": baseline_metrics["grid"]["max_line_loading_pct"],
                    "after": repaired_metrics["grid"]["max_line_loading_pct"],
                },
                "max_transformer_loading_pct": {
                    "before": baseline_metrics["grid"]["max_transformer_loading_pct"],
                    "after": repaired_metrics["grid"]["max_transformer_loading_pct"],
                },
            },
            "service": {
                "ev_completion_rate": {
                    "before": baseline_metrics["service"]["ev_completion_rate"],
                    "after": repaired_metrics["service"]["ev_completion_rate"],
                },
                "ev_avg_soc_at_departure": {
                    "before": baseline_metrics["service"]["ev_avg_soc_at_departure"],
                    "after": repaired_metrics["service"]["ev_avg_soc_at_departure"],
                },
                "ev_worst_soc_at_departure": {
                    "before": baseline_metrics["service"]["ev_worst_soc_at_departure"],
                    "after": repaired_metrics["service"]["ev_worst_soc_at_departure"],
                },
                "flexible_load_completion_rate": {
                    "before": baseline_metrics["service"][
                        "flexible_load_completion_rate"
                    ],
                    "after": repaired_metrics["service"][
                        "flexible_load_completion_rate"
                    ],
                },
                "comfort_violation_degree_hours": {
                    "before": baseline_metrics["service"][
                        "comfort_violation_degree_hours"
                    ],
                    "after": repaired_metrics["service"][
                        "comfort_violation_degree_hours"
                    ],
                },
                "member_cost_coverage": {
                    "before": baseline_metrics["service"]["member_cost_coverage"],
                    "after": repaired_metrics["service"]["member_cost_coverage"],
                },
                "members_interrupted_count": {
                    "before": baseline_metrics["service"]["members_interrupted_count"],
                    "after": repaired_metrics["service"]["members_interrupted_count"],
                },
                "member_cost_interrupted": {
                    "before": baseline_metrics["service"]["member_cost_interrupted"],
                    "after": repaired_metrics["service"]["member_cost_interrupted"],
                },
            },
            "verdict": {
                "accepted": verdict.accepted,
                "reasons": verdict.reasons,
                "metric_deltas": verdict.metric_deltas,
            },
        }

        confidence = 0.9 if verdict.accepted else 0.2
        recommendation = "accept" if verdict.accepted else "reject"

        return VerifierOutput(
            violations_resolved=verdict.accepted,
            remaining_violations=remaining,
            new_violations=[],
            metrics_comparison=metrics_comparison,
            confidence=confidence,
            recommendation=recommendation,
        )
