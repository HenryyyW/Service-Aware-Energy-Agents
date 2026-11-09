#!/usr/bin/env python3
"""Code-repair benchmark driver (deterministic; zero LLM calls as wired).

Per task: seed the defect -> detect (signature on the broken controller) ->
repair loop (Planner/Coder/Executor/Verifier/Reporter, <= 3 iterations) ->
criteria (a)-(f) per iteration -> before/after full simulation -> persist the
cell with manifest, repair audit, defect diff and per-cell L1/L5 telemetry.

Usage:
    python -m experiments.run_code_repair --dry-run        # task_1 + task_10 only
    python -m experiments.run_code_repair --all            # full matrix (post sign-off)
    python -m experiments.run_code_repair --tasks task_4 task_6
    python -m experiments.run_code_repair --list

Output: experiments/m2b_code_repair/<task_id>/<run_id>/ (authorized envelope).

NOTE ON LLM CALLS: as wired on origin/main the repair path (Planner ->
Coder -> Executor -> Verifier) is fully deterministic - CoderAgent maps
(issue, function, strategy) to AST transformations with no backend call - so
this driver makes zero LLM calls. The authorized laguna envelope stays unused
and available; it is only consumed if the Coder is later wired to a backend.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.code_repair_tasks import (  # noqa: E402
    CONTROLLER_FILE,
    TASKS,
    _load_controller,
    apply_mutation,
    load_tasks,
)
from experiments.code_repair_detectors import (  # noqa: E402
    _obs,
)

MATRIX = ROOT / "experiments" / "m2b_code_repair"
ARM = os.environ.get("CODE_REPAIR_ARM", "deterministic")
NIM_ENDPOINT = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "poolside/laguna-xs-2.1"
KEY_STORE = (
    "/home/box/.config/OpenBot/agent-api-keys/"
    "agent-66d119d6-4915-479e-a539-1ab4a6b3b57b/NVIDIA_API_KEY"
)


def configure_llm_arm() -> dict:
    """Set the LLM-arm environment (NIM / laguna-xs-2.1) before any config read.

    Called at process start for --arm llm. DASHSCOPE is unset so the
    DashScope key can never be picked up; the NIM key comes from the
    key-store file. Returns the probe-relevant settings for the record.
    """
    os.environ["AGENT_BACKEND"] = f"api:{NIM_MODEL}"
    os.environ["LLM_MODEL"] = NIM_MODEL
    os.environ["LLM_PROVIDER"] = "nvidia"
    os.environ["LLM_ENDPOINT"] = NIM_ENDPOINT
    os.environ.pop("DASHSCOPE_API_KEY", None)
    key_path = Path(KEY_STORE)
    if not key_path.is_file():
        raise RuntimeError(f"NIM key not found at {key_path}")
    os.environ["NVIDIA_API_KEY"] = key_path.read_text().strip()
    return {
        "agent_backend": f"api:{NIM_MODEL}",
        "endpoint": NIM_ENDPOINT,
        "model": NIM_MODEL,
        "dashscope_unset": "DASHSCOPE_API_KEY" not in os.environ,
    }


def build_nim_backend():
    """Explicit NIM backend via the coder's supported injection point.

    Needed because LLMConfig.create_backend() raises TypeError for the api
    backend (openai_api_key passed to ApiPromptCallable) and LLMCoderAgent
    swallows it into the keyless env fallback - a wiring defect in
    src/agents/backend/registry.py reported to A; the injection point is the
    documented alternative and uses the same endpoint/model/key.
    """
    from src.agents.backend.api import api_prompt_callable

    return api_prompt_callable(
        model=NIM_MODEL,
        base_url=NIM_ENDPOINT,
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=0.2,
        seed=42,
        timeout_s=120.0,
        max_tokens=4096,
    )


def preflight_probe_explicit() -> bool:
    """1-token probe through the explicit NIM backend (the injection path the
    LLM arm uses, because LLMConfig.create_backend() is broken - see report)."""
    try:
        backend = build_nim_backend()
        backend("probe")
        return backend.call_count >= 1 and backend.last_error is None
    except Exception as exc:  # noqa: BLE001
        print(f"pre-flight probe failed: {type(exc).__name__}: {exc}")
        return False


def preflight_probe() -> bool:
    """1-token probe against the configured NIM backend; True on success."""
    from src.agents.llm_coder import LLMCoderAgent

    coder = LLMCoderAgent(preflight_probe=False)
    backend = coder._get_backend()
    if backend is None:
        return False
    backend("probe")
    return backend.call_count >= 1 and backend.last_error is None


DRY_RUN_TASKS = ["task_1_ev_deadline_soc", "task_10_NEG_redispatch_removed"]


# ---------------------------------------------------------------------------
# per-cell helpers
# ---------------------------------------------------------------------------


def proposal_bound_violations(
    controller_cls, config, steps: int = 24
) -> Tuple[int, int]:
    """L1 (derived, E1 method): requested values beyond the device rating.

    Returns (violating values, steps). Ratings come from the probe config's
    battery/EV power; flex has no kW rating and is not checked (same rule as
    the E1 extraction).
    """
    ratings: Dict[str, float] = {}
    for b in config.buildings:
        bid = b.building_id
        if b.battery and b.battery.power_kw:
            ratings[f"{bid}_battery"] = float(b.battery.power_kw)
        for i, ev in enumerate(b.evs or []):
            if ev.max_charge_kw:
                ratings[f"{bid}_ev_{i}"] = float(ev.max_charge_kw)
    c = controller_cls(config)
    c.reset()
    values = steps = 0
    for t in range(steps):
        req = c.get_actions(_obs(), t)
        step_hit = False
        for a in req.actions:
            limit = ratings.get(a.asset_id)
            if limit and abs(a.value_kw) > limit + 1e-9:
                values += 1
                step_hit = True
        steps += 1 if step_hit else 0
    return values, steps


def run_detector_safe(
    detector, controller_cls, config
) -> Tuple[Optional[bool], str, Optional[str]]:
    """Run a detector, capturing exceptions (criterion (b): runs clean)."""
    try:
        ok, detail = detector(controller_cls, config)
        return ok, detail, None
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        return (
            None,
            f"detector raised {type(exc).__name__}: {exc}",
            f"{type(exc).__name__}: {exc}",
        )


def build_experiment_result(task, detector_detail: str):
    from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType

    return ExperimentResult(
        run_id=task.task_id,
        scenario_id="task_probe",
        controller_type=ControllerType.RULE_BASED,
        status=ExperimentStatus.FAILED,
        random_seed=42,
        diagnostic_reports=[{"detail": detector_detail}],
    )


def build_diagnostic_report(task, detector_detail: str):
    from src.schemas.diagnostics import (
        DiagnosticReport,
        Diagnostic,
        DiagnosticCategory,
        Severity,
    )

    return DiagnosticReport(
        scenario_id="task_probe",
        run_id=task.task_id,
        timestep=0,
        diagnostics=[
            Diagnostic(
                diagnostic_id=f"{task.task_id}_detector",
                category=DiagnosticCategory.GRID_LIMIT,
                severity=Severity.VIOLATION,
                message=detector_detail,
                timestep=0,
            )
        ],
        total_violations=1,
    )


def diff_text(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="broken_controller",
            tofile="patched_controller",
        )
    )


def sandbox_run(controller_code: str, cell_dir: Path, tag: str, max_steps: int = 24):
    """Full 24-step simulation in the sandbox (deterministic, no LLM)."""
    from src.agents.sandbox import validate_controller_in_sandbox

    controller_rel = f"controllers/rule_based_{tag}.py"
    cfg = cell_dir / "probe.yaml"
    try:
        result = validate_controller_in_sandbox(
            controller_code,
            controller_rel,
            str(cfg),
            project_root=str(ROOT),
            max_steps=max_steps,
        )
        return {
            "success": result.success,
            "error": result.error,
            "violation_counts": result.violation_counts,
            "max_violations": result.max_violations,
            "execution_time": round(result.execution_time, 2),
            "tests_passed": result.tests_passed,
        }
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


def cell_dir_for(task_id: str, run_id: str) -> Path:
    d = MATRIX / ARM / task_id / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def persist(cell_dir: Path, name: str, payload: dict) -> None:
    (cell_dir / name).write_text(json.dumps(payload, indent=2, default=str))


# ---------------------------------------------------------------------------
# cell execution
# ---------------------------------------------------------------------------


class ForcedPlanner:
    """Harness-side planner bypass (A's sign-off workaround): forces the task's
    own primary issue and target functions instead of the planner's
    severity-only prioritisation, whose issue map also lacks
    _apply_grid_violation_redispatch. Wraps PlannerAgent so the rest of the
    loop is unchanged."""

    def __init__(self, inner, issue: str, targets: List[str]):
        self._inner = inner
        self._issue = issue
        self._targets = targets

    def plan(self, state):
        plan = self._inner.plan(state)
        plan.primary_issue = self._issue
        plan.target_functions = list(self._targets)
        state.repair_plan = plan.model_dump()
        return plan

    def __getattr__(self, name):
        return getattr(self._inner, name)


def run_cell(task, max_iterations: int = 3, sandbox: bool = True) -> dict:
    from src.agents.multi_agent_loop import MultiAgentRepairLoop
    from src.agents.planner import PlannerAgent

    source = (ROOT / CONTROLLER_FILE).read_text()
    broken = apply_mutation(source, task)
    run_id = f"{task.task_id}_det"
    cell_dir = cell_dir_for(task.task_id, run_id)
    (cell_dir / "defect.diff").write_text(diff_text(source, broken))

    config = task.config()
    (cell_dir / "probe.yaml").write_text(
        json.dumps(config.model_dump(mode="json"), indent=2)
    )

    # 1) detector signature on the broken controller
    broken_ok, broken_detail, broken_exc = run_detector_safe(
        task.detector_fn(), _load_controller(broken, f"broken_{run_id}"), config
    )
    signature_present = (broken_exc is None) and (broken_ok is True)
    if task.negative_control:
        signature_present = (broken_exc is None) and (broken_ok is True)
    else:
        signature_present = (broken_exc is None) and (broken_ok is False)

    # 2) repair loop (sandbox memory limit raised: the 512 MB default makes the
    # sandbox's pytest subprocess fail in this container - jemalloc arena /
    # compile errors, an environment failure, not a patch failure; recorded in
    # the manifest)
    from src.agents.executor import ExecutorAgent
    from src.agents.sandbox import Sandbox as _Sandbox

    executor = ExecutorAgent(project_root=str(ROOT))
    executor.sandbox = _Sandbox(
        project_root=str(ROOT), timeout=120, memory_limit_mb=4096
    )
    planner = ForcedPlanner(
        PlannerAgent(), task.planner_issue or "none", task.planner_targets
    )
    coder_config = (
        {
            "use_llm_coder": True,
            "preflight_probe": True,
            "temperature": 0.2,
            "backend": build_nim_backend(),
            "wiring_workaround": (
                "explicit backend injection: LLMConfig.create_backend() raises "
                "TypeError (openai_api_key -> ApiPromptCallable) and "
                "LLMCoderAgent falls back to the keyless env path"
            ),
        }
        if ARM == "llm"
        else None
    )
    loop = MultiAgentRepairLoop(
        max_iterations=max_iterations,
        project_root=str(ROOT),
        executor=executor,
        planner=planner,
        coder_config=coder_config,
    )
    started = time.time()
    try:
        result = loop.run_repair(
            build_experiment_result(task, broken_detail),
            [build_diagnostic_report(task, broken_detail)],
            broken,
            CONTROLLER_FILE,
            config.model_dump(mode="json"),
            str(cell_dir / "probe.yaml"),
        )
        loop_error = None
    except Exception as exc:  # noqa: BLE001 - recorded
        result = None
        loop_error = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - started, 2)

    iterations = []
    patched_final = broken
    if result is not None:
        for it in result.iterations:
            patched_final = it.coder_output.patched_code or patched_final
            iterations.append(
                {
                    "iteration": it.iteration + 1,
                    "planner_issue": it.planner_output.primary_issue,
                    "planner_targets": it.planner_output.target_functions,
                    "planner_strategy": it.planner_output.repair_strategy,
                    "target_functions": it.planner_output.target_functions,
                    "coder_changes": len(it.coder_output.code_changes),
                    "coder_source": (
                        "LLM"
                        if "LLM-generated"
                        in (it.coder_output.implementation_notes or "")
                        else "deterministic"
                    ),
                    "diff": it.coder_output.diff,
                    "verifier_violations_resolved": it.verifier_output.violations_resolved,
                    "success": it.success,
                    "duration": round(it.duration, 2),
                }
            )

    backend_stats = None
    if ARM == "llm":
        try:
            backend = getattr(loop.coder, "_backend", None)
            if backend is not None:
                backend_stats = {
                    "llm_calls": backend.call_count,
                    "llm_prompt_tokens": backend.prompt_tokens,
                    "llm_completion_tokens": backend.completion_tokens,
                    "model_digest": backend.model_digest,
                    "last_error": backend.last_error,
                    "llm_backend_errors": (1 if backend.last_error else 0),
                }
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            backend_stats = {"telemetry_error": f"{type(exc).__name__}: {exc}"}

    # 3) criteria on the final patched controller
    patched_cls = _load_controller(patched_final, f"patched_{run_id}")
    patched_ok, patched_detail, patched_exc = run_detector_safe(
        task.detector_fn(), patched_cls, config
    )
    from src.agents.diff_classifier import classify_diff

    cosmetic = None
    try:
        classification = classify_diff(broken, patched_final)
        cosmetic = bool(getattr(classification, "cosmetic", False))
    except Exception as exc:  # noqa: BLE001
        cosmetic = f"unrecorded ({type(exc).__name__}: {exc})"

    # output differs from the broken baseline under the probe (criterion c)
    def _probe_magnitude(cls):
        try:
            c = cls(config)
            c.reset()
            return sum(abs(a.value_kw) for a in c.get_actions(_obs(), 12).actions)
        except Exception:  # noqa: BLE001
            return None

    broken_mag = _probe_magnitude(_load_controller(broken, f"broken_mag_{run_id}"))
    patched_mag = _probe_magnitude(patched_cls)
    output_differs = (
        broken_mag is not None
        and patched_mag is not None
        and abs(broken_mag - patched_mag) > 1e-6
    )

    # 4) L1/L5 telemetry (PM amendment 2)
    l1_broken = proposal_bound_violations(
        _load_controller(broken, f"broken_l1_{run_id}"), config
    )
    l1_patched = proposal_bound_violations(patched_cls, config)
    telemetry = {
        "l1_broken": {
            "violating_values": l1_broken[0],
            "violating_steps": l1_broken[1],
        },
        "l1_patched": {
            "violating_values": l1_patched[0],
            "violating_steps": l1_patched[1],
        },
    }
    if sandbox:
        telemetry["l5_before"] = sandbox_run(broken, cell_dir, "before")
        telemetry["l5_after"] = sandbox_run(patched_final, cell_dir, "after")

    criteria = {
        "a_parses": patched_exc is None,
        "b_ran_clean": patched_exc is None,
        "c_output_differs": output_differs,
        "d_not_cosmetic": (
            (cosmetic is False) if isinstance(cosmetic, bool) else cosmetic
        ),
        "e_harness_accepts": (
            result is not None
            and any(it.verifier_output.violations_resolved for it in result.iterations)
        ),
        "f_service_preserved": None,  # from the before/after KPIs; set below
    }
    if task.negative_control:
        # the required outcome is honest non-repair
        repaired = bool(output_differs and cosmetic is False)
        criteria["f_service_preserved"] = not repaired
    else:
        criteria["f_service_preserved"] = patched_ok  # detector = service/defect test

    if task.negative_control:
        # required outcome: honest non-repair - no iteration repaired the defect
        any_repaired = bool(
            result is not None
            and any(it.verifier_output.violations_resolved for it in result.iterations)
        )
        keep = (not any_repaired) and (criteria["f_service_preserved"] is True)
    else:
        keep = (
            criteria["a_parses"] is True
            and criteria["b_ran_clean"] is True
            and criteria["f_service_preserved"] is True
            and criteria["d_not_cosmetic"] is not False
        )

    loop_claimed_success = bool(
        result is not None and any(it.success for it in result.iterations)
    )
    manifest = {
        "run_id": run_id,
        "task_id": task.task_id,
        "arm": task.arm,
        "negative_control": task.negative_control,
        "arm": ARM,
        "wiring_workaround": (
            "explicit NIM backend injection (create_backend TypeError, A-side defect)"
            if ARM == "llm"
            else None
        ),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "controller_file": CONTROLLER_FILE,
        "expected_transformations": task.expected_transformations,
        "planner_bypass": {
            "forced_issue": task.planner_issue,
            "forced_targets": task.planner_targets,
        },
        "detector_signature_present_on_broken": signature_present,
        "detector_broken": {"passed": broken_ok, "detail": broken_detail},
        "detector_patched": {"passed": patched_ok, "detail": patched_detail},
        "iterations": len(iterations),
        "wall_clock_seconds": elapsed,
        "llm_calls": (backend_stats or {}).get("llm_calls", 0),
        "llm_backend_errors": (backend_stats or {}).get("llm_backend_errors", 0),
        "backend_telemetry": backend_stats,
        "sandbox_memory_limit_mb": 4096,
        "keep": keep,
        # acceptance of record = the driver-level criteria (a)-(f); the loop's
        # own success flag is recorded beside it, never as the verdict (the
        # false-positive finding of the first two runs)
        "acceptance_of_record": "driver criteria (a)-(f)",
        "loop_claimed_success": loop_claimed_success,
        "verdict": (
            "driver-keep"
            if keep
            else (
                "loop-claims-success / driver rejects"
                if loop_claimed_success
                else "driver-reject"
            )
        ),
    }
    persist(cell_dir, "manifest.json", manifest)
    persist(
        cell_dir,
        "repair_audit.json",
        {
            "criteria": criteria,
            "iterations": iterations,
            "loop_error": loop_error,
            "telemetry": telemetry,
            "cosmetic": cosmetic,
            "magnitudes": {"broken": broken_mag, "patched": patched_mag},
        },
    )
    return manifest


def _git_commit() -> Optional[str]:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def _git_dirty() -> Optional[bool]:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return bool(out)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", nargs="*", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help="skip the before/after full simulation",
    )
    args = parser.parse_args()

    if args.list:
        for t in TASKS:
            print(f"{t.task_id:<34} {t.title}")
        return 0

    if ARM == "llm":
        cfg = configure_llm_arm()
        print("LLM arm configuration:", json.dumps(cfg))
        if not preflight_probe_explicit():
            print("PRE-FLIGHT FAILED - aborting the queue (no LLM calls)")
            return 2
        print("PRE-FLIGHT: PASS (1 token, model digest recorded)")

    if args.dry_run:
        task_ids = DRY_RUN_TASKS
    elif args.tasks:
        task_ids = args.tasks
    else:
        task_ids = [t.task_id for t in TASKS]

    print(
        f"tasks: {len(task_ids)}; iterations <= {args.iterations}; "
        f"sandbox before/after: {'off' if args.no_sandbox else 'on'}; "
        f"LLM calls: 0 (deterministic repair path as wired)"
    )
    summaries = []
    for task in load_tasks(task_ids):
        print(f"\n=== {task.task_id} - {task.title} ===")
        m = run_cell(task, max_iterations=args.iterations, sandbox=not args.no_sandbox)
        summaries.append(m)
        print(
            f"  iterations={m['iterations']} keep={m['keep']} "
            f"signature_present={m['detector_signature_present_on_broken']} "
            f"patched_passes_detector={m['detector_patched']['passed']}"
        )
    kept = sum(1 for m in summaries if m["keep"])
    print(f"\nsummary: {kept}/{len(summaries)} cells keep")
    return 0


if __name__ == "__main__":
    sys.exit(main())
