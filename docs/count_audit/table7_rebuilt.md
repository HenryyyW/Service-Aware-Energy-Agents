# Table 7 (M2b) rebuilt from raw run artifacts

Recomputed per-cell from result.json controller_config counters:
- detection epoch: experiments/m2b_pilot
- recovery epoch: experiments/m2b_recovery
- re-run cells: /tmp/opencode/m2b_recovery_quarantine_round2
- keep rule: llm_backend_errors <= 2 AND llm_calls >= steps AND telemetry recorded

Headline (see `rows` for full verdicts):
- DETECTION raw: verified fallback 360/360, cost mean 203.44 USD
- RECOVERY as-run all-15: fallback 15/360, cost mean 442.11 USD
- RECOVERY keep-13: fallback 9/312, cost mean 440.85 USD

```json
{
 "provenance": {
  "detection_raw": "experiments/m2b_pilot (30 result.json)",
  "recovery_raw": "experiments/m2b_recovery (30 result.json)",
  "archive_correction": "/tmp/opencode/m2b_recovery_quarantine_round2 holds the ROUND-1 DEGRADED copies (llm_backend_errors=3, fallback=3, rsr 0.857-0.880 each), NOT round-2 re-runs. The on-disk matrix carries the in-place re-run (C/42: errs=0, fallback=0, rsr=1.000, promoted to keep). Verified by Research against the archive + docs/m2b-recovery-close-out.",
  "untraceable_paper_numbers": "The paper's 18/360 fallback and 442.62 cost trace to NO cell set: not as-run all-15 (15/360), not keep-13 (9/312), and substituting the archived degraded cells re-degrades C/42 (a promoted cell), so that construction is invalid. The detection column (18/360, 442.62) is a copy of the recovery column; the recovery numbers as printed also do not trace."
 },
 "rows": {
  "fallback_steps_verified": {
   "paper_detection": "18/360",
   "paper_recovery": "18/360",
   "raw_detection": "360/360",
   "raw_recovery_as_run_all15": "15/360",
   "raw_recovery_keep13": "9/312",
   "verdict": "DETECTION COLUMN UNTRACEABLE (copy of the recovery column): raw detection = 360/360 \u2014 every step fell back (re-prompts corrupted), matching the paper's own prose. RECOVERY TRACEABLE ONLY AS: as-run all-15 = 15/360 or keep-13 = 9/312. The printed 18/360 traces to no set."
  },
  "cost_mean_verified": {
   "paper_detection": 442.62,
   "paper_recovery": 442.62,
   "raw_detection": 203.44,
   "raw_recovery_as_run_all15": 442.11,
   "raw_recovery_keep13": 440.85,
   "verdict": "DETECTION COLUMN UNTRACEABLE: raw detection verified-arm mean cost = 203.44 USD (per cell 171-301), not 442.62. RECOVERY TRACEABLE ONLY AS keep-13 = 440.85 USD (or as-run all-15 = 442.11); the printed 442.62 traces to no set."
  },
  "cost_reference_multi_agent": {
   "paper": 67.13,
   "partner_corrected": 65.52,
   "computed_m2a_laguna_all_28_cells": 64.47,
   "computed_m2a_laguna_seeds_42_123_456_n7": 65.38,
   "verdict": "UNTRACEABLE ON DISK: 67.13 matches no artifact subset; 65.52 (Partner-corrected) does not reproduce from m2a_rerun_laguna multi_agent 24-step cells either (64.47 over all 28; 65.38 over the 7 cells at M2b seeds 42/123/456 \u2014 only 7 of the expected 15 reference cells exist at the M2b seed set). Research must state the exact reference cell list before this row is citable."
  },
  "repair_success_rate": {
   "paper_recovery": "0.880-1.000 (mean 0.974)",
   "raw_recovery_keep13": "0.909-1.000 (mean 0.970)",
   "verdict": "PAPER RANGE UNTRACEABLE: keep-13 range is 0.909-1.000 (mean 0.970); the 0.880 floor belongs to a degraded round-1 copy in the archive, not to any kept cell. State the cell set."
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
    "scenario_e_llm_agent_verified_42"
   ]
  }
 }
}
```
