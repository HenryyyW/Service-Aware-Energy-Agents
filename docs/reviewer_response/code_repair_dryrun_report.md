# Code-repair benchmark: zero-LLM dry-run report (2026-11-09)

Driver: `experiments/run_code_repair.py`; tasks:
`experiments/code_repair_tasks.py`; detectors:
`experiments/code_repair_detectors.py`; self-check:
`experiments/code_repair_selfcheck.py` (exit 0 - every mutation anchors exactly
once, every detector passes on the pristine controller and fails on the mutated
one, negative control inverted).

Scope: the PM-approved envelope (`docs/reviewer_response/code_repair_benchmark_scope.md`)
with amendments - A signs off the defect/detector set and the vocabulary
mapping before any LLM call; per-cell L1/L5 telemetry published.

## Dry-run result (both dry-run tasks, 1 iteration, `--no-sandbox` before/after off)

| Task | Seed/detect | Repair loop | Criteria | Verdict |
|---|---|---|---|---|
| `task_1_ev_deadline_soc` | defect diff applied; detector fires (EV SOC 0.4296 vs 0.800 target) | planner diagnosed `grid_export` (MISDIAGNOSIS - the defect is in `_control_ev`), 4 changes to `_apply_grid_limits`/`_control_battery`, patched code raises `UnboundLocalError` at run | (a)/(b) fail (patch crashes), (c) no output difference, (d) behavior-changing, (e) not verified, (f) n/a | honest non-repair; `keep=False` |
| `task_10_NEG_redispatch_removed` | negative-control signature present on the broken controller | 1 iteration; patch also crashes at run | as above | **required outcome**: honest non-repair; `keep=True` |

The harness therefore works end-to-end with **zero LLM calls** - as wired on
origin/main the repair path (Planner -> Coder -> Executor -> Verifier ->
Reporter) is deterministic (`CoderAgent` maps issue/function/strategy to AST
transformations with no backend call), so the authorized laguna envelope is
untouched and stays available.

## Two pre-run findings (blockers for the queue, both from the dry-run)

1. **Planner misdiagnosis**: for task 1 the planner maps the EV-deadline defect
   to `grid_export` and edits `_apply_grid_limits`/`_control_battery` instead of
   `_control_ev`. The diagnostic-to-issue mapping in `src/agents/planner.py`
   does not key on the detector's signature. Until each task's issue maps to the
   mutated function, most measured tasks will not even target the right code -
   A's vocabulary sign-off must cover this, not just the transformation names.
2. **Sandbox unit-test path fails in this environment**: the Executor's
   `run_tests` aborts with `<jemalloc>: arena 0 background thread creation
   failed (11)` (container memory limit), so criterion (b) can never pass and
   every repair attempt is recorded as a sandbox failure regardless of the
   patch. The sandbox's full-experiment path (used for the before/after L5 runs)
   works. Needs QA/DevOps (ulimit/jemalloc or run the tests in the main
   interpreter).

## Before/after simulation (verified working, one cell)

`sandbox_run` (24-step, scenario from the cell's `probe.yaml`) runs the broken
and patched controllers through the full co-simulation and returns
`violation_counts` per category (L5) plus `execution_time` (~0.8 s/run).
Per-cell L1 is recomputed from requested actions x device ratings (the E1
method, labelled derived) and L5 from the sandbox violation counts - PM
amendment 2 satisfied.

## Launch conditions

The authorized queue (all 10 tasks x <= 3 iterations) launches only after:
(1) Backend A's sign-off on the defect/detector set + the vocabulary mapping
(requested, includes findings 1 and 2 above);
(2) a fix or an explicit waiver for the sandbox unit-test failure (finding 2);
(3) the PM's go on the queue.

Cell artifacts from the dry run: `experiments/m2b_code_repair/<task_id>/<run_id>/`
(manifest.json, repair_audit.json, defect.diff, probe.yaml).
