"""Sandbox for validating code changes safely."""
import subprocess
import tempfile
import os
import sys
import shutil
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxResult:
    """Result of sandbox validation."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    execution_time: float = 0.0
    tests_passed: bool = False
    test_output: str = ""


class Sandbox:
    """Sandbox for safely testing code changes."""
    
    def __init__(
        self,
        project_root: str = None,
        timeout: int = 60,
        test_command: str = "python -m pytest tests/ -v --tb=short"
    ):
        self.project_root = project_root or os.getcwd()
        self.timeout = timeout
        self.test_command = test_command
        self.temp_dir: Optional[str] = None
    
    def create_sandbox(self) -> str:
        """Create a temporary sandbox directory with project copy."""
        self.temp_dir = tempfile.mkdtemp(prefix="repair_sandbox_")
        
        # Copy project files to sandbox (excluding large dirs)
        exclude_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv', 'env', 
                       'results', 'data', 'logs', '.pi', 'node_modules'}
        exclude_files = {'.pyc', '.pyo', '.pyd', '.so', '.dll'}
        
        for item in os.listdir(self.project_root):
            if item in exclude_dirs:
                continue
            src = os.path.join(self.project_root, item)
            dst = os.path.join(self.temp_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*exclude_dirs))
            else:
                if not any(item.endswith(ext) for ext in exclude_files):
                    shutil.copy2(src, dst)
        
        return self.temp_dir
    
    def cleanup(self):
        """Clean up sandbox directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
    
    def apply_changes(self, changes: List[Dict[str, Any]]) -> bool:
        """
        Apply code changes to sandbox.
        
        Args:
            changes: List of changes with file, function, change description
            
        Returns:
            True if changes applied successfully
        """
        if not self.temp_dir:
            self.create_sandbox()
        
        for change in changes:
            file_path = os.path.join(self.temp_dir, change["file"])
            if not os.path.exists(file_path):
                return False
            
            # For now, we just verify the file exists
            # Actual code modification would use AST or LLM
            # This is a placeholder
            pass
        
        return True
    
    def run_tests(self, test_filter: str = None) -> SandboxResult:
        """Run tests in sandbox."""
        if not self.temp_dir:
            return SandboxResult(
                success=False,
                error="Sandbox not created"
            )
        
        cmd = self.test_command
        if test_filter:
            cmd += f" -k {test_filter}"
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.temp_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            execution_time = time.time() - start_time
            
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time,
                tests_passed=result.returncode == 0,
                test_output=result.stdout
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Tests timed out after {self.timeout}s",
                execution_time=self.timeout
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def run_experiment(
        self, 
        scenario_config: str,
        controller_file: str,
        max_steps: int = 100
    ) -> SandboxResult:
        """Run a quick experiment in sandbox to validate controller."""
        if not self.temp_dir:
            return SandboxResult(
                success=False,
                error="Sandbox not created"
            )
        
        cmd = (
            f"python -m experiments.run_experiment "
            f"--config {scenario_config} "
            f"--controller {controller_file} "
            f"--max-steps {max_steps} "
            f"--output /tmp/sandbox_results"
        )
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.temp_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout * 2
            )
            execution_time = time.time() - start_time
            
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time,
                tests_passed=result.returncode == 0,
                test_output=result.stdout
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Experiment timed out after {self.timeout * 2}s",
                execution_time=self.timeout * 2
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def validate_syntax(self, file_path: str) -> SandboxResult:
        """Validate Python syntax of a file."""
        full_path = os.path.join(self.temp_dir, file_path) if self.temp_dir else file_path
        
        try:
            with open(full_path, 'r') as f:
                code = f.read()
            compile(code, file_path, 'exec')
            return SandboxResult(success=True, stdout="Syntax OK")
        except SyntaxError as e:
            return SandboxResult(
                success=False,
                error=f"Syntax error: {e}",
                stdout="",
                stderr=str(e)
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=str(e)
            )
    
    def __enter__(self):
        self.create_sandbox()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


def validate_controller_in_sandbox(
    controller_code: str,
    controller_file: str,
    scenario_config: str,
    project_root: str = None,
    max_steps: int = 50
) -> SandboxResult:
    """
    Validate a controller by running it in a sandbox.
    
    Args:
        controller_code: The controller code to validate
        controller_file: Path to controller file relative to project root
        scenario_config: Path to scenario config
        project_root: Project root directory
        max_steps: Maximum steps to run
        
    Returns:
        SandboxResult with validation outcome
    """
    with Sandbox(project_root=project_root) as sandbox:
        # Write controller code to sandbox
        controller_path = os.path.join(sandbox.temp_dir, controller_file)
        os.makedirs(os.path.dirname(controller_path), exist_ok=True)
        with open(controller_path, 'w') as f:
            f.write(controller_code)
        
        # Validate syntax
        syntax_result = sandbox.validate_syntax(controller_file)
        if not syntax_result.success:
            return syntax_result
        
        # Run quick experiment
        return sandbox.run_experiment(scenario_config, controller_file, max_steps)