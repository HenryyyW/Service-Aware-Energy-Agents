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
    violation_counts: Dict[str, int] = field(default_factory=dict)
    max_violations: Dict[str, int] = field(default_factory=dict)


class Sandbox:
    """Sandbox for safely testing code changes."""
    
    def __init__(
        self,
        project_root: str = None,
        timeout: int = 60,
        test_command: str = None
    ):
        self.project_root = project_root or os.getcwd()
        self.timeout = timeout
        # Use sys.executable to ensure correct python path
        # Run only quick syntax/import tests for speed
        self.test_command = test_command or f"{sys.executable} -m pytest tests/test_baseline_controllers.py tests/test_metrics.py -v --tb=short -x"
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
            
            # Find the target function in RuleBasedController class (the one used by experiments)
            target_node = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == 'RuleBasedController':
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == function_name:
                            target_node = item
                            break
            
            # Fallback: find any function with this name (last occurrence)
            if target_node is None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == function_name:
                        target_node = node
            
            if target_node:
                # Apply specific modifications based on the change description
                modified_code = self._modify_function_body(code, function_name, change_desc)
                return modified_code
            
            return code
            
        except Exception:
            return code
    
    def _modify_function_body(self, code: str, function_name: str, change_desc: str) -> str:
        """Modify a function's body based on the change description."""
        try:
            # Use AST to find the function in RuleBasedController
            tree = ast.parse(code)
            
            func_start = -1
            func_end = -1
            indent = 0
            
            # Find RuleBasedController class and the target function within it
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == 'RuleBasedController':
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == function_name:
                            func_start = item.lineno - 1  # AST line numbers are 1-indexed
                            indent = item.col_offset
                            func_end = item.end_lineno  # AST end_lineno is 1-indexed, exclusive
                            break
            
            # Fallback: find last occurrence
            if func_start == -1:
                lines = code.split('\n')
                func_starts = []
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith(f'def {function_name}('):
                        func_starts.append(i)
                
                if not func_starts:
                    return code
                
                func_start = func_starts[-1]
                indent = len(lines[func_start]) - len(lines[func_start].lstrip())
                
                func_end = -1
                for i in range(func_start + 1, len(lines)):
                    stripped = lines[i].strip()
                    if stripped and not stripped.startswith('#'):
                        line_indent = len(lines[i]) - len(lines[i].lstrip())
                        if line_indent <= indent and (stripped.startswith('def ') or stripped.startswith('class ')):
                            func_end = i
                            break
                
                if func_end == -1:
                    func_end = len(lines)
            else:
                lines = code.split('\n')
            
            # Get the function body
            func_lines = lines[func_start:func_end]
            func_body = '\n'.join(func_lines)
            
            # Apply modifications based on change description
            modified_body = self._apply_change_to_function(func_body, change_desc)
            
            # Replace in original code
            new_lines = lines[:func_start] + modified_body.split('\n') + lines[func_end:]
            return '\n'.join(new_lines)
            
        except Exception:
            return code
    
    def _apply_change_to_function(self, func_code: str, change_desc: str) -> str:
        """Apply a specific change to a function's code."""
        lines = func_code.split('\n')
        
        change_lower = change_desc.lower()
        
        if ("voltage-aware" in change_lower or "voltage aware" in change_lower 
            or "voltage monitoring" in change_lower or "voltage-triggered" in change_lower
            or "voltage trigger" in change_lower):
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
        max_steps: int = 100,
        check_categories: List[str] = None
    ) -> SandboxResult:
        """Run a quick experiment in sandbox to validate controller using SimulationCoupler directly."""
        if not self.temp_dir:
            return SandboxResult(
                success=False,
                error="Sandbox not created"
            )
        
        # Read the patched controller code
        controller_path = os.path.join(self.temp_dir, controller_file)
        if not os.path.exists(controller_path):
            return SandboxResult(
                success=False,
                error=f"Controller file not found: {controller_path}"
            )
        
        with open(controller_path, 'r') as f:
            controller_code = f.read()
        
        start_time = time.time()
        try:
            # Import required modules
            from src.simulation import SimulationCoupler
            from src.schemas.scenario import ScenarioConfig
            from src.schemas.action import RequestedActions, Action, ActionType
            import yaml
            
            # Load scenario config
            with open(scenario_config, 'r') as f:
                scenario_dict = yaml.safe_load(f)
            scenario = ScenarioConfig(**scenario_dict)
            
            # Create dynamic controller class from patched code
            controller_class = self._create_dynamic_controller(controller_code, scenario)
            
            # Create controller instance
            controller = controller_class(scenario)
            
            # Create simulation coupler
            coupler = SimulationCoupler(scenario, data_dir=os.path.join(self.project_root, "data"))
            
            # Run quick simulation
            observations = coupler.reset(random_seed=scenario.random_seed)
            controller.reset()
            
            success = True
            stdout_lines = []
            violation_counts = {cat: 0 for cat in (check_categories or ["voltage", "line_loading", "transformer_loading"])}
            max_violations = {cat: 0 for cat in (check_categories or ["voltage", "line_loading", "transformer_loading"])}
            
            for step in range(max_steps):
                # Get actions from controller
                requested = controller.get_actions(observations, step)
                
                # Step simulation
                result = coupler.step(requested)
                
                # Update controller with grid diagnostics
                if result.grid_diagnostics:
                    controller.update_grid_diagnostics(result.grid_diagnostics.model_dump())
                    
                    # Count violations
                    if result.grid_diagnostics.diagnostics:
                        for diag in result.grid_diagnostics.diagnostics:
                            cat = diag.category.value if hasattr(diag.category, 'value') else str(diag.category)
                            if cat in violation_counts:
                                violation_counts[cat] += 1
                                max_violations[cat] = max(max_violations[cat], 1)
                
                # Check for convergence
                if result.terminated or result.truncated:
                    break
                
                observations = result.citylearn_result.observations
                
                if step % 10 == 0:
                    stdout_lines.append(f"  Step {step}: power_flow_converged={result.power_flow_converged}")
            
            execution_time = time.time() - start_time
            
            # Determine success based on violation resolution
            # Success = no violations in checked categories
            violations_resolved = all(v == 0 for v in violation_counts.values())
            
            return SandboxResult(
                success=violations_resolved,
                stdout="\n".join(stdout_lines),
                stderr="",
                execution_time=execution_time,
                tests_passed=violations_resolved,
                test_output="\n".join(stdout_lines),
                violation_counts=violation_counts,
                max_violations=max_violations
            )
            
        except Exception as e:
            import traceback
            return SandboxResult(
                success=False,
                error=f"Experiment failed: {str(e)}\n{traceback.format_exc()}",
                execution_time=time.time() - start_time
            )
    
    def _create_dynamic_controller(self, controller_code: str, scenario) -> type:
        """Create a dynamic controller class from patched code."""
        import types
        
        # Create a new module for the controller
        module = types.ModuleType("dynamic_controller")
        
        # Execute the controller code in the module's namespace
        # This will define the controller class (e.g., RuleBasedController)
        exec(controller_code, module.__dict__)
        
        # Find the concrete controller class (not abstract BaseController)
        # Look for classes that have get_actions method implemented (not abstract)
        controller_class = None
        for name, obj in module.__dict__.items():
            if (isinstance(obj, type) and 
                hasattr(obj, 'get_actions') and 
                obj.__name__ != 'BaseController'):
                # Check if get_actions is implemented (not abstract)
                method = obj.__dict__.get('get_actions')
                if method is not None:
                    controller_class = obj
                    break
        
        if controller_class is None:
            # Fallback: create a wrapper class that uses the patched code
            class DynamicController:
                def __init__(self, scenario_config):
                    self.scenario_config = scenario_config
                    self.timestep = 0
                    self.last_grid_diagnostics = None
                    # Create namespace with the patched code
                    self._namespace = {}
                    exec(controller_code, self._namespace)
                    # Find the concrete controller class in the namespace
                    self._impl = None
                    for name, obj in self._namespace.items():
                        if (isinstance(obj, type) and 
                            hasattr(obj, 'get_actions') and 
                            obj.__name__ != 'BaseController'):
                            method = obj.__dict__.get('get_actions')
                            if method is not None:
                                self._impl = obj(scenario_config)
                                break
                
                def get_actions(self, observations, timestep):
                    self.timestep = timestep
                    if self._impl:
                        return self._impl.get_actions(observations, timestep)
                    # Fallback: return empty actions
                    from src.schemas.action import RequestedActions
                    return RequestedActions(timestep=timestep, actions=[])
                
                def update_grid_diagnostics(self, grid_diagnostics):
                    self.last_grid_diagnostics = grid_diagnostics
                    if self._impl and hasattr(self._impl, 'update_grid_diagnostics'):
                        self._impl.update_grid_diagnostics(grid_diagnostics)
                
                def reset(self):
                    self.timestep = 0
                    self.last_grid_diagnostics = None
                    if self._impl and hasattr(self._impl, 'reset'):
                        self._impl.reset()
            
            return DynamicController
        
        return controller_class
    
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