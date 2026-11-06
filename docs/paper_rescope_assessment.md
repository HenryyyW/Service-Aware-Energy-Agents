# Paper re-scope assessment — post PV-fix, post dataset restoration (2026-11-07)

**Standalone verdict for the arXiv paper.** Author: Research Engineer
(af498092). Every claim below was verified against the run artifacts on
2026-11-07 (health scan of all 750 queue runs + forensic read of
`experiments/results/scenario_c/`).

## TL;DR

The paper's "all 0 or null" symptom is **confined to `experiments/results/`** —
a debug-artifact directory from Backend B's PV-fix iteration (Nov 3 23:17 –
Nov 4 02:06, 13/28 runs `git_dirty=True`, mixed code eras). It does **not**
affect the paper's new data source: the **750-run B-axis queue** (completed
2026-11-04, health-verified 2026-11-07) is clean end-to-end and supersedes
every pre-fix matrix. All paper tables can be rebuilt from it; only M2a
absolutes and the aggressive stress test need (optional) re-runs. **No clean
re-run of the 750 is needed.**

## 1. Data inventory (health-verified 2026-11-07)

| Dataset | Location | Runs | Physics era | Trustworthy |
|---|---|---|---:|---|
| B-axis queue (pool_tou) | `experiments/matrix_full` | 250 (10 seeds) | fixed | **YES** |
| B-axis queue (p2p) | `experiments/matrix_p2p` | 250 (10 seeds) | fixed | **YES** |
| B-axis queue (LMP, incl. RL) | `experiments/m52_benchmark` | 250 (10 seeds) | fixed | **YES** |
| Backend B debug session | `experiments/results/scenario_{a..e}` | 28 in scenario_c | mixed eras | **NO** |
| Old M5.2 LMP matrix | (old checkout) @ b152037 | 100 | broken PV (14.5 kWh) | superseded |
| M2a real-LLM screen | `experiments/phase2_llm/m2a_screen` | 45 | broken PV; arms co-calibrated | partial |
| Aggressive stress | `m52_aggressive` | 20 | broken PV | superseded |
| Phase-1 release artifact | `Shared/paper_artifacts/matrix` @ 035a52f | 125+50 | real data, different dataset era/window | historical only |

Health scan of the 750 (all three matrices): **0 zero-cost runs, 0 zero-PV
runs, 0 missing manifests, `git_dirty=False` throughout**, commits
{`0911a6f5`, `210d35d5`, `0e584b74`}; PV range 1036.0–1914.8 kWh (all
scenarios within sane CF bands), cost range −24.7 (scenario_c export credit,
known caveat) to 188.5 USD.

## 2. Per-table verdicts

| Paper table | Old source | Verdict | New source |
|---|---|---|---|
| T2/T3 cost/peak/service (pool TOU) | 035a52f release (125, 5 seeds) | **REBUILD** — release stays as historical provenance only; its dataset era (lowercase-named series, April window) is not the current tree | `matrix_full` (250, 10 seeds) |
| LMP benchmark + RL row | m52 100 @ b152037 | **REBUILD** — old runs carry broken PV; the limitation "RL excluded from LMP" is now RESOLVED (rl runs with 138-state policies) | `m52_benchmark` (250, 10 seeds) |
| P2P regime (new RQ3 section) | none | **NEW** | `matrix_p2p` (250) paired with `matrix_full` (same seeds) |
| Paired deltas vs rule_based | old | **REBUILD** — n=10, Holm-corrected; headline (scenario_a multi_agent): −18.11 ± 0.03 USD, p_Holm < 1e-4; all controller deltas significant in all scenarios | computed from the three matrices |
| M2a real-LLM KPI table | 45 runs (broken PV) | **RE-SCOPE** — absolute KPIs are dead; the null-result gate verdict SURVIVES (all arms on the same broken tree: 0 unrepaired violations, 0 repair iterations, fallback-share difference 0.6 pp ≪ 10 pp) — report as gate verdict only, or re-run 45 runs (~45 min) for absolutes | gate verdict, or re-run |
| Aggressive stress (§5.10) | m52_aggressive (20) | **SUPERSEDED** — re-run 20 runs (~20 min) only if the section stays | optional |
| CI-tightening claim | none | **NEW** — median CI half-width ratio 5→10 seeds = **0.539** (≈46 % tighter, better than the 0.715 prediction) | computed |

## 3. The 251 skipped-existing runs — verdict

**No clean re-run of the queue is needed.** The 251 skips = 249 runs produced
by the queue's first leg + the B0-re smoke + the LMP smoke; all sit inside the
750 verified healthy today (see §1). The broken fields the PM found
(`total_cost=0.0`, empty agent section) live in `experiments/results/` — a
directory the queue never wrote to (it ran from a clean worktree at
0911a6f/0e584b7 with dedicated output dirs).

## 4. PV reconciliation: 1914.8 vs 14528.1 vs 1455.3 vs 14.5

Four (code, data) combinations — each with a verified mechanism; **no live
synthesis bug remains on main**:

| PV (kWh/wk, scenario_c) | Code state | Data state | Mechanism |
|---|---|---|---|
| 14.5 | pre-fix (any era) | cache has `Building_1.csv` | name-lookup gap (`building_0.csv` requested) → silent dummy fallback — removed by 4ab9e10 (hard failure) |
| 1455.3 | 035a52f release machine | lowercase real dataset | real data, episode window @ row 2266 (early April) |
| 14528.1 | 89b36d7 (×1000 nominal) | tiny synthesized series | unit overshoot ×1000 (reverted in b7efcb9) |
| **1914.8** | **4ab9e10/56dcb0c (kW nominal)** | **canonical cache dataset, rows 0–168** | **CORRECT — first-principles exact (expected 1914.8 = measured, +0.00 %)** |

- The `0 → 165.5 → 14528.1` same-seed swing in `results/` = Backend B toggling
  code paths with a dirty tree mid-debug (13/28 runs `git_dirty=True`); two
  runs even carry `commit=035a52f3` manifests with broken-tree values, so those
  manifests' commit fields are unreliable for the debug session.
- The "×7.6 gap" (14528.1 vs 1914.8) is not a unit or definition mismatch: the
  two values come from different (code, data) eras — ×1000 nominal × tiny
  synthesized series vs kW nominal × canonical stock series. Only 1914.8 (and
  the per-scenario values in the 750) is usable in the paper.

## 5. kpis.json vs result.json (results/ debug runs only)

In `results/`, `kpis.json` holds real pandapower values while `result.json`
energy/agent fields are zero: those runs executed with the shared checkout's
**uncommitted metrics refactor half-applied** (`src/evaluation/metrics.py`
rewrite + `run_experiment.py` timestep_hours edit on `typing/wip-metrics`),
which broke the result.json aggregation path in that working-tree state; the
queue's clean worktree produced fully populated result.json files (verified:
energy, service, and agent fields across all 750). Action for Backend B: when
landing the metrics refactor, add a test asserting result.json
energy/service/agent fields are non-default for a 24-step run — and do not run
benchmarks from a checkout with uncommitted source changes.

## 6. Action list (owner)

1. **Rebuild paper tables** from the three matrices (user / PM; sources per
   §2 — the summarize scripts operate on the three directories directly).
2. **M2a**: re-scope to gate-verdict-only (recommended — the null result IS the
   finding), or re-run 45 runs on fixed physics (~45 min) for absolutes.
3. **Aggressive**: re-run 20 runs (~20 min) only if §5.10 stays.
4. **Backend B**: result.json-aggregation guard test when the metrics refactor
   lands (see §5).
5. **QA**: package the three matrix directories as a release artifact
   (zip + SHA256SUMS + INDEX.json, same pattern as paper-artifacts-release.zip)
   so the paper pipeline consumes a frozen snapshot.
