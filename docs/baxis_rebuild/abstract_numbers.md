# Abstract / prose numbers (measured)

## Cost ranking per scenario (pool_tou leg, mean total_cost, n=10)

* A: centralized 175.83, rule_based 191.96, multi_agent 275.48, mpc 371.22, rl 476.28
* B: mpc 222.74, centralized 236.12, rule_based 258.24, multi_agent 307.33, rl 331.47
* C: centralized 159.65, rule_based 168.77, multi_agent 268.77, rl 292.75, mpc 366.11
* D: centralized 175.83, rule_based 191.96, multi_agent 275.48, mpc 371.22, rl 476.28
* E: centralized 175.91, rule_based 191.94, multi_agent 278.05, mpc 371.22, rl 476.28

## multi_agent paired cost delta vs rule_based (mean, USD)

{
 "A": 83.51909115876887,
 "B": 49.08375898291117,
 "C": 100.00557429274366,
 "D": 83.51909115876887,
 "E": 86.1108482578732
}

## EV completion rate (mean)

* multi_agent: {
 "A": 0.7028571428571428,
 "B": 0.39090909090909093,
 "C": 0.7142857142857143,
 "D": 0.7028571428571428,
 "E": 0.7028571428571428
}
* rule_based:  {
 "A": 0.3085714285714286,
 "B": 0.1,
 "C": 0.29714285714285715,
 "D": 0.3085714285714286,
 "E": 0.3085714285714286
}
* mpc:         {
 "A": 0.9971428571428571,
 "B": 0.10727272727272727,
 "C": 0.9914285714285714,
 "D": 0.9971428571428571,
 "E": 0.9971428571428571
}
