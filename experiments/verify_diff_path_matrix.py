"""Zero-LLM-call acceptance matrix for the DIFF path on the current coder -
the PM's precondition matrix before any LLM calls are spent: single + multi-hunk
diffs convert (the multi-hunk path regressed on the 648f7bf0e rewrite and must
apply with correct coordinates), and the reject gates work.

A stub backend returns canned responses, so the full coder path (primary parse
-> same-response diff fallback -> format validation -> applier -> cosmetic gate)
runs with zero API calls. Diffs are generated with difflib against the REAL
controller source, so headers, counts and context are exactly what a
well-formed model diff looks like.

    python3 experiments/verify_diff_path_matrix.py
"""

import ast
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.llm_coder import LLMCoderAgent  # noqa: E402
from src.agents.planner import PlannerAgent  # noqa: E402
from src.agents.roles import AgentState  # noqa: E402
from src.schemas.diagnostics import (  # noqa: E402
    Diagnostic,
    DiagnosticCategory,
    DiagnosticReport,
    Severity,
)
from src.schemas.report import (  # noqa: E402
    ExperimentResult,
    ExperimentStatus,
    ControllerType,
)

CONTROLLER = (ROOT / "src/controllers/__init__.py").read_text()
FILE = "controllers/__init__.py"

# two genuine behaviour changes in functions far apart in the file
MOD_A_OLD = "        if total_import > import_limit:\n"
MOD_A_NEW = (
    "        if total_import > import_limit * 1.05:\n"
    "            # tolerance band for grid import limiting\n"
    "            pass\n"
)
MOD_B_OLD = "        connected = arrival_hour <= hour_of_day < departure_hour\n"
MOD_B_NEW = "        connected = arrival_hour <= hour_of_day <= departure_hour\n"
assert MOD_A_OLD in CONTROLLER and MOD_B_OLD in CONTROLLER
# full-line fixtures only: a leading-substring match inside a deeper-indented
# line would silently produce a same-indent if/pass pair (IndentationError)
assert CONTROLLER.count(MOD_A_OLD) == 1 and CONTROLLER.count(MOD_B_OLD) == 1


def make_diff(mods):
    modified = CONTROLLER
    for old, new in mods:
        assert old in modified
        modified = modified.replace(old, new, 1)
    ast.parse(modified)  # the fixture itself must be valid Python
    diff = "".join(
        difflib.unified_diff(
            CONTROLLER.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{FILE}",
            tofile=f"b/{FILE}",
        )
    )
    return diff, modified


SINGLE, MODIFIED_SINGLE = make_diff([(MOD_A_OLD, MOD_A_NEW)])
MULTI, MODIFIED_MULTI = make_diff([(MOD_A_OLD, MOD_A_NEW), (MOD_B_OLD, MOD_B_NEW)])
# MULTI has a +2 line delta in the EARLIER hunk and 0 in the later one, so a
# forward-order applier would corrupt the later hunk's coordinates - this is
# the exact regression the PM flagged on the 648f7bf0e rewrite
print(
    f"diffs: single-hunk lines={len(SINGLE.splitlines())}, "
    f"multi-hunk lines={len(MULTI.splitlines())}, "
    f"multi hunks={MULTI.count('@@ -')}"
)

# reject-gate cases (each must NOT convert)
ADDITIONS_ONLY = (
    f"--- a/{FILE}\n+++ b/{FILE}\n"
    "@@ -280,3 +280,8 @@ def _apply_grid_limits(self, actions):\n"
    "     total_import = sum(a.value_kw for a in actions if a.value_kw > 0)\n"
    "     total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)\n"
    " \n"
    "+    if self.last_grid_diagnostics:\n"
    '+        diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n'
    "+        for d in diagnostics:\n"
    '+            if d.get("severity") in ["violation", "critical"]:\n'
    "+                pass\n"
)
DELETIONS_ONLY = (
    f"--- a/{FILE}\n+++ b/{FILE}\n"
    "@@ -286,3 +286,1 @@ def _apply_grid_limits(self, actions):\n"
    '-    import_limit = self.scenario_config.community_import_limit_kw or float("inf")\n'
    '-    export_limit = self.scenario_config.community_export_limit_kw or float("inf")\n'
    " \n"
)
COMMENT_ONLY = (
    f"--- a/{FILE}\n+++ b/{FILE}\n"
    "@@ -280,3 +280,6 @@ def _apply_grid_limits(self, actions):\n"
    "     total_import = sum(a.value_kw for a in actions if a.value_kw > 0)\n"
    "     total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)\n"
    " \n"
    "+    # voltage-triggered load reduction\n"
    "+    # grid violation re-dispatch\n"
    "+    # community-level limits applied\n"
)
UNBALANCED = (
    f"--- a/{FILE}\n+++ b/{FILE}\n"
    "@@ -280,4 +280,15 @@ def _apply_grid_limits(self, actions):\n"
    "     total_import = sum(a.value_kw for a in actions if a.value_kw > 0)\n"
    "-    total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)\n"
    " \n"
    "+    if self.last_grid_diagnostics:\n"
    '+        diagnostics = self.last_grid_diagnostics.get("diagnostics", [])\n'
    "+        for d in diagnostics:\n"
    '+            if d.get("severity") in ["violation", "critical"]:\n'
    "+                for a in actions:\n"
    "+                    a.value_kw *= 0.5\n"
    "+                break\n"
    "+        for d in diagnostics:\n"
    "+            pass\n"
    "+        for d in diagnostics:\n"
    "+            pass\n"
    "+        for d in diagnostics:\n"
    "+            pass\n"
    "+        for d in diagnostics:\n"
    "+            pass\n"
)
NO_CHANGE = (
    f"--- a/{FILE}\n+++ b/{FILE}\n"
    "@@ -280,3 +280,3 @@ def _apply_grid_limits(self, actions):\n"
    "     total_import = sum(a.value_kw for a in actions if a.value_kw > 0)\n"
    "     total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)\n"
    " \n"
)
NO_HEADERS = (
    "@@ -280,3 +280,4 @@ def _apply_grid_limits(self, actions):\n"
    "     total_import = sum(a.value_kw for a in actions if a.value_kw > 0)\n"
    "-    total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)\n"
    "+    total_export = sum(-a.value_kw for a in actions if a.value_kw < 0)\n"
    " \n"
)

MUST_CONVERT = {
    "single-hunk diff (1 -> 3 lines)": SINGLE,
    "two-hunk diff, +2 delta in the earlier hunk (reverse-order applier)": MULTI,
}
MUST_REJECT = {
    "additions-only single hunk": ADDITIONS_ONLY,
    "deletions-only, no context": DELETIONS_ONLY,
    "comment-only additions": COMMENT_ONLY,
    "unbalanced > 10:1": UNBALANCED,
    "no actual change (context only)": NO_CHANGE,
    "missing ---/+++ headers": NO_HEADERS,
}


class StubBackend:
    """Returns one canned response - no API call."""

    def __init__(self, text):
        self.text = text

    def __call__(self, prompt):
        return self.text

    def __getattr__(self, name):
        raise AttributeError(name)


def run_case(label, response, expect_convert, expect_modified=None):
    state = AgentState(
        experiment_result=ExperimentResult(
            run_id="matrix",
            scenario_id="task_probe",
            controller_type=ControllerType.RULE_BASED,
            status=ExperimentStatus.FAILED,
            random_seed=42,
        ),
        diagnostic_reports=[
            DiagnosticReport(
                scenario_id="task_probe",
                run_id="task_probe",
                timestep=0,
                diagnostics=[
                    Diagnostic(
                        diagnostic_id="p",
                        category=DiagnosticCategory.GRID_LIMIT,
                        severity=Severity.VIOLATION,
                        message="import limit exceeded",
                        timestep=0,
                    )
                ],
            )
        ],
        controller_code=CONTROLLER,
        controller_file=FILE,
        scenario_config={},
        scenario_config_path="",
        max_iterations=1,
    )
    plan = PlannerAgent().plan(state)
    coder = LLMCoderAgent(
        preflight_probe=False, timeout_s=60.0, backend=StubBackend(response)
    )
    out = coder.code(state, plan, FILE)
    converted = len(out.code_changes) > 0
    detail = ""
    if converted:
        try:
            ast.parse(out.patched_code)
            parses = "YES"
        except SyntaxError as exc:
            parses = f"NO: {exc}"
        if expect_modified is not None:
            exact = out.patched_code == expect_modified
            detail = f"patched_parses={parses} exact_apply={exact}"
        else:
            detail = f"patched_parses={parses}"
    else:
        errs = [str(f.get("error"))[:70] for f in coder.previous_failures[-1:]]
        detail = f"rejected: {errs}"
    ok = converted if expect_convert else (not converted)
    print(
        f"  {label:<58} {'CONVERTED' if converted else 'no-change':>10} | {detail} | {'OK' if ok else 'FAIL'}"
    )
    return ok


def main() -> int:
    print("diff-path cases that MUST convert:")
    ok = True
    ok &= run_case("single-hunk diff (1 -> 3 lines)", SINGLE, True, MODIFIED_SINGLE)
    ok &= run_case(
        "two-hunk diff, +2 delta in the earlier hunk (reverse-order applier)",
        MULTI,
        True,
        MODIFIED_MULTI,
    )
    print("reject-gate cases that MUST NOT convert:")
    for label, response in MUST_REJECT.items():
        ok &= run_case(label, response, False)
    print("\nverdict:", "PASS - diff path matrix green" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
