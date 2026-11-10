"""Capture the LLM's raw output shape against the coder's contracts.

One in-envelope probe: a single ``coder.code()`` call on one task with a
transparent recording backend, so the exact raw responses behind the
function-replacement (primary) and unified-diff (fallback) parse failures are
reproducible without re-deriving them from the 500-char failure history.

Usage (LLM arm env is set by ``configure_llm_arm``; 2 backend calls per run):

    CODE_REPAIR_ARM=llm python3 experiments/probe_llm_output_shape.py task_4_import_limit

Envelope: counts against the code-repair probe budget (<= 6 calls for the
2-3-task probe; this script alone is 2 calls - primary + fallback).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.run_code_repair import (  # noqa: E402
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

CATEGORY_BY_TASK = {
    "task_1_ev_deadline_soc": DiagnosticCategory.EV_DEADLINE,
    "task_2_ev_urgent_power": DiagnosticCategory.EV_DEADLINE,
    "task_4_import_limit": DiagnosticCategory.GRID_LIMIT,
    "task_8_flex_deadline": DiagnosticCategory.FLEXIBLE_LOAD,
}


class RecordingBackend:
    """Transparent proxy - identical generation, records every raw response."""

    def __init__(self, inner):
        self.inner = inner
        self.raws = []

    def __call__(self, prompt):
        out = self.inner(prompt)
        self.raws.append(out)
        return out

    def __getattr__(self, name):
        return getattr(self.inner, name)


def main() -> int:
    task_id = sys.argv[1] if len(sys.argv) > 1 else "task_4_import_limit"
    print("configured:", configure_llm_arm())
    inner = build_nim_backend()
    inner.timeout_s = 300.0
    inner.max_tokens = 4096
    backend = RecordingBackend(inner)

    task = [t for t in TASKS if t.task_id == task_id][0]
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
                category=CATEGORY_BY_TASK[task_id],
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

    print(
        f"\nbackend calls: {backend.call_count} | tokens: "
        f"{backend.prompt_tokens}/{backend.completion_tokens}"
    )
    for i, raw in enumerate(backend.raws):
        label = (
            "function-replacement (primary)" if i == 0 else "unified-diff (fallback)"
        )
        print(f"\n===== RAW {i + 1}: {label} (len {len(raw or '')}) =====")
        print("  '# FILE:' matches:", re.findall(r"# FILE:\s*(.+)", raw)[:5])
        print("  '# FUNCTION:' matches:", re.findall(r"# FUNCTION:\s*(\w+)", raw)[:5])
        print("  fence variants:", re.findall(r"```(\w*)", raw))
        print(
            "  code_match (```python\\n...```):",
            bool(re.search(r"```python\n(.*?)```", raw, re.DOTALL)),
        )
        print("  head:", (raw or "")[:400].replace("\n", "\\n"))
    print("\n----- verdict -----")
    print("changes:", len(out.code_changes), "| notes:", out.implementation_notes)
    for failure in coder.previous_failures[:3]:
        print("  failure:", str(failure.get("error"))[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
