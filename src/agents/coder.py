"""Coder agent - implements code changes based on repair plan."""

import ast
import textwrap
from typing import Optional, List, Dict, Any, Callable
from src.agents.roles import AgentState, CoderOutput, AgentRole
from src.agents.planner import PlannerOutput


class CoderAgent:
    """Coder agent that implements code changes based on the repair plan."""

    def __init__(self, model: str = "gpt-4", temperature: float = 0.2):
        self.model = model
        self.temperature = temperature

    def code(
        self, state: AgentState, plan: PlannerOutput, controller_file: str = None
    ) -> CoderOutput:
        """
        Implement code changes based on the repair plan.

        Args:
            state: Current agent state with controller code
            plan: Repair plan from Planner
            controller_file: Path to controller file (for change tracking)

        Returns:
            CoderOutput with code changes and patched code
        """
        changes = []

        # Get controller file from state or parameter
        controller_file = (
            controller_file or state.controller_file or "controllers/rule_based.py"
        )

        # Generate changes for each target function
        for func_name in plan.target_functions:
            func_changes = self._generate_function_changes(
                func_name,
                plan.primary_issue,
                plan.repair_strategy,
                state.controller_code,
                controller_file,
            )
            changes.extend(func_changes)

        # Apply changes to create patched code
        patched_code = self._apply_changes(state.controller_code, changes)

        # Generate diff
        diff = self._generate_diff(state.controller_code, patched_code)

        output = CoderOutput(
            code_changes=changes,
            patched_code=patched_code,
            diff=diff,
            implementation_notes=f"Implemented {plan.repair_strategy} for {plan.primary_issue}",
        )

        state.code_changes = changes
        state.patched_code = patched_code
        state.add_message(
            AgentRole.CODER,
            f"Implemented {len(changes)} code changes",
            output.model_dump(),
        )

        return output

    def _generate_function_changes(
        self,
        func_name: str,
        primary_issue: str,
        strategy: str,
        controller_code: str,
        controller_file: str,
    ) -> List[Dict[str, Any]]:
        """Generate specific code changes for a function."""
        changes = []

        # Find the function in the controller code
        func_info = self._find_function(controller_code, func_name)

        if not func_info:
            # Function doesn't exist, suggest adding it
            changes.append(
                {
                    "file": controller_file,
                    "function": func_name,
                    "change": f"Add new function {func_name} for {primary_issue} handling",
                    "type": "addition",
                    "location": "end_of_class",
                }
            )
            return changes

        # Generate specific changes based on issue and function
        change_details = self._get_change_details(primary_issue, func_name, strategy)

        for detail in change_details:
            changes.append(
                {
                    "file": controller_file,
                    "function": func_name,
                    "change": detail,
                    "type": "modification",
                    "location": func_info["lineno"],
                }
            )

        return changes

    def _find_function(self, code: str, func_name: str) -> Optional[Dict[str, Any]]:
        """Find function definition in code using AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == func_name:
                    return {
                        "name": node.name,
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "args": [arg.arg for arg in node.args.args],
                    }
        except SyntaxError:
            pass
        return None

    def _find_function_node(
        self, tree: ast.AST, func_name: str
    ) -> Optional[ast.FunctionDef]:
        """Find function node in AST tree."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node
        return None

    def _get_change_details(
        self, primary_issue: str, func_name: str, strategy: str
    ) -> List[str]:
        """Get specific change details for an issue and function."""
        details_map = {
            "voltage": {
                "_apply_grid_limits": [
                    "Add voltage monitoring: check bus voltages from grid_diagnostics",
                    "Add voltage-triggered load reduction: if voltage > 1.03 pu or < 0.97 pu, reduce flexible loads and battery charging",
                    "Add reactive power support: use battery inverters for voltage regulation",
                ],
                "_control_battery": [
                    "Add voltage regulation mode: when voltage deviates, adjust battery reactive power output",
                    "Implement volt-var curve: Q = f(V) for voltage support",
                ],
                "get_actions": [
                    "Add voltage check before returning actions",
                    "Pass voltage constraints to sub-controllers",
                ],
            },
            "line_loading": {
                "_apply_grid_limits": [
                    "Add line loading monitoring from grid_diagnostics",
                    "Implement load redistribution: shift loads from overloaded lines",
                    "Add generation curtailment on overloaded lines",
                ],
                "get_actions": ["Pass line loading constraints to limit checking"],
            },
            "transformer_loading": {
                "_apply_grid_limits": [
                    "Add transformer loading check from grid_diagnostics",
                    "Implement proportional load reduction when loading > 90%",
                    "Coordinate battery discharge to reduce transformer load",
                ],
                "get_actions": ["Add transformer loading constraint to limit checking"],
            },
            "ev_deadline": {
                "_control_ev": [
                    "Calculate time-to-departure more precisely",
                    "Start charging earlier when SOC is low",
                    "Use maximum available power when deadline < 2 hours",
                    "Prioritize EVs by departure time (earliest first)",
                ],
                "get_actions": ["Ensure EV actions respect deadline constraints"],
            },
            "comfort": {
                "_control_flexible_load": [
                    "Add pre-conditioning: pre-heat/cool 2 hours before peak",
                    "Widen temperature deadband during peak pricing",
                    "Use thermal mass for load shifting",
                ],
                "_apply_grid_limits": [
                    "Relax comfort constraints only when grid critical"
                ],
            },
            "battery_soc": {
                "_control_battery": [
                    "Add dynamic SOC reserve: increase min SOC before peak",
                    "Implement SOC forecast based on net load prediction",
                    "Maintain emergency reserve (10-15%) at all times",
                ],
                "_apply_grid_limits": ["Enforce battery SOC limits in limit checking"],
            },
            "flexible_load": {
                "_control_flexible_load": [
                    "Implement earliest-deadline-first scheduling",
                    "Allocate power proportional to urgency",
                    "Add deadline tracking and alerts",
                ],
                "get_actions": ["Pass flexible load deadlines to limit checking"],
            },
            "grid_import": {
                "_apply_grid_limits": [
                    "Enforce community import limit from scenario config",
                    "Proportional curtailment when limit exceeded",
                    "Prioritize battery discharge over import",
                ],
                "_control_battery": [
                    "Discharge battery to reduce grid import during peak"
                ],
            },
            "grid_export": {
                "_apply_grid_limits": [
                    "Enforce community export limit from scenario config",
                    "Curtail PV when export limit approached",
                    "Charge batteries to absorb excess generation",
                ],
                "_control_battery": [
                    "Charge battery to absorb excess PV instead of exporting"
                ],
            },
            "power_flow": {
                "get_actions": [
                    "Add power flow pre-check before applying actions",
                    "Fallback to safe actions if power flow fails",
                ],
                "_apply_grid_limits": [
                    "Reduce action magnitude if power flow diverges"
                ],
            },
        }

        return details_map.get(primary_issue, {}).get(
            func_name,
            [f"Modify {func_name} to address {primary_issue} per strategy: {strategy}"],
        )

    def _apply_changes(self, code: str, changes: List[Dict[str, Any]]) -> str:
        """
        Apply changes to code using AST manipulation.

        Args:
            code: Original controller code
            changes: List of changes to apply

        Returns:
            Modified code with changes applied
        """
        if not changes:
            return code

        try:
            # Parse the code into AST
            tree = ast.parse(code)

            # Sort changes by line number in descending order
            # so we don't mess up line numbers when modifying
            sorted_changes = sorted(
                changes, key=lambda x: x.get("location", 0), reverse=True
            )

            # Apply each change
            for change in sorted_changes:
                func_name = change["function"]
                change_type = change["type"]
                change_desc = change["change"]

                # Find the function to modify
                func_node = self._find_function_node(tree, func_name)
                if func_node:
                    if change_type == "modification":
                        # Apply actual AST transformations based on change description
                        self._apply_ast_transformation(func_node, change_desc)
                    elif change_type == "addition":
                        # For additions, we would add new functions - placeholder for now
                        pass

            # Convert AST back to code
            return ast.unparse(tree)
        except Exception as e:
            # If AST manipulation fails, fall back to original code with error comment
            # Comment EVERY line to avoid syntax errors
            error_lines = [f"# ERROR APPLYING CHANGES: {str(e)}"]
            for c in changes:
                for line in c["change"].split("\n"):
                    error_lines.append(f"# {line}")
            return code + "\n\n" + "\n".join(error_lines)

    def _apply_ast_transformation(
        self, func_node: ast.FunctionDef, change_desc: str
    ) -> None:
        """
        Apply actual AST transformation based on change description.

        This implements deterministic AST transformations for grid-violation fixes.
        """
        # Determine transformation type from change description
        transformation = self._determine_transformation(change_desc)
        if transformation:
            transformation(func_node)

    def _determine_transformation(self, change_desc: str) -> Optional[Callable]:
        """
        Map change description to actual AST transformation function.

        Returns a callable that takes a FunctionDef node and modifies it in place.
        """
        desc_lower = change_desc.lower()

        # Voltage-related transformations
        if (
            "voltage monitoring" in change_desc.lower()
            and "voltage > 1.03" in change_desc.lower()
        ):
            return self._add_voltage_monitoring_and_reduction
        elif "voltage-triggered load reduction" in change_desc.lower():
            return self._add_voltage_triggered_load_reduction
        elif (
            "reactive power support" in change_desc.lower()
            or "volt-var" in change_desc.lower()
        ):
            return self._add_volt_var_support
        elif (
            "voltage regulation mode" in change_desc.lower()
            or "adjust battery reactive power" in change_desc.lower()
        ):
            return self._add_voltage_regulation_mode
        elif (
            "volt-var curve" in change_desc.lower() or "q = f(v)" in change_desc.lower()
        ):
            return self._add_volt_var_curve

        # Line loading transformations
        elif "line loading monitoring" in change_desc.lower():
            return self._add_line_loading_monitoring
        elif (
            "load redistribution" in change_desc.lower()
            or "shift loads" in change_desc.lower()
        ):
            return self._add_load_redistribution
        elif "generation curtailment" in change_desc.lower():
            return self._add_generation_curtailment

        # Transformer loading transformations
        elif "transformer loading check" in change_desc.lower():
            return self._add_transformer_loading_check
        elif (
            "proportional load reduction" in change_desc.lower()
            or "loading > 90%" in change_desc.lower()
        ):
            return self._add_proportional_load_reduction
        elif (
            "coordinate battery discharge" in change_desc.lower()
            and "transformer" in change_desc.lower()
        ):
            return self._add_coordinated_battery_discharge

        # EV deadline transformations
        elif (
            "time-to-departure" in change_desc.lower()
            and "precisely" in change_desc.lower()
        ):
            return self._add_precise_time_to_departure
        elif (
            "start charging earlier" in change_desc.lower()
            or "soc is low" in change_desc.lower()
        ):
            return self._add_early_charging_for_low_soc
        elif (
            "maximum available power" in change_desc.lower()
            and "deadline < 2 hours" in change_desc.lower()
        ):
            return self._add_max_power_for_urgent_deadline
        elif (
            "prioritize evs by departure time" in change_desc.lower()
            or "earliest first" in change_desc.lower()
        ):
            return self._add_ev_prioritization_by_departure

        # Comfort transformations
        elif (
            "pre-conditioning" in change_desc.lower()
            or "pre-heat" in change_desc.lower()
        ):
            return self._add_preconditioning
        elif (
            "widen temperature deadband" in change_desc.lower()
            or "deadband during peak" in change_desc.lower()
        ):
            return self._add_wider_deadband
        elif (
            "thermal mass" in change_desc.lower()
            and "load shifting" in change_desc.lower()
        ):
            return self._add_thermal_mass_load_shifting

        # Battery SOC transformations
        elif (
            "dynamic soc reserve" in change_desc.lower()
            or "increase min soc before peak" in change_desc.lower()
        ):
            return self._add_dynamic_soc_reserve
        elif (
            "soc forecast" in change_desc.lower()
            or "net load prediction" in change_desc.lower()
        ):
            return self._add_soc_forecast
        elif (
            "emergency reserve" in change_desc.lower()
            or "10-15%" in change_desc.lower()
        ):
            return self._add_emergency_reserve

        # Flexible load transformations
        elif "earliest-deadline-first" in change_desc.lower():
            return self._add_earliest_deadline_first
        elif "allocate power proportional to urgency" in change_desc.lower():
            return self._add_proportional_power_allocation
        elif (
            "deadline tracking" in change_desc.lower()
            and "alerts" in change_desc.lower()
        ):
            return self._add_deadline_tracking

        # Grid import/export transformations
        elif "enforce community import limit" in change_desc.lower():
            return self._add_import_limit_enforcement
        elif (
            "proportional curtailment" in change_desc.lower()
            and "limit exceeded" in change_desc.lower()
        ):
            return self._add_proportional_curtailment
        elif "prioritize battery discharge over import" in change_desc.lower():
            return self._add_battery_discharge_priority
        elif "enforce community export limit" in change_desc.lower():
            return self._add_export_limit_enforcement
        elif "curtail pv when export limit" in change_desc.lower():
            return self._add_pv_curtailment
        elif "charge batteries to absorb excess" in change_desc.lower():
            return self._add_battery_charge_for_excess_pv

        # Power flow transformations
        elif "power flow pre-check" in change_desc.lower():
            return self._add_power_flow_precheck
        elif (
            "fallback to safe actions" in change_desc.lower()
            and "power flow fails" in change_desc.lower()
        ):
            return self._add_power_flow_fallback
        elif (
            "reduce action magnitude" in change_desc.lower()
            and "power flow diverges" in change_desc.lower()
        ):
            return self._add_action_magnitude_reduction

        return None

    # --- Voltage Transformation Implementations ---

    def _add_voltage_monitoring_and_reduction(self, func_node: ast.FunctionDef) -> None:
        """Add voltage monitoring and triggered load reduction for overvoltage/undervoltage."""
        # Build AST nodes for voltage monitoring from textwrap.dedent + ast.parse
        snippet = textwrap.dedent("""
        # Voltage monitoring from grid diagnostics
        overvoltage = False
        undervoltage = False
        if self.last_grid_diagnostics:
            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
            for d in diagnostics:
                category = d.get("category", "")
                severity = d.get("severity", "")
                if severity in ["violation", "critical"] and category == "voltage":
                    values = d.get("values", {})
                    voltage_pu = values.get("voltage_pu", 1.0)
                    if voltage_pu > 1.03:
                        overvoltage = True
                    elif voltage_pu < 0.97:
                        undervoltage = True
        """)
        monitoring_ast = ast.parse(snippet)
        for stmt in reversed(monitoring_ast.body):
            func_node.body.insert(0, stmt)

    def _add_voltage_triggered_load_reduction(self, func_node: ast.FunctionDef) -> None:
        """Add voltage-triggered load reduction when voltage exceeds limits."""
        # Find return statement and insert before it
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Voltage-triggered load reduction (self-contained)
                overvoltage = False
                undervoltage = False
                if self.last_grid_diagnostics:
                    diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
                    for d in diagnostics:
                        category = d.get("category", "")
                        severity = d.get("severity", "")
                        if severity in ["violation", "critical"] and category == "voltage":
                            values = d.get("values", {})
                            voltage_pu = values.get("voltage_pu", 1.0)
                            if voltage_pu > 1.03:
                                overvoltage = True
                            elif voltage_pu < 0.97:
                                undervoltage = True
                if overvoltage:
                    for a in actions:
                        if a.action_type in [ActionType.FLEXIBLE_LOAD, ActionType.BATTERY_CHARGE, ActionType.EV_CHARGE]:
                            a.value_kw *= 0.5
                elif undervoltage:
                    for a in actions:
                        if a.action_type == ActionType.BATTERY_DISCHARGE:
                            a.value_kw *= 0.5
                """)
                reduction_ast = ast.parse(snippet)
                for new_stmt in reversed(reduction_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_volt_var_support(self, func_node: ast.FunctionDef) -> None:
        """Add reactive power support - skip (method doesn't exist on controller)."""
        pass

    def _add_voltage_regulation_mode(self, func_node: ast.FunctionDef) -> None:
        """Add voltage regulation mode to battery control - skip (requires _set_battery_reactive_power)."""
        pass

    def _add_volt_var_curve(self, func_node: ast.FunctionDef) -> None:
        """Add volt-var curve Q = f(V) - skip (requires _set_battery_reactive_power)."""
        pass

    # --- Line Loading Transformation Implementations ---

    def _add_line_loading_monitoring(self, func_node: ast.FunctionDef) -> None:
        """Add line loading monitoring from grid diagnostics."""
        snippet = textwrap.dedent("""
        # Line loading monitoring
        line_loading_violated = False
        max_line_loading = 0.0
        if self.last_grid_diagnostics:
            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
            for d in diagnostics:
                if d.get("category") == "line_loading" and d.get("severity") in ["violation", "critical"]:
                    line_loading_violated = True
                    values = d.get("values", {})
                    loading = values.get("line_loading_pct", 0)
                    max_line_loading = max(max_line_loading, loading)
        """)
        monitoring_ast = ast.parse(snippet)
        for stmt in reversed(monitoring_ast.body):
            func_node.body.insert(0, stmt)

    def _add_load_redistribution(self, func_node: ast.FunctionDef) -> None:
        """Add load redistribution for overloaded lines."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Load redistribution for overloaded lines (self-contained)
                line_loading_violated = False
                if self.last_grid_diagnostics:
                    diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
                    for d in diagnostics:
                        if d.get("category") == "line_loading" and d.get("severity") in ["violation", "critical"]:
                            line_loading_violated = True
                            break
                if line_loading_violated:
                    for a in actions:
                        if a.action_type in [ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                            a.value_kw *= 0.7
                """)
                redistribution_ast = ast.parse(snippet)
                for new_stmt in reversed(redistribution_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_generation_curtailment(self, func_node: ast.FunctionDef) -> None:
        """Add generation curtailment on overloaded lines."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Generation curtailment on overloaded lines (self-contained)
                line_loading_violated = False
                if self.last_grid_diagnostics:
                    diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
                    for d in diagnostics:
                        if d.get("category") == "line_loading" and d.get("severity") in ["violation", "critical"]:
                            line_loading_violated = True
                            break
                if line_loading_violated:
                    for a in actions:
                        if a.action_type == ActionType.BATTERY_DISCHARGE:
                            a.value_kw *= 1.2
                """)
                curtail_ast = ast.parse(snippet)
                for new_stmt in reversed(curtail_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    # --- Transformer Loading Transformation Implementations ---

    def _add_transformer_loading_check(self, func_node: ast.FunctionDef) -> None:
        """Add transformer loading check from grid diagnostics."""
        snippet = textwrap.dedent("""
        # Transformer loading check
        transformer_loading_violated = False
        max_transformer_loading = 0.0
        if self.last_grid_diagnostics:
            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
            for d in diagnostics:
                if d.get("category") == "transformer_loading" and d.get("severity") in ["violation", "critical"]:
                    transformer_loading_violated = True
                    values = d.get("values", {})
                    loading = values.get("transformer_loading_pct", 0)
                    max_transformer_loading = max(max_transformer_loading, loading)
        """)
        monitoring_ast = ast.parse(snippet)
        for stmt in reversed(monitoring_ast.body):
            func_node.body.insert(0, stmt)

    def _add_proportional_load_reduction(self, func_node: ast.FunctionDef) -> None:
        """Add proportional load reduction when transformer loading > 90%."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Proportional load reduction when transformer loading > 90% (self-contained)
                max_transformer_loading = 0.0
                if self.last_grid_diagnostics:
                    diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
                    for d in diagnostics:
                        if d.get("category") == "transformer_loading" and d.get("severity") in ["violation", "critical"]:
                            values = d.get("values", {})
                            loading = values.get("transformer_loading_pct", 0)
                            max_transformer_loading = max(max_transformer_loading, loading)
                if max_transformer_loading > 90:
                    reduction_factor = min(1.0, max_transformer_loading / 100.0)
                    for a in actions:
                        if a.action_type in [ActionType.BATTERY_CHARGE, ActionType.BATTERY_DISCHARGE, ActionType.EV_CHARGE, ActionType.FLEXIBLE_LOAD]:
                            a.value_kw *= (1.0 - reduction_factor * 0.5)
                """)
                reduction_ast = ast.parse(snippet)
                for new_stmt in reversed(reduction_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_coordinated_battery_discharge(self, func_node: ast.FunctionDef) -> None:
        """Add coordinated battery discharge to reduce transformer load."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Coordinate battery discharge to reduce transformer load (self-contained)
                max_transformer_loading = 0.0
                if self.last_grid_diagnostics:
                    diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
                    for d in diagnostics:
                        if d.get("category") == "transformer_loading" and d.get("severity") in ["violation", "critical"]:
                            values = d.get("values", {})
                            loading = values.get("transformer_loading_pct", 0)
                            max_transformer_loading = max(max_transformer_loading, loading)
                if max_transformer_loading > 90:
                    for a in actions:
                        if a.action_type == ActionType.BATTERY_DISCHARGE:
                            a.value_kw *= 1.5
                """)
                coord_ast = ast.parse(snippet)
                for new_stmt in reversed(coord_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    # --- EV Deadline Transformation Implementations ---

    def _add_precise_time_to_departure(self, func_node: ast.FunctionDef) -> None:
        """Add more precise time-to-departure calculation."""
        snippet = textwrap.dedent("""
        # More precise time-to-departure calculation
        if hour_of_day < departure_hour:
            hours_remaining = departure_hour - hour_of_day
        else:
            hours_remaining = (24 - hour_of_day) + departure_hour
        minutes_remaining = hours_remaining * 60
        """)
        precise_ast = ast.parse(snippet)
        for stmt in reversed(precise_ast.body):
            func_node.body.insert(0, stmt)

    def _add_early_charging_for_low_soc(self, func_node: ast.FunctionDef) -> None:
        """Start charging earlier when SOC is low."""
        snippet = textwrap.dedent("""
        # Start charging earlier when SOC is low
        if current_soc < 0.3:
            charge_kw = max_charge
        elif current_soc < 0.5:
            charge_kw = max_charge * 0.8
        else:
            charge_kw = max_charge * 0.5
        """)
        early_ast = ast.parse(snippet)
        for stmt in reversed(early_ast.body):
            func_node.body.insert(0, stmt)

    def _add_max_power_for_urgent_deadline(self, func_node: ast.FunctionDef) -> None:
        """Use maximum available power when deadline < 2 hours."""
        snippet = textwrap.dedent("""
        # Use maximum available power when deadline < 2 hours
        if hours_remaining < 2:
            charge_kw = max_charge
        """)
        max_power_ast = ast.parse(snippet)
        for stmt in reversed(max_power_ast.body):
            func_node.body.insert(0, stmt)

    def _add_ev_prioritization_by_departure(self, func_node: ast.FunctionDef) -> None:
        """Prioritize EVs by departure time (earliest first)."""
        snippet = textwrap.dedent("""
        # Prioritize EVs by departure time (earliest first)
        pass  # Would require sorting EV actions by departure time
        """)
        prioritize_ast = ast.parse(snippet)
        for stmt in reversed(prioritize_ast.body):
            func_node.body.insert(0, stmt)

    # --- Comfort Transformation Implementations ---

    def _add_preconditioning(self, func_node: ast.FunctionDef) -> None:
        """Add pre-conditioning: pre-heat/cool 2 hours before peak."""
        snippet = textwrap.dedent("""
        # Pre-conditioning: pre-heat/cool 2 hours before peak
        peak_hours = [17, 18, 19, 20]
        if hour_of_day in [h - 2 for h in peak_hours]:
            power_kw = fl.power_kw
        """)
        precond_ast = ast.parse(snippet)
        for stmt in reversed(precond_ast.body):
            func_node.body.insert(0, stmt)

    def _add_wider_deadband(self, func_node: ast.FunctionDef) -> None:
        """Widen temperature deadband during peak pricing."""
        snippet = textwrap.dedent("""
        # Widen temperature deadband during peak pricing
        peak_pricing = 17 <= hour_of_day < 21
        if peak_pricing:
            temp_min = 19.0
            temp_max = 26.0
        else:
            temp_min = 20.0
            temp_max = 25.0
        """)
        deadband_ast = ast.parse(snippet)
        for stmt in reversed(deadband_ast.body):
            func_node.body.insert(0, stmt)

    def _add_thermal_mass_load_shifting(self, func_node: ast.FunctionDef) -> None:
        """Use thermal mass for load shifting."""
        snippet = textwrap.dedent("""
        # Use thermal mass for load shifting
        if 17 <= hour_of_day < 21:
            power_kw = 0.0
        elif 14 <= hour_of_day < 17:
            power_kw = fl.power_kw * 1.2
        else:
            power_kw = fl.power_kw
        """)
        thermal_ast = ast.parse(snippet)
        for stmt in reversed(thermal_ast.body):
            func_node.body.insert(0, stmt)

    # --- Battery SOC Transformation Implementations ---

    def _add_dynamic_soc_reserve(self, func_node: ast.FunctionDef) -> None:
        """Add dynamic SOC reserve: increase min SOC before peak."""
        snippet = textwrap.dedent("""
        # Dynamic SOC reserve: increase min SOC before peak
        peak_hours = [17, 18, 19, 20]
        if hour_of_day in [h - 1 for h in peak_hours]:
            effective_soc_min = max(battery.soc_min, battery.soc_min + 0.1)
        else:
            effective_soc_min = battery.soc_min
        """)
        reserve_ast = ast.parse(snippet)
        for stmt in reversed(reserve_ast.body):
            func_node.body.insert(0, stmt)

    def _add_soc_forecast(self, func_node: ast.FunctionDef) -> None:
        """Implement SOC forecast based on net load prediction."""
        snippet = textwrap.dedent("""
        # SOC forecast based on net load prediction
        forecast_hours = 4
        avg_net_demand = net_demand
        predicted_soc = current_soc - (avg_net_demand * forecast_hours / capacity_kwh)
        """)
        forecast_ast = ast.parse(snippet)
        for stmt in reversed(forecast_ast.body):
            func_node.body.insert(0, stmt)

    def _add_emergency_reserve(self, func_node: ast.FunctionDef) -> None:
        """Maintain emergency reserve (10-15%) at all times."""
        snippet = textwrap.dedent("""
        # Emergency reserve (15%) at all times
        emergency_reserve = 0.15
        effective_soc_min = max(battery.soc_min, emergency_reserve)
        """)
        reserve_ast = ast.parse(snippet)
        for stmt in reversed(reserve_ast.body):
            func_node.body.insert(0, stmt)

    # --- Flexible Load Transformation Implementations ---

    def _add_earliest_deadline_first(self, func_node: ast.FunctionDef) -> None:
        """Implement earliest-deadline-first scheduling for flexible loads."""
        snippet = textwrap.dedent("""
        # Earliest-deadline-first scheduling
        flex_loads = sorted(
            [(fl_id, fl) for fl_id, fl in building.flexible_loads.items()],
            key=lambda x: x[1].latest_end
        )
        """)
        edf_ast = ast.parse(snippet)
        for stmt in reversed(edf_ast.body):
            func_node.body.insert(0, stmt)

    def _add_proportional_power_allocation(self, func_node: ast.FunctionDef) -> None:
        """Allocate power proportional to urgency."""
        snippet = textwrap.dedent("""
        # Allocate power proportional to urgency
        total_urgency = sum(1 / max(0.5, hours_until_deadline) for fl in flex_loads)
        for fl_id, fl in flex_loads:
            urgency = 1 / max(0.5, hours_until_deadline)
            allocated_power = fl.power_kw * (urgency / total_urgency)
        """)
        prop_ast = ast.parse(snippet)
        for stmt in reversed(prop_ast.body):
            func_node.body.insert(0, stmt)

    def _add_deadline_tracking(self, func_node: ast.FunctionDef) -> None:
        """Add deadline tracking and alerts."""
        snippet = textwrap.dedent("""
        # Deadline tracking and alerts
        if hours_until_deadline < 1.0 and progress < 0.5:
            pass  # Would trigger alert in production
        """)
        tracking_ast = ast.parse(snippet)
        for stmt in reversed(tracking_ast.body):
            func_node.body.insert(0, stmt)

    # --- Grid Import/Export Transformation Implementations ---

    def _add_import_limit_enforcement(self, func_node: ast.FunctionDef) -> None:
        """Enforce community import limit from scenario config."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Enforce community import limit
                import_limit = self.scenario_config.community_import_limit_kw
                if import_limit and total_import > import_limit:
                    scale = import_limit / total_import
                    for a in actions:
                        if a.value_kw > 0:
                            a.value_kw *= scale
                """)
                import_ast = ast.parse(snippet)
                for new_stmt in reversed(import_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_proportional_curtailment(self, func_node: ast.FunctionDef) -> None:
        """Proportional curtailment when limit exceeded."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Proportional curtailment when limit exceeded
                if total_import > import_limit:
                    excess = total_import - import_limit
                    for a in actions:
                        if a.value_kw > 0:
                            a.value_kw *= (1 - excess / total_import)
                """)
                curtail_ast = ast.parse(snippet)
                for new_stmt in reversed(curtail_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_battery_discharge_priority(self, func_node: ast.FunctionDef) -> None:
        """Discharge battery to reduce grid import during peak."""
        snippet = textwrap.dedent("""
        # Discharge battery to reduce grid import during peak
        peak_hours = [17, 18, 19, 20]
        if hour_of_day in peak_hours and battery_soc > battery.soc_min + 0.1:
            for a in actions:
                if a.action_type == ActionType.BATTERY_DISCHARGE:
                    a.value_kw *= 1.5
        """)
        discharge_ast = ast.parse(snippet)
        for stmt in reversed(discharge_ast.body):
            func_node.body.insert(0, stmt)

    def _add_export_limit_enforcement(self, func_node: ast.FunctionDef) -> None:
        """Enforce community export limit from scenario config."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Enforce community export limit
                export_limit = self.scenario_config.community_export_limit_kw
                if export_limit and total_export > export_limit:
                    scale = export_limit / total_export
                    for a in actions:
                        if a.value_kw < 0:
                            a.value_kw *= scale
                """)
                export_ast = ast.parse(snippet)
                for new_stmt in reversed(export_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_pv_curtailment(self, func_node: ast.FunctionDef) -> None:
        """Curtail PV when export limit approached."""
        snippet = textwrap.dedent("""
        # Curtail PV when export limit approached
        if export_limit and total_export > export_limit * 0.9:
            for a in actions:
                if a.action_type == ActionType.BATTERY_CHARGE and a.value_kw < 0:
                    pass  # PV curtailment handled at inverter level
        """)
        curtail_ast = ast.parse(snippet)
        for stmt in reversed(curtail_ast.body):
            func_node.body.insert(0, stmt)

    def _add_battery_charge_for_excess_pv(self, func_node: ast.FunctionDef) -> None:
        """Charge batteries to absorb excess generation instead of exporting."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Charge batteries to absorb excess PV
                if export_limit and total_export > export_limit * 0.8:
                    for a in actions:
                        if a.action_type == ActionType.BATTERY_CHARGE:
                            a.value_kw *= 1.5
                """)
                charge_ast = ast.parse(snippet)
                for new_stmt in reversed(charge_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    # --- Power Flow Transformation Implementations ---

    def _add_power_flow_precheck(self, func_node: ast.FunctionDef) -> None:
        """Add power flow pre-check before applying actions."""
        snippet = textwrap.dedent("""
        # Power flow pre-check
        if not self._check_power_flow_convergence(actions):
            return self._get_safe_fallback_actions()
        """)
        precheck_ast = ast.parse(snippet)
        for stmt in reversed(precheck_ast.body):
            func_node.body.insert(0, stmt)

    def _add_power_flow_fallback(self, func_node: ast.FunctionDef) -> None:
        """Fallback to safe actions if power flow fails."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Power flow fallback
                try:
                    if not self._run_power_flow(actions):
                        return self._get_safe_actions()
                except Exception:
                    return self._get_safe_actions()
                """)
                fallback_ast = ast.parse(snippet)
                for new_stmt in reversed(fallback_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _add_action_magnitude_reduction(self, func_node: ast.FunctionDef) -> None:
        """Reduce action magnitude if power flow diverges."""
        for i, stmt in enumerate(func_node.body):
            if isinstance(stmt, ast.Return):
                snippet = textwrap.dedent("""
                # Reduce action magnitude if power flow diverges
                if not self._check_power_flow_stability(actions):
                    for a in actions:
                        a.value_kw *= 0.8
                """)
                reduction_ast = ast.parse(snippet)
                for new_stmt in reversed(reduction_ast.body):
                    func_node.body.insert(i, new_stmt)
                break

    def _generate_diff(self, original: str, patched: str) -> str:
        """Generate a unified diff between original and patched code."""
        import difflib

        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines, patched_lines, fromfile="original", tofile="patched"
        )
        return "".join(diff)
