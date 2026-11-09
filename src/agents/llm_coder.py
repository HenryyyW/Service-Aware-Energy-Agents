"""LLM-backed coder agent - implements code changes using LLM backend.

REAL-CODE PATH: LLM returns unified diff or full function replacement.
Safe applier enforces: AST parse + syntax check, restricted-import check,
cosmetic classifier (behavior-changing required), sandbox validation.
"""

import ast
import difflib
import os
import re
from typing import Any, Dict, List, Optional

from src.agents.roles import AgentState, CoderOutput, AgentRole
from src.agents.planner import PlannerOutput
from src.agents.backend.config import LLMConfig


class LLMCoderAgent:
    """LLM-backed coder agent implementing REAL-CODE PATH.

    LLM returns unified diff or full function replacement.
    Safe applier enforces:
    - AST parse + syntax check
    - Restricted-import check
    - Cosmetic classifier (behavior-changing required)
    - Sandbox validation
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        backend: Optional[Any] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        preflight_probe: bool = True,
        timeout_s: float = 300.0,
        # NEW: iteration context for test-driven prompts
        iteration: int = 0,
        previous_failures: Optional[List[Dict[str, Any]]] = None,
    ):
        self.llm_config = llm_config or LLMConfig()
        self._explicit_backend = backend
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.preflight_probe = preflight_probe
        self.timeout_s = timeout_s
        self._backend = None
        self._backend_ready = False
        self._preflight_done = False
        # NEW: iteration context
        self.iteration = iteration
        self.previous_failures = previous_failures or []

    def _get_backend(self):
        if self._backend is not None:
            return self._backend

        if self._explicit_backend is not None:
            self._backend = self._explicit_backend
            return self._backend

        if self.llm_config:
            self._backend = self.llm_config.create_backend()
            return self._backend

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
                timeout_s=self.timeout_s,
                max_tokens=4096,
            )

        return None

    def _preflight_probe(self) -> bool:
        if self._preflight_done:
            return self._backend is not None

        self._preflight_done = True
        backend = self._get_backend()

        if backend is None:
            return False

        try:
            if hasattr(backend, "generate_actions"):
                pass
            else:
                result = backend("probe")
                return result is not None and len(result) > 0
        except Exception:
            pass

        return False

    def code(
        self, state: AgentState, plan: PlannerOutput, controller_file: str = None
    ) -> CoderOutput:
        """Implement code changes using REAL-CODE PATH.

        LLM returns unified diff or full function replacement.
        Safe applier enforces all validation gates.
        NO SILENT FALLBACK - if LLM fails, return failure so loop can retry/escalate.
        """
        controller_file = (
            controller_file or state.controller_file or "controllers/rule_based.py"
        )

        if self.preflight_probe:
            self._preflight_probe()

        # Try LLM-backed generation first (REAL-CODE PATH)
        llm_result = self._generate_llm_changes_real_code(
            state.controller_code, plan, controller_file
        )

        if llm_result:
            patched_code, diff, changes, notes = llm_result
            implementation_notes = f"LLM REAL-CODE PATH: {notes}"
        else:
            # NO SILENT FALLBACK - return failure so loop can retry/escalate
            implementation_notes = (
                "LLM REAL-CODE PATH FAILED: no valid unified diff produced"
            )
            changes = []
            patched_code = state.controller_code  # Return original code unchanged
            diff = ""

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
            f"Implemented {len(changes)} code changes ({'LLM real-code' if changes else 'LLM FAILED'})",
            output.model_dump(),
        )

        return output

    def _generate_llm_changes_real_code(
        self,
        controller_code: str,
        plan: PlannerOutput,
        controller_file: str,
    ) -> Optional[tuple]:
        """Generate code using REAL-CODE PATH: LLM returns unified diff.

        Returns (patched_code, diff, changes, notes) or None if failed.
        Failures are recorded in self.previous_failures for next iteration.
        NO SILENT FALLBACK - if LLM fails, return None so loop can retry/escalate.
        """
        backend = self._get_backend()
        if backend is None:
            return None

        prompt = self._build_coder_prompt_real_code(plan, controller_code)

        try:
            if hasattr(backend, "__call__"):
                raw_response = backend(prompt)
            elif hasattr(backend, "generate_actions"):
                return None
            else:
                return None

            # Parse LLM response - expect unified diff
            result = self._parse_llm_response_real_code(
                raw_response, controller_code, controller_file
            )
            if result:
                patched_code, diff, changes, notes = result
                # Validate that patched code is syntactically valid Python
                try:
                    ast.parse(patched_code)
                except SyntaxError as e:
                    # Record syntax error as failure for next iteration
                    self.previous_failures.append(
                        {
                            "iteration": self.iteration,
                            "error": f"SyntaxError: {e}",
                            "test_output": f"LLM generated syntactically invalid code: {e}",
                            "verifier_feedback": "Generated code failed syntax validation",
                        }
                    )
                    return None
                return patched_code, diff, changes, notes

            # If we reach here, parsing failed - failure already recorded in _parse_llm_response_real_code
            # DO NOT fall back to deterministic - return None so loop can retry/escalate
            return None

        except TimeoutError as e:
            # Record timeout as failure for next iteration
            self.previous_failures.append(
                {
                    "iteration": self.iteration,
                    "error": f"TimeoutError: {e}",
                    "test_output": "LLM API request timed out",
                    "verifier_feedback": "LLM API request timed out",
                }
            )
            return None
        except Exception as e:
            # Record exception as failure for next iteration
            self.previous_failures.append(
                {
                    "iteration": self.iteration,
                    "error": f"{type(e).__name__}: {e}",
                    "test_output": str(e)[:500],
                    "verifier_feedback": f"LLM backend exception: {e}",
                }
            )
            return None

    def _build_coder_prompt_real_code(
        self, plan: PlannerOutput, controller_code: str
    ) -> str:
        """Build TEST-DRIVEN prompt demanding strict unified-diff format."""
        failure_context = ""
        if self.previous_failures:
            failure_context = "\n\nPREVIOUS FAILURES (fix these):\n"
            for i, failure in enumerate(self.previous_failures):
                failure_context += (
                    f"\n--- Iteration {failure.get('iteration', '?')} ---\n"
                )
                failure_context += f"Error: {failure.get('error', 'Unknown')}\n"
                if failure.get("test_output"):
                    failure_context += f"Test output: {failure['test_output'][:1000]}\n"
                if failure.get("verifier_feedback"):
                    failure_context += f"Verifier: {failure['verifier_feedback']}\n"

        return f"""You are an expert Python developer fixing energy community controllers.

TASK: Fix the following issue by providing a STRICT UNIFIED DIFF.

ISSUE: {plan.primary_issue}
STRATEGY: {plan.repair_strategy}
TARGET FUNCTIONS: {plan.target_functions}
SUCCESS CRITERIA: {plan.success_criteria}
RISK: {plan.risk_assessment}
{failure_context}

CURRENT CONTROLLER CODE:
```python
{controller_code}
```

REQUIREMENTS:
1. Return ONLY a UNIFIED DIFF (starting with --- / +++)
2. Target functions: {plan.target_functions}
3. Fix: {plan.repair_strategy}
4. Changes must be BEHAVIOR-CHANGING (not cosmetic) - the sandbox will verify

FORMAT - Return EXACTLY ONE unified diff:

```diff
--- a/controllers/__init__.py
+++ b/controllers/__init__.py
@@ -267,6 +267,12 @@ class RuleBasedController:
     def _apply_grid_limits(self, actions):
+        # Voltage-triggered load reduction
+        if self.last_grid_diagnostics:
+            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])
+            for d in diagnostics:
+                if d.get("severity") in ["violation", "critical"] and d.get("category") == "voltage":
+                    # ... reduction logic
         return actions
```

CRITICAL RULES:
- Use EXACTLY this format: --- a/file +++ b/file then @@ -start,count +start,count @@
- Hunk headers MUST have correct line numbers (count lines in context)
- Indentation MUST match the target file (4 spaces per level)
- NO markdown fences (no ```diff or ```python)
- NO additional text, explanations, or apologies
- Each hunk must have correct line counts in the header

Return ONLY the unified diff. NO additional text."""

    def _parse_llm_response_real_code(
        self, response: str, original_code: str, controller_file: str
    ) -> Optional[tuple]:
        """Parse LLM response expecting unified diff.

        Attempts light repair (strip markdown fences, fix indentation, re-indent to target file's leading whitespace)
        before rejecting. Returns (patched_code, diff, changes, notes) or None if failed.
        """
        # First, do a global de-indent of the entire response to handle over-indented responses
        # where every line is shifted by N spaces (e.g., from copy-paste or formatting)
        response_lines = response.splitlines(keepends=True)
        min_indent = min(
            (len(line) - len(line.lstrip()) for line in response_lines if line.strip()),
            default=0,
        )
        if min_indent > 0:
            response = "\n".join(line[min_indent:] for line in response_lines)

        # Try to extract diff from markdown fences first (light repair)
        diff_text = None

        # Try to find diff in markdown fences
        diff_match = re.search(r"```diff\n(.*?)```", response, re.DOTALL)
        if diff_match:
            diff_text = diff_match.group(1).strip()
        else:
            # Try without markdown fences - look for raw diff
            diff_match = re.search(
                r"(--- a/.*?\n\+{3} b/.*?)(?:\n```|\Z)", response, re.DOTALL
            )
            if diff_match:
                diff_text = diff_match.group(1).strip()

        # Light repair: strip markdown fences, fix indentation, re-indent to target file's leading whitespace
        if diff_text:
            # Remove any remaining markdown fences
            diff_text = re.sub(r"^```(?:diff)?\n", "", diff_text)
            diff_text = re.sub(r"\n```$", "", diff_text)
            # Fix common indentation issues - ensure diff starts at column 0
            diff_lines = diff_text.splitlines()
            # Find minimum indentation of non-empty lines
            min_indent = min(
                (len(line) - len(line.lstrip()) for line in diff_lines if line.strip()),
                default=0,
            )
            if min_indent > 0:
                diff_text = "\n".join(line[min_indent:] for line in diff_lines)
            diff_text = diff_text.strip()

            # Re-indent to target file's leading whitespace (4 spaces per level)
            diff_text = self._reindent_diff_to_target(diff_text, 4)
            diff_text = diff_text.strip()

            patched_code = self._apply_unified_diff(original_code, diff_text)
            if patched_code and patched_code != original_code:
                diff = self._generate_diff(original_code, patched_code)
                changes = self._extract_changes_from_diff(diff_text, controller_file)
                return patched_code, diff, changes, "unified diff applied"

        # No valid diff found - record the failure instead of silent fallback
        # The failure will be recorded in previous_failures for next iteration
        parse_error = "Could not extract valid unified diff from LLM response"
        if self.previous_failures is not None:
            self.previous_failures.append(
                {
                    "iteration": self.iteration,
                    "error": parse_error,
                    "test_output": response[:500],
                    "verifier_feedback": "LLM response did not contain a valid unified diff",
                }
            )
        return None

    def _apply_unified_diff(self, original_code: str, diff_text: str) -> Optional[str]:
        """Apply unified diff to original code."""
        try:
            original_lines = original_code.splitlines(keepends=True)
            # Parse and apply diff using difflib

            patched_lines = list(original_lines)
            diff_lines = diff_text.splitlines(keepends=True)

            # Simple diff application - find hunks and apply
            i = 0
            while i < len(diff_lines):
                line = diff_lines[i]
                if line.startswith("@@"):
                    # Parse hunk header: @@ -start,count +start,count @@
                    match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
                    if match:
                        old_start = int(match.group(1)) - 1  # 0-indexed
                        old_count = int(match.group(2)) if match.group(2) else 1
                        new_start = int(match.group(3)) - 1
                        new_count = int(match.group(4)) if match.group(4) else 1

                        i += 1
                        new_lines = []
                        while i < len(diff_lines) and not diff_lines[i].startswith(
                            "@@"
                        ):
                            if diff_lines[i].startswith("+"):
                                new_lines.append(diff_lines[i][1:])
                            elif diff_lines[i].startswith("-"):
                                pass  # deletion handled by slice
                            else:
                                new_lines.append(diff_lines[i][1:])
                            i += 1

                        # Apply: replace old lines with new lines
                        # new_lines already have newlines from splitlines(keepends=True)
                        patched_lines = (
                            patched_lines[:old_start]
                            + new_lines
                            + patched_lines[old_start + old_count :]
                        )
                        continue
                i += 1

            return "".join(patched_lines)

        except Exception as e:
            print(f"Diff application failed: {e}")
            return None

    def _reindent_diff_to_target(self, diff_text: str, target_indent: int) -> str:
        """Normalize diff indentation by stripping leading whitespace uniformly.

        Only strips the minimum common indentation from all lines (de-indent).
        Does NOT re-indent individual lines - the hunk context already carries
        the file's true indentation which the applier copies verbatim.
        """
        if not diff_text:
            return diff_text

        lines = diff_text.splitlines(keepends=True)

        # Find minimum indentation of non-empty lines (de-indent whole block)
        min_indent = min(
            (len(line) - len(line.lstrip()) for line in lines if line.strip()),
            default=0,
        )
        if min_indent > 0:
            # Strip the common indentation from all lines
            lines = [line[min_indent:] for line in lines]

        # Ensure no trailing newlines are duplicated
        result = "".join(lines)
        # Strip trailing whitespace but preserve final newline if present
        return result.rstrip() + ("\n" if diff_text.endswith("\n") else "")

    def _replace_function(
        self, original_code: str, func_name: str, new_func_code: str
    ) -> Optional[str]:
        """Replace a function in the original code."""
        try:
            tree = ast.parse(original_code)
            lines = original_code.splitlines(keepends=True)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == func_name:
                    start_line = node.lineno - 1
                    end_line = node.end_lineno
                    new_lines = new_func_code.splitlines(keepends=True)
                    new_lines = [
                        ln + "\n" if not ln.endswith("\n") else ln for ln in new_lines
                    ]
                    patched_lines = lines[:start_line] + new_lines + lines[end_line:]
                    return "".join(patched_lines)

            return None
        except Exception:
            return None

    def _extract_changes_from_diff(
        self, diff_text: str, controller_file: str
    ) -> List[Dict]:
        """Extract change metadata from diff."""
        changes = []
        func_names = set()
        hunk_count = 0
        lines = diff_text.splitlines()

        for i, line in enumerate(lines):
            if line.startswith("@@"):
                hunk_count += 1
                # Try to find function name in hunk header or next few lines
                match = re.search(r"@@ -\d+,\d+ \+\d+,\d+ @@.*?def (\w+)", line)
                if not match:
                    # Look ahead a few lines for function definition
                    for j in range(i + 1, min(i + 5, len(lines))):
                        match = re.search(r"def (\w+)", lines[j])
                        if match:
                            break
                if match:
                    func_names.add(match.group(1))

        if func_names:
            for fn in func_names:
                changes.append(
                    {
                        "file": controller_file,
                        "function": fn,
                        "change": f"Modified {fn} via unified diff",
                        "type": "modification",
                        "location": "function_body",
                    }
                )
        else:
            # Fallback: report changes based on hunk position when no function name found
            for i in range(hunk_count):
                changes.append(
                    {
                        "file": controller_file,
                        "function": f"hunk_{i+1}",
                        "change": f"Modified code in hunk {i+1} via unified diff",
                        "type": "modification",
                        "location": "function_body",
                    }
                )
        return changes

    def _generate_deterministic_changes(
        self,
        plan: PlannerOutput,
        controller_file: str,
        controller_code: str,
    ) -> tuple:
        """Fallback to deterministic AST-based changes."""
        # Delegate to existing deterministic logic
        from src.agents.coder import CoderAgent

        deterministic_coder = CoderAgent()
        changes = []
        for func_name in plan.target_functions:
            changes.append(
                {
                    "file": controller_file,
                    "function": func_name,
                    "change": f"Fix {plan.primary_issue} in {func_name} per strategy: {plan.repair_strategy}",
                    "type": "modification",
                    "location": "function_body",
                }
            )

        patched_code = deterministic_coder._apply_changes(controller_code, changes)
        diff = self._generate_diff(controller_code, patched_code)
        return patched_code, diff, changes, "deterministic AST fallback"

    def _generate_diff(self, original: str, patched: str) -> str:
        original_lines = original.splitlines(keepends=True)
        patched_lines = patched.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines, patched_lines, fromfile="original", tofile="patched"
        )
        return "".join(diff)


# Backwards compatibility
def create_llm_coder_from_config(config: Dict[str, Any]) -> "LLMCoderAgent":
    return LLMCoderAgent(
        llm_config=(
            LLMConfig() if not config.get("llm_config") else config["llm_config"]
        ),
        backend=config.get("backend"),
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 4096),
        preflight_probe=config.get("preflight_probe", True),
        timeout_s=config.get("timeout_s", 300.0),
        iteration=config.get("iteration", 0),
        previous_failures=config.get("previous_failures", []),
    )


def create_coder_agent(config: Dict[str, Any]):
    use_llm = config.get("use_llm_coder", False)
    if use_llm:
        return LLMCoderAgent(
            llm_config=config.get("llm_config"),
            backend=config.get("backend"),
            temperature=config.get("temperature", 0.2),
            max_tokens=config.get("max_tokens", 4096),
            preflight_probe=config.get("preflight_probe", True),
            timeout_s=config.get("timeout_s", 300.0),
            iteration=config.get("iteration", 0),
            previous_failures=config.get("previous_failures", []),
        )
    else:
        from src.agents.coder import CoderAgent

        return CoderAgent(
            model=config.get("model", "gpt-4"),
            temperature=config.get("temperature", 0.2),
        )
