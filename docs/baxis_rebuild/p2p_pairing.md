# P2P vs pool TOU pairing (aggregate + member redistribution)

Paired per-seed (p2p − pool_tou) per scenario/controller, n=10.
"Redistribution" = mean |Δ per-member all-in bill| over the five members
(energy_sharing.per_member[].actual_total_bill). Volume = P2P community
traded volume (energy_sharing.total_community_volume_kwh).

| Scenario | Controller | Δ aggregate cost (USD) | aggregate identical | mean redistribution (USD) | Δ Gini(all-in bills) | P2P volume (kWh) | dispatch identical |
|---|---|---|---|---|---|---|---|
| A | rule_based | +4.61 ± 1.66 | 0/10 | 1.623 | +0.0139 | 77.7 | 10/10 |
| A | multi_agent | +6.81 ± 2.02 | 0/10 | 1.905 | +0.0058 | 76.6 | 10/10 |
| A | centralized | +4.36 ± 0.90 | 0/10 | 1.563 | +0.0135 | 65.9 | 10/10 |
| A | mpc | +8.14 ± 4.13 | 0/10 | 2.767 | +0.0132 | 80.3 | 10/10 |
| A | rl | +7.54 ± 0.28 | 0/10 | 2.304 | +0.0014 | 128.0 | 10/10 |
| B | rule_based | +7.09 ± 1.44 | 0/10 | 2.072 | +0.0063 | 72.0 | 10/10 |
| B | multi_agent | +4.63 ± 1.07 | 0/10 | 1.265 | -0.0057 | 65.5 | 10/10 |
| B | centralized | +4.55 ± 1.44 | 0/10 | 1.396 | +0.0025 | 67.0 | 10/10 |
| B | mpc | +15.22 ± 4.16 | 0/10 | 3.233 | -0.0163 | 67.8 | 10/10 |
| B | rl | +6.26 ± 0.23 | 0/10 | 1.970 | -0.0009 | 106.3 | 10/10 |
| C | rule_based | -0.96 ± 1.44 | 0/10 | 1.456 | +0.0220 | 85.1 | 10/10 |
| C | multi_agent | -10.59 ± 11.25 | 0/10 | 4.033 | +0.0291 | 123.2 | 10/10 |
| C | centralized | -1.66 ± 2.11 | 0/10 | 1.693 | +0.0270 | 82.4 | 10/10 |
| C | mpc | -9.41 ± 9.52 | 0/10 | 4.859 | +0.0297 | 133.5 | 10/10 |
| C | rl | -50.63 ± 4.66 | 0/10 | 10.126 | -0.0065 | 100.1 | 10/10 |
| D | rule_based | +4.61 ± 1.66 | 0/10 | 1.623 | +0.0139 | 77.7 | 10/10 |
| D | multi_agent | +6.81 ± 2.02 | 0/10 | 1.905 | +0.0058 | 76.6 | 10/10 |
| D | centralized | +4.36 ± 0.90 | 0/10 | 1.563 | +0.0135 | 65.9 | 10/10 |
| D | mpc | +8.14 ± 4.13 | 0/10 | 2.767 | +0.0132 | 80.3 | 10/10 |
| D | rl | +7.54 ± 0.28 | 0/10 | 2.304 | +0.0014 | 128.0 | 10/10 |
| E | rule_based | +4.60 ± 1.65 | 0/10 | 1.624 | +0.0137 | 76.7 | 10/10 |
| E | multi_agent | +6.28 ± 1.87 | 0/10 | 1.806 | +0.0060 | 74.8 | 10/10 |
| E | centralized | +4.39 ± 0.89 | 0/10 | 1.560 | +0.0134 | 65.1 | 10/10 |
| E | mpc | +8.14 ± 4.13 | 0/10 | 2.767 | +0.0132 | 80.3 | 10/10 |
| E | rl | +7.54 ± 0.28 | 0/10 | 2.304 | +0.0014 | 128.0 | 10/10 |
