| Scenario | Controller | n | total_cost | grid_import_kwh | peak_demand_kw | ev_completion_rate | member_cost_coverage | members_interrupted_count |
|---|---|---|---|---|---|---|---|---|
| scenario_a | centralized | 5 | 349.30 ± 4.38 | 2672.67 ± 27.86 | 42.22 ± 1.25 | 0.18 ± 0.15 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_a | mpc | 5 | 460.34 ± 32.86 | 3629.92 ± 227.44 | 70.96 ± 7.11 | 0.99 ± 0.02 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_a | multi_agent | 5 | 334.06 ± 4.77 | 2497.54 ± 31.64 | 21.29 ± 0.55 | 0.07 ± 0.08 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_a | rule_based | 5 | 349.36 ± 4.76 | 2679.79 ± 31.41 | 41.75 ± 1.92 | 0.18 ± 0.15 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_b | centralized | 5 | 377.01 ± 5.53 | 2835.48 ± 35.45 | 44.68 ± 2.92 | 0.16 ± 0.04 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_b | mpc | 5 | 453.68 ± 18.16 | 3498.91 ± 73.04 | 68.25 ± 10.94 | 0.20 ± 0.06 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_b | multi_agent | 5 | 334.32 ± 4.77 | 2499.44 ± 31.63 | 21.30 ± 0.54 | 0.04 ± 0.04 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_b | rule_based | 5 | 378.27 ± 6.23 | 2847.66 ± 42.69 | 55.60 ± 4.55 | 0.15 ± 0.05 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_c | centralized | 5 | 348.62 ± 4.38 | 2667.75 ± 27.87 | 42.21 ± 1.25 | 0.18 ± 0.15 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_c | mpc | 5 | 465.16 ± 21.87 | 3656.59 ± 192.92 | 70.97 ± 3.03 | 0.98 ± 0.02 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_c | multi_agent | 5 | 333.39 ± 4.77 | 2492.62 ± 31.64 | 21.26 ± 0.58 | 0.07 ± 0.08 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_c | rule_based | 5 | 348.69 ± 4.76 | 2674.87 ± 31.41 | 41.75 ± 1.92 | 0.18 ± 0.15 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_d | centralized | 5 | 349.30 ± 4.38 | 2672.67 ± 27.86 | 42.22 ± 1.25 | 0.18 ± 0.15 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_d | mpc | 5 | 460.34 ± 32.86 | 3629.92 ± 227.44 | 70.96 ± 7.11 | 0.99 ± 0.02 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_d | multi_agent | 5 | 334.06 ± 4.77 | 2497.54 ± 31.64 | 21.29 ± 0.55 | 0.07 ± 0.08 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_d | rule_based | 5 | 349.36 ± 4.76 | 2679.79 ± 31.41 | 41.75 ± 1.92 | 0.18 ± 0.15 | 1.00 ± 0.00 | 0.00 ± 0.00 |
| scenario_e | centralized | 5 | 338.12 ± 3.92 | 2582.20 ± 23.58 | 38.27 ± 1.36 | 0.18 ± 0.14 | 0.80 ± 0.00 | 1.00 ± 0.00 |
| scenario_e | mpc | 5 | 442.64 ± 32.55 | 3503.78 ± 210.25 | 70.63 ± 6.60 | 0.93 ± 0.04 | 0.80 ± 0.00 | 1.00 ± 0.00 |
| scenario_e | multi_agent | 5 | 324.98 ± 4.25 | 2430.90 ± 26.99 | 21.29 ± 0.55 | 0.07 ± 0.08 | 0.80 ± 0.00 | 1.00 ± 0.00 |
| scenario_e | rule_based | 5 | 338.24 ± 4.24 | 2589.04 ± 26.83 | 38.02 ± 2.01 | 0.17 ± 0.15 | 0.80 ± 0.00 | 1.00 ± 0.00 |

Paired deltas vs `multi_agent` (negative cost/import/peak is better):

| Scenario | Controller | n pairs | total_cost | grid_import_kwh | peak_demand_kw | ev_completion_rate | member_cost_coverage | members_interrupted_count |
|---|---|---|---|---|---|---|---|---|
| scenario_a | centralized | 5 | +15.23 ± 0.49 | +175.13 ± 4.57 | +20.93 ± 1.53 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_a | mpc | 5 | +126.28 ± 30.55 | +1132.38 ± 206.21 | +49.67 ± 7.53 | +0.92 ± 0.08 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_a | rule_based | 5 | +15.30 ± 0.03 | +182.25 ± 0.40 | +20.46 ± 2.37 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_b | centralized | 5 | +42.68 ± 3.61 | +336.04 ± 24.76 | +23.38 ± 2.83 | +0.12 ± 0.06 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_b | mpc | 5 | +119.36 ± 15.85 | +999.47 ± 66.73 | +46.96 ± 11.10 | +0.16 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_b | rule_based | 5 | +43.95 ± 3.65 | +348.22 ± 25.78 | +34.30 ± 4.54 | +0.11 ± 0.06 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_c | centralized | 5 | +15.23 ± 0.49 | +175.13 ± 4.57 | +20.95 ± 1.53 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_c | mpc | 5 | +131.77 ± 17.55 | +1163.97 ± 162.87 | +49.71 ± 2.56 | +0.91 ± 0.09 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_c | rule_based | 5 | +15.30 ± 0.03 | +182.25 ± 0.40 | +20.49 ± 2.41 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_d | centralized | 5 | +15.23 ± 0.49 | +175.13 ± 4.57 | +20.93 ± 1.53 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_d | mpc | 5 | +126.28 ± 30.55 | +1132.38 ± 206.21 | +49.67 ± 7.53 | +0.92 ± 0.08 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_d | rule_based | 5 | +15.30 ± 0.03 | +182.25 ± 0.40 | +20.46 ± 2.37 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_e | centralized | 5 | +13.14 ± 0.44 | +151.30 ± 4.09 | +16.98 ± 1.73 | +0.11 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_e | mpc | 5 | +117.66 ± 31.66 | +1072.89 ± 192.85 | +49.34 ± 6.84 | +0.86 ± 0.10 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| scenario_e | rule_based | 5 | +13.26 ± 0.03 | +158.15 ± 0.34 | +16.74 ± 2.46 | +0.10 ± 0.07 | +0.00 ± 0.00 | +0.00 ± 0.00 |

Each cell is mean ± 95% confidence half-width (Student-t, sample std). A paired delta whose interval excludes zero is evidence of a difference for these seeds; it is not yet a paper-level claim.

Paired t-tests vs `multi_agent` (Holm within scenario x metric family):

| Scenario | Comparison | Metric | n | mean delta | t | p | p (Holm) | sig 0.05 |
|---|---|---|---|---|---|---|---|---|
| scenario_a | centralized | total_cost | 5 | +15.23 | 85.60 | 0.0000 | 0.0000 | yes |
| scenario_a | mpc | total_cost | 5 | +126.28 | 11.48 | 0.0003 | 0.0003 | yes |
| scenario_a | rule_based | total_cost | 5 | +15.30 | 1324.63 | 0.0000 | 0.0000 | yes |
| scenario_a | centralized | grid_import_kwh | 5 | +175.13 | 106.34 | 0.0000 | 0.0000 | yes |
| scenario_a | mpc | grid_import_kwh | 5 | +1132.38 | 15.25 | 0.0001 | 0.0001 | yes |
| scenario_a | rule_based | grid_import_kwh | 5 | +182.25 | 1262.53 | 0.0000 | 0.0000 | yes |
| scenario_a | centralized | peak_demand_kw | 5 | +20.93 | 38.00 | 0.0000 | 0.0000 | yes |
| scenario_a | mpc | peak_demand_kw | 5 | +49.67 | 18.31 | 0.0001 | 0.0001 | yes |
| scenario_a | rule_based | peak_demand_kw | 5 | +20.46 | 23.94 | 0.0000 | 0.0000 | yes |
| scenario_a | centralized | ev_completion_rate | 5 | +0.11 | 4.47 | 0.0111 | 0.0221 | yes |
| scenario_a | mpc | ev_completion_rate | 5 | +0.92 | 30.16 | 0.0000 | 0.0000 | yes |
| scenario_a | rule_based | ev_completion_rate | 5 | +0.11 | 4.42 | 0.0115 | 0.0221 | yes |
| scenario_a | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_a | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_a | rule_based | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_a | centralized | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_a | mpc | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_a | rule_based | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_b | centralized | total_cost | 5 | +42.68 | 32.85 | 0.0000 | 0.0000 | yes |
| scenario_b | mpc | total_cost | 5 | +119.36 | 20.91 | 0.0000 | 0.0000 | yes |
| scenario_b | rule_based | total_cost | 5 | +43.95 | 33.43 | 0.0000 | 0.0000 | yes |
| scenario_b | centralized | grid_import_kwh | 5 | +336.04 | 37.68 | 0.0000 | 0.0000 | yes |
| scenario_b | mpc | grid_import_kwh | 5 | +999.47 | 41.58 | 0.0000 | 0.0000 | yes |
| scenario_b | rule_based | grid_import_kwh | 5 | +348.22 | 37.50 | 0.0000 | 0.0000 | yes |
| scenario_b | centralized | peak_demand_kw | 5 | +23.38 | 22.93 | 0.0000 | 0.0001 | yes |
| scenario_b | mpc | peak_demand_kw | 5 | +46.96 | 11.75 | 0.0003 | 0.0003 | yes |
| scenario_b | rule_based | peak_demand_kw | 5 | +34.30 | 20.96 | 0.0000 | 0.0001 | yes |
| scenario_b | centralized | ev_completion_rate | 5 | +0.12 | 5.66 | 0.0048 | 0.0096 | yes |
| scenario_b | mpc | ev_completion_rate | 5 | +0.16 | 6.71 | 0.0026 | 0.0077 | yes |
| scenario_b | rule_based | ev_completion_rate | 5 | +0.11 | 4.74 | 0.0090 | 0.0096 | yes |
| scenario_b | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_b | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_b | rule_based | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_b | centralized | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_b | mpc | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_b | rule_based | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_c | centralized | total_cost | 5 | +15.23 | 85.60 | 0.0000 | 0.0000 | yes |
| scenario_c | mpc | total_cost | 5 | +131.77 | 20.85 | 0.0000 | 0.0000 | yes |
| scenario_c | rule_based | total_cost | 5 | +15.30 | 1324.63 | 0.0000 | 0.0000 | yes |
| scenario_c | centralized | grid_import_kwh | 5 | +175.13 | 106.34 | 0.0000 | 0.0000 | yes |
| scenario_c | mpc | grid_import_kwh | 5 | +1163.97 | 19.84 | 0.0000 | 0.0000 | yes |
| scenario_c | rule_based | grid_import_kwh | 5 | +182.25 | 1262.53 | 0.0000 | 0.0000 | yes |
| scenario_c | centralized | peak_demand_kw | 5 | +20.95 | 38.04 | 0.0000 | 0.0000 | yes |
| scenario_c | mpc | peak_demand_kw | 5 | +49.71 | 53.83 | 0.0000 | 0.0000 | yes |
| scenario_c | rule_based | peak_demand_kw | 5 | +20.49 | 23.63 | 0.0000 | 0.0000 | yes |
| scenario_c | centralized | ev_completion_rate | 5 | +0.11 | 4.47 | 0.0111 | 0.0221 | yes |
| scenario_c | mpc | ev_completion_rate | 5 | +0.91 | 29.21 | 0.0000 | 0.0000 | yes |
| scenario_c | rule_based | ev_completion_rate | 5 | +0.11 | 4.42 | 0.0115 | 0.0221 | yes |
| scenario_c | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_c | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_c | rule_based | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_c | centralized | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_c | mpc | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_c | rule_based | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_d | centralized | total_cost | 5 | +15.23 | 85.60 | 0.0000 | 0.0000 | yes |
| scenario_d | mpc | total_cost | 5 | +126.28 | 11.48 | 0.0003 | 0.0003 | yes |
| scenario_d | rule_based | total_cost | 5 | +15.30 | 1324.63 | 0.0000 | 0.0000 | yes |
| scenario_d | centralized | grid_import_kwh | 5 | +175.13 | 106.34 | 0.0000 | 0.0000 | yes |
| scenario_d | mpc | grid_import_kwh | 5 | +1132.38 | 15.25 | 0.0001 | 0.0001 | yes |
| scenario_d | rule_based | grid_import_kwh | 5 | +182.25 | 1262.53 | 0.0000 | 0.0000 | yes |
| scenario_d | centralized | peak_demand_kw | 5 | +20.93 | 38.00 | 0.0000 | 0.0000 | yes |
| scenario_d | mpc | peak_demand_kw | 5 | +49.67 | 18.31 | 0.0001 | 0.0001 | yes |
| scenario_d | rule_based | peak_demand_kw | 5 | +20.46 | 23.94 | 0.0000 | 0.0000 | yes |
| scenario_d | centralized | ev_completion_rate | 5 | +0.11 | 4.47 | 0.0111 | 0.0221 | yes |
| scenario_d | mpc | ev_completion_rate | 5 | +0.92 | 30.16 | 0.0000 | 0.0000 | yes |
| scenario_d | rule_based | ev_completion_rate | 5 | +0.11 | 4.42 | 0.0115 | 0.0221 | yes |
| scenario_d | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_d | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_d | rule_based | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_d | centralized | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_d | mpc | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_d | rule_based | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_e | centralized | total_cost | 5 | +13.14 | 83.51 | 0.0000 | 0.0000 | yes |
| scenario_e | mpc | total_cost | 5 | +117.66 | 10.32 | 0.0005 | 0.0005 | yes |
| scenario_e | rule_based | total_cost | 5 | +13.26 | 1350.99 | 0.0000 | 0.0000 | yes |
| scenario_e | centralized | grid_import_kwh | 5 | +151.30 | 102.69 | 0.0000 | 0.0000 | yes |
| scenario_e | mpc | grid_import_kwh | 5 | +1072.89 | 15.45 | 0.0001 | 0.0001 | yes |
| scenario_e | rule_based | grid_import_kwh | 5 | +158.15 | 1288.88 | 0.0000 | 0.0000 | yes |
| scenario_e | centralized | peak_demand_kw | 5 | +16.98 | 27.26 | 0.0000 | 0.0000 | yes |
| scenario_e | mpc | peak_demand_kw | 5 | +49.34 | 20.03 | 0.0000 | 0.0001 | yes |
| scenario_e | rule_based | peak_demand_kw | 5 | +16.74 | 18.92 | 0.0000 | 0.0001 | yes |
| scenario_e | centralized | ev_completion_rate | 5 | +0.11 | 4.42 | 0.0115 | 0.0231 | yes |
| scenario_e | mpc | ev_completion_rate | 5 | +0.86 | 25.17 | 0.0000 | 0.0000 | yes |
| scenario_e | rule_based | ev_completion_rate | 5 | +0.10 | 3.90 | 0.0175 | 0.0231 | yes |
| scenario_e | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_e | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_e | rule_based | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_e | centralized | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_e | mpc | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| scenario_e | rule_based | members_interrupted_count | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |

With n = 3-5 seeds these tests are sensitive only to large effects; report interval widths alongside significance.
