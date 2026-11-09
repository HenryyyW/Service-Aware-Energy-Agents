"""LLM-backed coder agent - implements code changes using LLM backend."""

import ast
import json
import os
from typing import Optional, List, Dict, Any, Callable

from src.agents.roles import AgentState, CoderOutput, AgentRole
from src.agents.planner import PlannerOutput
from src.agents.backend.config import LLMConfig


class LLMCoderAgent:
    """LLM-backed coder agent that implements code changes using LLM backend.

    Uses the existing backend infrastructure to generate code changes via LLM,
    with deterministic AST-based fallback as comparator.
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        backend: Optional[Any] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        preflight_probe: bool = True,
    ):
        """Initialize LLM-backed coder.

        Args:
            llm_config: LLM configuration (if None, loads from env)
            backend: Explicit backend to use (overrides config)
            temperature: Sampling temperature
            max_tokens: Max tokens for completion
            preflight_probe: Whether to run 1-token pre-flight probe before first use
        """
        self.llm_config = llm_config or LLMConfig()
        self._explicit_backend = backend
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.preflight_probe = preflight_probe
        self._backend = None
        self._backend_ready = False
        self._preflight_done = False

    def _get_backend(self):
        """Get or create the LLM backend."""
        if self._backend is not None:
            return self._backend

        # Explicit backend injection (tests/mock)
        if self._explicit_backend is not None:
            self._backend = self._explicit_backend
            return self._backend

        # Use LLMConfig to create backend
        if self.llm_config:
            self._backend = self.llm_config.create_backend()
            return self._backend

        # Fallback: try to create from env directly
        raw = os.getenv("AGENT_BACKEND", "").strip().lower()
        if raw.startswith("api:") or raw == "api":
            model = raw.split(":", 1)[1] if raw.startswith("api:") else ""
            if not model:
                model = os.getenv("LLM_API_MODEL") or "poolside/laguna-xs-2.1"
            from src.agents.backend.api import api_prompt_callable

            return api_prompt_callable(
                model=model,
                base_url=os.getenv("LLM_BASE_URL"),
                temperature=0.2,
                seed=42,
                timeout_s=120.0,
                max_tokens=4096,
            )

        # Fallback to deterministic
        return None

    def _preflight_probe(self) -> bool:
        """Run 1-token pre-flight probe to verify backend connectivity.

        Returns True if probe succeeds, False otherwise.
        """
        if self._preflight_done:
            return self._backend is not None

        self._preflight_done = True
        backend = self._get_backend()

        if backend is None:
            return False

        # Run 1-token probe
        try:
            if hasattr(backend, "generate_actions"):
                # Async backend - can't easily probe sync
                pass
            else:
                # Sync prompt callable
                result = backend("probe")
                return result is not None and len(result) > 0
        except Exception:
            pass

        return False

    def code(
        self, state: AgentState, plan: PlannerOutput, controller_file: str = None
    ) -> CoderOutput:
        """
        Implement code changes based on the repair plan.

        First tries LLM-backed generation, falls back to deterministic AST.

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

        # Run pre-flight probe if enabled
        if self.preflight_probe:
            self._preflight_probe()

        # Try LLM-backed generation first
        llm_changes = self._generate_llm_changes(
            state.controller_code, plan, controller_file
        )

        if llm_changes:
            changes = llm_changes
            implementation_notes = f"LLM-generated changes for {plan.repair_strategy} on {plan.primary_issue}"
        else:
            # Fallback to deterministic AST-based changes
            changes = self._generate_deterministic_changes(
                plan, controller_file, state.controller_code
            )
            implementation_notes = f"Deterministic AST fallback for {plan.repair_strategy} on {plan.primary_issue}"

        # Apply changes to create patched code
        patched_code = self._apply_changes(state.controller_code, changes)

        # Generate diff
        diff = self._generate_diff(state.controller_code, patched_code)

        output = CoderOutput(
            code_changes=changes,
            patched_code=patched_code,
            diff=diff,
            implementation_notes=implementation_notes,
        )

        state.code_changes = changes
        state.patched_code = patched_code
        state.add_message(
            AgentRole.CODER,
            f"Implemented {len(changes)} code changes ({'LLM' if llm_changes else 'deterministic'})",
            output.model_dump(),
        )

        return output

    def _generate_llm_changes(
        self,
        controller_code: str,
        plan: PlannerOutput,
        controller_file: str,
    ) -> List[Dict[str, Any]]:
        """Generate code changes using LLM backend.

        Returns list of changes if successful, empty list if LLM unavailable/failed.
        """
        backend = self._get_backend()
        if backend is None:
            return []

        # Build prompt for code generation
        prompt = self._build_coder_prompt(plan, controller_code)

        try:
            # Use backend (sync callable)
            if hasattr(backend, "__call__"):
                raw_response = backend(prompt)
            elif hasattr(backend, "generate_actions"):
                # Async backend - would need async handling
                return []
            else:
                return []

            # Parse LLM response
            changes = self._parse_llm_response(raw_response)
            if changes:
                return changes

        except Exception as e:
            # Log and fall back
            print(f"LLM coder failed: {e}")

        return []

    def _build_coder_prompt(self, plan: PlannerOutput, controller_code: str) -> str:
        """Build prompt for LLM code generation."""
        return f"""You are an expert Python developer specializing in energy community controllers.

TASK: Generate code changes to fix the following issue in a Python controller.

ISSUE: {plan.primary_issue}
STRATEGY: {plan.repair_strategy}
TARGET FUNCTIONS: {plan.target_functions}
SUCCESS CRITERIA: {plan.success_criteria}
RISK: {plan.risk_assessment}

CURRENT CONTROLLER CODE:
```python
{controller_code}
```

TARGET FUNCTIONS TO MODIFY: {plan.target_functions}

Generate specific code changes to fix the {plan.primary_issue} issue per the strategy: {plan.repair_strategy}

Return ONLY a JSON array of changes, each with:
- "file": file path (e.g., "controllers/__init__.py")
- "function": function name to modify (e.g., "_apply_grid_limits")
- "change": specific change description
- "type": "modification" or "addition"
- "location": line number or "end_of_class"

Example:
[
  {{
    "file": "controllers/__init__.py",
    "function": "_apply_grid_limits",
    "change": "Add voltage-triggered load reduction when voltage > 1.03 pu or < 0.97 pu",
    "type": "modification",
    "location": 267
  }}
]

Return ONLY the JSON array, no additional text."""

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into list of changes."""
        import re

        # Try to extract JSON from response
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return []

        try:
            changes = json.loads(json_match.group())
            # Validate structure
            valid_changes = []
            for change in changes:
                if all(k in change for k in ["file", "function", "change", "type"]):
                    change.setdefault("location", "end_of_class")
                    valid_changes.append(change)
            return valid_changes
        except json.JSONDecodeError:
            return []

    def _generate_deterministic_changes(
        self,
        plan: PlannerOutput,
        controller_file: str,
        controller_code: str,
    ) -> List[Dict[str, Any]]:
        """Generate deterministic AST-based changes (fallback)."""
        # Use the existing deterministic logic from CoderAgent
        # This is a simplified version - in practice would delegate to CoderAgent
        changes = []

        # Use the existing _get_change_details logic from CoderAgent
        # For now, return minimal changes
        for func_name in plan.target_functions:
            changes.append(
                {
                    "file": controller_file,
                    "function": func_name,
                    "change": f"Fix {plan.primary_issue} in {func_name} per strategy: {plan.repair_strategy}",
                    "type": "modification",
                    "location": "end_of_class",
                }
            )

        return changes

    def _apply_changes(self, code: str, changes: List[Dict[str, Any]]) -> str:
        """Apply changes to code using AST manipulation."""
        if not changes:
            return code

        try:
            tree = ast.parse(code)

            # Sort changes by line number in descending order
            sorted_changes = sorted(
                changes, key=lambda x: x.get("location", 0), reverse=True
            )

            for change in sorted_changes:
                func_name = change["function"]
                change_type = change["type"]
                change_desc = change["change"]

                func_node = self._find_function_node(tree, func_name)
                if func_node and change_type == "modification":
                    self._apply_ast_transformation(func_node, change_desc)

            return ast.unparse(tree)
        except Exception:
            return self._apply_changes_fallback(code, changes)

    def _apply_changes_fallback(self, code: str, changes: List[Dict[str, Any]]) -> str:
        """Fallback: append changes as comments."""
        error_lines = ["# LLM/AST changes could not be applied automatically"]
        for c in changes:
            for line in c["change"].split("\n"):
                error_lines.append(f"# {line}")
        return code + "\n\n" + "\n".join(error_lines)

    def _find_function_node(
        self, tree: ast.AST, func_name: str
    ) -> Optional[ast.FunctionDef]:
        """Find function node in AST tree."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node
        return None

    def _apply_ast_transformation(
        self, func_node: ast.FunctionDef, change_desc: str
    ) -> None:
        """Apply AST transformation based on change description."""
        # Delegate to the deterministic transformations
        transformation = self._determine_transformation(change_desc)
        if transformation:
            transformation(func_node)

    def _determine_transformation(self, change_desc: str) -> Optional[Callable]:
        """Map change description to deterministic AST transformation."""
        # This would use the same logic as the deterministic coder
        # For now, return None to indicate no specific transformation
        return None

    def _generate_diff(self, original: str, patched: str) -> str:
        """Generate a unified diff between original and patched code."""
        import difflib

        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines, patched_lines, fromfile="original", tofile="patched"
        )
        return "".join(diff)


# Register in backend registry for discovery
def create_llm_coder_from_config(config: Dict[str, Any]) -> "LLMCoderAgent":
    """Factory function to create LLM coder from config."""
    return LLMCoderAgent(
        llm_config=(
            LLMConfig() if not config.get("llm_config") else config["llm_config"]
        ),
        backend=config.get("backend"),
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 4096),
        preflight_probe=config.get("preflight_probe", True),
    )


# Also update the CoderAgent to support LLM backend option
def create_coder_agent(config: Dict[str, Any]):
    """Factory function to create appropriate coder based on config."""
    use_llm = config.get("use_llm_coder", False)
    if use_llm:
        return LLMCoderAgent(
            llm_config=config.get("llm_config"),
            backend=config.get("backend"),
            temperature=config.get("temperature", 0.2),
            max_tokens=config.get("max_tokens", 4096),
            preflight_probe=config.get("preflight_probe", True),
        )
    else:
        from src.agents.coder import CoderAgent

        return CoderAgent(
            model=config.get("model", "gpt-4"),
            temperature=config.get("temperature", 0.2),
        )
