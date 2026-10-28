"""Sandbox for validating code changes safely."""
import subprocess
import tempfile
import os
import sys
import shutil
import json
import time
import ast
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
        Apply code changes to sandbox using AST manipulation.
        
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
            
            # Read the file
            with open(file_path, 'r') as f:
                code = f.read()
            
            # Apply the change
            function_name = change.get("function", "")
            change_desc = change.get("change", "")
            change_type = change.get("type", "modification")
            
            if change_type == "modification" and function_name:
                modified_code = self._apply_function_modification(
                    code, function_name, change_desc
                )
                
                # Write back the modified code
                with open(file_path, 'w') as f:
                    f.write(modified_code)
        
        return True
    
    def _apply_function_modification(self, code: str, function_name: str, change_desc: str) -> str:
        """Apply a modification to a specific function using AST."""
        try:
            tree = ast.parse(code)
            
            # Find the target function
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    # Apply specific modifications based on the change description
                    modified_code = self._modify_function_body(code, function_name, change_desc)
                    return modified_code
            
            return code
            
        except Exception:
            return code
    
    def _modify_function_body(self, code: str, function_name: str, change_desc: str) -> str:
        """Modify a function's body based on the change description."""
        lines = code.split('\n')
        
        # Find the function
        func_start = -1
        func_end = -1
        indent = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f'def {function_name}('):
                func_start = i
                indent = len(line) - len(line.lstrip())
                break
        
        if func_start == -1:
            return code
        
        for i in range(func_start + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped and not stripped.startswith('#'):
                line_indent = len(lines[i]) - len(lines[i].lstrip())
                if line_indent <= indent and (stripped.startswith('def ') or stripped.startswith('class ')):
                    func_end = i
                    break
        
        if func_end == -1:
            func_end = len(lines)
        
        # Get the function body
        func_lines = lines[func_start:func_end]
        func_body = '\n'.join(func_lines)
        
        # Apply modifications based on change description
        modified_body = self._apply_change_to_function(func_body, change_desc)
        
        # Replace in original code
        new_lines = lines[:func_start] + modified_body.split('\n') + lines[func_end:]
        return '\n'.join(new_lines)
    
    def _apply_change_to_function(self, func_code: str, change_desc: str) -> str:
        """Apply a specific change to a function's code."""
        lines = func_code.split('\n')
        
        change_lower = change_desc.lower()
        
        if "voltage-aware" in change_lower or "voltage aware" in change_lower:
            return self._add_voltage_aware_logic(lines)
        elif "line loading" in change_lower:
            return self._add_line_loading_logic(lines)
        elif "transformer" in change_lower:
            return self._add_transformer_loading_logic(lines)
        elif "ev" in change_lower and ("earlier" in change_lower or "deadline" in change_lower):
            return self._improve_ev_charging_logic(lines)
        elif "comfort" in change_lower or "pre-heat" in change_lower or "pre-cool" in change_lower:
            return self._add_comfort_aware_logic(lines)
        elif "import limit" in change_lower:
            return self._add_import_limit_logic(lines)
        elif "export limit" in change_lower:
            return self._add_export_limit_logic(lines)
        elif "reactive power" in change_lower:
            return self._add_reactive_power_logic(lines)
        elif "constraint checking" in change_lower:
            return self._add_constraint_checking_logic(lines)
        
        return func_code
    
    def _add_voltage_aware_logic(self, lines: List[str]) -> str:
        """Add voltage-aware load reduction to _apply_grid_limits."""
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i]:
                voltage_check = '''
        # Voltage-aware re-dispatch: check for voltage violations in diagnostics
        if hasattr(self, 'last_grid_diagnostics') and self.last_grid_diagnostics:
            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
            voltage_high = False
            voltage_low = False
            for d in diagnostics:
                if d.get("category") == "voltage" and d.get("severity") in ["violation", "critical"]:
                    values = d.get("values", {})
                    if values.get("voltage_pu", 1.0) > 1.03:
                        voltage_high = True
                    elif values.get("voltage_pu", 1.0) < 0.97:
                        voltage_low = True
            
            if voltage_high:
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.EV_CHARGE]:
                        a.value_kw *= 0.8
            elif voltage_low:
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_DISCHARGE]:
                        a.value_kw *= 0.8
'''
                lines.insert(i, voltage_check)
                break
        return '\n'.join(lines)
    
    def _add_line_loading_logic(self, lines: List[str]) -> str:
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i]:
                loading_check = '''
        # Line loading constraint: check for line overloads
        if hasattr(self, 'last_grid_diagnostics') and self.last_grid_diagnostics:
            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
            line_overloaded = False
            for d in diagnostics:
                if d.get("category") == "line_loading" and d.get("severity") in ["violation", "critical"]:
                    line_overloaded = True
                    break
            
            if line_overloaded:
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                                         ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                        a.value_kw *= 0.75
'''
                lines.insert(i, loading_check)
                break
        return '\n'.join(lines)
    
    def _add_transformer_loading_logic(self, lines: List[str]) -> str:
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i]:
                trafo_check = '''
        # Transformer loading constraint
        if hasattr(self, 'last_grid_diagnostics') and self.last_grid_diagnostics:
            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
            trafo_overloaded = False
            for d in diagnostics:
                if d.get("category") == "transformer_loading" and d.get("severity") in ["violation", "critical"]:
                    trafo_overloaded = True
                    break
            
            if trafo_overloaded:
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                                         ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                        a.value_kw *= 0.85
'''
                lines.insert(i, trafo_check)
                break
        return '\n'.join(lines)
    
    def _improve_ev_charging_logic(self, lines: List[str]) -> str:
        for i in range(len(lines) - 1, -1, -1):
            if 'required_power = energy_needed / max(hours_remaining' in lines[i]:
                lines[i] = '''        # Energy needed
        energy_needed = (ev.target_soc - current_soc) * capacity_kwh
        
        # More aggressive charging as deadline approaches
        if hours_remaining < 2.0:
            required_power = energy_needed / max(hours_remaining, 0.25) * 1.5
        elif hours_remaining < 4.0:
            required_power = energy_needed / max(hours_remaining, 0.25) * 1.2
        else:
            required_power = energy_needed / max(hours_remaining, 0.25)'''
                break
        return '\n'.join(lines)
    
    def _add_comfort_aware_logic(self, lines: List[str]) -> str:
        return '\n'.join(lines)
    
    def _add_import_limit_logic(self, lines: List[str]) -> str:
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i]:
                import_check = '''
        # Community import limit enforcement
        if self.scenario_config.community_import_limit_kw:
            total_import = sum(a.value_kw for a in actions if a.value_kw > 0)
            import_limit = self.scenario_config.community_import_limit_kw
            if total_import > import_limit:
                scale = import_limit / total_import
                for a in actions:
                    if a.value_kw > 0:
                        a.value_kw *= scale
'''
                lines.insert(i, import_check)
                break
        return '\n'.join(lines)
    
    def _add_export_limit_logic(self, lines: List[str]) -> str:
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i]:
                export_check = '''
        # Community export limit enforcement
        if self.scenario_config.community_export_limit_kw:
            total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)
            export_limit = self.scenario_config.community_export_limit_kw
            if total_export > export_limit:
                scale = export_limit / total_export
                for a in actions:
                    if a.value_kw < 0:
                        a.value_kw *= scale
'''
                lines.insert(i, export_check)
                break
        return '\n'.join(lines)
    
    def _add_reactive_power_logic(self, lines: List[str]) -> str:
        return '\n'.join(lines)
    
    def _add_constraint_checking_logic(self, lines: List[str]) -> str:
        for i in range(len(lines) - 1, -1, -1):
            if 'return self._create_requested_actions(actions)' in lines[i]:
                check = '''
        # Comprehensive constraint validation
        for a in actions:
            if hasattr(self, '_validate_action'):
                a = self._validate_action(a)
'''
                lines.insert(i, check)
                break
        return '\n'.join(lines)
    
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