# Code-Repair Benchmark Task List (Amended)

**Authorization**: laguna-xs-2.1 / NVIDIA NIM / experiments/m2b_code_repair/
**Call Ceiling**: ≤48 steps/sim; LLM seeds 42/123 (tasks 4,5,9); det. seeds 42/123/456
**Max Calls**: 3 LLM tasks × 2 seeds × 3 iters × 48 steps = 864 calls (tightened: 24 steps → 432 calls)
**Comparator**: deterministic_safety arm runs on EVERY task (5-level stratification)
**Keep Rule**: Patch passes iff (a) parses, (b) runs without exception under {no diag, 1.08, 0.92}, (c) output ≠ baseline under violating diagnostic, (d) verification harness accepts, (e) service metrics not sacrificed (EV completion / flex load completion where applicable)

---

## Task 1: RuleBasedController — Overvoltage at Bus_1
- **Breakage**: Neutralize `_apply_grid_violation_redispatch` (comment out the voltage-scaling block)
- **Diagnostic**: 1.08 pu overvoltage at Bus_1
- **Simulation**: 7-day, voltage violations count
- **Target**: Patched resolves ≥80% violations vs baseline 0%
- **Comparator**: deterministic_safety (rule_based proposer)

## Task 2: RuleBasedController — Line Loading >100% on Line_1-2
- **Breakage**: Neutralize line-loading scaling in `_apply_grid_violation_redispatch`
- **Diagnostic**: Line_1-2 loading 110%
- **Simulation**: 7-day, loading violations count
- **Target**: Patched resolves ≥80% violations
- **Comparator**: deterministic_safety (rule_based proposer)

## Task 3: RuleBasedController — Transformer Loading >95%
- **Breakage**: Neutralize transformer-loading scaling in `_apply_grid_violation_redispatch`
- **Diagnostic**: Transformer loading 98%
- **Simulation**: 7-day, transformer violations
- **Target**: Patched resolves ≥80% violations
- **Comparator**: deterministic_safety (rule_based proposer)

## Task 4: LLMAgentController (verified) — Undervoltage at Bus_2
- **Breakage**: Cap battery charge at 30% of limit in `_control_battery`
- **Diagnostic**: 0.92 pu undervoltage at Bus_2
- **Simulation**: 7-day (≤48 steps), voltage violations
- **Target**: Verified arm repair_success_rate ≥70%
- **Comparator**: deterministic_safety (rule_based proposer)
- **Seeds**: 42, 123; ≤3 iters; ≤48 steps/sim

## Task 5: LLMAgentController (unverified) — Same as Task 4
- **Breakage**: Same as Task 4
- **Diagnostic**: Same as Task 4
- **Simulation**: Same
- **Target**: Unverified arm unrepaired violations count (should be high)
- **Comparator**: deterministic_safety
- **Seeds**: Same; hostile proposer mode: SAEA_LLM_HOSTILE=out_of_bounds

## Task 6: RuleBasedController — Overvoltage + Line Loading Combo (COMPARATOR: deterministic_safety)
- **Breakage**: Disable ALL redispatch in `_apply_grid_violation_redispatch`
- **Diagnostic**: 1.08 pu overvoltage + Line_1-2 at 105%
- **Simulation**: 7-day, 5-level stratification
- **Target**: Deterministic safety arm clamps Level 1 violations; Level 5 post-execution = 0
- **Comparator**: N/A (this IS the deterministic_safety arm running as repair target)

## Task 7: MultiAgentController — Transformer Overloading
- **Breakage**: Remove transformer-coordination logic from planner/coder path
- **Diagnostic**: Transformer loading 96%
- **Simulation**: 7-day, violations count
- **Target**: Code repair produces behavior-changing patch
- **Comparator**: deterministic_safety (rule_based proposer)

## Task 7b: LLMAgentController (verified) — EV Deadline Miss + Voltage Violation
- **Breakage**: Remove EV deadline check from `_control_ev`; cap battery charge at 40%
- **Diagnostic**: EV departure SOC < target + 1.05 pu overvoltage
- **Simulation**: 7-day, service + grid violations
- **Target**: Both service and grid violations reduced
- **Comparator**: deterministic_safety
- **Seeds**: 42, 123; ≤3 iters; ≤48 steps/sim

## Task 8: LLMAgentController (verified) — Flexible Load Deadline + Line Loading
- **Breakage**: Remove flexible load deadline check; neutralize line-loading response
- **Diagnostic**: Flex load missed deadline + Line_1-2 at 108%
- **Simulation**: 7-day (≤48 steps), service + grid
- **Target**: Verified arm replaces invalid steps
- **Comparator**: deterministic_safety
- **Seeds**: 42, 123; ≤3 iters; ≤48 steps/sim

## Task 9: CentralizedController — Export Limit Exceeded
- **Breakage**: Remove export-limit enforcement from `_apply_grid_limits`
- **Diagnostic**: Export 120% of limit
- **Simulation**: 7-day, export violations
- **Target**: Patch reduces export violations ≥50%
- **Comparator**: deterministic_safety

---

## Functional Regression Criteria (every task)
(a) Patched controller parses  
(b) Executes without NameError/AttributeError under {no diag, 1.08 pu, 0.92 pu}  
(c) Output DIFFERS from baseline under violating diagnostic  
(d) Not rejected as cosmetic by diff classifier  
(e) Verification harness accepts (no masking)  
(f) Service metrics preserved: EV completion ≥ baseline, flex load completion ≥ baseline (where applicable)

## Call/Step Budget Arithmetic
- **LLM tasks (4, 5, 8)**: 3 tasks × 2 seeds × 3 iters × 24 steps = 432 calls (tightened from 48 steps)
- **Deterministic tasks (1, 2, 3, 6, 7, 9)**: 6 tasks × 3 seeds × 3 iters × 24 steps = 1296 runs (no LLM calls)
- **Total LLM call ceiling**: 432 (pre-registered)

## Pilot Caveats
- LLM runs require NIM endpoint; fallback to deterministic_safety if unavailable
- Max 10 tasks, 3 iterations each (30 repair runs total)
- Record 5-level stratification for deterministic_safety arm on every task
- Hostile proposer mode (SAEA_LLM_HOSTILE=out_of_bounds) only for Task 5 (M2b ablation)

## Keep Rule
A task passes ONLY if the patched controller's output differs from baseline under violating diagnostic AND the verification harness accepts it AND service metrics are not sacrificed.