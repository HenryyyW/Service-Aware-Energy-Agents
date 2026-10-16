"""Repair agent for automated code diagnosis and fixing."""
import json
import hashlib
import subprocess
import tempfile
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from src.schemas.task import TaskSpec, TaskType, AssetSpec, ConstraintSpec
from src.schemas.diagnostics import DiagnosticReport, Diagnostic, DiagnosticCategory, Severity
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType, AgentMetrics
from src.schemas.action import RequestedActions, Action, ActionType


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
        Apply a patch to controller code.
        
        In a real implementation, this would use AST manipulation or LLM-based editing.
        For now, this is a placeholder that returns the original code.
        """
        # TODO: Implement actual code patching using AST or LLM
        # For now, return the original code
        return controller_code
    
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