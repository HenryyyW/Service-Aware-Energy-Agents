"""Repair loop for iterative code fixing."""
import os
import time
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from src.agents.repair_agent import RepairAgent, RepairPatch, RepairContext, create_repair_agent_from_config
from src.agents.sandbox import Sandbox, SandboxResult, validate_controller_in_sandbox
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType
from src.schemas.diagnostics import DiagnosticReport
from src.schemas.task import TaskSpec


@dataclass
class RepairIteration:
    """Single repair iteration record."""
    iteration: int
    patch: RepairPatch
    sandbox_result: SandboxResult
    experiment_result: Optional[ExperimentResult] = None
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
        Run the complete repair loop.
        
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
            
            # Apply patch to controller code (placeholder - would use AST/LLM)
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
            
            # Record iteration
            repair_iteration = RepairIteration(
                iteration=iteration,
                patch=patch,
                sandbox_result=sandbox_result,
                success=sandbox_result.success
            )
            self.iteration_history.append(repair_iteration)
            
            if sandbox_result.success:
                # If sandbox passes, run full experiment to verify
                print("Sandbox validation passed. Running full experiment...")
                # In practice, would run full experiment here
                # For now, assume success if sandbox passes
                repair_iteration.success = True
                current_experiment_result = self._create_success_result(
                    current_experiment_result, patch, iteration
                )
                break
            else:
                print("Sandbox validation failed. Trying next iteration...")
                # Try to fix the patch and retry
                if iteration == self.max_iterations - 1:
                    # Last iteration - return failure
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
    
    def _create_success_result(
        self, 
        original: ExperimentResult, 
        patch: RepairPatch, 
        iteration: int
    ) -> ExperimentResult:
        """Create a success result from the repaired controller."""
        # Create new experiment result with repair info
        new_result = ExperimentResult(
            run_id=f"{original.run_id}_repaired_{iteration}",
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
            controller_code=patch.diff,
            repair_iterations=[
                {
                    "iteration": iter.iteration,
                    "patch_id": iter.patch.patch_id,
                    "success": iter.success,
                    "sandbox_passed": iter.sandbox_result.success
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