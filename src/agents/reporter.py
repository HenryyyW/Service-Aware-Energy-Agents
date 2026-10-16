"""Reporter agent - generates comprehensive repair reports."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.agents.roles import AgentState, ReporterOutput, AgentRole
from src.agents.planner import PlannerOutput
from src.agents.coder import CoderOutput
from src.agents.executor import ExecutorOutput
from src.agents.verifier import VerifierOutput
from src.schemas.report import ExperimentResult


class ReporterAgent:
    """Reporter agent that generates comprehensive repair reports."""
    
    def __init__(self, model: str = "gpt-4", temperature: float = 0.2):
        self.model = model
        self.temperature = temperature
    
    def report(
        self, 
        state: AgentState,
        plan: PlannerOutput,
        coder_output: CoderOutput,
        executor_output: ExecutorOutput,
        verifier_output: VerifierOutput
    ) -> ReporterOutput:
        """
        Generate a comprehensive repair report.
        
        Args:
            state: Current agent state
            plan: Repair plan from Planner
            coder_output: Code changes from Coder
            executor_output: Execution results from Executor
            verifier_output: Verification results from Verifier
            
        Returns:
            ReporterOutput with comprehensive report
        """
        # Generate summary
        summary = self._generate_summary(state, plan, verifier_output)
        
        # Generate detailed report
        detailed = self._generate_detailed_report(
            state, plan, coder_output, executor_output, verifier_output
        )
        
        # List artifacts
        artifacts = self._list_artifacts(state)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(plan, verifier_output)
        
        output = ReporterOutput(
            summary=summary,
            detailed_report=detailed,
            artifacts=artifacts,
            recommendations=recommendations
        )
        
        state.final_report = output.model_dump()
        state.add_message(AgentRole.REPORTER, "Generated final repair report", output.model_dump())
        
        return output
    
    def _generate_summary(
        self, 
        state: AgentState, 
        plan: PlannerOutput, 
        verifier_output: VerifierOutput
    ) -> str:
        """Generate executive summary."""
        status = "SUCCESS" if verifier_output.violations_resolved else "FAILED"
        return (
            f"Repair #{state.iteration + 1} for {state.experiment_result.run_id}: {status}\n"
            f"Primary Issue: {plan.primary_issue}\n"
            f"Strategy: {plan.repair_strategy}\n"
            f"Confidence: {verifier_output.confidence:.0%}\n"
            f"Recommendation: {verifier_output.recommendation.upper()}"
        )
    
    def _generate_detailed_report(
        self,
        state: AgentState,
        plan: PlannerOutput,
        coder_output: CoderOutput,
        executor_output: ExecutorOutput,
        verifier_output: VerifierOutput
    ) -> Dict[str, Any]:
        """Generate detailed technical report."""
        return {
            "repair_metadata": {
                "run_id": state.experiment_result.run_id,
                "scenario_id": state.experiment_result.scenario_id,
                "controller_type": state.experiment_result.controller_type.value,
                "iteration": state.iteration + 1,
                "timestamp": datetime.now().isoformat()
            },
            "planner_analysis": {
                "primary_issue": plan.primary_issue,
                "secondary_issues": plan.secondary_issues,
                "root_cause": plan.root_cause_analysis,
                "strategy": plan.repair_strategy,
                "target_functions": plan.target_functions,
                "success_criteria": plan.success_criteria,
                "risk_assessment": plan.risk_assessment
            },
            "coder_implementation": {
                "changes_count": len(coder_output.code_changes),
                "changes": coder_output.code_changes,
                "diff": coder_output.diff,
                "notes": coder_output.implementation_notes
            },
            "executor_results": {
                "success": executor_output.success,
                "execution_time_sec": executor_output.execution_time,
                "stdout_tail": executor_output.stdout[-500:] if executor_output.stdout else "",
                "stderr_tail": executor_output.stderr[-500:] if executor_output.stderr else "",
                "error": executor_output.error,
                "test_results": executor_output.test_results
            },
            "verifier_assessment": {
                "violations_resolved": verifier_output.violations_resolved,
                "remaining_violations": verifier_output.remaining_violations,
                "new_violations": verifier_output.new_violations,
                "metrics_comparison": verifier_output.metrics_comparison,
                "confidence": verifier_output.confidence,
                "recommendation": verifier_output.recommendation
            },
            "message_log": [
                {"role": m.role.value, "content": m.content, "timestamp": m.timestamp}
                for m in state.messages
            ]
        }
    
    def _list_artifacts(self, state: AgentState) -> List[str]:
        """List all artifacts generated during repair."""
        artifacts = []
        if state.patched_code:
            artifacts.append("patched_controller.py")
        if state.code_changes:
            artifacts.append("code_changes.json")
        if state.sandbox_result:
            artifacts.append("sandbox_execution.log")
        if state.verification_result:
            artifacts.append("verification_results.json")
        if state.final_report:
            artifacts.append("repair_report.json")
        return artifacts
    
    def _generate_recommendations(
        self, 
        plan: PlannerOutput, 
        verifier_output: VerifierOutput
    ) -> List[str]:
        """Generate follow-up recommendations."""
        recs = []
        
        if verifier_output.recommendation == "accept":
            recs.append("Deploy repaired controller to production")
            recs.append("Monitor for regression in next 24-48 hours")
            recs.append("Add regression test for this failure mode")
        elif verifier_output.recommendation == "accept_with_monitoring":
            recs.append("Deploy with enhanced monitoring")
            recs.append("Set up alerts for primary issue metrics")
        elif verifier_output.recommendation == "retry":
            recs.append("Analyze remaining violations for refined repair")
            recs.append("Consider alternative strategies from secondary issues")
            if plan.secondary_issues:
                recs.append(f"Address secondary issue: {plan.secondary_issues[0]}")
        else:  # escalate
            recs.append("Escalate to human operator")
            recs.append("Review controller architecture for fundamental issues")
            recs.append("Consider scenario redesign if constraints infeasible")
        
        return recs
    
    def generate_final_report(
        self,
        all_iterations: List[Dict[str, Any]],
        final_state: AgentState
    ) -> Dict[str, Any]:
        """Generate final report across all repair iterations."""
        return {
            "repair_session": {
                "run_id": final_state.experiment_result.run_id,
                "scenario_id": final_state.experiment_result.scenario_id,
                "total_iterations": len(all_iterations),
                "final_status": "SUCCESS" if final_state.verification_result.get("violations_resolved") else "FAILED",
                "completed_at": datetime.now().isoformat()
            },
            "iteration_history": all_iterations,
            "final_recommendations": self._generate_recommendations(
                PlannerOutput(**final_state.repair_plan) if final_state.repair_plan else PlannerOutput(
                    primary_issue="unknown", repair_strategy=""
                ),
                VerifierOutput(**final_state.verification_result) if final_state.verification_result else VerifierOutput(
                    violations_resolved=False, confidence=0.0, recommendation="escalate"
                )
            ),
            "lessons_learned": self._extract_lessons(all_iterations)
        }
    
    def _extract_lessons(self, iterations: List[Dict[str, Any]]) -> List[str]:
        """Extract lessons learned from repair iterations."""
        lessons = []
        if len(iterations) > 1:
            lessons.append(f"Required {len(iterations)} iterations - consider more comprehensive initial analysis")
        # Could add more sophisticated pattern analysis
        return lessons