# Code-repair benchmark scope (task list for approval before any run)

Reviewer-response item A1 / user decision D-A. Gate condition is now met: the
coder AST-transformation fix (`94f0161fd`, merged into origin/main via
`373d415ce`) restored all 34 `_add_*` transformation bodies, and the regression
test `d42a3f623` proves patched output now differs from baseline under a
voltage-violating diagnostic (1.08 pu -> `BATTERY_CHARGE` 5.0 becomes 2.5). A
benchmark on comment-only patches would prove nothing; this list targets real,
test-detectable defects.

## Authorized envelope (user decision D-A, verbatim constraints)

- Model `poolside/laguna-xs-2.1`, provider NVIDIA NIM (`https://integrate.api.nvidia.com/v1`).
- Count **<= 10 seeded repair tasks x <= 3 iterations each**.
- Same hostile-flag discipline and keep rule as M2b.
- Single matrix directory `experiments/m2b_code_repair/`.
- No other model, no other provider, no other output directory.

## Task list (10 tasks; defects seeded into copies of the rule-based controller)

Each task ships as: a seeded defect (a documented, minimal source diff against
the shipped controller), a failing test file (the defect's detector), the full
regression suite, and a before/after 24-step simulation run. Target functions
are the real methods in `src/controllers/__init__.py`; expected repair
vocabulary is the coder's restored `_add_*` transformations
(`src/agents/coder.py`).

| # | Task | Seeded defect (target function) | Failing test detects | Expected repair vocabulary |
|---|---|---|---|---|
| 1 | `ev_deadline_soc` | `_control_ev` stops at a fixed SOC proxy instead of the departure-time requirement | departure SOC < required SOC in the sandbox sim | `_add_precise_time_to_departure` |
| 2 | `ev_urgent_power` | `_control_ev` charges at a flat rate regardless of remaining energy vs time | urgent-deadline cases miss required SOC | `_add_max_power_for_urgent_deadline`, `_add_ev_prioritization_by_departure` |
| 3 | `battery_soc_floor` | `_control_battery` discharges below `soc_min` | SOC floor violated in unit test | `_add_dynamic_soc_reserve`, `_add_emergency_reserve` |
| 4 | `pv_export_overshoot` | battery charges from excess PV without the export-limit check | export kW exceeds the community limit | `_add_export_limit_enforcement`, `_add_battery_charge_for_excess_pv` |
| 5 | `import_limit_curtailment` | no proportional curtailment when net demand exceeds the import limit | import kW exceeds the limit | `_add_import_limit_enforcement`, `_add_proportional_curtailment` |
| 6 | `voltage_response` | no reaction to voltage diagnostics (rise under PV export) | no voltage-triggered reduction in the response test | `_add_voltage_monitoring_and_reduction`, `_add_voltage_triggered_load_reduction` |
| 7 | `line_loading_check` | no line/transformer loading check in the limit path | loading check absent from `_apply_grid_limits` output | `_add_line_loading_monitoring`, `_add_transformer_loading_check` |
| 8 | `flex_deadline` | flexible loads scheduled so cycles miss their window | completion rate 0 in the sandbox sim | `_add_earliest_deadline_first`, `_add_deadline_tracking` |
| 9 | `peak_spike` | all chargers at max simultaneously (peak spike) | community peak exceeds the configured cap | `_add_proportional_power_allocation`, `_add_action_magnitude_reduction` |
| 10 | `NEG_tariff_lookup` (negative control) | off-peak/on-peak tariff lookup inverted | cost series wrong under TOU | **none** - outside the transformation vocabulary; an honest failure is the expected and correct outcome |

Task 10 is the boundary probe: it must NOT be repaired, and the pipeline must
report the failure rather than manufacture a pass. Tasks 1-9 are the measured
set; task 10 is reported separately.

## Protocol per task

1. **Seed**: apply the documented defect diff to a copy of the controller; record `git commit`, `git_dirty`, config SHA-256 in the cell manifest (M2b manifest hygiene).
2. **Detect**: run the failing test + the full suite; record which tests fail (the defect's signature) and which pass (the no-regression set).
3. **Repair**: the repair loop (Planner -> Coder -> Executor(sandbox: unit tests + quick sim) -> Verifier) with **at most 3 iterations**; the repair prompt carries the failing-test output, not a solution hint.
4. **Before/after**: full 24-step simulation (scenario A pool TOU) of the broken-baseline controller and each repaired controller; record cost, peak, EV completion, flexible-load completion, grid violations, member cost coverage.
5. **Keep rule (identical to M2b)**: cell kept iff `llm_backend_errors <= 2` AND `llm_calls >= iterations` AND telemetry recorded; quarantined cells (endpoint degradation) are published per cell and excluded from headline stats; epochs are never pooled.

## Success and functional-regression criteria (pre-registered)

- **Task success** requires all of: (i) every previously failing test passes; (ii) every previously passing test still passes (no regression); (iii) in the before/after simulation, no new grid violation and EV completion / member cost coverage / flexible-load completion not worse than the **broken baseline**; (iv) cost and peak within a pre-set tolerance of the broken baseline (the repair resolves the defect without silently changing the objective - it is not required to beat the original controller).
- **Pilot headline**: success rate over tasks 1-9, reported with exact counts; pre-registered demonstration threshold **>= 7 of 9** (reported either way; below threshold the paper keeps the "pilot, not demonstrated" framing and publishes the per-task outcomes).
- **Negative control (task 10)**: pass only if the pipeline honestly reports non-repair; a manufactured pass is a pipeline failure and is reported as such.

## Count arithmetic (LLM calls, inside the authorized envelope)

- 10 tasks x <= 3 iterations. Each iteration makes at least one Coder call; a Planner call precedes it where the loop plans, so the worst case is 10 x 3 x 2 = **<= 60 LLM calls**, the best case 10 (one iteration per task). All sandbox executions (unit tests, quick simulation, the before/after simulations) are deterministic and consume no LLM calls.
- One queue, `--workers 3`, `--timeout` as in the M2b queues; pre-flight 1-token probe first; skip-existing resume by run id.

## Pilot caveats (stated in the results, M2b style)

- Single model, single prompt version, single 24-step horizon; results are specific to that combination.
- Seeded defects are minimal and within the coder's transformation vocabulary by construction; they measure the repair path, not general bug-finding.
- The reference for held-harmless comparison is the **broken baseline** (not the original controller); beating the original is out of scope.
- Endpoint degradation is a reported result, not a silence: per-cell error/fallback shares published, quarantined cells excluded from the headline.

## Deliverables on approval

- `experiments/m2b_code_repair/` (single matrix dir; manifests per cell).
- `docs/reviewer_response/code_repair_benchmark_results.md` + `.json` (per-task table, success rate vs the >= 7/9 threshold, negative-control outcome, per-cell error/fallback shares, keep/quarantine lists).
- Paper update only on the user's word: the A2 "scaffolded, not demonstrated" sentence becomes a pilot-demonstrated claim with this benchmark's numbers and caveats.

**This document is the pre-run task list; nothing runs until the Project Partner approves it.**
