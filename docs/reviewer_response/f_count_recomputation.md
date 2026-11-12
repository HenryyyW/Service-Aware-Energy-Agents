# F-count recomputation: claim -> source -> manifest-backed value

Reviewer-response items F4/F5/F6 (+F7 counts from the E1 telemetry). Pure data
work: every number below is recounted from run artifacts on disk today
(2026-11-09), counting **run-id directories** (the run id encodes the true
controller), never `result.json`'s `controller_type` field (see finding F-LABEL
below). Commands are reproducible; the per-cell extraction behind F7 is
[`e1_cells.csv`](e1_cells.csv) / [`e1_safety_stratification.py`](e1_safety_stratification.py).

## Method

```bash
# per-matrix, per-scenario, per-controller run counts (result.json present)
python3 - <<'EOF'
import os, json, re
pat = re.compile(r"^scenario_([a-e])_(.+)_(\d+)$")
for m in ["matrix_full", "matrix_full_postfix", "matrix_p2p", "m52_benchmark",
          "matrix_d_rerun", "matrix_d_rerun_lmp", "matrix_d_rerun_p2p",
          "m2a_rerun_laguna", "m2b_recovery", "m2b_pilot"]:
    base = f"experiments/{m}"
    tot = {}
    for s in sorted(os.listdir(base)):
        sd = f"{base}/{s}"
        if not os.path.isdir(sd): continue
        for c in sorted(os.listdir(sd)):
            mm = pat.match(c)
            if mm and os.path.isfile(f"{sd}/{c}/result.json"):
                tot[mm.group(2)] = tot.get(mm.group(2), 0) + 1
    print(m, sum(tot.values()), tot)
EOF
```

## Counts table

| # | Paper claim (current text) | Source | Manifest-backed value | Verdict / correct phrasing |
|---|---|---|---|---|
| F4 | "150-cell screen (5 scenarios x 2 LLM arms x 10 seeds)" (§2.3/§3) | `experiments/m2a_rerun_laguna` | 149 manifests on disk: `llm_agent` 50 + `llm_agent_verified` 49 + `multi_agent` 50. `5x2x10 = 100` LLM cells, **not 150**; 150 = 100 LLM + 50 reference | **Arithmetic wrong as phrased.** Correct: "a 150-cell screen planned as 100 LLM-arm cells (5 scenarios x 2 arms x 10 seeds) + 50 `multi_agent` reference cells; 149 landed (99 usable LLM-arm + 50 reference), with `scenario_d_llm_agent_verified_1234` quarantined (FAV 0.958, 1/24 backend-error-degraded steps)". Also fix the label: the 50 reference cells are `multi_agent` deterministic-scaffold runs, not a separate reference controller |
| F5 | "zero across the 160 paired runs" (§4.3 P2P, A/B/C/E) | `matrix_full_postfix` + `matrix_p2p`, A/B/C/E only | 200 pairs: 4 scenarios x 5 controllers x 10 seeds; per controller 40 pairs each (centralized, mpc, multi_agent, rl, rule_based) | **Paper wrong: 200, not 160.** `160 = 4x4x10` has no manifest backing — no controller is excluded; RL runs are present 10+10 in every A/B/C/E scenario (internal type `rl_single`). Correct phrasing: "200 paired runs (A/B/C/E x 5 controllers x 10 seeds)" |
| F6 | "All 50 runs per controller" (§4.3 Scenario E text + tab:aggressive caption) | scenario-E manifests in `matrix_full_postfix`, `matrix_p2p`, `m52_benchmark` | Per regime matrix, scenario E = **50 total = 10 per controller** (5 controllers x 10 seeds); across the three regime legs (pool_tou, p2p, lmp) that is **30 runs per controller**. The aggressive set is the scenario-E block of the LMP leg (`m52_benchmark`), which carries the aggressive failure config (EV severity 1.0, grid limit 0.95) while its A/B/C/D rows use the standard config | **Paper wrong twice over.** (a) No matrix has 50 runs per controller — the paper conflated a matrix total (50) with a per-controller count. Correct: "10 runs per controller per pricing regime; 30 per controller across the three regimes (pool TOU, P2P, LMP)". (b) The "aggressive stress test" is a within-matrix asymmetry of the LMP leg, not a standalone stress matrix — disclose that A/B/C/D in the LMP leg use the standard config. (c) **RL is present** in the stress data (10 runs per regime) — the aggressive table's four rows silently omit `rl`; add the row or state the exclusion |
| F-LABEL | (no paper claim — counting-method trap found during this recount) | all four B-axis matrices + screen | `result.json` `controller_type` is mislabeled for 3 of 5 controllers in every landed matrix: `centralized` runs are recorded as `rule_based`, `multi_agent` as `llm_agent`, `rl` as `rl_single` (750 B-axis runs + 22/50 screen `multi_agent` cells) | **Any count or per-arm analysis grouped by `controller_type` is wrong.** Count/group by run-id directory (the run id carries the true controller). Ask QA to fix the field or drop it from analyses; the screen's KPI pairing already used directory names |
| F-DUP | (no paper claim — double-count trap) | `matrix_full` vs `matrix_full_postfix` vs `matrix_d_rerun{,_lmp,_p2p}` | `matrix_full` and `matrix_full_postfix` both hold 250 runs; they are byte-identical for 200 cells and differ only in the scenario-D block (pre-fix 40.51 USD vs post-fix 190.78 USD for `rule_based`/42 — postfix D rows equal `matrix_d_rerun`). Summing all matrix dirs naively gives 1,150; the distinct legs are 250 pool_tou (postfix) + 250 p2p + 250 lmp = **750**, plus the D reruns already contained in postfix | **State the leg of record:** pool_tou = `matrix_full_postfix` (post-fix D); `matrix_full` keeps the pre-fix D rows; `matrix_d_rerun*` duplicates postfix's D block — do not add them to the 750 |
| F7 | "Table 7: 18/360 fallback, 442.62 USD both epochs" | `e1_cells.csv` (from `m2b_pilot` / `m2b_recovery` manifests + trajectories) | Detection epoch (`m2b_pilot`, build `8a869b28be`): unverified 360/360 corrupted steps, 3,816 OOB values, 0 fallback; verified 720 corrupted proposals (48/cell — first attempt **and** re-prompt corrupted), 720 repair iterations, **360/360 steps ended in deterministic replacement**. Recovery epoch (`m2b_recovery`, build `8a0503022e`): unverified 349 corrupted steps, 3,694 OOB values, 11 fallback steps (10 backend errors); verified 352 corrupted first attempts, 359 repair iterations, 15 fallback steps, 13/15 keep (C/123, E/42 quarantined) | **"18/360" and the identical 442.62 are backed by neither epoch.** Rebuild Table 7 per epoch from these counts: detection's verified arm ran the deterministic fallback at every step (pre-`5f161a4a7` re-prompts were corrupted too), which is why its service profile reads like `rule_based` (EV completion < 1 in 15/15 cells) and its cost column is not comparable to the recovery epoch's |

## Cross-checks

- Prior audit `docs/count_audit/counts_table.md` rows 2/3/4 are independently
  confirmed by this recount (200 pairs; 149/150 manifests; 10 per controller per
  scenario-E block). Rows to add there: F-LABEL, F-DUP, and the F7 per-epoch
  counts above.
- E1 cross-reference: the L1 value counts feeding F7 (3,816 / 3,694 unverified;
  verified-arm step counts) are recomputed from trajectories x device ratings and
  match the controller counters in 159/159 cells (0 mismatches) — see
  `e1_safety_stratification.py` output.

## What this means for the paper edit (F1-F7 wording, landing after B/A verdicts)

- F4: cite 149/150 with the quarantine note (aggressive re-scoping: the M2a
  claims are aggregate nulls; one quarantined cell cannot flip them).
- F5: 200 paired runs; name the leg of record (`matrix_full_postfix`).
- F6: "10 per controller per regime, 30 across the three regimes"; disclose the
  LMP-leg scenario-E aggressive-config asymmetry; add the `rl` row or state its
  exclusion.
- F7: rebuild Table 7 per epoch from `e1_cells.csv` (never pool the epochs;
  their fallback semantics differ by a code fix, `5f161a4a7`).
- F3 (unit definition): the unverified arm's violation counter counts **values**
  (`llm_unrepaired_violations` = 240 for a 24-step cell = 10 values x 24 steps),
  the verified arm's counts **steps** (`verification_failures.bound_violation` =
  24). Define one unit (step-level event rate) in the paper and recompute both.
