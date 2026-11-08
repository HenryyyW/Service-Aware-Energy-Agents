# Table 7 (M2b) rebuilt from raw run artifacts

Recomputed per-cell from result.json controller_config counters:
- detection epoch: experiments/m2b_pilot
- recovery epoch: experiments/m2b_recovery
- re-run cells: /tmp/opencode/m2b_recovery_quarantine_round2
- keep rule: llm_backend_errors <= 2 AND llm_calls >= steps AND telemetry recorded

Headline (see `rows` for full verdicts):
- DETECTION raw: verified fallback 360/360, cost mean 203.44 USD
- RECOVERY raw (15 cells, q2 substituted): fallback 18/360, cost mean 442.62 USD
- RECOVERY keep-13: fallback 9/288, cost mean 439.59 USD

```json
{
 "provenance": {
  "detection_raw": "experiments/m2b_pilot (30 result.json)",
  "recovery_raw": "experiments/m2b_recovery (30 result.json)",
  "recovery_rerun_cells": "3 verified cells in /tmp/opencode/m2b_recovery_quarantine_round2 (scenario_c_llm_agent_verified_{42,123}, scenario_e_llm_agent_verified_42)",
  "paper_recovery_column_reconstruction": "fallback 18/360 and cost 442.62 reproduce EXACTLY as: recovery matrix over ALL 15 verified cells with the round-2 re-run cells substituted (no keep-rule filter on the denominator)"
 },
 "rows": {
  "fallback_steps_verified": {
   "paper_detection": "18/360",
   "paper_recovery": "18/360",
   "raw_detection": "360/360",
   "raw_recovery": "18/360",
   "raw_recovery_keep13": "9/288",
   "verdict": "DETECTION COLUMN UNTRACEABLE: raw detection = 360/360 (every step fell back \u2014 re-prompts were corrupted, matching the paper's own prose); the table's 18/360 for detection is a copy of the recovery column. Recovery 18/360 traces to all-15-cells-with-substitutions."
  },
  "cost_mean_verified": {
   "paper_detection": 442.62,
   "paper_recovery": 442.62,
   "raw_detection": 203.44,
   "raw_recovery": 442.62,
   "raw_recovery_keep13": 439.59,
   "verdict": "DETECTION COLUMN UNTRACEABLE: raw detection verified-arm mean cost = 203.44 USD (per cell 171-301), not 442.62. Recovery 442.62 traces to the substituted 15-cell set."
  },
  "repair_success_rate": {
   "paper_recovery": "0.880-1.000 (mean 0.974)",
   "raw_recovery_keep13": "0.909-1.000 (mean 0.968)",
   "raw_recovery_sub15": "0.857-1.000 (mean 0.949)",
   "verdict": "PARTIALLY UNTRACEABLE: paper mixes the keep-13 mean (~0.97) with an all-15 range (0.88 floor comes from a quarantined cell). State the cell set for both numbers."
  },
  "unsafe_acceptance_per_step": {
   "paper_detection_unverified": 10.33,
   "raw_detection_unverified_mean": 10.6,
   "raw_recovery_unverified_mean": 10.261,
   "verdict": "10.33 does not trace to either epoch's cell-mean (detection = 10.6, recovery = 10.26); per-cell values emitted so Research can locate the intended aggregation."
  },
  "paired_wins": {
   "paper_detection": "12/12",
   "raw_detection": "15/15 (15 cells on disk, all pass keep: the paper's 12/15 pre-rerun bookkeeping does not match the on-disk state)",
   "paper_recovery": "13/13",
   "raw_recovery": "15/15"
  },
  "quarantine": {
   "detection_drop": [],
   "recovery_drop_after_substitution": [
    "scenario_c_llm_agent_verified_123",
    "scenario_c_llm_agent_verified_42",
    "scenario_e_llm_agent_verified_42"
   ]
  }
 }
}
```
