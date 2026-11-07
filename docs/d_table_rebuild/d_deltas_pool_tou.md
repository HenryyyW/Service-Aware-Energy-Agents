# Scenario D — Table `tab:deltas` rows (pool TOU, post-fix)

Paired per-seed deltas vs. `rule_based`, n=10 seeds; Holm within
scenario D over the controller comparisons.

| Scenario | Controller | Δ cost (USD) | Δ peak (kW) | p_Holm |
|---|---|---|---|---|
| D | multi_agent | -78.56 ± 0.03 | -16.59 ± 0.00 | < 0.0001 |
| D | centralized | +3.99 ± 0.24 | +1.43 ± 0.00 | < 0.0001 |
| D | mpc | +242.63 ± 18.93 | +29.44 ± 0.00 | < 0.0001 |
| D | rl | +374.34 ± 14.41 | +49.28 ± 3.37 | < 0.0001 |
