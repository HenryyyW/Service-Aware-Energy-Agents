"""Repair loop for iterative code fixing."""
import os
import time
import hashlib
import shutil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from src.agents.repair_agent import RepairAgent, RepairPatch, RepairContext, create_repair_agent_from_config
from src.agents.sandbox import Sandbox, SandboxResult, validate_controller_in_sandbox
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType
from src.schemas.diagnostics import DiagnosticReport
from src.schemas.task import TaskSpec
from src.evaluation.verification_harness import VerificationHarness, create_harness_for_grid_violation, HarnessReport


@dataclass
class RepairIteration:
    """Single repair iteration record."""
    iteration: int
    patch: RepairPatch
    sandbox_result: SandboxResult
    experiment_result: Optional[ExperimentResult] = None
    verification_report: Optional[HarnessReport] = None
    success: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class RepairLoopResult:
    """Result of the complete repair loop."""
    success: bool
    final_experiment_result: Optional[ExperimentResult] = None
    iterations: List[RepairIteration] = field(default_factory=list)
    total_iterations: int = 0
    total_time: float = 0.0
    final_patch: Optional[RepairPatch] = None


class RepairLoop:
    """Orchestrates iterative repair of controllers."""
    
    def __init__(
        self,
        repair_agent: RepairAgent = None,
        sandbox: Sandbox = None,
        max_iterations: int = 3,
        project_root: str = None
    ):
        self.repair_agent = repair_agent or RepairAgent()
        self.sandbox = sandbox or Sandbox(project_root=project_root)
        self.max_iterations = max_iterations
        self.project_root = project_root or os.getcwd()
        self.iteration_history: List[RepairIteration] = []
    
    def run_repair(
        self,
        experiment_result: ExperimentResult,
        diagnostic_reports: List[DiagnosticReport],
        baseline_controller_code: str,
        controller_file: str,
        scenario_config: Dict[str, Any],
        scenario_config_path: str
    ) -> RepairLoopResult:
        """
        Run the complete repair loop with verification harness integration.
        
        Args:
            experiment_result: Failed experiment result with violations
            diagnostic_reports: List of diagnostic reports
            baseline_controller_code: Original controller code
            controller_file: Path to controller file
            scenario_config: Scenario configuration
            scenario_config_path: Path to scenario config file
            
        Returns:
            RepairLoopResult with final outcome
        """
        start_time = time.time()
        current_controller_code = baseline_controller_code
        current_experiment_result = experiment_result
        
        # Create verification harness from diagnostic violations
        verification_harness = self._create_verification_harness(experiment_result, diagnostic_reports)
        
        for iteration in range(self.max_iterations):
            print(f"\n=== Repair Iteration {iteration + 1}/{self.max_iterations} ===")
            
            # Create repair context
            context = RepairContext(
                experiment_result=current_experiment_result,
                diagnostic_reports=diagnostic_reports,
                baseline_controller_code=current_controller_code,
                controller_file=controller_file,
                scenario_config=scenario_config,
                iteration=iteration,
                max_iterations=self.max_iterations
            )
            
            # Get repair patch from agent
            patch = self.repair_agent.diagnose_and_repair(context)
            print(f"Patch: {patch.patch_id} - {patch.description}")
            print(f"Expected improvement: {patch.expected_improvement}")
            print(f"Changes: {len(patch.code_changes)}")
            
            # Apply patch to controller code using AST
            new_controller_code = self.repair_agent.apply_patch(patch, current_controller_code)
            
            # Validate in sandbox
            print("Running sandbox validation...")
            sandbox_result = validate_controller_in_sandbox(
                new_controller_code,
                controller_file,
                scenario_config_path,
                self.project_root,
                max_steps=50  # Quick validation
            )
            
            print(f"Sandbox result: {'PASS' if sandbox_result.success else 'FAIL'}")
            if sandbox_result.error:
                print(f"  Error: {sandbox_result.error}")
            
            # Record iteration with verification
            repair_iteration = RepairIteration(
                iteration=iteration,
                patch=patch,
                sandbox_result=sandbox_result,
                success=sandbox_result.success
            )
            self.iteration_history.append(repair_iteration)
            
            if sandbox_result.success:
                # If sandbox passes, run FULL experiment to verify with verification harness
                print("Sandbox validation passed. Running full experiment for verification...")
                verification_report = self._run_full_experiment_and_verify(
                    new_controller_code,
                    controller_file,
                    scenario_config_path,
                    current_experiment_result,
                    verification_harness
                )
                repair_iteration.verification_report = verification_report
                
                # Check if verification harness confirms the repair
                if verification_report and verification_report.passed:
                    print(f"VERIFICATION PASSED: {verification_report.summary}")
                    repair_iteration.success = True
                    current_experiment_result = self._create_verified_success_result(
                        current_experiment_result, patch, iteration, verification_report
                    )
                    break
                else:
                    print(f"VERIFICATION FAILED: {verification_report.summary if verification_report else 'No report'}")
                    # Sandbox passed but full experiment shows repair didn't fix violations
                    repair_iteration.success = False
            else:
                print("Sandbox validation failed. Trying next iteration...")
                if iteration == self.max_iterations - 1:
                    break
        
        total_time = time.time() - start_time
        success = any(iter.success for iter in self.iteration_history)
        
        return RepairLoopResult(
            success=success,
            final_experiment_result=current_experiment_result if success else None,
            iterations=self.iteration_history,
            total_iterations=len(self.iteration_history),
            total_time=total_time,
            final_patch=self.iteration_history[-1].patch if self.iteration_history else None
        )
    
    def _create_verification_harness(self, experiment_result: ExperimentResult, 
                                      diagnostic_reports: List[DiagnosticReport]) -> VerificationHarness:
        """Create a verification harness based on the violations in the experiment."""
        harness = VerificationHarness()
        
        # Add targets based on grid violations
        grid = experiment_result.grid
        if grid.voltage_violations_count > 0:
            harness.add_target(
                create_harness_for_grid_violation('voltage').targets[0]
            )
        if grid.line_loading_violations > 0:
            harness.add_target(
                create_harness_for_grid_violation('line_loading').targets[0]
            )
        if grid.transformer_loading_violations > 0:
            harness.add_target(
                create_harness_for_grid_violation('transformer_loading').targets[0]
            )
        
        # Add targets based on service violations
        service = experiment_result.service
        if service.ev_completion_rate < 0.95:
            harness.add_target(
                create_harness_for_grid_violation('ev_deadline').targets[0]
            )
        if service.comfort_violation_degree_hours > 0:
            harness.add_target(
                create_harness_for_grid_violation('comfort').targets[0]
            )
        
        return harness
    
    def _run_full_experiment_and_verify(
        self,
        controller_code: str,
        controller_file: str,
        scenario_config_path: str,
        before_result: ExperimentResult,
        verification_harness: VerificationHarness
    ) -> Optional[HarnessReport]:
        """Run a full experiment with the repaired controller and verify with harness."""
        try:
            # Write controller code to a temporary file in the project
            controller_path = os.path.join(self.project_root, controller_file)
            os.makedirs(os.path.dirname(controller_path), exist_ok=True)
            
            # Backup original
            backup_path = controller_path + '.backup'
            if os.path.exists(controller_path):
                shutil.copy2(controller_path, backup_path)
            
            # Write new controller
            with open(controller_path, 'w') as f:
                f.write(controller_code)
            
            try:
                # Run full experiment
                from experiments.run_experiment import ExperimentRunner, load_scenario
                
                scenario = load_scenario(scenario_config_path)
                runner = ExperimentRunner(scenario, output_dir="experiments/results")
                
                # Determine controller type from file
                if 'rule_based' in controller_file:
                    runner.setup('rule_based')
                elif 'multi_agent' in controller_file:
                    runner.setup('multi_agent')
                else:
                    runner.setup('rule_based')
                
                # Run full experiment (or at least more steps)
                after_result = runner.run(max_steps=200)
                
                # Verify with harness
                verification_report = verification_harness.verify_repair(before_result, after_result)
                return verification_report
                
            finally:
                # Restore original controller
                if os.path.exists(backup_path):
                    shutil.move(backup_path, controller_path)
                elif os.path.exists(controller_path):
                    os.remove(controller_path)
                    
        except Exception as e:
            print(f"Full experiment verification failed: {e}")
            return None
    
    def _create_verified_success_result(
        self, 
        original: ExperimentResult, 
        patch: RepairPatch, 
        iteration: int,
        verification_report: HarnessReport
    ) -> ExperimentResult:
        """Create a success result from the verified repaired controller."""
        new_result = ExperimentResult(
            run_id=f"{original.run_id}_repaired_{iteration}",
            scenario_id=original.scenario_id,
            controller_type=ControllerType.LLM_AGENT_VERIFIED,
            controller_config=original.controller_config,
            status=ExperimentStatus.COMPLETED,
            random_seed=original.random_seed,
            energy=original.energy,  # Will be updated by actual experiment
            service=original.service,
            grid=original.grid,
            agent=original.agent,
            kpis=original.kpis,
            per_member=original.per_member,
            diagnostic_reports=original.diagnostic_reports,
            controller_code=patch.diff,
            repair_iterations=[
                {
                    "iteration": iter.iteration,
                    "patch_id": iter.patch.patch_id,
                    "success": iter.success,
                    "sandbox_passed": iter.sandbox_result.success,
                    "verification_passed": iter.verification_report.passed if iter.verification_report else False,
                    "verification_summary": iter.verification_report.summary if iter.verification_report else ""
                }
                for iter in self.iteration_history
            ]
        )
        return new_result


def run_repair_loop(
    experiment_result: ExperimentResult,
    diagnostic_reports: List[DiagnosticReport],
    controller_code: str,
    controller_file: str,
    scenario_config: Dict[str, Any],
    scenario_config_path: str,
    max_iterations: int = 3,
    project_root: str = None
) -> RepairLoopResult:
    """Convenience function to run repair loop."""
    repair_agent = RepairAgent()
    sandbox = Sandbox(project_root=project_root)
    loop = RepairLoop(repair_agent, sandbox, max_iterations, project_root)
    
    return loop.run_repair(
        experiment_result,
        diagnostic_reports,
        controller_code,
        controller_file,
        scenario_config,
        scenario_config_path
    )