"""Test the two specific fixes for the function replacement parser."""
from src.agents.llm_coder import LLMCoderAgent
import ast

coder = LLMCoderAgent()

# Use a simplified controller that matches our test signatures
test_controller_code = (
    "class RuleBasedController:\n"
    "    def _control_ev(self, state):\n"
    "        return []\n"
    "\n"
    "    def _control_battery(self, state):\n"
    "        return []\n"
    "\n"
    "    def _apply_grid_limits(self, actions):\n"
    "        return actions\n"
)

print("=" * 60)
print("ACCEPTANCE TESTS")
print("=" * 60)

# Test 1: Issue A - Fenced block with markers OUTSIDE the fence (Issue A)
print("\nTest 1: Issue A - Markers OUTSIDE the fence")
response_a = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "```python\n"
    "    def _apply_grid_limits(self, actions):\n"
    '        """Enforce grid voltage and loading limits."""\n'
    "        if self.last_grid_diagnostics:\n"
    '            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n'
    "            for d in diagnostics:\n"
    '                if d.get("severity") in ["violation", "critical"] and d.get("category") == "voltage":\n'
    "                    pass\n"
    "        return actions\n"
    "```"
)

result = coder._parse_llm_response_function_replacement(response_a, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS' if result else 'FAIL'}")
if result:
    try:
        ast.parse(result[0])
        print("  File parses: YES")
    except SyntaxError as e:
        print(f"  File parses: NO - {e}")

# Test 2: Issue B - Mixed modified + unchanged (echo) functions (Issue B)
print("\nTest 2: Issue B - Mixed modified + unchanged functions")
response_b = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _control_ev\n"
    "    def _control_ev(self, state):\n"
    '        """Control EV charging."""\n'
    "        return []\n"
    "\n"
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _control_battery\n"
    "    def _control_battery(self, state):\n"
    '        """Control battery."""\n'
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

result = coder._parse_llm_response_function_replacement(response_b, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS' if result else 'FAIL'}")
if result:
    print(f"  Changes: {len(result[2])}")
    for c in result[2]:
        print(f"  - {c['function']}")
    try:
        ast.parse(result[0])
        print("  File parses: YES")
    except SyntaxError:
        print("  File parses: NO")

# Test 3: Single fenced with markers INSIDE fence (should still work)
print("\nTest 3: Fenced with markers INSIDE fence")
response_c = (
    "```python\n"
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
    "```"
)

result = coder._parse_llm_response_function_replacement(response_c, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS' if result else 'FAIL'}")
if result:
    try:
        ast.parse(result[0])
        print("  File parses: YES")
    except SyntaxError:
        print("  File parses: NO")

# Test 4: Mixed - one modified, one unchanged (echo) - should skip unchanged and apply modified
print("\nTest 4: Mixed - one modified, one unchanged (echo)")
response_d = (
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

result = coder._parse_llm_response_function_replacement(response_d, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS' if result else 'FAIL'}")
if result:
    print(f"  Changes: {len(result[2])}")
    for c in result[2]:
        print(f"  - {c['function']}")
    try:
        ast.parse(result[0])
        print("  File parses: YES")
    except SyntaxError:
        print("  File parses: NO")

# Test 5: Wrong signature rejection
print("\nTest 5: Wrong signature rejection")
bad_response = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "    def _apply_grid_limits(self, actions, extra_param):\n"
    "        return actions\n"
)

result = coder._parse_llm_response_function_replacement(bad_response, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS (rejected)' if result is None else 'FAIL (accepted)'}")

# Test 6: No-change rejection
print("\nTest 6: No-change rejection")
no_change_response = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "    def _apply_grid_limits(self, actions):\n"
    "        return actions\n"
)

result = coder._parse_llm_response_function_replacement(no_change_response, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS (rejected)' if result is None else 'FAIL (accepted)'}")

# Test 7: Missing markers rejected
print("\nTest 7: Missing markers rejected")
incomplete_response = (
    "```python\n"
    "def _apply_grid_limits(self, actions):\n"
    "    return actions\n"
    "```"
)

result = coder._parse_llm_response_function_replacement(incomplete_response, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS (rejected)' if result is None else 'FAIL (accepted)'}")

# Test 8: Syntax error rejected
print("\nTest 8: Syntax error rejected")
syntax_error_response = (
    "```python\n"
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "    def _apply_grid_limits(self, actions):\n"
    "        return invalid syntax\n"
    "```"
)

result = coder._parse_llm_response_function_replacement(syntax_error_response, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS (rejected)' if result is None else 'FAIL (accepted)'}")

# Test 9: Multiple fenced blocks with markers OUTSIDE (Issue A - multiple)
print("\nTest 9: Multiple fenced blocks with markers OUTSIDE (Issue A)")
response_multiple = (
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _control_ev\n"
    "```python\n"
    "    def _control_ev(self, state):\n"
    '        """Control EV charging."""\n'
    "        return []\n"
    "```\n"
    "\n"
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _control_battery\n"
    "```python\n"
    "    def _control_battery(self, state):\n"
    '        """Control battery."""\n'
    "        return []\n"
    "```\n"
    "\n"
    "# FILE: controllers/__init__.py\n"
    "# FUNCTION: _apply_grid_limits\n"
    "```python\n"
    "    def _apply_grid_limits(self, actions):\n"
    '        """Enforce grid voltage and loading limits."""\n'
    "        if self.last_grid_diagnostics:\n"
    '            diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n'
    "            for d in diagnostics:\n"
    '                if d.get("severity") in ["violation", "critical"] and d.get("category") == "voltage":\n'
    "                    pass\n"
    "        return actions\n"
    "```"
)

result = coder._parse_llm_response_function_replacement(response_multiple, test_controller_code, 'controllers/__init__.py')
print(f"  Result: {'PASS' if result else 'FAIL'}")
if result:
    print(f"  Changes: {len(result[2])}")
    for c in result[2]:
        print(f"  - {c['function']}")
    try:
        ast.parse(result[0])
        print("  File parses: YES")
    except SyntaxError as e:
        print(f"  File parses: NO - {e}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)