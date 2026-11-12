# Code-repair benchmark: analysis contract

Owner: Research (analysis). Producer: Backend A (execution). Status: **waiting
for the matrix** — `experiments/m2b_code_repair/` does not exist yet, so there
is nothing to analyse. This doc fixes what the analysis will consume so the
harness records it on the first run (the E1 lesson: an unrecorded level cannot
be analysed afterwards).

The task list and pre-registered criteria are on origin/main at
`experiments/m2b_code_repair_tasks.md` (amended: tasks 1-9 + 7b; LLM tasks
4/5/8 with seeds 42/123 and ≤3 iterations × 24 steps = 432-call ceiling;
deterministic tasks 1/2/3/6/7/9 = 1296 deterministic runs; functional criteria
(a)-(f); the deterministic_safety comparator runs on every task with 5-level
stratification).

## What each cell must record (analysis contract)

Per cell (one directory per task × seed × arm), the run already writes
`manifest.json`, `result.json`, `kpis.json`, `trajectories.jsonl`. For this
benchmark the harness must additionally emit `repair_audit.json` (or the same
fields under a `code_repair` key inside `manifest.json`):

| Field | Meaning |
|---|---|
| `task_id`, `arm`, `seed`, `diagnostic` | cell identity |
| `parses` | criterion (a) |
| `ran_clean_under_three_diagnostics` | (b): no NameError/AttributeError under {no diag, 1.08 pu, 0.92 pu} |
| `baseline_patch_differs` | (c): patched output ≠ baseline under the violating diagnostic |
| `diff_classifier_cosmetic` | (d): True = rejected as cosmetic |
| `verification_harness_accepts` | (e): no masking |
| `service_preserved` | (f): EV completion ≥ baseline and flex-load completion ≥ baseline where applicable (per-metric values welcome) |
| `llm_calls`, `llm_backend_errors`, `repair_iterations`, `repair_success_rate` | M2b-style agent telemetry for the keep rule |
| `stratification` (L1..L5 counts) | for the deterministic_safety comparator cells |
| `git_commit`, `git_dirty`, `scenario_config_sha256` | provenance (already standard) |

## Acceptance of record

`manifest.json` records, per cell: `keep` and `verdict` computed from the
driver-level criteria (a)-(f) only, plus `loop_claimed_success` (the pipeline's
own success flag) beside them as a **recorded claim, never the verdict** - the
first two runs proved the loop's flag untrustworthy (it claims success on
patches that crash), so no analysis or paper number may use it as acceptance.

## Analysis script

`docs/reviewer_response/code_repair_analysis.py` (read-only, no LLM calls):

- locates `experiments/m2b_code_repair/`; if absent, exits 0 printing
  "matrix not found — nothing to analyse" (no fabricated numbers);
- enumerates cells by run-id directory name (never `controller_type` — the
  standing counting trap);
- applies the M2b keep rule to LLM cells (`llm_backend_errors <= 2` AND
  `llm_calls >= iterations` AND telemetry recorded);
- reads criteria (a)-(f) from the recorded fields and reports any criterion
  that is **not recorded** as such rather than assuming it;
- aggregates per task and per arm: pass rate vs the pre-registered threshold
  (≥7/9 measured tasks), LLM call accounting vs the 432 ceiling, per-cell
  error/fallback shares, quarantine list;
- writes `docs/reviewer_response/code_repair_results.md` + `.json` with the
  per-task table and the five-level stratification summary for the
  deterministic_safety comparator.

Until cells exist the script only prints the not-found line; it has been run
against the current tree and exits 0.
