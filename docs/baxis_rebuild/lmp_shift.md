# LMP regime shift - scenario A (and dispatch identity)

TOU(pool) vs LMP per controller, scenario A, paired per-seed (n=10):

| Controller | TOU cost | LMP cost | Δ (LMP-TOU) | Δ EV completion | dispatch identical (traj hash) |
|---|---|---|---|---|---|
| rule_based | 191.96 | 183.42 | -8.54 | +0.000 | 10/10 |
| multi_agent | 275.48 | 249.58 | -25.91 | +0.000 | 10/10 |
| centralized | 175.83 | 165.15 | -10.68 | +0.000 | 10/10 |
| mpc | 371.22 | 309.10 | -62.12 | -0.369 | 0/10 |
| rl | 476.28 | 325.49 | -150.79 | -0.271 | 0/10 |
