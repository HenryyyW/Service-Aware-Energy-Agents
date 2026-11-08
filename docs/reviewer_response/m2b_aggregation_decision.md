# M2b Table 7 rebuild: aggregation decision + traceable values

Reviewer-response F7. QA's merged audit (`docs/count_audit/table7_rebuilt.md`,
origin/main `b732dbd3b6` line) proved the paper's Table 7 detection column
(fallback 18/360, cost 442.62) is a copy of the recovery column, and that
"10.33 unsafe acceptance" and "repair success mean 0.974" trace to no
aggregation. This doc records the **aggregation decision** and every value the
rebuilt table uses, recomputed independently from run artifacts
(`manifest.json` + `result.json`) with the same keep rule QA used.

## Aggregation decision (binding for the paper)

- **Headline basis = KEEP cells under the final keep rule** (`llm_backend_errors
  <= 2` AND `llm_calls >= total_steps` AND telemetry recorded), **per epoch,
  never pooled**:
  - detection epoch (`experiments/m2b_pilot`): **15/15 keep** (0 backend errors
    in every cell).
  - recovery epoch (`experiments/m2b_recovery`): **13/15 keep** after the
    user-approved re-run of the three quarantined cells was applied **in place**
    (`scenario_c_llm_agent_verified_42` re-run 0 errors, promoted; C/123 and
    E/42 re-run still 3 errors, quarantined). Quarantined cells are published
    per cell (docs/m2b_recovery/summary.md) and excluded from headline stats.
- **The all-15 unfiltered values are published alongside** so the quarantined
  cells cannot silently drive a headline number, and so both bases are auditable.
- Paired values (unsafe-acceptance aggregate, wins, cost) use the **keep-13
  paired set** in the recovery epoch; unpaired all-15 numbers are given in the
  "unfiltered" columns below.
- `first_attempt_validity` is 0.0 by design under `out_of_bounds` (the corruptor
  breaks every first attempt) and is not a keep-condition — unchanged.

## Correction to QA's provenance (verified against the archive)

`/tmp/opencode/m2b_recovery_quarantine_round2` holds the **round-1 original
(degraded) copies** of the three cells (each 3 backend errors, 3 fallbacks,
rsr 0.857/0.880/0.880), not the round-2 re-runs — the on-disk matrix carries the
in-place re-run (C/42 now 0 errors). QA's "recovery = all-15 with q2 substituted"
reconstruction therefore re-degraded C/42; the on-disk truth is: recovery
verified all-15 = fallback 15/360, cost mean 442.11; keep-13 = 9/312, 440.85.
The paper's 18/360 and 442.62 trace to neither — they came from mixing the
archived degraded cell back in. Rebuilt from the on-disk state below.

## Traceable values (recomputed 2026-11-09)

| Metric | Detection (15/15 keep) | Recovery (13 keep) | Recovery unfiltered (15) | Reference (15 `multi_agent`, M2b seeds) |
|---|---|---|---|---|
| Unsafe acceptance, unverified (per step) | 10.60 | 10.30 (keep-paired) | 10.26 | — |
| Unsafe acceptance, verified (per step) | 0.0000 | 0.0000 | 0.0000 | — |
| Per-cell unverified rate range | 10.0–13.0 | 9.17–13.0 | same | — |
| Paired directional wins | 15/15 | 13/13 | 15/15 | — |
| Bound-violation detections (per cell) | 24/24 | 24/24 | 24/24 | — |
| Repair success rate (verified) | 0.500 derived (720 iterations − 360 fallbacks; recorded field null in this build) | 0.909–1.000, mean 0.970 | 0.880–1.000, mean 0.959 | — |
| Fallback steps (verified) | 360/360 | 9/312 | 15/360 | — |
| Cost (USD, mean) verified | 203.44 | 440.85 | 442.11 | 65.52 |
| Cost (USD, mean) unverified | 440.79 | 437.15 (keep-paired) | 439.54 | — |
| Peak (kW, mean) verified | — | 75.14 | — | 12.03 |
| Peak (kW, mean) unverified | — | 74.88 | — | — |

Sign test on the 13 recovery pairs: two-sided p = 2.4e-4 (exact, reference only).

## What was untraceable and is replaced

- Table detection column "18/360" → raw **360/360** (every step ended on the
  deterministic replacement: the detection build corrupted re-prompts too).
- Table detection cost "442.62" → raw **203.44** (verified arm mean; per-cell
  171.04–301.69).
- "10.33" unsafe acceptance (both columns) → **10.60** detection / **10.30**
  recovery keep-paired (10.26 unfiltered).
- "0.880–1.000 (mean 0.974)" → **0.909–1.000, mean 0.970** on the 13 keep cells
  (the 0.880 floor belongs to the two quarantined cells, published per cell).
  The old mean 0.974 traced to no cell set.
- Reference cost "67.13" → **65.52** (mean over the 15 reused `multi_agent`
  reference cells at the M2b seeds; the old value traces to nothing on disk).
  Reference peak 12.03 is confirmed.
- Detection "not measurable" repair success → **0.500 derived**, with the
  derivation stated (the recorded field is null in that build).

Honesty upside (as the PM noted): the detection epoch's 360/360 fallback is
exactly what the paper's own prose predicted — the corrected table strengthens
the narrative rather than weakening it.
