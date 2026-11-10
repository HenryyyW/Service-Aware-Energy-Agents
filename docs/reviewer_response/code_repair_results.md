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

## Deterministic-arm validation against origin/main 7980673a8f (A's crash-tracking fix)

Re-ran the deterministic comparator (10 cells, zero LLM calls) after A's
dynamic-path crash tracking (`controller_crashed` / `crash_error` in the
sandbox; the verifier treats a crashed controller as absent execution).
Result: **7/10 loop/driver agreement** (was 0/10): the seven cells whose
patches crash (tasks 1-5, 8, 9) now get `loop_claimed_success=False`, matching
the driver rejection. The three remaining disagreements are a different,
narrower class: patches that **execute cleanly but do not repair the defect**
(tasks 6, 7 - the patch runs, the behaviour is unchanged; task 10 - the
negative control, correctly unrepaired). Those still get
`loop_claimed_success=True` because the loop's verifier checks "no violations
in the sandbox experiment" rather than "the defect is fixed" - the probe
config produces zero grid violations in both the broken and patched runs, so
an unrepaired patch reads as a resolution. That is an acceptance-path design
gap, not a crash.

Also validated on this main: the configured `AGENT_BACKEND` path builds the
NIM backend (no TypeError any more), but it still carries `api_key=None`
because the registry maps the present-but-None `dashscope_api_key` before
`nvidia_api_key` - so the LLM arm still needs the explicit injection until
that mapping order is fixed (reported to A with the reproduction; the driver
now prefers the product path and falls back with the reason recorded).

## Decision-grade re-run on origin/main 1ed5a2193 (A's real-code path merged, envelope <= 5 iterations)

The authoritative run, on the code the paper cites: `origin/main` (A's real-code
path with the safe applier + test-driven prompt + loop feedback, max-iterations
5, registry key fix, and the acceptance-path crash tracking). Both arms under
the user's envelope; the LLM arm through the **configured product path**
(`AGENT_BACKEND=api:poolside/laguna-xs-2.1`, NIM key from the key store,
`DASHSCOPE_API_KEY` unset, 1-token pre-flight per cell) with no injection.

| Task | deterministic: iters / keep / loop | LLM: iters / keep / loop | LLM patched outcome |
|---|---|---|---|
| task_1_ev_deadline_soc | 5 / False / False | 1 / False / **True** | does not parse (IndentationError) |
| task_2_ev_urgent_power | 5 / False / False | 1 / False / **True** | does not parse (IndentationError) |
| task_3_battery_soc_floor | 5 / False / False | 1 / False / **True** | does not parse (SyntaxError: unmatched ')') |
| task_4_import_limit | 5 / False / False | 1 / False / **True** | does not parse (SyntaxError: invalid syntax) |
| task_5_export_limit | 5 / False / False | 1 / False / **True** | does not parse (SyntaxError: '(' never closed) |
| task_6_voltage_response | 1 / False / **True** | 1 / False / **True** | does not parse (IndentationError) |
| task_7_line_loading_response | 1 / False / **True** | 1 / False / **True** | does not parse (IndentationError) |
| task_8_flex_deadline | 5 / False / False | 1 / False / **True** | does not parse (SyntaxError) |
| task_9_overcharge_spike | 5 / False / False | 1 / False / **True** | does not parse (IndentationError) |
| task_10_NEG (negative control) | 1 / False / **True** | 1 / False / **True** | does not parse (IndentationError) |

**Headline: 0 of 9 measured repairs in BOTH arms** (pre-registered threshold
>= 7/9 not met; reported either way). **The A2 sentence therefore stays
"scaffolded, not yet demonstrated"** - this run does not move it.

**Per-iteration story (as requested):**
- Deterministic arm: the seven crash-class cells ran the full 5-iteration
  budget (5 patches each, all deterministic-vocabulary, none behaviour-changing)
  and ended with `loop_claimed_success=False` - the acceptance fix works for
  that class. The three clean-but-unrepaired cells (6, 7, 10) still get
  `loop_claimed_success=True` after 1 iteration because the loop's verifier
  checks "no grid violations in the sandbox experiment" rather than "the defect
  is fixed".
- LLM arm: 20 calls, 0 backend errors, model digest `poolside/laguna-xs-2.1`,
  every cell authenticated through the configured path. Every cell stopped
  after **one** iteration because the loop declared success - so the <= 5
  budget and the test-driven failure-history feedback were never exercised. The
  LLM's real-code output **does not parse in 10 of 10 cells** (IndentationError
  / SyntaxError), so the coder fell back to the deterministic vocabulary and
  the final patch is again invalid or ineffective. The loop then claims success
  on 10/10 cells whose patches do not parse.

**Two A-side findings, sharper than before:**
1. The real-code path's model output is syntactically invalid Python in
   **10 of 10** cells (was 9/10 in the pre-merge run) - the binding defect is
   the model's code generation, not the applier.
2. The acceptance path claims success on patches that do not parse - the loop
   applies neither the driver's syntax check nor a defect-level check. Driver
   criteria (a)-(f) remain the acceptance of record and reject 10/10 in both
   arms.

Both arms published unpooled; all cells carry per-iteration records, per-cell
L1/L5 telemetry and `loop_claimed_success` beside the verdict.

## Recommendation

Do not put any code-repair number in the paper from this run. The pipeline
needs (1) a task-aware issue->function mapping, (2) a Coder that emits a
minimal in-place patch, and (3) an Executor that runs the patched controller
and a Verifier that rejects absent execution. All three are A's; the benchmark
harness, detectors, and criteria are proven and will re-run unchanged once
those land. The paper's "scaffolded, not yet demonstrated" wording therefore
stays correct.

## Rebased on origin/main (160893e71) with the 2-tuple detector adapter - deterministic verification for the decisive re-run

**What was wrong (mechanism correction, verified by the PM and reproduced on
the merged tree):** the adapter returned a 3-tuple `(ok, detail, None)` while
`VerifierAgent._run_detector` unpacks `ok, detail = detector_fn(cls, cfg)`, so
every in-loop detector call failed closed with "too many values to unpack
(expected 2)". The 10/10 `loop_claimed_success=False` reported from that branch
was therefore fail-closed rejection, not a working detector check - safe for the
all-failing deterministic arm, but it would also have rejected a genuine LLM
repair.

**Fix:** `_harness_detector` returns the 2-tuple `(ok, detail)` (A's unified
convention, now merged on main). Verified directly: broken controller ->
`(False, "requested import 5.0 kW vs limit 3 kW")`, pristine controller ->
`(True, "requested import 3.0 kW vs limit 3 kW")` - the detector genuinely
discriminates.

**Full deterministic re-run on the rebased branch (10 cells, zero LLM calls,
budget 5): `loop_claimed_success=False` on all 10 cells, 0/9 measured repairs,
negative control `keep=True`, zero "too many values to unpack" occurrences in
the run log - the in-loop detector check now runs for real.** Independently
merge-checked by the Project Partner on their tree with the same expectation.

**Labelling (binding):** the negative control's `keep=True` is a **valid
honest-failure cell** - the pipeline correctly does not repair a defect outside
the transformation vocabulary - and is **not a counted repair**. Repair counts
are read from the 9 measured tasks only; this applies to every section of this
document.

The LLM arm is held until A's remaining diff-application defect is fixed; the
decisive two-arm re-run (deterministic comparator first, then the LLM arm via
the configured product path, <= 10 tasks x <= 5 iterations, both arms unpooled,
`loop_claimed_success` beside every verdict, threshold >= 7/9 reported either
way) runs on the PM's GO.


## LLM-arm probe after A's conversion fixes (main 160893e71) - the blocker moved to the model's diff format

A's conversion fixes (diff look-ahead, double-newline) are merged. Verified on
the merged tree with the 2-tuple detector wired in:

- Deterministic comparator (10 cells, 0 LLM calls, budget 5): 10/10
  loop/driver agreement, `loop_claimed_success=False` on all 10, 0/9 measured
  repairs, negative control `keep=True` (valid honest-failure cell).
- LLM real-code probe, 3 tasks, 6 calls total (in-envelope): the model still
  does not emit a well-formed unified diff, so `changes=0` and the notes read
  "LLM REAL-CODE PATH FAILED: no valid unified diff produced":
  - task_4_import_limit: 10 `-` lines vs 41 `+` lines (unbalanced hunk), 5
    no-op identical pairs, the "changes" are comment-text edits (e.g. appending
    "(in hours)" to a comment) - parser rejects.
  - task_6_voltage_response: 0 `-` lines vs 84 `+` lines - additions only.
  - task_8_flex_deadline: 0 `-` lines vs 6 `+` lines - additions only.

So the binding defect is no longer the diff application: it is the model's
output format. A's applier accepts strict unified diffs; this model does not
produce them at this prompt/temperature. The full LLM arm is HELD: running it
would spend ~60 calls recording the same parse failures (the exact case the PM
excluded). Recommended next step (A's decision): either change the output
contract to function replacement (the coder already has `_replace_function`),
or re-prompt for strict `@@ -a,b +c,d @@` hunks with balanced -/+ counts.

## Decisive two-arm re-run on origin/main (A's full fix line merged) - the run that decides the A2 sentence

Base: `origin/main` as of this run (A's full real-code fix line: re-indent,
de-indent, double-newline, diff look-ahead, 300s timeouts, detector-path and
arity unification; plus the merged detector wiring and the truthful
`wiring_workaround` field). Envelope: <= 10 tasks x <= 5 iterations,
`poolside/laguna-xs-2.1` on NVIDIA NIM via the **configured product path**
(`AGENT_BACKEND=api:poolside/laguna-xs-2.1`, NIM key from the key store,
`DASHSCOPE_API_KEY` unset, 1-token pre-flight per cell, `timeout_s=300`),
deterministic comparator first, both arms unpooled.

**Deterministic comparator (10 cells, 0 LLM calls): 10/10 loop/driver
agreement** - every cell used the full 5-iteration budget,
`loop_claimed_success=False` on all 10, the 9 measured cells keep=False with
`f_service_preserved=False` (the in-loop detector check runs the real defect
signature and honestly fails the unrepaired patches), negative control
`keep=True` = **valid honest-failure cell (honest non-repair), not a counted
repair**.

**LLM arm (60 calls, 0 backend errors): 10/10 loop/driver agreement, 0/9
measured repairs, negative control `keep=True`, every cell used the full
5-iteration budget with the accumulated failure history.** One cell (task_8)
recorded a single LLM change that did not repair the defect; the other nine
produced no applicable change (the model's unified diffs remain structurally
unbalanced - e.g. 12 `-` vs 330 `+` lines - so the syntax rejection drops
them and each iteration is a no-op the detector rejects).

**Claim decision: 0 of 9 measured repairs in BOTH arms - the pre-registered
threshold >= 7/9 is not met - the paper's A2 sentence stays "scaffolded, not
yet demonstrated".** Reported either way; both arms unpooled; acceptance of
record = driver criteria (a)-(f); `loop_claimed_success` recorded beside every
verdict and agreeing with the driver verdict in both arms (10/10).

**Labelling correction applied to the earlier sections:** the LLM-arm section
produced on the `e7434ae` base reported "Changes: 0 on every iteration" as the
model's ceiling; that base still contained the diff re-indent corruption (the
model's diff was mangled before apply), so that section is a **corruption
artifact**, not evidence about the model. The decisive numbers are the ones
above, produced on the fully-fixed base. The negative control's `keep=True` is
labelled throughout as a valid honest-failure cell, not a counted repair.

## Decisive two-arm re-run v3 on A's latest tree (applier fix + function-replacement primary path) - mechanism now real, blocker precisely located

Tree: `origin/fix/llm-real-code-path` merged with `origin/main` (A's
offset-aware multi-hunk applier `a9b32b633`, diff-format validation
`bc0744bed`, strengthened prompt `7160f596a`, function-replacement primary path
`4bb1add9a`, additions/deletions-only rejection `8def38842`). Harness changes on
this branch: the detector adapter resolves the concrete controller class from
the verifier's abstract `BaseController` hand-off (the in-loop detector now runs
for real), and the negative-control detector uses the same orientation as the
measured tasks (passes only when the unrepairable defect is fixed), so the loop
cannot claim success on a no-op patch there.

**Deterministic comparator (10 cells, 0 LLM calls, budget 5): 10/10 loop/driver
agreement, `loop_claimed_success=False` on all 10, 0/9 measured repairs,
negative control `keep=True` = valid honest-failure cell, and zero
"Can't instantiate abstract class" events in the log - for the first time the
loop's verdict is produced by a genuinely running in-loop detector check (the
driver criteria (a)-(f), the acceptance of record, agree).**

**LLM arm (60 calls, 0 backend errors, budget 5 fully used per cell): 0/9
measured repairs, negative control `keep=True`, 10/10 agreement, zero
instantiation/unpack errors.** One cell (task_8) remains the only cell ever to
record an LLM-produced change; none repaired.

**Located blocker (A-side, reproduced standalone):**
`_generate_llm_changes_real_code` calls
`self._parse_llm_response_function_replacement(...)` (src/agents/llm_coder.py
line 185) but that method is **not defined** on `LLMCoderAgent` - the
function-replacement primary path raises
`AttributeError: 'LLMCoderAgent' object has no attribute
'_parse_llm_response_function_replacement'` on every attempt, which the coder
records as a failed iteration and returns None (no silent fallback), so
`changes=0` and the patch is a no-op the detector rejects. Standalone probe on
task_4: 4,273 prompt / 2,236 completion tokens spent, then the AttributeError.

**Claim decision: 0 of 9 measured repairs in BOTH arms - threshold >= 7/9 not
met - A2 stays "scaffolded, not yet demonstrated"** (reported either way; both
arms unpooled; acceptance of record = driver criteria (a)-(f); the loop's own
verdict now agrees with the driver in both arms, 10/10).

## In-envelope probe on main `648f7bf0e` (A's function-replacement contract) - NO conversion; exact blocker located; full arm NOT spent (per the PM sequence)

Tree: `origin/main` `648f7bf0e` (A's function-replacement primary path
`4bb1add9a` + the missing parser methods `4bbcf33be`, class-selection fix
`c21d55e3f`, additions/deletions-only rejection `8def38842`), which already
carries my two harness deltas via the merged detector wiring (concrete-class
resolution, negative-control orientation).

**Probe 1 - 3 tasks (task_1, task_4, task_8), budget 5, pre-flight on: 7 backend
calls (1 pre-flight + 2 per task: primary + diff fallback), 28,388 prompt /
6,363 completion tokens.** No task converted: task_4 and task_1 both ended
`changes=0` with notes "LLM REAL-CODE PATH FAILED: no valid function replacement
or unified diff produced"; task_8 was in-flight when the probe output was
truncated, with the identical primary-then-fallback trace. Per the PM sequence
(no conversion -> do NOT spend the full arm), the full two-arm run was NOT
executed.

**Probes 2+3 - single task (task_4), pre-flight off, transparent recording
backend: 2 + 2 backend calls, 8,766/2,420 and 8,762/2,210 tokens.** Exact raw
shapes (reproducible with `experiments/probe_llm_output_shape.py`):

1. **Function-replacement response (primary, 8,080 chars):** THREE
   `# FILE: controllers/__init__.py` / `# FUNCTION: <name>` marker pairs
   (`_control_ev`, `_control_battery`, `_apply_grid_limits`) followed by
   **unfenced** code, and **ZERO backtick fences in the entire response**
   (`fence variants found: []`). The parser's `code_match` requires a
   ```` ```python\n...``` ```` block, so it can never match: the failure message
   "Could not extract function replacement format (missing FILE/FUNCTION/code)"
   is misleading - FILE and FUNCTION both matched; the missing element is the
   fence. A second defect in the same path: the model returns THREE function
   replacements in one response while the parser extracts one.
2. **Unified-diff fallback response (529 chars):** a fenced ```diff with a
   single ADDITIONS-ONLY hunk whose added lines are comments
   ("# ... reduction logic") - correctly rejected by A's additions-only
   validation (`8def38842`) and cosmetic anyway. So the fallback cannot convert
   either.

**Exact blocker (A-side):** the function-replacement parser requires a
```python fenced block; the model now emits the `# FILE:`/`# FUNCTION:` markers
(A's strengthened prompt partially works) but no fence, and emits multiple
replacements per response. The contract must either accept marker-delimited
UNFENCED blocks (with multi-replacement support), or the prompt must actually
produce fences.

**Envelope accounting (honest):** the probe used 11 backend calls in total
(7 + 2 + 2) against the <= 6-call probe guidance - the per-task cost turned out
to be 2 calls (primary + fallback), which the <= 6 figure did not anticipate,
and 2 extra single-task calls were spent to capture the exact raw shapes for
A's repro rather than an inference. The full-arm budget (<= 10 tasks x <= 5
iterations, `poolside/laguna-xs-2.1` on NIM, code-repair benchmark only) was
NOT touched this round; deterministic-arm runs stay LLM-free.

**Claim decision: no conversion in the probe -> the full two-arm re-run was not
spent -> the pre-registered threshold >= 7/9 is untested this round and the
paper's A2 sentence stays "scaffolded, not yet demonstrated"** (reported either
way; both arms unpooled; acceptance of record = driver criteria (a)-(f) with
`loop_claimed_success` beside every verdict - unchanged from the last decisive
run: deterministic 10/10, LLM 0/9).

## Probe f4 on A's `29c9b22c2` (unfenced + multi-replacement handling) - 2/3 convert, NEW failure shape, no full-arm spend (re-decide with A)

A shipped two further fixes after the f3 run: `c64c35d1d` (multi-hunk applier +
diff validator for insertions) and `29c9b22c2` (handles UNFENCED
marker-delimited responses and MULTIPLE replacements per response - the exact
dispatch from the earlier probe). Probe tree: `origin/fix/llm-real-code-path`
(`29c9b22c2`) merged with `origin/main` (src byte-identical to A's tip).

**Zero-cost parser verification (committed as
`experiments/verify_function_replacement_parser.py`, no LLM calls, exit 0):**
fenced/unfenced single replacements apply (col-0 and indent-4 code);
multi-replacement responses with genuinely-modified functions apply ALL of
them; two open shapes are reported, not asserted: (i) a modified replacement
plus a byte-identical echo of another function is REJECTED wholesale
("Function replacement did not modify the code for X"), and (ii) markers
OUTSIDE the fenced blocks are rejected ("Could not extract function
replacement format (missing FILE/FUNCTION/code)") because the fenced path
requires the markers inside the block.

**Live probe (3 tasks, 3 backend calls - one per task on the same-response
fallback): 2/3 convert.**
- `task_1_ev_deadline_soc`: UNFENCED response, 2 marker pairs, BOTH
  replacements applied (`changes=2`, notes "function replacement (2
  functions)"), detector passes (EV SOC 0.8002 vs target 0.800). The new
  unfenced multi-replacement capability works live.
- `task_4_import_limit`: fenced block with the marker inside, `changes=1`,
  detector passes (import 3.0 kW vs limit 3 kW).
- `task_8_flex_deadline`: FAILS on the new shape - 3 fenced blocks with the
  3 marker pairs OUTSIDE the fences -> the fenced path finds no markers inside
  any block -> "missing FILE/FUNCTION/code" -> `changes=0`. task_8 has now
  failed to convert on both trees (different reasons).

**Decision: no demonstrated gain over the f3 run (5/9 on `b014d421c`) - the
full LLM arm was NOT spent; re-decide with A.** Two concrete asks for A, both
evidence-backed: (1) associate each marker pair with the FOLLOWING fenced
block when the block itself carries no markers (the task_8 shape); (2) skip
unchanged echoes and apply the modified replacements instead of rejecting the
whole response (the echo shape - under `b014d421c` the first block was applied
and the rest ignored, so this is a regression risk if the model echoes).

**Envelope accounting:** probe f4 = 3 backend calls; cumulative probe usage 17
calls; NO new full-arm spend this round (the f3 record - deterministic 10/10,
LLM 5/9, threshold >= 7/9 not met, A2 "scaffolded, not yet demonstrated" -
stands).
