# Code-repair benchmark: authorized queue results (2026-11-09, zero-LLM run)

Run: `experiments/run_code_repair.py --all --iterations 3` on branch
`reviewer-response/e1-f-counts` (driver @ the run commit; cells in
`experiments/m2b_code_repair/<task_id>/<run_id>/`). Envelope per the PM's
clearance: `experiments/m2b_code_repair/` only, <= 10 tasks x <= 3 iterations,
M2b keep discipline, per-cell publication, quarantine excluded, epochs never
pooled. Amendment 2 (per-cell L1/L5) satisfied: L1 is the derived
proposal-layer count (requested actions x device ratings, the E1 method,
labelled derived) and L5 is the before/after 24-step sandbox simulation's
violation counts, both published per cell in `repair_audit.json`.

**LLM accounting: zero LLM calls were made.** As wired on origin/main the
repair path (Planner -> Coder -> Executor -> Verifier) is deterministic
(`CoderAgent` maps issue/function/strategy to AST transformations; no backend
call exists in `src/agents/{planner,coder,verifier}.py`). The authorized
laguna/NIM envelope is therefore untouched; an LLM-wired variant requires
wiring the Coder to `src/agents/backend/` (A's change). No cell has
`llm_backend_errors > 2` (all are 0), so no quarantine trigger fired.

## Per-cell results

| Task | Iter | Planner issue | Loop claim | Driver criteria (a/b/c/d/e/f) | keep | L5 before | L5 after (patched) |
|---|---|---|---|---|---|---|---|
| task_1_ev_deadline_soc | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_2_ev_urgent_power | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_3_battery_soc_floor | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_4_import_limit | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_5_export_limit | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_6_voltage_response | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_7_line_loading_response | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_8_flex_deadline | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_9_overcharge_spike | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/? | False | ran, 0 viol | CRASH |
| task_10_NEG_redispatch_removed | 1 | grid_export | success=True, resolved=True | N/N/N/Y/Y/Y | False | ran, 0 viol | CRASH |

Criteria: (a) parses/applies, (b) runs clean, (c) output differs from the broken
baseline, (d) not cosmetic, (e) harness accepts, (f) service/defect test passes.

## Headline

- **Measured tasks repaired: 0 of 9** (threshold >= 7/9: not met; reported
  either way, as pre-registered).
- **Negative control: PIPELINE FALSE POSITIVE** - the loop claims
  `success=True, resolved=True` for a patch that crashes on execution. The
  driver-level criteria correctly reject it (keep=False for all 10 cells), but
  the loop's internal verifier does not.
- **L1 (derived): 0 violating proposal values in every broken cell and every
  patched cell** - the seeded defects are not proposal-layer bound violations
  (they are logic defects inside the controller), so the L1 telemetry is
  reported as 0/0 with that explanation rather than omitted.
- **L5: every broken controller runs clean in the before/after simulation
  (0 voltage/line/transformer violations); every "repaired" controller fails
  to execute** (`UnboundLocalError: cannot access local variable
  'export_limit'`, raised on the first `get_actions` call because the Coder
  inserts its snippet above the early-return guard in `_apply_grid_limits`).
  No cost/peak/service deltas exist for any patched cell because no patched
  controller completed a simulation.

## Root causes (three, all actionable, none of them the benchmark's design)

1. **Planner issue mapping is task-blind** - every task's plan maps to
   `grid_export` and targets `_apply_grid_limits`/`_control_battery`, whatever
   the seeded defect. Flagged to A with the sign-off request; confirmed by this
   run across all 10 tasks.
2. **The Coder's `_apply_changes` is not a minimal patch** - it reformats the
   whole file (statement collapsing, quote normalization) and inserts its
   snippet at the top of the function, above the variables the snippet
   references. The result parses but crashes. The diff classifier marks it
   behavior-changing, which is technically true and useless.
3. **The loop's acceptance path is a false positive** - the Executor validates
   with `run_tests` (the shipped suite, which never touches the patched
   controller) and the verifier's `violations_resolved` is then computed from
   an execution that never ran the patched code, so a crashing patch reads as
   "violations resolved". (The sandbox's `run_experiment` path - used for my
   before/after - catches the crash correctly.)

## Environment fix applied and disclosed

The sandbox's default 512 MB `RLIMIT_AS` makes its pytest subprocess fail in
this container (`jemalloc: arena 0 background thread creation failed`), which
broke criterion (b) for every patch in the dry-run. For this queue the driver
constructs the loop's Executor with `Sandbox(memory_limit_mb=4096)` and records
`sandbox_memory_limit_mb: 4096` in every cell manifest. With that, the
sandbox's unit tests pass (3.7 s) and the failure mode above is purely the
patch content, not the environment.

## Recommendation

Do not put any code-repair number in the paper from this run. The pipeline
needs (1) a task-aware issue->function mapping, (2) a Coder that emits a
minimal in-place patch, and (3) an Executor that runs the patched controller
and a Verifier that rejects absent execution. All three are A's; the benchmark
harness, detectors, and criteria are proven and will re-run unchanged once
those land. The paper's "scaffolded, not yet demonstrated" wording therefore
stays correct.
