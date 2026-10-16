"""Multi-agent repair loop orchestrating Planner → Coder → Executor → Verifier → Reporter."""
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from src.agents.roles import AgentState, AgentRole
from src.agents.planner import PlannerAgent, PlannerOutput
from src.agents.coder import CoderAgent, CoderOutput
from src.agents.executor import ExecutorAgent, ExecutorOutput
from src.agents.verifier import VerifierAgent, VerifierOutput
from src.agents.reporter import ReporterAgent, ReporterOutput
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType
from src.schemas.diagnostics import DiagnosticReport


@dataclass
class IterationRecord:
    """Record of a single repair iteration."""
    iteration: int
    planner_output: PlannerOutput
    coder_output: CoderOutput
    executor_output: ExecutorOutput
    verifier_output: VerifierOutput
    reporter_output: ReporterOutput
    success: bool
    duration: float


@dataclass
class MultiAgentRepairResult:
    """Result of the complete multi-agent repair process."""
    success: bool
    final_experiment_result: Optional[ExperimentResult] = None
    iterations: List[IterationRecord] = field(default_factory=list)
    total_iterations: int = 0
    total_time: float = 0.0
    final_report: Optional[Dict[str, Any]] = None


class MultiAgentRepairLoop:
    """
    Orchestrates the multi-agent repair workflow:
    Planner → Coder → Executor → Verifier → Reporter
    """
    
    def __init__(
        self,
        planner: PlannerAgent = None,
        coder: CoderAgent = None,
        executor: ExecutorAgent = None,
        verifier: VerifierAgent = None,
        reporter: ReporterAgent = None,
        max_iterations: int = 3,
        project_root: str = None
    ):
        self.planner = planner or PlannerAgent()
        self.coder = coder or CoderAgent()
        self.executor = executor or ExecutorAgent(project_root=project_root)
        self.verifier = verifier or VerifierAgent()
        self.reporter = reporter or ReporterAgent()
        self.max_iterations = max_iterations
        self.project_root = project_root
        self.iteration_history: List[IterationRecord] = []
    
    def run_repair(
        self,
        experiment_result: ExperimentResult,
        diagnostic_reports: List[DiagnosticReport],
        baseline_controller_code: str,
        controller_file: str,
        scenario_config: Dict[str, Any],
        scenario_config_path: str
    ) -> MultiAgentRepairResult:
        """
        Run the complete multi-agent repair loop.
        
        Args:
            experiment_result: Failed experiment result with violations
            diagnostic_reports: List of diagnostic reports
            baseline_controller_code: Original controller code
            controller_file: Path to controller file
            scenario_config: Scenario configuration
            scenario_config_path: Path to scenario config file
            
        Returns:
            MultiAgentRepairResult with final outcome
        """
        start_time = time.time()
        current_controller_code = baseline_controller_code
        current_experiment_result = experiment_result
        
        # Initialize shared state
        state = AgentState(
            experiment_result=experiment_result,
            diagnostic_reports=diagnostic_reports,
            controller_code=baseline_controller_code,
            controller_file=controller_file,
            scenario_config=scenario_config,
            scenario_config_path=scenario_config_path,
            max_iterations=self.max_iterations
        )
        
        print(f"\n{'='*60}")
        print(f"MULTI-AGENT REPAIR LOOP STARTED")
        print(f"Run ID: {experiment_result.run_id}")
        print(f"Max Iterations: {self.max_iterations}")
        print(f"{'='*60}")
        
        for iteration in range(self.max_iterations):
            state.iteration = iteration
            iter_start = time.time()
            
            print(f"\n{'='*60}")
            print(f"ITERATION {iteration + 1}/{self.max_iterations}")
            print(f"{'='*60}")
            
            # === PLANNER ===
            print(f"\n[PLANNER] Analyzing violations and creating repair plan...")
            plan = self.planner.plan(state)
            print(f"  Primary Issue: {plan.primary_issue}")
            print(f"  Secondary Issues: {plan.secondary_issues}")
            print(f"  Strategy: {plan.repair_strategy}")
            print(f"  Target Functions: {plan.target_functions}")
            print(f"  Risk: {plan.risk_assessment}")
            
            if plan.primary_issue == "none":
                print("  No violations detected - repair not needed!")
                break
            
            # === CODER ===
            print(f"\n[CODER] Implementing code changes...")
            coder_output = self.coder.code(state, plan)
            print(f"  Changes: {len(coder_output.code_changes)}")
            for change in coder_output.code_changes:
                print(f"    - {change['function']}: {change['change'][:80]}...")
            
            # === EXECUTOR ===
            print(f"\n[EXECUTOR] Running sandbox validation...")
            executor_output = self.executor.execute(state)
            print(f"  Result: {'PASS' if executor_output.success else 'FAIL'}")
            print(f"  Time: {executor_output.execution_time:.1f}s")
            if executor_output.error:
                print(f"  Error: {executor_output.error}")
            
            # === VERIFIER ===
            print(f"\n[VERIFIER] Verifying repair effectiveness...")
            verifier_output = self.verifier.verify(state, plan, executor_output.test_results)
            print(f"  Violations Resolved: {verifier_output.violations_resolved}")
            print(f"  Confidence: {verifier_output.confidence:.0%}")
            print(f"  Recommendation: {verifier_output.recommendation}")
            if verifier_output.remaining_violations:
                print(f"  Remaining: {verifier_output.remaining_violations}")
            
            # === REPORTER ===
            print(f"\n[REPORTER] Generating iteration report...")
            reporter_output = self.reporter.report(
                state, plan, coder_output, executor_output, verifier_output
            )
            print(f"  Summary: {reporter_output.summary.split(chr(10))[0]}")
            
            # Record iteration
            iter_duration = time.time() - iter_start
            iteration_record = IterationRecord(
                iteration=iteration,
                planner_output=plan,
                coder_output=coder_output,
                executor_output=executor_output,
                verifier_output=verifier_output,
                reporter_output=reporter_output,
                success=executor_output.success and verifier_output.violations_resolved,
                duration=iter_duration
            )
            self.iteration_history.append(iteration_record)
            
            # Check if repair successful
            if executor_output.success and verifier_output.violations_resolved:
                print(f"\n✓ REPAIR SUCCESSFUL in iteration {iteration + 1}")
                # Create final experiment result with repair info
                final_result = self._create_final_result(
                    experiment_result, state, iteration_record
                )
                break
            
            # Check if should continue
            if verifier_output.recommendation in ["escalate", "retry"]:
                if iteration == self.max_iterations - 1:
                    print(f"\n✗ MAX ITERATIONS REACHED - Repair incomplete")
                    break
                print(f"\n→ Continuing to next iteration (recommendation: {verifier_output.recommendation})")
                # Update state for next iteration
                state.controller_code = state.patched_code
            else:
                print(f"\n→ Stopping (recommendation: {verifier_output.recommendation})")
                break
        
        total_time = time.time() - start_time
        success = any(iter.success for iter in self.iteration_history)
        
        # Generate final comprehensive report
        final_report = self.reporter.generate_final_report(
            [self._iteration_to_dict(iter_rec) for iter_rec in self.iteration_history],
            state
        )
        
        return MultiAgentRepairResult(
            success=success,
            final_experiment_result=current_experiment_result if success else None,
            iterations=self.iteration_history,
            total_iterations=len(self.iteration_history),
            total_time=total_time,
            final_report=final_report
        )
    
    def _create_final_result(
        self, 
        original: ExperimentResult, 
        state: AgentState,
        iteration_record: IterationRecord
    ) -> ExperimentResult:
        """Create final experiment result with repair metadata."""
        return ExperimentResult(
            run_id=f"{original.run_id}_repaired_v{state.iteration + 1}",
            scenario_id=original.scenario_id,
            controller_type=ControllerType.LLM_AGENT_VERIFIED,
            controller_config=original.controller_config,
            status=ExperimentStatus.COMPLETED,
            random_seed=original.random_seed,
            energy=original.energy,
            service=original.service,
            grid=original.grid,
            agent=original.agent,
            kpis=original.kpis,
            per_member=original.per_member,
            diagnostic_reports=original.diagnostic_reports,
            controller_code=state.patched_code,
            code_diffs=[{"diff": iteration_record.coder_output.diff}],
            repair_iterations=[
                {
                    "iteration": iter_rec.iteration,
                    "primary_issue": iter_rec.planner_output.primary_issue,
                    "strategy": iter_rec.planner_output.repair_strategy,
                    "changes": len(iter_rec.coder_output.code_changes),
                    "executor_success": iter_rec.executor_output.success,
                    "violations_resolved": iter_rec.verifier_output.violations_resolved,
                    "confidence": iter_rec.verifier_output.confidence,
                    "duration_sec": iter_rec.duration
                }
                for iter_rec in self.iteration_history
            ]
        )
    
    def _iteration_to_dict(self, iter_rec: IterationRecord) -> Dict[str, Any]:
        """Convert iteration record to dictionary."""
        return {
            "iteration": iter_rec.iteration,
            "planner": iter_rec.planner_output.model_dump(),
            "coder": iter_rec.coder_output.model_dump(),
            "executor": iter_rec.executor_output.model_dump(),
            "verifier": iter_rec.verifier_output.model_dump(),
            "reporter": iter_rec.reporter_output.model_dump(),
            "success": iter_rec.success,
            "duration": iter_rec.duration
        }


def run_multi_agent_repair(
    experiment_result: ExperimentResult,
    diagnostic_reports: List[DiagnosticReport],
    controller_code: str,
    controller_file: str,
    scenario_config: Dict[str, Any],
    scenario_config_path: str,
    max_iterations: int = 3,
    project_root: str = None
) -> MultiAgentRepairResult:
    """Convenience function to run multi-agent repair loop."""
    loop = MultiAgentRepairLoop(
        max_iterations=max_iterations,
        project_root=project_root
    )
    return loop.run_repair(
        experiment_result,
        diagnostic_reports,
        controller_code,
        controller_file,
        scenario_config,
        scenario_config_path
    )