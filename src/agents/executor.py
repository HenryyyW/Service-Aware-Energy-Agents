"""Executor agent - runs code in sandbox and executes experiments."""
import subprocess
import tempfile
import os
import shutil
import time
from typing import Optional, List, Dict, Any
from src.agents.roles import AgentState, ExecutorOutput, AgentRole
from src.agents.sandbox import Sandbox, SandboxResult, validate_controller_in_sandbox


class ExecutorAgent:
    """Executor agent that runs code in sandbox and validates it."""
    
    def __init__(
        self, 
        project_root: str = None,
        timeout: int = 120,
        quick_test_steps: int = 50
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
                error="No patched code to execute"
            )
        
        start_time = time.time()
        
        try:
            # Create sandbox
            self.sandbox.create_sandbox()
            
            # Write patched controller to sandbox
            controller_path = os.path.join(self.sandbox.temp_dir, state.controller_file)
            os.makedirs(os.path.dirname(controller_path), exist_ok=True)
            with open(controller_path, 'w') as f:
                f.write(state.patched_code)
            
            # Validate syntax
            syntax_result = self.sandbox.validate_syntax(state.controller_file)
            if not syntax_result.success:
                return ExecutorOutput(
                    success=False,
                    error=f"Syntax error: {syntax_result.error}",
                    execution_time=time.time() - start_time
                )
            
            # Run unit tests first
            print(f"  Running unit tests...")
            test_result = self.sandbox.run_tests()
            print(f"  Unit tests: {'PASS' if test_result.success else 'FAIL'} ({test_result.execution_time:.1f}s)")
            if not test_result.success:
                return ExecutorOutput(
                    success=False,
                    error=f"Unit tests failed: {test_result.error or test_result.stderr}",
                    execution_time=time.time() - start_time,
                    test_results={
                        "syntax_valid": True,
                        "unit_tests_passed": False,
                        "unit_test_output": test_result.stdout[-1000:] if test_result.stdout else "",
                        "unit_test_error": test_result.stderr[-1000:] if test_result.stderr else ""
                    }
                )
            
            # Run quick experiment validation
            exp_result = self.sandbox.run_experiment(
                state.scenario_config_path,
                state.controller_file,
                self.quick_test_steps
            )
            
            execution_time = time.time() - start_time
            
            output = ExecutorOutput(
                success=exp_result.success,
                stdout=exp_result.stdout,
                stderr=exp_result.stderr,
                error=exp_result.error,
                execution_time=execution_time,
                test_results={
                    "syntax_valid": True,
                    "unit_tests_passed": True,
                    "unit_test_time": test_result.execution_time,
                    "experiment_passed": exp_result.success,
                    "experiment_output": exp_result.stdout[-1000:] if exp_result.stdout else ""
                }
            )
            
            state.sandbox_result = exp_result
            state.add_message(AgentRole.EXECUTOR, f"Execution {'succeeded' if exp_result.success else 'failed'}", output.model_dump())
            
            return output
            
        except Exception as e:
            return ExecutorOutput(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
        finally:
            self.sandbox.cleanup()
    
    def run_full_experiment(
        self, 
        controller_code: str,
        controller_file: str,
        scenario_config_path: str,
        max_steps: int = None
    ) -> SandboxResult:
        """Run a full experiment with the given controller."""
        return validate_controller_in_sandbox(
            controller_code,
            controller_file,
            scenario_config_path,
            self.project_root,
            max_steps or self.quick_test_steps
        )


def create_executor_agent(config: Dict[str, Any]) -> ExecutorAgent:
    """Factory function to create executor agent from config."""
    return ExecutorAgent(
        project_root=config.get("project_root"),
        timeout=config.get("timeout", 120),
        quick_test_steps=config.get("quick_test_steps", 50)
    )