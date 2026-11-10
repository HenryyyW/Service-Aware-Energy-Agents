"""Debug the mixed modified+unchanged case."""
from src.agents.llm_coder import LLMCoderAgent

coder = LLMCoderAgent()

original_code = (
    "class RuleBasedController:\n"
    "    def _control_ev(self, state):\n"
    "        return []\n"
    "\n"
    "    def _apply_grid_limits(self, actions):\n"
    "        return actions\n"
)

# Test 2: Mixed modified + unchanged functions
response_b = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _control_ev\n"
    "    def _control_ev(self, state):\n"
    '        """Control EV charging."""\n'
    "        return []\n"
    "\n"
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "    def _apply_grid_limits(self, actions):\n"
    '        """Enforce grid voltage and loading limits."""\n'
    "        if self.last_grid_diagnostics:\n"
    '            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n'
    "            for d in diagnostics:\n"
    '                if d.get("severity") in ["violation", "critical"] and d.get("category") == "voltage":\n'
    "                    pass\n"
    "        return actions\n"
)

coder = LLMCoderAgent()
result = coder._parse_llm_response_function_replacement(response_b, original_code, 'controllers/__init__.py')
print(f"Result: {'PASS' if result else 'FAIL'}")
if result:
    print(f"Changes: {len(result[2])}")
    for c in result[2]:
        print(f"  - {c['function']}")
    import ast
    try:
        ast.parse(result[0])
        print("File parses: YES")
    except SyntaxError as e:
        print(f"File parses: NO - {e}")

# Add debug - trace through the logic
print("\n--- Manual trace ---")
response = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _control_ev\n"
    "    def _control_ev(self, state):\n"
    '        """Control EV charging."""\n'
    "        return []\n"
    "\n"
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "    def _apply_grid_limits(self, actions):\n"
    '        """Enforce grid voltage and loading limits."""\n'
    "        if self.last_grid_diagnostics:\n"
    '            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n'
    "            for d in diagnostics:\n"
    '                if d.get("severity") in ["violation", "critical"] and d.get("category") == "voltage":\n'
    "                    pass\n"
    "        return actions\n"
)

import re
marker_pattern = r"# FILE:\s*(.+?)\s*\n# FUNCTION:\s*(\w+)\n?"
matches = list(re.finditer(r"# FILE:\s*(.+?)\s*\n# FUNCTION:\s*(\w+)\n?", response_b))
print(f"Matches found: {len(matches)}")
for i, m in enumerate(matches):
    print(f"  Match {i}: FILE={m.group(1)}, FUNC={m.group(2)}")

# Test the second function replacement
print("\n--- Testing _apply_grid_limits replacement ---")
coder = LLMCoderAgent()
# First apply _control_ev (no change)
code1 = coder._replace_function(original_code, '_control_ev', 
    'def _control_ev(self, state):\n    """Control EV charging."""\n    return []')
print(f"After first replace: {'changed' if code1 != original_code else 'unchanged'}")
# Then apply _apply_grid_limits
code2 = coder._replace_function(code1, '_apply_grid_limits',
    'def _apply_grid_limits(self, actions):\n    """Enforce grid voltage and loading limits."""\n    if self.last_grid_diagnostics:\n        diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n        for d in diagnostics:\n            if d.get("severity") in ["violation", "critical"] and d.get("category") == "voltage":\n                pass\n        return actions')
print(f"After second replace: {'changed' if code2 != code1 else 'unchanged'}")
if code2 != original_code:
    import ast
    try:
        ast.parse(code2)
        print("Final parses: YES")
    except SyntaxError as e:
        print(f"Final parses: NO - {e}")