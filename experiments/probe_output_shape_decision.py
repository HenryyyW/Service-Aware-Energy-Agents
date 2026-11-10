"""The PM's decision-point probe on origin/main: 2 tasks, <= 6 calls, configured
product path. Records each response's shape (fenced blocks, marker pairs inside
vs outside fences, ---/+++/@@ headers, per-hunk +/-/context counts), whether it
converts (changes > 0, ast-valid), and the detector verdict on the patched
controller.

    CODE_REPAIR_ARM=llm python3 experiments/probe_output_shape_decision.py
"""

import ast
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.run_code_repair import (  # noqa: E402
    _configured_backend_ok,
    _harness_detector,
    build_nim_backend,
    configure_llm_arm,
)
from experiments.code_repair_tasks import TASKS  # noqa: E402
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

CATS = {
    "task_4_import_limit": DiagnosticCategory.GRID_LIMIT,
    "task_8_flex_deadline": DiagnosticCategory.FLEXIBLE_LOAD,
}


class RecordingBackend:
    """Delegates to the configured product path (or the explicit NIM injection
    when the configured path is unusable - the runner's own selection) and
    records every raw response for the shape record."""

    def __init__(self, inner):
        self.inner = inner
        self.raws = []

    def __call__(self, prompt):
        out = self.inner(prompt)
        self.raws.append(out)
        return out

    def __getattr__(self, name):
        return getattr(self.inner, name)


def shape_of(raw: str) -> dict:
    fenced = re.findall(r"```python\n(.*?)```", raw, re.DOTALL)
    pairs = re.findall(r"# FILE:\s*(.+?)\s*\n# FUNCTION:\s*(\w+)\n", raw)
    pairs_inside = sum(1 for b in fenced if "# FILE:" in b and "# FUNCTION:" in b)
    return {
        "len": len(raw or ""),
        "fenced_blocks": len(fenced),
        "marker_pairs_total": len(pairs),
        "marker_pairs_inside_fences": pairs_inside,
        "diff_headers": "---" in raw and "+++" in raw,
        "hunks": len(re.findall(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", raw, re.M)),
        "plus_lines": len(re.findall(r"^\+(?!\+\+)", raw, re.M)),
        "minus_lines": len(re.findall(r"^-(?!--)", raw, re.M)),
        "context_lines": len(re.findall(r"^ (?! )", raw, re.M)),
    }


def main() -> int:
    print("configured:", configure_llm_arm())
    configured_ok = _configured_backend_ok()
    print("configured product path usable:", configured_ok)

    def make_backend():
        if configured_ok:
            from src.agents.backend.config import LLMConfig

            inner = LLMConfig().create_backend()
        else:
            inner = build_nim_backend()
            inner.timeout_s = 300.0
            inner.max_tokens = 4096
        return RecordingBackend(inner)

    total_calls = 0
    for tid, cat in CATS.items():
        backend = make_backend()
        task = [t for t in TASKS if t.task_id == tid][0]
        result = ExperimentResult(
            run_id="probe",
            scenario_id="task_probe",
            controller_type=ControllerType.RULE_BASED,
            status=ExperimentStatus.FAILED,
            random_seed=42,
        )
        report = DiagnosticReport(
            scenario_id="task_probe",
            run_id="probe",
            timestep=0,
            diagnostics=[
                Diagnostic(
                    diagnostic_id="p",
                    category=cat,
                    severity=Severity.VIOLATION,
                    message="detector failure",
                    timestep=0,
                )
            ],
        )
        state = AgentState(
            experiment_result=result,
            diagnostic_reports=[report],
            controller_code=(ROOT / "src/controllers/__init__.py").read_text(),
            controller_file="src/controllers/__init__.py",
            scenario_config={},
            scenario_config_path="",
            max_iterations=1,
            detector_fn=_harness_detector(task),
        )
        plan = PlannerAgent().plan(state)
        coder = LLMCoderAgent(preflight_probe=False, timeout_s=300.0, backend=backend)
        out = coder.code(state, plan, "src/controllers/__init__.py")
        total_calls += backend.call_count
        print(f"\n===== {tid} =====")
        print(
            f"calls: {backend.call_count} | tokens: "
            f"{backend.prompt_tokens}/{backend.completion_tokens}"
        )
        for i, raw in enumerate(backend.raws):
            print(f"  raw[{i}] shape: {shape_of(raw)}")
        print(
            f"  verdict: changes={len(out.code_changes)} | "
            f"{out.implementation_notes[:100]}"
        )
        for f in coder.previous_failures[:2]:
            print(f"  failure: {str(f.get('error'))[:120]}")
        try:
            ast.parse(out.patched_code)
            parses = "YES"
        except SyntaxError as e:
            parses = f"NO: {e}"
        print(f"  patched ast-valid: {parses}")
        if out.code_changes:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
                fh.write(out.patched_code)
                tp = fh.name
            spec = importlib.util.spec_from_file_location("pp", tp)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            ok, detail = task.detector_fn()(mod.RuleBasedController, task.config())
            print(f"  DETECTOR on patched: {ok} | {detail[:70]}")
            os.unlink(tp)
    print(
        f"\nTOTAL backend calls this probe: {total_calls} " "(<= 6 per the PM envelope)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
