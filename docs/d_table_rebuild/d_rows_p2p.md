# Scenario D — P2P regression check (post-fix)

Paired per-seed (scenario D, controller, seed) comparison of the new
pool-TOU and P2P runs.

| Controller | Δ cost P2P−TOU (USD) | Δ peak (kW) | Δ EV | community volume (kWh) |
|---|---|---|---|---|
| rule_based | +9.58 ± 0.91 | +0.00 ± 0.00 | +0.0000 | 312.1 ± 2.7 |
| multi_agent | -24.10 ± 0.00 | +0.00 ± 0.00 | +0.0000 | 252.1 ± 0.0 |
| centralized | +12.08 ± 1.04 | +0.00 ± 0.00 | +0.0000 | 283.8 ± 3.3 |
| mpc | +29.06 ± 4.63 | +0.00 ± 0.00 | +0.0000 | 320.4 ± 8.9 |
| rl | +34.02 ± 0.91 | +0.00 ± 0.00 | +0.0000 | 520.4 ± 12.7 |
