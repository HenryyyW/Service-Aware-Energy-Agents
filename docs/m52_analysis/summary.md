| Scenario | Controller | n | total_cost | grid_import_kwh | peak_demand_kw | pv_self_consumption_kwh | ev_completion_rate | member_cost_coverage | members_interrupted_count |
|---|---|---|---|---|---|---|---|---|---|
| a | centralized | 5 | 349.30 ± 4.38 | 2672.67 ± 27.86 | 42.22 ± 1.25 | 9.85 ± 0.15 | 0.18 ± 0.15 | 1.00 ± 0.00 | — |
| a | mpc | 5 | 460.34 ± 32.86 | 3629.92 ± 227.44 | 70.96 ± 7.11 | 0.00 ± 0.00 | 0.99 ± 0.02 | 1.00 ± 0.00 | — |
| a | multi_agent | 5 | 334.06 ± 4.77 | 2497.54 ± 31.64 | 21.29 ± 0.55 | 9.85 ± 0.15 | 0.07 ± 0.08 | 1.00 ± 0.00 | — |
| a | rule_based | 5 | 349.36 ± 4.76 | 2679.79 ± 31.41 | 41.75 ± 1.92 | 9.85 ± 0.15 | 0.18 ± 0.15 | 1.00 ± 0.00 | — |
| b | centralized | 5 | 377.01 ± 5.53 | 2835.48 ± 35.45 | 44.68 ± 2.92 | 7.95 ± 0.10 | 0.16 ± 0.04 | 1.00 ± 0.00 | — |
| b | mpc | 5 | 453.68 ± 18.16 | 3498.91 ± 73.04 | 68.25 ± 10.94 | 0.00 ± 0.00 | 0.20 ± 0.06 | 1.00 ± 0.00 | — |
| b | multi_agent | 5 | 334.32 ± 4.77 | 2499.44 ± 31.63 | 21.30 ± 0.54 | 7.95 ± 0.10 | 0.04 ± 0.04 | 1.00 ± 0.00 | — |
| b | rule_based | 5 | 378.27 ± 6.23 | 2847.66 ± 42.69 | 55.60 ± 4.55 | 7.95 ± 0.10 | 0.15 ± 0.05 | 1.00 ± 0.00 | — |
| c | centralized | 5 | 348.62 ± 4.38 | 2667.75 ± 27.87 | 42.21 ± 1.25 | 14.78 ± 0.22 | 0.18 ± 0.15 | 1.00 ± 0.00 | — |
| c | mpc | 5 | 465.16 ± 21.87 | 3656.59 ± 192.92 | 70.97 ± 3.03 | 0.00 ± 0.00 | 0.98 ± 0.02 | 1.00 ± 0.00 | — |
| c | multi_agent | 5 | 333.39 ± 4.77 | 2492.62 ± 31.64 | 21.26 ± 0.58 | 14.78 ± 0.22 | 0.07 ± 0.08 | 1.00 ± 0.00 | — |
| c | rule_based | 5 | 348.69 ± 4.76 | 2674.87 ± 31.41 | 41.75 ± 1.92 | 14.78 ± 0.22 | 0.18 ± 0.15 | 1.00 ± 0.00 | — |
| d | centralized | 5 | 349.30 ± 4.38 | 2672.67 ± 27.86 | 42.22 ± 1.25 | 9.85 ± 0.15 | 0.18 ± 0.15 | 1.00 ± 0.00 | — |
| d | mpc | 5 | 460.34 ± 32.86 | 3629.92 ± 227.44 | 70.96 ± 7.11 | 0.00 ± 0.00 | 0.99 ± 0.02 | 1.00 ± 0.00 | — |
| d | multi_agent | 5 | 334.06 ± 4.77 | 2497.54 ± 31.64 | 21.29 ± 0.55 | 9.85 ± 0.15 | 0.07 ± 0.08 | 1.00 ± 0.00 | — |
| d | rule_based | 5 | 349.36 ± 4.76 | 2679.79 ± 31.41 | 41.75 ± 1.92 | 9.85 ± 0.15 | 0.18 ± 0.15 | 1.00 ± 0.00 | — |
| e | centralized | 5 | 338.12 ± 3.92 | 2582.20 ± 23.58 | 38.27 ± 1.36 | 9.85 ± 0.15 | 0.18 ± 0.14 | 0.80 ± 0.00 | — |
| e | mpc | 5 | 442.64 ± 32.55 | 3503.78 ± 210.25 | 70.63 ± 6.60 | 0.00 ± 0.00 | 0.93 ± 0.04 | 0.80 ± 0.00 | — |
| e | multi_agent | 5 | 324.98 ± 4.25 | 2430.90 ± 26.99 | 21.29 ± 0.55 | 9.85 ± 0.15 | 0.07 ± 0.08 | 0.80 ± 0.00 | — |
| e | rule_based | 5 | 338.24 ± 4.24 | 2589.04 ± 26.83 | 38.02 ± 2.01 | 9.85 ± 0.15 | 0.17 ± 0.15 | 0.80 ± 0.00 | — |

Paired deltas vs `rule_based` (negative cost/import/peak is better):

| Scenario | Controller | n pairs | total_cost | grid_import_kwh | peak_demand_kw | pv_self_consumption_kwh | ev_completion_rate | member_cost_coverage | members_interrupted_count |
|---|---|---|---|---|---|---|---|---|---|
| a | centralized | 5 | -0.07 ± 0.47 | -7.12 ± 4.27 | +0.46 ± 1.68 | +0.00 ± 0.00 | +0.01 ± 0.02 | +0.00 ± 0.00 | — |
| a | mpc | 5 | +110.98 ± 30.56 | +950.13 ± 206.43 | +29.21 ± 5.39 | -9.85 ± 0.15 | +0.81 ± 0.15 | +0.00 ± 0.00 | — |
| a | multi_agent | 5 | -15.30 ± 0.03 | -182.25 ± 0.40 | -20.46 ± 2.37 | +0.00 ± 0.00 | -0.11 ± 0.07 | +0.00 ± 0.00 | — |
| b | centralized | 5 | -1.26 ± 0.92 | -12.18 ± 9.22 | -10.93 ± 2.00 | +0.00 ± 0.00 | +0.01 ± 0.01 | +0.00 ± 0.00 | — |
| b | mpc | 5 | +75.41 ± 17.79 | +651.25 ± 90.17 | +12.65 ± 9.94 | -7.95 ± 0.10 | +0.05 ± 0.07 | +0.00 ± 0.00 | — |
| b | multi_agent | 5 | -43.95 ± 3.65 | -348.22 ± 25.78 | -34.30 ± 4.54 | +0.00 ± 0.00 | -0.11 ± 0.06 | +0.00 ± 0.00 | — |
| c | centralized | 5 | -0.07 ± 0.47 | -7.12 ± 4.27 | +0.46 ± 1.68 | +0.00 ± 0.00 | +0.01 ± 0.02 | +0.00 ± 0.00 | — |
| c | mpc | 5 | +116.47 ± 17.56 | +981.72 ± 163.07 | +29.23 ± 4.12 | -14.78 ± 0.22 | +0.81 ± 0.15 | +0.00 ± 0.00 | — |
| c | multi_agent | 5 | -15.30 ± 0.03 | -182.25 ± 0.40 | -20.49 ± 2.41 | +0.00 ± 0.00 | -0.11 ± 0.07 | +0.00 ± 0.00 | — |
| d | centralized | 5 | -0.07 ± 0.47 | -7.12 ± 4.27 | +0.46 ± 1.68 | +0.00 ± 0.00 | +0.01 ± 0.02 | +0.00 ± 0.00 | — |
| d | mpc | 5 | +110.98 ± 30.56 | +950.13 ± 206.43 | +29.21 ± 5.39 | -9.85 ± 0.15 | +0.81 ± 0.15 | +0.00 ± 0.00 | — |
| d | multi_agent | 5 | -15.30 ± 0.03 | -182.25 ± 0.40 | -20.46 ± 2.37 | +0.00 ± 0.00 | -0.11 ± 0.07 | +0.00 ± 0.00 | — |
| e | centralized | 5 | -0.12 ± 0.42 | -6.84 ± 3.82 | +0.24 ± 1.50 | +0.00 ± 0.00 | +0.01 ± 0.02 | +0.00 ± 0.00 | — |
| e | mpc | 5 | +104.40 ± 31.67 | +914.74 ± 193.03 | +32.60 ± 5.36 | -9.85 ± 0.15 | +0.77 ± 0.16 | +0.00 ± 0.00 | — |
| e | multi_agent | 5 | -13.26 ± 0.03 | -158.15 ± 0.34 | -16.74 ± 2.46 | +0.00 ± 0.00 | -0.10 ± 0.07 | +0.00 ± 0.00 | — |

Each cell is mean ± 95% confidence half-width (Student-t, sample std). A paired delta whose interval excludes zero is evidence of a difference for these seeds; it is not yet a paper-level claim.

Paired t-tests vs `rule_based` (Holm within scenario x metric family):

| Scenario | Comparison | Metric | n | mean delta | t | p | p (Holm) | sig 0.05 |
|---|---|---|---|---|---|---|---|---|
| a | centralized | total_cost | 5 | -0.07 | -0.39 | 0.7152 | 0.7152 | no |
| a | mpc | total_cost | 5 | +110.98 | 10.08 | 0.0005 | 0.0011 | yes |
| a | multi_agent | total_cost | 5 | -15.30 | -1324.63 | 0.0000 | 0.0000 | yes |
| a | centralized | grid_import_kwh | 5 | -7.12 | -4.62 | 0.0098 | 0.0098 | yes |
| a | mpc | grid_import_kwh | 5 | +950.13 | 12.78 | 0.0002 | 0.0004 | yes |
| a | multi_agent | grid_import_kwh | 5 | -182.25 | -1262.53 | 0.0000 | 0.0000 | yes |
| a | centralized | peak_demand_kw | 5 | +0.46 | 0.76 | 0.4884 | 0.4884 | no |
| a | mpc | peak_demand_kw | 5 | +29.21 | 15.05 | 0.0001 | 0.0002 | yes |
| a | multi_agent | peak_demand_kw | 5 | -20.46 | -23.94 | 0.0000 | 0.0001 | yes |
| a | centralized | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| a | mpc | pv_self_consumption_kwh | 5 | -9.85 | -184.98 | 0.0000 | 0.0000 | yes |
| a | multi_agent | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| a | centralized | ev_completion_rate | 5 | +0.01 | 1.00 | 0.3739 | 0.3739 | no |
| a | mpc | ev_completion_rate | 5 | +0.81 | 14.84 | 0.0001 | 0.0004 | yes |
| a | multi_agent | ev_completion_rate | 5 | -0.11 | -4.42 | 0.0115 | 0.0231 | yes |
| a | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| a | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| a | multi_agent | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| b | centralized | total_cost | 5 | -1.26 | -3.80 | 0.0191 | 0.0191 | yes |
| b | mpc | total_cost | 5 | +75.41 | 11.77 | 0.0003 | 0.0006 | yes |
| b | multi_agent | total_cost | 5 | -43.95 | -33.43 | 0.0000 | 0.0000 | yes |
| b | centralized | grid_import_kwh | 5 | -12.18 | -3.67 | 0.0214 | 0.0214 | yes |
| b | mpc | grid_import_kwh | 5 | +651.25 | 20.05 | 0.0000 | 0.0001 | yes |
| b | multi_agent | grid_import_kwh | 5 | -348.22 | -37.50 | 0.0000 | 0.0000 | yes |
| b | centralized | peak_demand_kw | 5 | -10.93 | -15.14 | 0.0001 | 0.0002 | yes |
| b | mpc | peak_demand_kw | 5 | +12.65 | 3.53 | 0.0242 | 0.0242 | yes |
| b | multi_agent | peak_demand_kw | 5 | -34.30 | -20.96 | 0.0000 | 0.0001 | yes |
| b | centralized | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| b | mpc | pv_self_consumption_kwh | 5 | -7.95 | -215.05 | 0.0000 | 0.0000 | yes |
| b | multi_agent | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| b | centralized | ev_completion_rate | 5 | +0.01 | 2.45 | 0.0705 | 0.1410 | no |
| b | mpc | ev_completion_rate | 5 | +0.05 | 2.30 | 0.0829 | 0.1410 | no |
| b | multi_agent | ev_completion_rate | 5 | -0.11 | -4.74 | 0.0090 | 0.0270 | yes |
| b | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| b | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| b | multi_agent | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| c | centralized | total_cost | 5 | -0.07 | -0.39 | 0.7152 | 0.7152 | no |
| c | mpc | total_cost | 5 | +116.47 | 18.41 | 0.0001 | 0.0001 | yes |
| c | multi_agent | total_cost | 5 | -15.30 | -1324.63 | 0.0000 | 0.0000 | yes |
| c | centralized | grid_import_kwh | 5 | -7.12 | -4.62 | 0.0098 | 0.0098 | yes |
| c | mpc | grid_import_kwh | 5 | +981.72 | 16.71 | 0.0001 | 0.0002 | yes |
| c | multi_agent | grid_import_kwh | 5 | -182.25 | -1262.53 | 0.0000 | 0.0000 | yes |
| c | centralized | peak_demand_kw | 5 | +0.46 | 0.76 | 0.4891 | 0.4891 | no |
| c | mpc | peak_demand_kw | 5 | +29.23 | 19.67 | 0.0000 | 0.0001 | yes |
| c | multi_agent | peak_demand_kw | 5 | -20.49 | -23.63 | 0.0000 | 0.0001 | yes |
| c | centralized | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| c | mpc | pv_self_consumption_kwh | 5 | -14.78 | -184.98 | 0.0000 | 0.0000 | yes |
| c | multi_agent | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| c | centralized | ev_completion_rate | 5 | +0.01 | 1.00 | 0.3739 | 0.3739 | no |
| c | mpc | ev_completion_rate | 5 | +0.81 | 14.99 | 0.0001 | 0.0003 | yes |
| c | multi_agent | ev_completion_rate | 5 | -0.11 | -4.42 | 0.0115 | 0.0231 | yes |
| c | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| c | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| c | multi_agent | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| d | centralized | total_cost | 5 | -0.07 | -0.39 | 0.7152 | 0.7152 | no |
| d | mpc | total_cost | 5 | +110.98 | 10.08 | 0.0005 | 0.0011 | yes |
| d | multi_agent | total_cost | 5 | -15.30 | -1324.63 | 0.0000 | 0.0000 | yes |
| d | centralized | grid_import_kwh | 5 | -7.12 | -4.62 | 0.0098 | 0.0098 | yes |
| d | mpc | grid_import_kwh | 5 | +950.13 | 12.78 | 0.0002 | 0.0004 | yes |
| d | multi_agent | grid_import_kwh | 5 | -182.25 | -1262.53 | 0.0000 | 0.0000 | yes |
| d | centralized | peak_demand_kw | 5 | +0.46 | 0.76 | 0.4884 | 0.4884 | no |
| d | mpc | peak_demand_kw | 5 | +29.21 | 15.05 | 0.0001 | 0.0002 | yes |
| d | multi_agent | peak_demand_kw | 5 | -20.46 | -23.94 | 0.0000 | 0.0001 | yes |
| d | centralized | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| d | mpc | pv_self_consumption_kwh | 5 | -9.85 | -184.98 | 0.0000 | 0.0000 | yes |
| d | multi_agent | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| d | centralized | ev_completion_rate | 5 | +0.01 | 1.00 | 0.3739 | 0.3739 | no |
| d | mpc | ev_completion_rate | 5 | +0.81 | 14.84 | 0.0001 | 0.0004 | yes |
| d | multi_agent | ev_completion_rate | 5 | -0.11 | -4.42 | 0.0115 | 0.0231 | yes |
| d | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| d | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| d | multi_agent | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| e | centralized | total_cost | 5 | -0.12 | -0.80 | 0.4689 | 0.4689 | no |
| e | mpc | total_cost | 5 | +104.40 | 9.15 | 0.0008 | 0.0016 | yes |
| e | multi_agent | total_cost | 5 | -13.26 | -1350.99 | 0.0000 | 0.0000 | yes |
| e | centralized | grid_import_kwh | 5 | -6.84 | -4.97 | 0.0077 | 0.0077 | yes |
| e | mpc | grid_import_kwh | 5 | +914.74 | 13.16 | 0.0002 | 0.0004 | yes |
| e | multi_agent | grid_import_kwh | 5 | -158.15 | -1288.88 | 0.0000 | 0.0000 | yes |
| e | centralized | peak_demand_kw | 5 | +0.24 | 0.45 | 0.6755 | 0.6755 | no |
| e | mpc | peak_demand_kw | 5 | +32.60 | 16.89 | 0.0001 | 0.0001 | yes |
| e | multi_agent | peak_demand_kw | 5 | -16.74 | -18.92 | 0.0000 | 0.0001 | yes |
| e | centralized | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| e | mpc | pv_self_consumption_kwh | 5 | -9.85 | -184.98 | 0.0000 | 0.0000 | yes |
| e | multi_agent | pv_self_consumption_kwh | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| e | centralized | ev_completion_rate | 5 | +0.01 | 1.63 | 0.1778 | 0.1778 | no |
| e | mpc | ev_completion_rate | 5 | +0.77 | 13.17 | 0.0002 | 0.0006 | yes |
| e | multi_agent | ev_completion_rate | 5 | -0.10 | -3.90 | 0.0175 | 0.0351 | yes |
| e | centralized | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| e | mpc | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |
| e | multi_agent | member_cost_coverage | 5 | +0.00 | 0.00 | 1.0000 | 1.0000 | no |

With n = 3-5 seeds these tests are sensitive only to large effects; report interval widths alongside significance.
