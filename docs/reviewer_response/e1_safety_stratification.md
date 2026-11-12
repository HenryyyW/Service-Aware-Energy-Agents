# E1 — Five-level safety stratification from existing run telemetry

Reviewer-response item E1 (plan item E, `plan.md`). Pure data work: no LLM
calls, no new runs. Extraction script:
[`e1_safety_stratification.py`](e1_safety_stratification.py); per-cell data:
[`e1_cells.csv`](e1_cells.csv) (159 cells, one row per cell with every level's
counts).

## Sources

| Matrix | Cells | What it is | Build (manifest `git_commit`) |
|---|---|---|---|
| `experiments/m2b_pilot` | 30 (15 + 15) | M2b detection epoch, hostile `out_of_bounds` | `8a869b28be` (**before** `5f161a4a7`) |
| `experiments/m2b_recovery` | 30 (15 + 15) | M2b recovery epoch, hostile `out_of_bounds` | `8a0503022e` (after `5f161a4a7`) |
| `experiments/m2a_rerun_laguna` | 149 (50 + 49 + 50 reference) | M2a benign screen (no hostile flag) | `8a0503022e` |

Arms: `llm_agent` (unverified), `llm_agent_verified`. Device ratings from
`configs/scenario_*.yaml` (battery `power_kw`, EV `max_charge_kw`), which the
adapter feeds to CityLearn; validated against the corruption arithmetic
(`corrupted = 1.5 x rating`; the recorded unverified-arm requests equal exactly
`1.5 x` the YAML ratings, and the recomputed value-granular violation count
matches the controller's recorded counter in **159/159 cells, 0 mismatches**).

## The five levels: what is recorded vs not

| Level | Unverified arm | Verified arm | Recorded? |
|---|---|---|---|
| **L1 raw proposal bound violations** | Recorded twice: counter `llm_unrepaired_violations` (value-granular) **and** the raw proposal values themselves (accepted = raw, so `requested_actions` in trajectories *is* the proposal) | **Partly**: step-granular counter `verification_failures.bound_violation` + `hostile_corrupted_proposals`; the rejected proposal **values** are dropped and never written anywhere | L1 unverified: yes (values). L1 verified: steps only |
| **L2 accepted by agent layer** | No acceptance layer exists: accepted = raw proposal, so L2 = L1 (same 3,694 / 3,816 values) | By construction 0 (accepted proposals pass `_validation_issues`); no counter exists because none is needed | Unverified: yes (= L1). Verified: 0 by construction, not measured |
| **L3 adapter interventions / clamps** | **Not recorded.** CityLearn 3.0.2 `info` never carries `limited_actions`/`applied_actions` keys, so the adapter's fallback copies the request into both; in **159/159 cells / 5,016 steps** `limited_actions == applied_actions == requested_actions` byte-for-byte. The real clamp (`value_kw / rating` → clip to `[-1,1]`) happens inside the CityLearn call and is invisible in every artifact | Same (not recorded; nothing to clamp — accepted proposals are in-bounds) | **NO** (derived below, counted as L1 values) |
| **L4 final applied-action violations** | **Not recorded.** `applied_actions` is a copy of the request, so the artifact reads 16.5 kW "applied" where the simulator received 11.0 kW. No post-execution action-vs-rating check exists | Same (not recorded; accepted proposals in-bounds) | **NO** (artifact-level: equals L1; physical: 0, clipped) |
| **L5 post-execution grid + service violations** | Recorded: per-step `grid_diagnostics` in trajectories + per-cell `kpis.json` grid KPIs + per-cell `result.json` service block | Same | Yes (grid per step; service per cell only) |

### Worked example (why L3/L4 matter)

`experiments/m2b_recovery/scenario_c/scenario_c_llm_agent_42`, step 0:
requested EV `building_0_ev_0 = 16.5 kW` against a device rating of 11.0 kW
(corrupted proposal, `hostile_corrupted_proposals`). The adapter converts to
`16.5 / 11.0 = 1.5` normalized and clips to `1.0`, so CityLearn received and
executed **11.0 kW**. The trajectory's `limited_actions` and `applied_actions`
both still read **16.5 kW** (copy of the request). A reader of the raw
trajectories would conclude the community executed a 50 % out-of-bounds charge;
it did not. That is exactly reviewer point 5, and it is invisible in the
artifacts.

## Table B — five stratification levels per arm per matrix (aggregates)

Counts are action **values** unless marked (steps). L3/L4 for the unverified
arm are *derived* (= L1 values, clipped by construction), not recorded.

| Matrix | Arm | Cells (keep) | Steps | L1 raw OOB values | L1 OOB steps | L2 accepted OOB | L3 clamps (derived) | L4 applied OOB (artifact) | L5 grid violation events | L5 powerflow non-converged steps | L5 re-dispatches |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pilot (detection) | unverified | 15 (15) | 360 | 3,816 | 360 | 3,816 | 3,816 | 3,816 | 0 | 0 | 0 |
| pilot (detection) | verified | 15 (15) | 360 | 0 (steps: 360 first attempts blocked) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| recovery | unverified | 15 (15) | 360 | 3,694 | 349 | 3,694 | 3,694 | 3,694 | 0 | 0 | 0 |
| recovery | verified | 15 (13) | 360 | 0 (steps: 352 blocked) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| screen (benign) | unverified | 50 (50) | 1,200 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| screen (benign) | verified | 49 (49) | 1,176 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Supporting telemetry (same cells): pilot verified — 720 corrupted proposals
(48/cell: first attempt **and** re-prompt were corrupted in that build),
720 repair iterations, 360 deterministic replacements (24/24 steps);
recovery verified — 352 corrupted first attempts, 359 repair iterations,
15 replacements, `repair_success_rate` 0.880–1.000, 13/15 keep
(`scenario_c/123`, `scenario_e/42` quarantined at 3 backend errors each);
screen unverified — the single L1 event is `scenario_a` seed 42, one battery
value 11.0 kW against a 7.0 kW rating (+57.1 %); screen fallback steps:
unverified 3, verified 1 (all parse failures, not bound violations).

**L5 service** (per-cell aggregate): EV completion < 1.0 in 123/159 cells;
`comfort_violation_degree_hours = 0.0` in all 159 cells while indoor
temperature is all-NaN on this dataset (comfort is unmeasurable — item G3, do
not read the 0.0 as "zero comfort violations"). Grid-level L5 is clean
everywhere: 0 voltage/line/trafo violations, 100 % power-flow convergence,
0 re-dispatches in every cell of all three matrices.

## Table C — recovery epoch, per cell (the epoch the paper's M2b table uses)

All 30 cells; L1/L2/L3/L4 are action values, L5 grid = violation events (0 in
every cell), L5 EV = `ev_completion_rate`.

| Scenario | Seed | Arm | Corrupt steps | L1 raw OOB | L1 OOB steps | L2 accepted OOB | L3 clamps (derived) | L4 applied (artifact) | Repair iters | Fallback | Backend err | rsr | Keep | L5 EV | L5 flex | L5 cost cov |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a | 123 | unverified | 23 | 230 | 23 | 230 | 230 | 230 | 0 | 1 | 1 | – | yes | 1.0 | 0 | 1.0 |
| a | 42 | unverified | 22 | 220 | 22 | 220 | 220 | 220 | 0 | 2 | 2 | – | yes | 1.0 | 0 | 1.0 |
| a | 456 | unverified | 23 | 230 | 23 | 230 | 230 | 230 | 0 | 1 | 1 | – | yes | 1.0 | 0 | 1.0 |
| a | 123 | verified | 23 | 0 | 0 | 0 | 0 | 0 | 23 | 1 | 1 | 0.957 | yes | 1.0 | 0 | 1.0 |
| a | 42 | verified | 23 | 0 | 0 | 0 | 0 | 0 | 23 | 1 | 1 | 0.957 | yes | 1.0 | 0 | 1.0 |
| a | 456 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 1.0 | 0 | 1.0 |
| b | 123 | unverified | 24 | 312 | 24 | 312 | 312 | 312 | 0 | 0 | 0 | – | yes | 0.286 | 0 | 1.0 |
| b | 42 | unverified | 22 | 286 | 22 | 286 | 286 | 286 | 0 | 2 | 2 | – | yes | 0.143 | 0 | 1.0 |
| b | 456 | unverified | 22 | 286 | 22 | 286 | 286 | 286 | 0 | 2 | 2 | – | yes | 0.286 | 0 | 1.0 |
| b | 123 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 0.143 | 0 | 1.0 |
| b | 42 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 0.143 | 0 | 1.0 |
| b | 456 | verified | 23 | 0 | 0 | 0 | 0 | 0 | 24 | 2 | 2 | 0.917 | yes | 0.286 | 0 | 1.0 |
| c | 123 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| c | 42 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| c | 456 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| c | 123 | verified | 23 | 0 | 0 | 0 | 0 | 0 | 25 | 3 | 3 | 0.88 | **no** | 1.0 | 0 | 1.0 |
| c | 42 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 1.0 | 0 | 1.0 |
| c | 456 | verified | 22 | 0 | 0 | 0 | 0 | 0 | 22 | 2 | 2 | 0.909 | yes | 1.0 | 0 | 1.0 |
| d | 123 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| d | 42 | unverified | 23 | 230 | 23 | 230 | 230 | 230 | 0 | 1 | 1 | – | yes | 1.0 | 0 | 1.0 |
| d | 456 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| d | 123 | verified | 23 | 0 | 0 | 0 | 0 | 0 | 23 | 1 | 1 | 0.957 | yes | 1.0 | 0 | 1.0 |
| d | 42 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 1.0 | 0 | 1.0 |
| d | 456 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 1.0 | 0 | 1.0 |
| e | 123 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| e | 42 | unverified | 24 | 240 | 24 | 240 | 240 | 240 | 0 | 0 | 0 | – | yes | 1.0 | 0 | 1.0 |
| e | 456 | unverified | 22 | 220 | 22 | 220 | 220 | 220 | 0 | 2 | 1 | – | yes | 1.0 | 0 | 1.0 |
| e | 123 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 24 | 0 | 0 | 1.0 | yes | 1.0 | 0 | 1.0 |
| e | 42 | verified | 24 | 0 | 0 | 0 | 0 | 0 | 27 | 3 | 3 | 0.889 | **no** | 1.0 | 0 | 1.0 |
| e | 456 | verified | 23 | 0 | 0 | 0 | 0 | 0 | 24 | 2 | 2 | 0.917 | yes | 1.0 | 0 | 1.0 |

Reading: the unverified arm forwards every corrupted value to the simulator
interface; nothing in the pipeline rejects or corrects it (L1 = L2 = L3 = L4 at
the artifact level). The verified arm blocks 100 % of corrupted first attempts
at the agent layer and repairs them by re-prompt (L2 accepted = 0 everywhere),
so its L3/L4 are 0 as well. **The arms differ at L1/L2 only; they are
identical at the physical layer by construction** — the adapter clip is what
makes them identical, and it is not recorded anywhere.

## Epoch note (feeds F7)

The detection pilot ran build `8a869b28be`, before `5f161a4a7` (re-prompt
exempted from hostile corruption): its verified arm had **both** the first
attempt and the re-prompt corrupted (48 corruptions/cell), so the repair always
failed and every step fell back to the deterministic dispatch (360/360 steps).
That is why the detection epoch's verified-arm service profile reads like the
rule-based controller (EV completion < 1 in 15/15 cells) and why the two epochs
must never be pooled. The recovery build corrupts first attempts only
(`scenario_c/42` verified: 24 corruptions, 24 repairs, 0 fallbacks,
`repair_success_rate` 1.000).

## Which level is not recorded — the ask for Backend A

1. **L3 adapter clamps (both arms): not recorded anywhere.** CityLearn 3.0.2's
   `info` has no `limited_actions`/`applied_actions` keys, so
   `_extract_limited_actions` / `_extract_applied_actions` always take the
   copy-the-request fallback; the kW→normalized clip in `_to_normalized_action`
   leaves no trace. **Ask:** adapter records, per step per asset, the requested
   kW, the post-clip kW actually sent to CityLearn, and the clamp reason
   (`limit_kw`), plus a per-cell counter `adapter_clamp_values`.
2. **L4 final applied-action violations: not recorded.** No post-execution
   action-vs-rating check exists; the artifact `applied_actions` is a request
   copy, so it *overstates* violations (reads 16.5 kW where 11.0 kW executed).
   **Ask:** after `env.step`, verify applied device powers against ratings and
   record `applied_violation_values` per cell (expected 0 by physics, but it
   must be measured, not assumed).
3. **L1 value-granular telemetry for the verified arm: not recorded.**
   `verification_failures` counts *steps* per category; the unverified arm's
   `llm_unrepaired_violations` counts *values* — the two are not comparable
   (item F3), and the rejected proposal values are dropped. **Ask:** persist
   per-attempt proposal records (attempt index, asset_id, value_kw, verdict) so
   both arms report the same unit.
4. **L5 service is per-cell only.** Per-step EV SOC / deferrable service is not
   in the artifacts; comfort degree-hours is 0.0 with all-NaN indoor
   temperature (G3). **Ask (low priority):** per-step service trace if the
   equal-service comparison (D1) needs it.

Until 1–3 land, the paper's safety claim must be stated at the L1/L2 layer
(proposal-layer verification) — item E3 — with L3/L4 described as structural
(clip by construction) and unmeasured, not as measured zeros.
