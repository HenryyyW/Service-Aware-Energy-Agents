"""Executor agent - runs code in sandbox and executes experiments."""

import os
import time
from typing import Dict, Any
from src.agents.roles import AgentState, ExecutorOutput, AgentRole
from src.agents.sandbox import Sandbox, SandboxResult, validate_controller_in_sandbox
from src.agents.diff_classifier import (
    classify_diff,
)


class ExecutorAgent:
    """Executor agent that runs code in sandbox and validates it."""

    def __init__(
        self, project_root: str = None, timeout: int = 120, quick_test_steps: int = 50
    ):
        self.project_root = project_root or os.getcwd()
        self.timeout = timeout
        self.quick_test_steps = quick_test_steps
        self.sandbox = Sandbox(project_root=self.project_root, timeout=timeout)

    def execute(self, state: AgentState) -> ExecutorOutput:
        """
        Execute the patched code in sandbox.

        Args:
            state: Current agent state with patched code

        Returns:
            ExecutorOutput with execution results
        """
        if not state.patched_code:
            return ExecutorOutput(
                success=False,
                error="No patched code to execute",
                test_results={"experiment_error": "No patched code to execute"},
            )

        start_time = time.time()

        # Check if the patch is behavior-changing before running tests
        # This rejects cosmetic patches (comments, docstrings, whitespace only)
        if state.controller_code:
            classification = classify_diff(state.controller_code, state.patched_code)
            if not classification.is_behavior_changing:
                return ExecutorOutput(
                    success=False,
                    error=f"Patch rejected: {classification.reason}",
                    execution_time=time.time() - start_time,
                    test_results={
                        "syntax_valid": True,
                        "unit_tests_passed": False,
                        "patch_rejected": True,
                        "rejection_reason": "cosmetic_only",
                        "experiment_error": f"Patch rejected: {classification.reason}",
                        "classification": {
                            "is_behavior_changing": classification.is_behavior_changing,
                            "reason": classification.reason,
                            "behavior_changes": classification.behavior_changes,
                            "cosmetic_changes": classification.cosmetic_changes,
                        },
                    },
                )

        try:
            # Create sandbox
            self.sandbox.create_sandbox()

            # Apply code changes using sandbox's AST-based implementation
            # This applies the actual logic changes, not just comments
            if state.code_changes:
                success = self.sandbox.apply_changes(state.code_changes)
                if not success:
                    return ExecutorOutput(
                        success=False,
                        error="Failed to apply code changes in sandbox",
                        execution_time=time.time() - start_time,
                        test_results={
                            "experiment_error": "Failed to apply code changes in sandbox"
                        },
                    )

            # Write patched controller to sandbox (get the modified code from sandbox)
            assert self.sandbox.temp_dir is not None
            controller_path = os.path.join(self.sandbox.temp_dir, state.controller_file)
            # Read the modified code from sandbox after changes were applied
            with open(controller_path, "r") as f:
                patched_code = f.read()

            # Validate syntax
            syntax_result = self.sandbox.validate_syntax(state.controller_file)
            if not syntax_result.success:
                return ExecutorOutput(
                    success=False,
                    error=f"Syntax error: {syntax_result.error}",
                    execution_time=time.time() - start_time,
                    test_results={
                        "experiment_error": f"Syntax error: {syntax_result.error}"
                    },
                )

            # Run unit tests first
            print("  Running unit tests...")
            test_result = self.sandbox.run_tests()
            print(
                f"  Unit tests: {'PASS' if test_result.success else 'FAIL'} ({test_result.execution_time:.1f}s)"
            )
            if not test_result.success:
                return ExecutorOutput(
                    success=False,
                    error=f"Unit tests failed: {test_result.error or test_result.stderr}",
                    execution_time=time.time() - start_time,
                    test_results={
                        "syntax_valid": True,
                        "unit_tests_passed": False,
                        "unit_test_output": (
                            test_result.stdout[-1000:] if test_result.stdout else ""
                        ),
                        "unit_test_error": (
                            test_result.stderr[-1000:] if test_result.stderr else ""
                        ),
                        "experiment_error": f"Unit tests failed: {test_result.error or test_result.stderr}",
                    },
                )

            # Run quick experiment validation
            # Determine which violation categories to check based on repair plan
            check_categories = ["voltage", "line_loading", "transformer_loading"]
            if state.repair_plan and "primary_issue" in state.repair_plan:
                primary = state.repair_plan["primary_issue"]
                if primary in [
                    "voltage",
                    "line_loading",
                    "transformer_loading",
                    "ev_deadline",
                    "comfort",
                    "battery_soc",
                    "flexible_load",
                    "grid_import",
                    "grid_export",
                ]:
                    check_categories = [primary]

            exp_result = self.sandbox.run_experiment(
                state.scenario_config_path,
                state.controller_file,
                self.quick_test_steps,
                check_categories=check_categories,
            )

            execution_time = time.time() - start_time

            # Executor success = code runs without errors (syntax, unit tests, experiment execution)
            # Repair effectiveness is judged by the verifier from violation_counts
            executor_success = (
                exp_result.error is None
            )  # No exception during experiment run

            output = ExecutorOutput(
                success=executor_success,
                stdout=exp_result.stdout,
                stderr=exp_result.stderr,
                error=exp_result.error,
                execution_time=execution_time,
                test_results={
                    "syntax_valid": True,
                    "unit_tests_passed": True,
                    "unit_test_time": test_result.execution_time,
                    "experiment_passed": exp_result.success,  # All violations resolved
                    "experiment_output": (
                        exp_result.stdout[-1000:] if exp_result.stdout else ""
                    ),
                    "experiment_error": exp_result.error,  # Include error for verifier
                    "violation_counts": exp_result.violation_counts,
                    "max_violations": exp_result.max_violations,
                    "check_categories": check_categories,
                },
            )

            state.sandbox_result = exp_result
            state.add_message(
                AgentRole.EXECUTOR,
                f"Execution {'succeeded' if executor_success else 'failed'} (experiment_passed={exp_result.success})",
                output.model_dump(),
            )

            return output

        except Exception as e:
            return ExecutorOutput(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
                test_results={"experiment_error": str(e)},
            )
        finally:
            self.sandbox.cleanup()

    def run_full_experiment(
        self,
        controller_code: str,
        controller_file: str,
        scenario_config_path: str,
        max_steps: int = None,
    ) -> SandboxResult:
        """Run a full experiment with the given controller."""
        return validate_controller_in_sandbox(
            controller_code,
            controller_file,
            scenario_config_path,
            self.project_root,
            max_steps or self.quick_test_steps,
        )


def create_executor_agent(config: Dict[str, Any]) -> ExecutorAgent:
    """Factory function to create executor agent from config."""
    return ExecutorAgent(
        project_root=config.get("project_root"),
        timeout=config.get("timeout", 120),
        quick_test_steps=config.get("quick_test_steps", 50),
    )
