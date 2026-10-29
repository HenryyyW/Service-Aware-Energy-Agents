# EV Scoring Trace — B1 Market/Settlement Review

**Scope**: Targeted review of B1 market clearing & settlement code for potential masking of EV service events (EV completion rate = 0 in QA matrix)

**Date**: 2026-10-29  
**Branch**: `feature/ev-scoring-trace`  
**Time spent**: ~45 min

---

## Findings Summary

**No masking found in B1 market clearing or settlement accounting.** The EV completion rate = 0 in QA matrix is **not caused by B1 code**. Root cause is likely elsewhere (simulation duration, controller logic, or metrics computation).

---

## Code Paths Reviewed

| File | Component | EV Interaction |
|------|-----------|----------------|
| `src/simulation/market.py` | UniformPriceClearing, WeightedClearing, CarbonAwareClearing, FairnessAwareClearing | Operates on `BuildingEnergyState.net_demand_kw` (building-level aggregate). **No asset-level awareness**; EV charging embedded in net demand. |
| `src/simulation/settlement.py` | SettlementEngine, BuildingSettlement | Tracks per-building totals only. **No asset-level breakdown**; EV energy folded into `total_grid_import_kwh` vs `baseline_grid_import_kwh`. |
| `src/simulation/coupling.py` | SimulationCoupler.step(), `_extract_building_powers`, `_build_building_states` | Extracts `building_ev_powers` from observations/actions but **does not pass to market clearing** (only used for grid power flow & failure injection). |

---

## Key Observations

### 1. Market Clearing Does Not Reorder Charger Actions
- Market clearing runs **after** CityLearn applies controller actions
- Input: `BuildingEnergyState.net_demand_kw` = total building consumption (includes EV charging)
- Output: Community trades that offset grid import/export
- **No action modification** — controller actions already applied in CityLearn

### 2. Settlement Accounting Does Not Drop EV Entries
- Settlement is **building-level**, not asset-level
- EV charging energy is part of `total_grid_import_kwh` (baseline) and reduced by community trades
- Savings correctly computed in `metadata.savings_vs_baseline` for whole building
- No per-asset lookup that could "drop" EV entries

### 3. EV Charger Power Extracted But Not Used in Market
```python
# coupling.py:_extract_building_powers() returns building_ev_powers
# but _build_building_states() only uses building_powers, building_pvs, building_battery_powers
```
- EV charger power extracted from observations/actions for **grid power flow only** (pandapower)
- Not passed to market clearing or settlement

### 4. EV Charger Failure Injection Only Affects Grid Representation
```python
# _apply_ev_charger_failures() modifies building_ev_powers
# but this only affects pandapower grid power flow
# CityLearn's internal EV state (SOC, charging) is NOT affected
```
- Failure injection is grid-side only
- Controller & CityLearn see normal EV charging

---

## Potential Indirect Effects (Low Likelihood)

| Mechanism | Assessment |
|-----------|------------|
| Market trades → different grid flows → grid violations → controller re-dispatch scales EV_CHARGE | Possible but **controller re-dispatch** (multi_agent.py:90) handles this, not market |
| Community trades reduce grid import → less grid stress → fewer violations → less EV scaling | Beneficial, not masking |
| Settlement at building level hides EV-specific savings | True but **by design** — savings correctly attributed to building |

---

## EV Completion Rate = 0: Likely Root Causes (Outside B1)

1. **Simulation duration too short** — 50 steps × 60 min = 2 days; EV arrival/departure cycles need full week
2. **Controller EV logic** — rule_based/multi_agent may not charge sufficiently
3. **Metrics computation** — `ev_completion_rate` in `src/evaluation/metrics.py` may need EV departure events that don't occur in short runs
4. **CityLearn EV configuration** — arrival/departure times, target SOC, initial SOC

---

## Recommendation

**Focus investigation on:**
1. `src/evaluation/metrics.py` — `compute_service_metrics()` EV completion logic
2. `experiments/run_experiment.py` — simulation duration / max_steps
3. Controller EV charging policies (rule_based, multi_agent coordinator)
4. Full-week scenario runs (672 steps at 15-min intervals)

**No B1 code changes needed.** The market clearing and settlement correctly handle EV charging as part of building net demand.

---

## Files Verified (No Changes Required)

- `src/simulation/market.py` ✓
- `src/simulation/settlement.py` ✓
- `src/simulation/coupling.py` ✓
- `src/controllers/multi_agent.py` (re-dispatch reviewed) ✓