"""Zero-LLM-call verification of the function-replacement parser contract.

Runs synthetic responses in every observed model shape through
``LLMCoderAgent._parse_llm_response_function_replacement`` against the real
controller, so a parser change (A's side) can be regression-checked without
spending benchmark envelope. No backend is constructed - parsing only.

Shapes covered (all observed in live probes on poolside/laguna-xs-2.1):
  1. fenced block, markers INSIDE the fence, single replacement  -> must apply
  2. unfenced (markers at column 0, code dedented), single       -> must apply
  3. unfenced, code indented at the method's column, single      -> must apply
  4. fenced/unfenced, MULTIPLE genuinely-modified replacements   -> must apply all
  5. modified replacement + byte-identical echo of another function
                                                                 -> currently
     REJECTED wholesale (documented semantics; a repair must modify)
  6. markers OUTSIDE the fenced blocks (observed 2026-11-10 on
     task_8)                                                      -> currently
     REJECTED: the fenced path requires the markers inside the block

Exit code 0 when the must-apply shapes apply and the patched controller parses;
the two rejected shapes are reported, not asserted (they are the open items
dispatched to A).
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.llm_coder import LLMCoderAgent  # noqa: E402

CONTROLLER_FILE = "controllers/__init__.py"
CONTROLLER = (ROOT / "src" / CONTROLLER_FILE).read_text()


def body_of(func_name: str) -> str:
    """Real function source, dedented to column 0 (the model's typical output)."""
    lines = CONTROLLER.splitlines(keepends=True)
    for node in ast.walk(ast.parse(CONTROLLER)):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            start = node.lineno - 1
            indent = len(lines[start]) - len(lines[start].lstrip())
            chunk = lines[start : node.end_lineno]
            return "".join(ln[indent:] if ln.strip() else ln for ln in chunk).rstrip()
    raise KeyError(func_name)


def tweak(grid_body: str) -> str:
    """A genuine behaviour change (allow a 5% import-limit overshoot)."""
    out = grid_body.replace(
        "if total_import > import_limit:",
        "if total_import > import_limit * 1.05:",
        1,
    )
    assert out != grid_body, "tweak did not apply - controller changed?"
    return out


EV = body_of("_control_ev")
EV_MOD = EV.replace(
    "connected = arrival_hour <= hour_of_day < departure_hour",
    "connected = arrival_hour <= hour_of_day <= departure_hour",
    1,
)
assert EV_MOD != EV, "EV tweak did not apply - controller changed?"

GRID = body_of("_apply_grid_limits")
GRID_MOD = tweak(GRID)
REDISP = body_of("_apply_grid_violation_redispatch")
REDISP_MOD = REDISP.replace("return actions", "return list(actions)", 1)
assert REDISP_MOD != REDISP
MARKER = "# FILE: controllers/__init__.py\n"


def indent4(code: str) -> str:
    return "\n".join("    " + ln if ln.strip() else ln for ln in code.splitlines())


MUST_APPLY = {
    "fenced, markers inside, single": (
        f"```python\n{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n```\n"
    ),
    "unfenced col-0, single": (f"{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n"),
    "unfenced indent-4, single": (
        f"{MARKER}# FUNCTION: _apply_grid_limits\n{indent4(GRID_MOD)}\n"
    ),
    "unfenced col-0, two modified": (
        f"{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n"
        f"{MARKER}# FUNCTION: _apply_grid_violation_redispatch\n{REDISP_MOD}\n"
    ),
    "fenced, two modified": (
        f"```python\n{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n```\n\n"
        f"```python\n{MARKER}# FUNCTION: _apply_grid_violation_redispatch\n{REDISP_MOD}\n```\n"
    ),
    # CLOSED on main 07fa66512 (the integrated markers-inside fix) and verified
    # there at zero cost - now must-apply so a future regression is caught
    "modified + unchanged echo (unfenced)": (
        f"{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n"
        f"{MARKER}# FUNCTION: _apply_grid_violation_redispatch\n{REDISP}\n"
    ),
    "modified + unchanged echo (fenced)": (
        f"```python\n{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n```\n\n"
        f"```python\n{MARKER}# FUNCTION: _apply_grid_violation_redispatch\n{REDISP}\n```\n"
    ),
    # CLOSED on main 07fa66512 (block-local fence slicing) - was the task_8
    # family: 3 marker pairs each followed by its OWN fence, all modified
    "multi-fenced, markers outside each fence, 3 modified": (
        f"{MARKER}# FUNCTION: _apply_grid_limits\n"
        f"```python\n{GRID_MOD}\n```\n\n"
        f"{MARKER}# FUNCTION: _apply_grid_violation_redispatch\n"
        f"```python\n{REDISP_MOD}\n```\n\n"
        f"{MARKER}# FUNCTION: _control_ev\n"
        f"```python\n{EV_MOD}\n```\n"
    ),
}

REPORTED = {
    # closed on A's ce987e856 (layout-independent parser): markers before the
    # fence are now associated with the fence - with a genuine modification
    # this shape applies
    "markers BEFORE fence, modified": (
        f"{MARKER}# FUNCTION: _apply_grid_limits\n" f"```python\n{GRID_MOD}\n```\n"
    ),
    # open: an unchanged echo next to a genuine modification rejects the WHOLE
    # response (the dominant live failure on ce987e856)
    "modified + unchanged echo (unfenced)": (
        f"{MARKER}# FUNCTION: _apply_grid_limits\n{GRID_MOD}\n"
        f"{MARKER}# FUNCTION: _apply_grid_violation_redispatch\n{REDISP}\n"
    ),
    # (the echo and multi-fenced gap cases moved to MUST_APPLY when they closed
    # on main 07fa66512 - verified there at zero cost)
}


def run(label: str, response: str, coder: LLMCoderAgent) -> bool:
    result = coder._parse_llm_response_function_replacement(
        response, CONTROLLER, CONTROLLER_FILE
    )
    if result is None:
        err = str(coder.previous_failures[-1].get("error"))[:90]
        print(f"  {label:<42} REJECTED | {err}")
        coder.previous_failures.clear()
        return False
    patched, _diff, changes, notes = result
    try:
        ast.parse(patched)
        parses = "YES"
    except SyntaxError as exc:
        parses = f"NO: {exc}"
    funcs = [c["function"] for c in changes]
    print(f"  {label:<42} APPLIED {len(changes)} -> {funcs} | patched parses: {parses}")
    coder.previous_failures.clear()
    return parses == "YES" and bool(changes)


def main() -> int:
    coder = LLMCoderAgent(preflight_probe=False)
    print("shapes that MUST apply:")
    ok = all(run(k, v, coder) for k, v in MUST_APPLY.items())
    print(
        "shapes reported for the record (not asserted): the two dispatched gap"
        " families (echo-skip; block-local fence slicing) CLOSED on main"
        " 07fa66512 and were promoted to MUST_APPLY above - verified there at"
        " zero cost."
    )
    for k, v in REPORTED.items():
        run(k, v, coder)
    print("\nverdict:", "PASS - all must-apply shapes apply" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
