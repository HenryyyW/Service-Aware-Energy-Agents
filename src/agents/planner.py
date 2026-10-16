"""Planner agent - analyzes diagnostics and creates repair plan."""
from typing import Optional, List, Dict, Any
from src.agents.roles import AgentState, PlannerOutput, AgentRole, Message
from src.schemas.diagnostics import DiagnosticReport, Diagnostic, DiagnosticCategory, Severity
from src.schemas.report import ExperimentResult, GridMetrics, ServiceMetrics


class PlannerAgent:
    """Planner agent that analyzes violations and creates a repair plan."""
    
    def __init__(self, model: str = "gpt-4", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature
    
    def plan(self, state: AgentState) -> PlannerOutput:
        """
        Analyze diagnostics and create a repair plan.
        
        Args:
            state: Current agent state with experiment results and diagnostics
            
        Returns:
            PlannerOutput with repair plan
        """
        # Analyze all violations
        violations = self._analyze_violations(state)
        
        # Determine primary issue
        primary_issue, secondary_issues = self._prioritize_issues(violations)
        
        # Root cause analysis
        root_cause = self._analyze_root_cause(primary_issue, violations, state)
        
        # Generate repair strategy
        strategy = self._generate_strategy(primary_issue, violations, state)
        
        # Identify target functions
        target_functions = self._identify_target_functions(primary_issue, state)
        
        # Define success criteria
        success_criteria = self._define_success_criteria(primary_issue, state)
        
        # Risk assessment
        risk = self._assess_risk(primary_issue, strategy)
        
        plan = PlannerOutput(
            primary_issue=primary_issue,
            secondary_issues=secondary_issues,
            root_cause_analysis=root_cause,
            repair_strategy=strategy,
            target_functions=target_functions,
            success_criteria=success_criteria,
            risk_assessment=risk
        )
        
        state.repair_plan = plan.model_dump()
        state.add_message(AgentRole.PLANNER, f"Created repair plan for {primary_issue}", plan.model_dump())
        
        return plan
    
    def _analyze_violations(self, state: AgentState) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze all violations from diagnostics and metrics."""
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
        for report in state.diagnostic_reports:
            for diag in report.diagnostics:
                cat = diag.category
                issue_data = {
                    "message": diag.message,
                    "severity": diag.severity.value,
                    "values": diag.values,
                    "limits": diag.limits,
                    "source": "diagnostic"
                }
                if cat == DiagnosticCategory.VOLTAGE:
                    violations["voltage"].append({**issue_data, "bus_indices": diag.bus_indices})
                elif cat == DiagnosticCategory.LINE_LOADING:
                    violations["line_loading"].append(issue_data)
                elif cat == DiagnosticCategory.TRANSFORMER_LOADING:
                    violations["transformer_loading"].append(issue_data)
                elif cat == DiagnosticCategory.EV_DEADLINE:
                    violations["ev_deadline"].append(issue_data)
                elif cat == DiagnosticCategory.COMFORT:
                    violations["comfort"].append(issue_data)
                elif cat == DiagnosticCategory.BATTERY_SOC:
                    violations["battery_soc"].append(issue_data)
                elif cat == DiagnosticCategory.FLEXIBLE_LOAD:
                    violations["flexible_load"].append(issue_data)
                elif cat == DiagnosticCategory.GRID_LIMIT:
                    if diag.values.get("limit_type") == "import":
                        violations["grid_import"].append(issue_data)
                    else:
                        violations["grid_export"].append(issue_data)
                elif cat == DiagnosticCategory.POWER_FLOW:
                    violations["power_flow"].append(issue_data)
        
        # From experiment result metrics
        grid: GridMetrics = state.experiment_result.grid
        service: ServiceMetrics = state.experiment_result.service
        
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
    
    def _prioritize_issues(self, violations: Dict[str, List[Dict]]) -> tuple:
        """Prioritize issues by severity and impact."""
        critical = []
        warnings = []
        
        for category, issues in violations.items():
            for issue in issues:
                severity = issue.get("severity", "warning")
                if severity in ["critical", "violation"]:
                    critical.append((category, issue))
                else:
                    warnings.append((category, issue))
        
        if critical:
            primary = critical[0][0]
            secondary = [c for c, _ in critical[1:]] + [c for c, _ in warnings]
        elif warnings:
            primary = warnings[0][0]
            secondary = [c for c, _ in warnings[1:]]
        else:
            primary = "none"
            secondary = []
        
        return primary, secondary
    
    def _analyze_root_cause(self, primary_issue: str, violations: Dict, state: AgentState) -> str:
        """Analyze root cause of the primary issue."""
        causes = {
            "voltage": "Insufficient voltage regulation - lack of reactive power support, excessive peak demand, or inadequate PV curtailment",
            "line_loading": "Power flow exceeds line thermal limits - unbalanced load distribution or excessive community import/export",
            "transformer_loading": "Total community demand exceeds transformer capacity - insufficient peak shaving or load shifting",
            "ev_deadline": "EV charging starts too late or uses insufficient power - scheduling algorithm doesn't account for deadline pressure",
            "comfort": "Temperature control doesn't pre-condition during off-peak or allows excessive deviation from setpoints",
            "battery_soc": "Battery SOC limits too aggressive or charging/discharging logic doesn't maintain reserves",
            "flexible_load": "Flexible load scheduler doesn't prioritize deadline-constrained loads",
            "grid_import": "Community import limit exceeded - insufficient peak shaving, load shifting, or local generation utilization",
            "grid_export": "Export limit exceeded - insufficient self-consumption or curtailment logic",
            "power_flow": "Network topology or extreme power flows cause convergence failure"
        }
        return causes.get(primary_issue, "Unknown root cause")
    
    def _generate_strategy(self, primary_issue: str, violations: Dict, state: AgentState) -> str:
        """Generate repair strategy for the primary issue."""
        strategies = {
            "voltage": "Implement voltage-aware control: add voltage monitoring, reactive power support from batteries, and voltage-triggered load reduction",
            "line_loading": "Add line loading constraints: monitor per-line loading, redistribute loads, curtail generation on overloaded lines",
            "transformer_loading": "Implement transformer loading limits: track total community power, proportional load reduction when approaching limit",
            "ev_deadline": "Improve EV charging scheduling: start earlier, use maximum power when deadline approaches, prioritize by departure time",
            "comfort": "Add comfort-aware pre-conditioning: pre-heat/cool during off-peak, wider deadbands during peak, predictive control",
            "battery_soc": "Dynamic battery reserves: adjust SOC limits based on forecast, maintain minimum reserve for critical periods",
            "flexible_load": "Deadline-aware flexible load scheduling: earliest-deadline-first, power allocation proportional to urgency",
            "grid_import": "Community import limit enforcement: real-time monitoring, proportional curtailment, battery discharge for peak shaving",
            "grid_export": "Export management: increase self-consumption via battery charging, curtail PV when export limit approached",
            "power_flow": "Power flow validation: add pre-check, fallback to simplified model, reduce extreme power injections"
        }
        return strategies.get(primary_issue, "General controller optimization needed")
    
    def _identify_target_functions(self, primary_issue: str, state: AgentState) -> List[str]:
        """Identify controller functions that need modification."""
        function_map = {
            "voltage": ["_apply_grid_limits", "_control_battery", "get_actions"],
            "line_loading": ["_apply_grid_limits", "get_actions"],
            "transformer_loading": ["_apply_grid_limits", "get_actions"],
            "ev_deadline": ["_control_ev", "get_actions"],
            "comfort": ["_control_flexible_load", "_apply_grid_limits"],
            "battery_soc": ["_control_battery", "_apply_grid_limits"],
            "flexible_load": ["_control_flexible_load", "get_actions"],
            "grid_import": ["_apply_grid_limits", "_control_battery"],
            "grid_export": ["_apply_grid_limits", "_control_battery"],
            "power_flow": ["get_actions", "_apply_grid_limits"]
        }
        return function_map.get(primary_issue, ["get_actions"])
    
    def _define_success_criteria(self, primary_issue: str, state: AgentState) -> Dict[str, Any]:
        """Define measurable success criteria."""
        criteria = {
            "voltage": {"voltage_violations": 0, "max_voltage_pu": 1.05, "min_voltage_pu": 0.95},
            "line_loading": {"line_loading_violations": 0, "max_line_loading_pct": 95.0},
            "transformer_loading": {"transformer_loading_violations": 0, "max_transformer_loading_pct": 90.0},
            "ev_deadline": {"ev_completion_rate": 0.95, "ev_worst_soc_at_departure": 0.8},
            "comfort": {"comfort_violation_degree_hours": 0, "max_deviation_c": 1.0},
            "battery_soc": {"battery_soc_violations": 0, "min_soc_maintained": True},
            "flexible_load": {"flexible_load_completion_rate": 0.95},
            "grid_import": {"import_limit_violations": 0, "peak_import_kw": "within_limit"},
            "grid_export": {"export_limit_violations": 0, "peak_export_kw": "within_limit"},
            "power_flow": {"power_flow_convergence_rate": 1.0}
        }
        return criteria.get(primary_issue, {"violations_resolved": True})
    
    def _assess_risk(self, primary_issue: str, strategy: str) -> str:
        """Assess risk of the proposed repair."""
        risk_levels = {
            "voltage": "Medium - Voltage changes affect all downstream loads",
            "line_loading": "Medium - Load redistribution may shift overloads",
            "transformer_loading": "Low - Load reduction is generally safe",
            "ev_deadline": "Low - Earlier charging is safe if power available",
            "comfort": "Medium - Wider deadbands may affect occupant satisfaction",
            "battery_soc": "Low - SOC limit changes are conservative",
            "flexible_load": "Low - Deadline-aware scheduling is improvement",
            "grid_import": "Low - Import limits are grid requirements",
            "grid_export": "Low - Export limits are grid requirements",
            "power_flow": "High - Model changes may introduce new issues"
        }
        return risk_levels.get(primary_issue, "Medium - General controller modification")