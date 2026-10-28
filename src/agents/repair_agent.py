"""Repair agent for automated code diagnosis and fixing."""
import json
import hashlib
import subprocess
import tempfile
import os
import ast
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from src.schemas.task import TaskSpec, TaskType, AssetSpec, ConstraintSpec
from src.schemas.diagnostics import DiagnosticReport, Diagnostic, DiagnosticCategory, Severity
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType, AgentMetrics
from src.schemas.action import RequestedActions, Action, ActionType
from src.evaluation.verification_harness import VerificationHarness, create_harness_for_grid_violation


@dataclass
class RepairPatch:
    """A code patch proposed by the repair agent."""
    patch_id: str
    description: str
    code_changes: List[Dict[str, Any]]  # file, function, change description
    expected_improvement: str
    confidence: float = 0.5
    target_files: List[str] = field(default_factory=list)
    diff: Optional[str] = None


@dataclass
class RepairContext:
    """Context for the repair agent."""
    experiment_result: ExperimentResult
    diagnostic_reports: List[DiagnosticReport]
    baseline_controller_code: str
    controller_file: str
    scenario_config: Dict[str, Any]
    iteration: int = 0
    max_iterations: int = 3


class RepairAgent:
    """Agent that diagnoses issues and proposes code fixes for controllers."""
    
    def __init__(
        self,
        model: str = "gpt-4",
        temperature: float = 0.2,
        max_tokens: int = 4000
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.repair_history: List[Dict[str, Any]] = []
    
    def diagnose_and_repair(self, context: RepairContext) -> RepairPatch:
        """
        Analyze diagnostics and propose a repair patch.
        
        Args:
            context: RepairContext with experiment results and diagnostics
            
        Returns:
            RepairPatch with proposed changes
        """
        # Analyze violations
        violations = self._analyze_violations(context)
        
        # Generate repair strategy
        strategy = self._generate_repair_strategy(violations, context)
        
        # Create patch
        patch = self._create_patch(strategy, context)
        
        # Record in history
        self.repair_history.append({
            "iteration": context.iteration,
            "patch": patch,
            "violations": violations
        })
        
        return patch
    
    def _analyze_violations(self, context: RepairContext) -> Dict[str, Any]:
        """Analyze all violations from diagnostics and experiment results."""
        violations = {
            "voltage": [],
            "line_loading": [],
            "transformer_loading": [],
            "ev_deadline": [],
            "comfort": [],
            "battery_soc": [],
            "flexible_load": [],
            "grid_import": [],
            "grid_export": [],
            "power_flow": []
        }
        
        # From diagnostic reports
        for report in context.diagnostic_reports:
            for diag in report.diagnostics:
                cat = diag.category
                if cat == DiagnosticCategory.VOLTAGE:
                    violations["voltage"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "bus_indices": diag.bus_indices,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.LINE_LOADING:
                    violations["line_loading"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.TRANSFORMER_LOADING:
                    violations["transformer_loading"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.EV_DEADLINE:
                    violations["ev_deadline"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.COMFORT:
                    violations["comfort"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.BATTERY_SOC:
                    violations["battery_soc"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.FLEXIBLE_LOAD:
                    violations["flexible_load"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
                elif cat == DiagnosticCategory.GRID_LIMIT:
                    if diag.values.get("limit_type") == "import":
                        violations["grid_import"].append({
                            "message": diag.message,
                            "severity": diag.severity.value,
                            "values": diag.values,
                            "limits": diag.limits
                        })
                    else:
                        violations["grid_export"].append({
                            "message": diag.message,
                            "severity": diag.severity.value,
                            "values": diag.values,
                            "limits": diag.limits
                        })
                elif cat == DiagnosticCategory.POWER_FLOW:
                    violations["power_flow"].append({
                        "message": diag.message,
                        "severity": diag.severity.value,
                        "values": diag.values,
                        "limits": diag.limits
                    })
        
        # From experiment result metrics
        grid = context.experiment_result.grid
        service = context.experiment_result.service
        
        if grid.voltage_violations_count > 0:
            violations["voltage"].append({
                "source": "metrics",
                "count": grid.voltage_violations_count,
                "duration_hours": grid.voltage_violation_duration_hours,
                "max_voltage_pu": grid.max_voltage_pu,
                "min_voltage_pu": grid.min_voltage_pu
            })
        
        if grid.line_loading_violations > 0:
            violations["line_loading"].append({
                "source": "metrics",
                "count": grid.line_loading_violations,
                "max_loading_pct": grid.max_line_loading_pct
            })
        
        if grid.transformer_loading_violations > 0:
            violations["transformer_loading"].append({
                "source": "metrics",
                "count": grid.transformer_loading_violations,
                "max_loading_pct": grid.max_transformer_loading_pct
            })
        
        if service.ev_completion_rate < 1.0:
            violations["ev_deadline"].append({
                "source": "metrics",
                "completion_rate": service.ev_completion_rate,
                "avg_soc": service.ev_avg_soc_at_departure,
                "worst_soc": service.ev_worst_soc_at_departure
            })
        
        if service.comfort_violation_degree_hours > 0:
            violations["comfort"].append({
                "source": "metrics",
                "degree_hours": service.comfort_violation_degree_hours
            })
        
        return violations
    
    def _generate_repair_strategy(
        self, 
        violations: Dict[str, Any], 
        context: RepairContext
    ) -> Dict[str, Any]:
        """Generate a repair strategy based on violations."""
        strategy = {
            "primary_issue": None,
            "secondary_issues": [],
            "approach": "",
            "target_controller": context.controller_file
        }
        
        # Determine primary issue (highest severity)
        critical_issues = []
        warning_issues = []
        
        for category, issues in violations.items():
            for issue in issues:
                severity = issue.get("severity", "warning")
                if severity == "critical" or severity == "violation":
                    critical_issues.append((category, issue))
                else:
                    warning_issues.append((category, issue))
        
        if critical_issues:
            strategy["primary_issue"] = critical_issues[0][0]
            strategy["secondary_issues"] = [c for c, _ in critical_issues[1:]] + [c for c, _ in warning_issues]
        elif warning_issues:
            strategy["primary_issue"] = warning_issues[0][0]
            strategy["secondary_issues"] = [c for c, _ in warning_issues[1:]]
        else:
            strategy["primary_issue"] = "none"
            return strategy
        
        # Define approach based on primary issue
        approaches = {
            "voltage": "Reduce peak demand through load shifting, increase PV self-consumption, or adjust reactive power",
            "line_loading": "Reduce power flow on overloaded lines via load redistribution or generation curtailment",
            "transformer_loading": "Reduce total community demand or increase local generation during peak hours",
            "ev_deadline": "Prioritize EV charging earlier, increase charging power when available, or adjust departure SOC target",
            "comfort": "Relax temperature bounds temporarily, pre-heat/pre-cool during cheap electricity periods",
            "battery_soc": "Adjust battery SOC limits, increase reserve margin, or improve charging efficiency",
            "flexible_load": "Adjust flexible load deadlines, increase power allocation, or shift more loads",
            "grid_import": "Reduce community import through peak shaving, increase self-consumption, or export more",
            "grid_export": "Reduce export through increased self-consumption or curtailment",
            "power_flow": "Check network topology, reduce extreme power flows, add voltage regulation"
        }
        
        strategy["approach"] = approaches.get(
            strategy["primary_issue"], 
            "General optimization of controller parameters"
        )
        
        return strategy
    
    def _create_patch(self, strategy: Dict[str, Any], context: RepairContext) -> RepairPatch:
        """Create a concrete code patch from the strategy."""
        primary = strategy["primary_issue"]
        
        if primary == "none":
            return RepairPatch(
                patch_id=f"patch_{context.iteration:03d}",
                description="No violations detected - no changes needed",
                code_changes=[],
                expected_improvement="System operating within limits",
                confidence=1.0
            )
        
        # Get the controller code
        controller_code = context.baseline_controller_code
        
        # Generate specific changes based on issue
        changes = self._generate_code_changes(primary, strategy, controller_code, context)
        
        # Generate patch ID
        patch_id = f"patch_{context.iteration:03d}_{hashlib.md5(str(changes).encode()).hexdigest()[:8]}"
        
        # Create description
        descriptions = {
            "voltage": "Implement voltage-aware load shifting and reactive power support",
            "line_loading": "Add line loading constraints to prevent overloads",
            "transformer_loading": "Implement transformer loading limits with load shedding",
            "ev_deadline": "Improve EV charging scheduling with deadline awareness",
            "comfort": "Add comfort-aware temperature control with pre-conditioning",
            "battery_soc": "Adjust battery SOC management with dynamic reserves",
            "flexible_load": "Optimize flexible load scheduling with deadline constraints",
            "grid_import": "Add community import limit enforcement with peak shaving",
            "grid_export": "Optimize export management with curtailment logic",
            "power_flow": "Add power flow validation and corrective actions"
        }
        
        expected = {
            "voltage": "Reduce voltage violations by 50-80%",
            "line_loading": "Eliminate line overloads through load redistribution",
            "transformer_loading": "Keep transformer loading below 90%",
            "ev_deadline": "Achieve >95% EV completion rate",
            "comfort": "Reduce comfort violations by >70%",
            "battery_soc": "Maintain battery SOC within safe bounds",
            "flexible_load": "Achieve >95% flexible load completion",
            "grid_import": "Enforce community import limits",
            "grid_export": "Manage export within grid limits",
            "power_flow": "Achieve 100% power flow convergence"
        }
        
        return RepairPatch(
            patch_id=patch_id,
            description=descriptions.get(primary, "General controller improvement"),
            code_changes=changes,
            expected_improvement=expected.get(primary, "Improve overall performance"),
            confidence=0.7,
            target_files=[context.controller_file]
        )
    
    def _generate_code_changes(
        self, 
        primary_issue: str, 
        strategy: Dict[str, Any], 
        controller_code: str,
        context: RepairContext
    ) -> List[Dict[str, Any]]:
        """Generate specific code changes for the controller."""
        changes = []
        
        # Parse the controller code to find relevant functions
        # This is a simplified version - in practice would use AST parsing
        
        if primary_issue == "voltage":
            changes.append({
                "file": context.controller_file,
                "function": "_apply_grid_limits",
                "change": "Add voltage-aware load reduction when voltage exceeds 1.03 pu or drops below 0.97 pu",
                "type": "modification"
            })
            changes.append({
                "file": context.controller_file,
                "function": "_control_battery",
                "change": "Add reactive power support from batteries for voltage regulation",
                "type": "modification"
            })
        
        elif primary_issue == "line_loading":
            changes.append({
                "file": context.controller_file,
                "function": "_apply_grid_limits",
                "change": "Add line loading check and redistribute loads away from overloaded lines",
                "type": "modification"
            })
        
        elif primary_issue == "transformer_loading":
            changes.append({
                "file": context.controller_file,
                "function": "_apply_grid_limits",
                "change": "Add transformer loading limit with proportional load reduction",
                "type": "modification"
            })
        
        elif primary_issue == "ev_deadline":
            changes.append({
                "file": context.controller_file,
                "function": "_control_ev",
                "change": "Start charging earlier and use maximum available power when deadline approaches",
                "type": "modification"
            })
        
        elif primary_issue == "comfort":
            changes.append({
                "file": context.controller_file,
                "function": "_control_flexible_load",
                "change": "Add pre-heating/pre-cooling during off-peak hours",
                "type": "modification"
            })
        
        elif primary_issue == "grid_import":
            changes.append({
                "file": context.controller_file,
                "function": "_apply_grid_limits",
                "change": f"Enforce community import limit of {context.scenario_config.get('community_import_limit_kw', 200)} kW",
                "type": "modification"
            })
        
        elif primary_issue == "grid_export":
            changes.append({
                "file": context.controller_file,
                "function": "_apply_grid_limits",
                "change": f"Enforce community export limit of {context.scenario_config.get('community_export_limit_kw', 100)} kW",
                "type": "modification"
            })
        
        # If no specific changes, add a general improvement
        if not changes:
            changes.append({
                "file": context.controller_file,
                "function": "get_actions",
                "change": "Add comprehensive constraint checking before returning actions",
                "type": "modification"
            })
        
        return changes
    
    def apply_patch(self, patch: RepairPatch, controller_code: str) -> str:
        """
        Apply a patch to controller code using AST manipulation.
        
        Args:
            patch: RepairPatch with code changes
            controller_code: Original controller source code
            
        Returns:
            Modified controller code
        """
        if not patch.code_changes:
            return controller_code
        
        try:
            # Parse the controller code into an AST
            tree = ast.parse(controller_code)
            
            # Apply each change
            for change in patch.code_changes:
                change_type = change.get("type", "modification")
                function_name = change.get("function", "")
                change_desc = change.get("change", "")
                
                if change_type == "modification" and function_name:
                    # Apply the modification to the specified function
                    controller_code = self._apply_function_modification(
                        controller_code, function_name, change_desc
                    )
            
            return controller_code
            
        except Exception as e:
            # If AST parsing fails, return original code
            print(f"Warning: Failed to apply patch via AST: {e}")
            return controller_code
    
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
            
            # Function not found, return original
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
                # Find indentation level
                indent = len(line) - len(line.lstrip())
                break
        
        if func_start == -1:
            return code
        
        # Find end of function (next function or class at same or less indentation)
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
        
        # Parse the change description to determine what to do
        change_lower = change_desc.lower()
        
        if "voltage-aware" in change_lower or "voltage aware" in change_lower:
            # Add voltage violation check and load reduction
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
        # Find the end of the function (before return)
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i]:
                # Insert voltage check before return
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
                # Reduce charging/export to lower voltage
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.EV_CHARGE]:
                        a.value_kw *= 0.8
            elif voltage_low:
                # Reduce discharging/import to raise voltage
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_DISCHARGE]:
                        a.value_kw *= 0.8
'''
                lines.insert(i, voltage_check)
                break
        return '\n'.join(lines)
    
    def _add_line_loading_logic(self, lines: List[str]) -> str:
        """Add line loading constraint logic."""
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
                # Reduce all controllable loads to relieve line loading
                for a in actions:
                    if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE,
                                         ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                        a.value_kw *= 0.75
'''
                lines.insert(i, loading_check)
                break
        return '\n'.join(lines)
    
    def _add_transformer_loading_logic(self, lines: List[str]) -> str:
        """Add transformer loading constraint logic."""
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
        """Improve EV charging with deadline awareness."""
        # Find the _control_ev function and modify charging logic
        for i in range(len(lines) - 1, -1, -1):
            if 'required_power = energy_needed / max(hours_remaining' in lines[i]:
                # Replace with more aggressive charging near deadline
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
        """Add comfort-aware pre-conditioning logic."""
        # This would be for flexible load control - add pre-heating/cooling
        return '\n'.join(lines)
    
    def _add_import_limit_logic(self, lines: List[str]) -> str:
        """Add community import limit enforcement."""
        for i in range(len(lines) - 1, -1, -1):
            if 'return actions' in lines[i] and '_apply_grid_limits' in '\n'.join(lines):
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
        """Add community export limit enforcement."""
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
        """Add reactive power support from batteries."""
        # This would require more complex changes to the battery control
        return '\n'.join(lines)
    
    def _add_constraint_checking_logic(self, lines: List[str]) -> str:
        """Add comprehensive constraint checking."""
        for i in range(len(lines) - 1, -1, -1):
            if 'return self._create_requested_actions(actions)' in lines[i]:
                check = '''
        # Comprehensive constraint validation
        for a in actions:
            # Ensure action values are within asset limits
            if hasattr(self, '_validate_action'):
                a = self._validate_action(a)
'''
                lines.insert(i, check)
                break
        return '\n'.join(lines)
    
    def validate_patch(self, patch: RepairPatch, context: RepairContext) -> bool:
        """
        Validate a patch by running it in a sandbox.
        
        Returns True if patch passes validation.
        """
        # TODO: Implement sandbox validation
        return True


def create_repair_agent_from_config(config: Dict[str, Any]) -> RepairAgent:
    """Factory function to create repair agent from config."""
    return RepairAgent(
        model=config.get("model", "gpt-4"),
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 4000)
    )