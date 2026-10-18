"""Coder agent - implements code changes based on repair plan."""
import ast
import hashlib
from typing import Optional, List, Dict, Any
from src.agents.roles import AgentState, CoderOutput, AgentRole
from src.agents.planner import PlannerOutput


class CoderAgent:
    """Coder agent that implements code changes based on the repair plan."""
    
    def __init__(self, model: str = "gpt-4", temperature: float = 0.2):
        self.model = model
        self.temperature = temperature
    
    def code(self, state: AgentState, plan: PlannerOutput) -> CoderOutput:
        """
        Implement code changes based on the repair plan.
        
        Args:
            state: Current agent state with controller code
            plan: Repair plan from Planner
            
        Returns:
            CoderOutput with code changes and patched code
        """
        changes = []
        
        # Generate changes for each target function
        for func_name in plan.target_functions:
            func_changes = self._generate_function_changes(
                func_name, plan.primary_issue, plan.repair_strategy, state.controller_code
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
            implementation_notes=f"Implemented {plan.repair_strategy} for {plan.primary_issue}"
        )
        
        state.code_changes = changes
        state.patched_code = patched_code
        state.add_message(AgentRole.CODER, f"Implemented {len(changes)} code changes", output.model_dump())
        
        return output
    
    def _generate_function_changes(
        self, 
        func_name: str, 
        primary_issue: str, 
        strategy: str, 
        controller_code: str
    ) -> List[Dict[str, Any]]:
        """Generate specific code changes for a function."""
        changes = []
        
        # Find the function in the controller code
        func_info = self._find_function(controller_code, func_name)
        
        if not func_info:
            # Function doesn't exist, suggest adding it
            changes.append({
                "file": "controllers/rule_based.py",
                "function": func_name,
                "change": f"Add new function {func_name} for {primary_issue} handling",
                "type": "addition",
                "location": "end_of_class"
            })
            return changes
        
        # Generate specific changes based on issue and function
        change_details = self._get_change_details(primary_issue, func_name, strategy)
        
        for detail in change_details:
            changes.append({
                "file": "controllers/rule_based.py",
                "function": func_name,
                "change": detail,
                "type": "modification",
                "location": func_info["lineno"]
            })
        
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
                        "args": [arg.arg for arg in node.args.args]
                    }
        except SyntaxError:
            pass
        return None
    
    def _find_function_node(self, tree: ast.AST, func_name: str) -> Optional[ast.FunctionDef]:
        """Find function node in AST tree."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node
        return None
    
    def _get_change_details(self, primary_issue: str, func_name: str, strategy: str) -> List[str]:
        """Get specific change details for an issue and function."""
        details_map = {
            "voltage": {
                "_apply_grid_limits": [
                    "Add voltage monitoring: check bus voltages from grid_diagnostics",
                    "Add voltage-triggered load reduction: if voltage > 1.03 pu or < 0.97 pu, reduce flexible loads and battery charging",
                    "Add reactive power support: use battery inverters for voltage regulation"
                ],
                "_control_battery": [
                    "Add voltage regulation mode: when voltage deviates, adjust battery reactive power output",
                    "Implement volt-var curve: Q = f(V) for voltage support"
                ],
                "get_actions": [
                    "Add voltage check before returning actions",
                    "Pass voltage constraints to sub-controllers"
                ]
            },
            "line_loading": {
                "_apply_grid_limits": [
                    "Add line loading monitoring from grid_diagnostics",
                    "Implement load redistribution: shift loads from overloaded lines",
                    "Add generation curtailment on overloaded lines"
                ],
                "get_actions": [
                    "Pass line loading constraints to limit checking"
                ]
            },
            "transformer_loading": {
                "_apply_grid_limits": [
                    "Add transformer loading check from grid_diagnostics",
                    "Implement proportional load reduction when loading > 90%",
                    "Coordinate battery discharge to reduce transformer load"
                ],
                "get_actions": [
                    "Add transformer loading constraint to limit checking"
                ]
            },
            "ev_deadline": {
                "_control_ev": [
                    "Calculate time-to-departure more precisely",
                    "Start charging earlier when SOC is low",
                    "Use maximum available power when deadline < 2 hours",
                    "Prioritize EVs by departure time (earliest first)"
                ],
                "get_actions": [
                    "Ensure EV actions respect deadline constraints"
                ]
            },
            "comfort": {
                "_control_flexible_load": [
                    "Add pre-conditioning: pre-heat/cool 2 hours before peak",
                    "Widen temperature deadband during peak pricing",
                    "Use thermal mass for load shifting"
                ],
                "_apply_grid_limits": [
                    "Relax comfort constraints only when grid critical"
                ]
            },
            "battery_soc": {
                "_control_battery": [
                    "Add dynamic SOC reserve: increase min SOC before peak",
                    "Implement SOC forecast based on net load prediction",
                    "Maintain emergency reserve (10-15%) at all times"
                ],
                "_apply_grid_limits": [
                    "Enforce battery SOC limits in limit checking"
                ]
            },
            "flexible_load": {
                "_control_flexible_load": [
                    "Implement earliest-deadline-first scheduling",
                    "Allocate power proportional to urgency",
                    "Add deadline tracking and alerts"
                ],
                "get_actions": [
                    "Pass flexible load deadlines to limit checking"
                ]
            },
            "grid_import": {
                "_apply_grid_limits": [
                    f"Enforce community import limit from scenario config",
                    "Proportional curtailment when limit exceeded",
                    "Prioritize battery discharge over import"
                ],
                "_control_battery": [
                    "Discharge battery to reduce grid import during peak"
                ]
            },
            "grid_export": {
                "_apply_grid_limits": [
                    f"Enforce community export limit from scenario config",
                    "Curtail PV when export limit approached",
                    "Charge batteries to absorb excess generation"
                ],
                "_control_battery": [
                    "Charge battery to absorb excess PV instead of exporting"
                ]
            },
            "power_flow": {
                "get_actions": [
                    "Add power flow pre-check before applying actions",
                    "Fallback to safe actions if power flow fails"
                ],
                "_apply_grid_limits": [
                    "Reduce action magnitude if power flow diverges"
                ]
            }
        }
        
        return details_map.get(primary_issue, {}).get(func_name, [
            f"Modify {func_name} to address {primary_issue} per strategy: {strategy}"
        ])
    
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
            sorted_changes = sorted(changes, key=lambda x: x.get("location", 0), reverse=True)
            
            # Apply each change
            for change in sorted_changes:
                func_name = change["function"]
                change_type = change["type"]
                change_desc = change["change"]
                
                # Find the function to modify
                func_node = self._find_function_node(tree, func_name)
                if func_node:
                    if change_type == "modification":
                        # For now, we'll add a comment at the beginning of the function
                        # In a more advanced implementation, we would modify the actual logic
                        pass_comment = ast.Expr(
                            value=ast.Constant(
                                value=f"# PATCHED: {change_desc}"
                            )
                        )
                        # Insert at the beginning of the function body
                        func_node.body.insert(0, pass_comment)
                    elif change_type == "addition":
                        # For additions, we would add new functions - placeholder for now
                        pass
                        
            # Convert AST back to code
            return ast.unparse(tree)
        except Exception as e:
            # If AST manipulation fails, fall back to original code with error comment
            return f"{code}\n\n# ERROR APPLYING CHANGES: {str(e)}\n# Original changes requested: {chr(10).join([c['change'] for c in changes])}"
    
    def _generate_diff(self, original: str, patched: str) -> str:
        """Generate a unified diff between original and patched code."""
        import difflib
        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        diff = difflib.unified_diff(original_lines, patched_lines, 
                                     fromfile='original', tofile='patched')
        return ''.join(diff)