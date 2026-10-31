# RL policy provenance – LMP regime

**Finding**
QA clone contains 5 untracked files in `experiments/reference/rl_policy/lmp_scenario_{a..e}.json`.
These files were not produced by the Research Engineer on the current PC.

**Evidence**
- `n_states`: 138  (126 base + 12 LMP price buckets)
- `episodes`: 60
- `seed`: 0
- Matches Plan 4.3 specification: *“rl: retrain per LMP scenario (state price bucket from LMP, 60 episodes, seed 0): 5 policies ~10 min each; publish to experiments/reference/rl_policy/lmp_<scenario>.json”*

**Implication**
- The 138-state encoder is not in `main`.
- M1 matrix used the tracked base 126-state policies; no deviation from current main.
- The stray files should be tracked fixtures with a reproducible training script and regen recipe for the 138-state encoder.

**Action**
Pending: add tracked training script + encoder + Makefile target to regenerate `lmp_scenario_*.json`. Until then, keep files untracked and document here.
