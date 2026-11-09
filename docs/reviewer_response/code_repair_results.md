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

## Re-run with A's harness-side planner bypass (same envelope, zero LLM)

Per A's sign-off the driver now forces each task's own primary issue and target
functions (`ForcedPlanner` in `experiments/run_code_repair.py`; the override is
needed on `PlannerAgent.plan`, not `create_plan` - the loop calls `plan`).
The bypass works: every task now plans its own issue and targets the mutated
function. The outcome isolates the remaining causes:

- the Coder's patches still fail on **every** measured task (9/9), now with
  target-specific errors that pinpoint the bug: snippets inserted at the top of
  the function body reference variables defined later in it
  (`_control_ev` -> `hours_remaining`, `_control_battery` -> `current_soc`,
  `_apply_grid_limits` -> `export_limit` / `hour_of_day`,
  `_control_flexible_load` -> `hours_until_deadline`,
  `_apply_grid_violation_redispatch` -> `export_limit`). The insertion position,
  not the transformation vocabulary, is the defect (A confirmed the vocabulary
  is expressible);
- the negative control's patch runs cleanly but does not repair the removed
  call site, and the loop still claims `success=True` - the false-positive
  acceptance path (root cause 3) is unchanged: the Executor validates with the
  shipped unit tests, which never execute the patched controller, so the
  verifier reads a non-execution as "violations resolved". My driver-level
  criteria and the before/after sandbox both catch it (keep=False, 10/10).

So: 0/9 measured tasks repaired with correct targeting as well; the planner
bypass removes root cause 1 but exposes root causes 2 (insertion position) and
3 (acceptance path) as the binding ones, both in `src/agents/` (A's).

## Re-run after A's two landed fixes (0a83db3d2)

A landed both binding fixes (`_find_insertion_point` insertion-position helper;
Executor/Verifier absent-execution rejection with `action_counts`). Re-ran the
same envelope (all 10 tasks x <= 3 iterations, zero LLM). Result: **still 0/10
keep** - the fixes are necessary but not sufficient, and the residual failure is
now precisely characterized:

- the Coder now inserts after the function's variable definitions, but the
  transformation snippets still reference names that are **not in the target
  function's scope at all** - they belong to a different function. Task 1's
  snippet went into `get_actions` (my forced target list includes it) and
  references `hours_remaining`, a local of `_control_ev`; the other tasks fail
  on `avg_net_demand`, `hour_of_day`, `building`, `export_limit` in the same
  way. The snippets are authored for one function context and applied to
  another; no insertion position can fix a name that does not exist there.
- the loop's Executor still reports PASS and the Verifier still records
  `violations_resolved=True` / `accept` for a patch that raises on execution -
  reproduced two ways: the sandbox's own `_create_dynamic_controller` path
  raises the same `UnboundLocalError`, and my driver's before/after 24-step run
  fails with the same error. The absent-execution rejection therefore did not
  fire on this path (the Executor's experiment reports actions taken while the
  patched controller crashes - the exception is being swallowed inside the
  experiment loop).
- negative control: patch runs, does not repair, loop still claims success -
  same acceptance-path gap.

So the remaining work for A: snippets must be scoped to the function they are
inserted into (or the coder must choose the function the snippet was authored
for), and the Executor must surface a controller exception as a failed
execution. Both are inside the three gate items the PM already listed.

## Comparator arm (per the user's wire-the-LLM decision)

The deterministic run is no longer a dry-run artefact: it is the comparator
arm's baseline (every task's broken-controller detector signature, the
before/after simulation behaviour, and the honest non-repair outcomes), to be
published separately from the LLM arm and never pooled with it - see the wiring
design in `docs/reviewer_response/code_repair_benchmark_scope.md`.

## Two-arm re-run on origin/main 66e7a7432 (deterministic comparator + LLM-wired measured run)

Both arms ran the same 10 tasks x <= 3 iterations, same detectors, same
driver-level criteria (a)-(f) as the acceptance of record, `loop_claimed_success`
recorded beside the verdict and never as it. Cells:
`experiments/m2b_code_repair/{deterministic,llm}/<task_id>/<run_id>/`.
LLM arm: `AGENT_BACKEND=api:poolside/laguna-xs-2.1`, NVIDIA NIM
(`https://integrate.api.nvidia.com/v1`), key from the key store,
`DASHSCOPE_API_KEY` unset, 1-token pre-flight PASS (model digest
`poolside/laguna-xs-2.1`), per-cell backend telemetry in every manifest.

| Task | deterministic: keep / loop claim | LLM: keep / loop claim | detector (patched, both arms) |
|---|---|---|---|
| task_1_ev_deadline_soc | False / True | False / False | EV SOC 0.4296 vs 0.800 (not repaired) |
| task_2_ev_urgent_power | False / True | False / False | 3.30 kW vs required 11.00 kW |
| task_3_battery_soc_floor | False / True | False / False | overshoot 1.3 kWh/step remains |
| task_4_import_limit | False / True | False / False | import 5.0 kW vs 3 kW limit |
| task_5_export_limit | False / True | False / False | export 5.0 kW vs 3 kW limit |
| task_6_voltage_response | False / True | False / False | 2.50 kW vs expected 2.0x baseline |
| task_7_line_loading_response | False / True | False / False | 2.50 kW vs expected 0.1x baseline |
| task_8_flex_deadline | False / True | False / False | flexible load never ran |
| task_9_overcharge_spike | False / True | False / False | overshoot 10.93 kW remains |
| task_10_NEG (negative control) | False / True | **True** / False | re-dispatch still inert (correct outcome) |

**Headline: 0 of 9 measured tasks repaired in BOTH arms** (pre-registered
threshold >= 7/9 not met; reported either way). The negative control is
`keep=True` in the LLM arm - honest non-repair - while the deterministic arm's
loop still falsely claims success on it.

**Arm differences worth recording:**
- LLM arm: 40 calls total (1 pre-flight + 3 iterations x 10 cells), 0 backend
  errors; every cell used the LLM coder (`coder_source=LLM`); prompt/completion
  tokens ~11,030/900 per cell. `loop_claimed_success` is **False for all 10
  cells** - with the LLM path the loop's own verdict now agrees with the
  driver-level rejection.
- Deterministic arm: `loop_claimed_success` is **True for all 10 cells** - the
  false-positive acceptance pattern survives on the deterministic path even
  after the landed fixes (the Executor's sandbox experiment still passes the
  crashing/unrepaired patches there). The false positive is therefore a
  property of the deterministic acceptance path, not of the LLM path.
- Neither arm repaired any measured defect: the LLM's change descriptions are
  sensible ("Fix grid import limit enforcement by properly scaling down
  actions...") but the AST-application layer still cannot turn them into
  behaviour-changing patches that flip the detectors; and the deterministic
  vocabulary patches still crash or no-op.

**Paper consequence (unchanged):** the code-repair claim stays
"scaffolded, not yet demonstrated"; the honest reported result is a
0-of-9 measured benchmark with the loop's self-report unreliable on the
deterministic path. If any of this is quoted in the paper, the two arms are
published unpooled with these exact per-cell rows.

## Rearm re-run on origin/fix/llm-real-code-path + origin/main (user envelope: <= 10 tasks x <= 5 iterations, laguna/NIM only)

Branch state: A's rearm (`d2c171567` real-code path with test-driven prompt and
loop feedback; `75dafe541` max-iterations 5; `e1e709db3` registry truthiness key
fix) merged with `origin/main` for the acceptance-path crash tracking
(`9f0929041`) - the rearm branch alone lacked it, which reproduced the 0/10
false-positive pattern. Driver: hardened to record an unparsable patch as
criterion (a)=False and continue (the first rearm cell raised IndentationError
inside the driver); LLM arm now runs through the **product path**
(`AGENT_BACKEND=api:poolside/laguna-xs-2.1` + NIM key from the key store,
`DASHSCOPE_API_KEY` unset) with the explicit injection only as a recorded
fallback - the product path built and authenticated in this run (0 injection).

| Task | deterministic: keep / loop | LLM: keep / loop | LLM coder source | LLM calls | criteria (a/b/c/d/e/f) | patched outcome |
|---|---|---|---|---|---|---|
| task_1_ev_deadline_soc | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | patch does not parse (IndentationError) |
| task_2_ev_urgent_power | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (IndentationError) |
| task_3_battery_soc_floor | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (SyntaxError) |
| task_4_import_limit | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (IndentationError) |
| task_5_export_limit | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (IndentationError) |
| task_6_voltage_response | False / True | False / False | LLM | 2 | Y/Y/N/Y/N/N | parses and runs, does not repair (2.50 vs expected 2.0x) |
| task_7_line_loading_response | False / True | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (IndentationError) |
| task_8_flex_deadline | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (SyntaxError) |
| task_9_overcharge_spike | False / False | False / **True** | deterministic | 2 | N/N/N/Y/Y/? | does not parse (IndentationError) |
| task_10_NEG (negative control) | False / True | False / **True** | deterministic | 2 | N/N/N/Y/Y/Y | does not parse (IndentationError) |

**Headline: 0 of 9 measured repairs in BOTH arms** (pre-registered threshold
>= 7/9 not met, reported either way). LLM arm used **20 calls total**
(1 pre-flight + 1 coder call per cell - the loop stopped after one iteration on
each cell because it declared success), **0 backend errors**, product path
authenticated (model digest `poolside/laguna-xs-2.1`).

**Findings from the rearm (both A-side):**
1. The real-code path's LLM output is **syntactically invalid Python in 9 of 10
   cells** (IndentationError/SyntaxError on parse), so the coder falls back to
   the deterministic vocabulary path on those cells - the rearm changed nothing
   about the 0/9 outcome but produced a sharper diagnosis: the model's
   real-code generations do not parse.
2. The loop's acceptance path still claims success on 9 of 10 LLM-arm cells
   whose final patches do not parse - the same class as the deterministic arm's
   remaining false positives: the loop does not apply the same
   syntax/behaviour validity check the driver does. Driver criteria (a)-(f)
   remain the acceptance of record and reject 10/10 in both arms.

**Paper consequence unchanged:** the code-repair claim stays "scaffolded, not
yet demonstrated"; both arms published unpooled.

## Recommendation

Do not put any code-repair number in the paper from this run. The pipeline
needs (1) a task-aware issue->function mapping, (2) a Coder that emits a
minimal in-place patch, and (3) an Executor that runs the patched controller
and a Verifier that rejects absent execution. All three are A's; the benchmark
harness, detectors, and criteria are proven and will re-run unchanged once
those land. The paper's "scaffolded, not yet demonstrated" wording therefore
stays correct.
