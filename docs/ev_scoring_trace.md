# EV Scoring Trace Document

## Executive Summary

**Problem**: EV completion rate is 0.000 in experiments despite EVs being present and active in the simulation.

**Root Cause**: The EV charger schedule CSV is generated correctly but the EV never connects in simulation (connected=0.0 always). The evaluation fallback path has a key format mismatch.

**Confirmed**: Charger schedule CSV is generated correctly (169 rows, 92 connected steps). Adapter produces observation keys like `building_0_ev_0_soc`. Evaluation explicit path (`_compute_observed_ev_metrics`) works with these keys. Fallback path had key format mismatch - now fixed.

## Trace: EV Charging Flow from Schema to Scoring

### 1. Scenario Schema (EVConfig)
**File**: `src/schemas/scenario.py` (lines 35-44)

```python
class EVConfig(BaseModel):
    capacity_kwh: float
    max_charge_kw: float
    efficiency: float = 0.90
    arrival_time: str      # HH:MM format
    departure_time: str    # HH:MM format
    target_soc: float = 0.8
    initial_soc: float = 0.3
    connected_days: List[int] = Field(default_factory=lambda: list(range(7)))
```

**Key fields**: `arrival_time`, `departure_time`, `target_soc`, `connected_days` drive the charger schedule.

---

### 2. CityLearn Adapter - Charger Schedule Generation

**File**: `src/simulation/citylearn_adapter.py` ??`_apply_device_overrides` (lines 280-300) ??`_charger_schedule_frame` (lines 327-370)

**Flow**:
1. `_apply_device_overrides` iterates over `building_config.evs`
2. For each EV, creates a charger entry in schema with `charger_simulation` pointing to a CSV file
3. `_charger_schedule_frame` generates a DataFrame with one row per episode step containing:
   - `electric_vehicle_charger_state`: 1 (connected) or 0 (disconnected)
   - `electric_vehicle_departure_time`: steps until departure
   - `electric_vehicle_required_soc_departure`: target SOC ? 100
   - `electric_vehicle_estimated_arrival_time`: steps until next arrival
   - `electric_vehicle_estimated_soc_arrival`: initial SOC ? 100

**Schedule Logic** (`_in_daily_window`, lines 382-388):
- Handles overnight windows (e.g., 18:00 ??07:00)
- Respects `connected_days` (default: all 7 days)
- Generates connection state per timestep based on arrival/departure times

**CSV Output** (line 299): Written to `{building_name}_charger_{index}.csv` and copied to schema dir.

---

### 3. CityLearn Adapter - Observation Enrichment

**File**: `src/simulation/citylearn_adapter.py` ??`_enrich_electric_vehicle_observations` (lines 831-875)

**Called from**: `reset()` and `step()` AFTER `_convert_observations_to_dict`

**Key Generation** (line 844):
```python
prefix = f"{bid}_ev_{index}"  # e.g., "building_0_ev_0"
```

**Keys Added** (lines 848-874):
| Key Suffix | Source |
|------------|--------|
| `_connected` | `vehicle is not None` (1.0/0.0) |
| `_soc` | `battery.soc[step]` |
| `_capacity_kwh` | `battery.capacity` |
| `_energy_kwh` | `soc * capacity` |
| `_hours_to_departure` | `simulation.electric_vehicle_departure_time[step]` |
| `_required_soc` | `simulation.electric_vehicle_required_soc_departure[step]` |
| `_max_charge_kw` | `charger.max_charging_power` |
| `_min_charge_kw` | `charger.min_charging_power` |

**Example Keys Produced**:
```
building_0_ev_0_connected      ??1.0
building_0_ev_0_soc            ??0.45
building_0_ev_0_required_soc   ??80.0
building_0_ev_0_hours_to_departure ??4.0
building_0_ev_0_max_charge_kw  ??11.0
```

---

### 4. Evaluation Layer - Explicit Observation Path

**File**: `src/evaluation/metrics.py` ??`_compute_observed_ev_metrics` (lines 203-249)

**Prefix Extraction** (lines 219-223):
```python
prefixes = {
    key[: -len("_connected")]
    for key in observations
    if key.endswith("_connected") and "_ev_" in key
}
```
- Finds keys like `building_0_ev_0_connected` ??extracts prefix `building_0_ev_0`

**Tracking Logic** (lines 226-236):
- When connected: records `soc[prefix]` and `required[prefix]`
- When disconnected (was connected): records departure with `(soc, required)`
- Tracks via `connected_prev` dict

**Return Value** (lines 245-249):
```python
return (
    completed / len(values),      # completion_rate
    float(np.mean(values)),       # avg_soc
    float(np.min(values)),        # worst_soc
)
```

**??This path SHOULD work with adapter's keys** (`building_0_ev_0_soc`, `building_0_ev_0_required_soc`)

---

### 5. Evaluation Layer - Fallback Scoring Path (BUG HERE)

**File**: `src/evaluation/metrics.py` ??`compute_service_metrics` (lines 267-327)

**Fallback Triggered When**: `_compute_observed_ev_metrics` returns `None` (no explicit EV keys found)

**Key Format Mismatch** (lines 302-304):
```python
soc_key = f"{building_id}_connected_electric_vehicle_at_charger_soc"
if soc_key in obs:
    ev_soc_tracking[ev_id] = float(obs[soc_key])
```

**Mismatch**:
| Component | Adapter Produces | Fallback Expects |
|-----------|------------------|------------------|
| SOC key | `building_0_ev_0_soc` | `building_0_connected_electric_vehicle_at_charger_soc` |
| Required SOC | `building_0_ev_0_required_soc` | (not checked) |
| Departure detection | `_connected` transition | timestep comparison only |

**Impact**: If explicit path fails ??fallback runs ??finds no SOC data ??`ev_departure_soc` empty ??completion rate = 0.0

---

### 6. Root Cause Analysis

**Why does explicit path fail?** (`_compute_observed_ev_metrics` returns `None`)

**Confirmed Finding**: The EV never connects in simulation (`_connected` = 0.0 for all steps). The charger schedule CSV is generated correctly (169 rows, 92 connected steps at 60-min resolution), but the EV never connects in simulation.

**Root Cause**: The charger schedule CSV is generated correctly (169 rows at 60-min resolution, 92 connected steps), but the EV never connects in simulation (`_connected` = 0.0 for all steps). The evaluation fallback path had a key format mismatch - now fixed.

**Key Findings**:
1. Charger schedule CSV is generated correctly at 60-min resolution (169 rows, 92 connected steps)
2. Adapter produces observation keys in format `building_0_ev_0_soc`, `building_0_ev_0_required_soc`, etc.
3. Explicit evaluation path (`_compute_observed_ev_metrics`) works with these keys
4. Fallback path had key format mismatch - **now fixed** to support adapter's key format
5. EV never connects in simulation (`_connected` = 0.0 always) - root cause in CityLearn charger integration

**Investigated Hypotheses**:
1. ??Charger schedule CSV generated correctly (169 rows, 92 connected)
2. ??Building ID mismatch - adapter uses `building_0`, eval expects `building_0` (matches)
3. ??Charger devices not created - CSV generated correctly
4. ??Timestep alignment - fixed: schedule generated at 60-min resolution (dataset resolution)
5. ??CSV not read by CityLearn - likely cause: `electric_vehicle_id` in CSV is fixed string "Electric_Vehicle_scenario" for all EVs, may conflict
6. ??Vehicle never connects in simulation - `_connected` always 0.0

---

### 7. Key Files & Line References

| Component | File | Key Lines |
|-----------|------|-----------|
| EVConfig schema | `src/schemas/scenario.py` | 35-44 |
| Charger schedule gen | `src/simulation/citylearn_adapter.py` | 280-300, 327-370 |
| Observation enrichment | `src/simulation/citylearn_adapter.py` | 831-875 |
| Explicit EV scoring | `src/evaluation/metrics.py` | 203-249 |
| Fallback EV scoring (BUG) | `src/evaluation/metrics.py` | 267-327 |
| Controller EV actions | `src/controllers/rl.py` | 149 |
| Test observation format | `tests/test_metrics.py` | 283-285 |

---

### 8. Fixes Applied

**??Fixed: Fallback Key Format** (`src/evaluation/metrics.py`)
- Added `_compute_ev_metrics_fallback()` function supporting both adapter key format (`{bid}_ev_{i}_soc`) and stock CityLearn format (`{bid}_connected_electric_vehicle_at_charger_soc`)
- Updated fallback logic in `compute_service_metrics` to use new fallback function first
- Fallback now correctly reads adapter's key format

**??Fixed: Charger Schedule Timestep Alignment**
- Verified: Charger schedule generated at dataset resolution (60 min) after timestep override
- CSV has 169 rows (7 days ? 24 hours + 1), 92 connected steps - correct

**Pending**: EV never connects in simulation (`_connected` = 0.0 always) - requires CityLearn charger integration debug

---

### 9. Tests Added/Updated

**File**: `tests/test_metrics.py`
- `test_ev_metrics_use_explicit_observation_keys`: Verifies explicit path works with adapter keys
- `test_ev_metrics_fall_back_without_explicit_keys`: Verifies fallback works with stock keys
- All 9 metric tests pass

**All tests pass**: 210 tests pass

---

### Next Steps

1. **Debug EV connection in simulation** - Root cause: EV never connects (`_connected` = 0.0)
   - Check `electric_vehicle_id` in charger CSV (currently fixed string "Electric_Vehicle_scenario" for all EVs)
   - Verify CityLearn reads charger CSV correctly
   - Add debug logging to `_enrich_electric_vehicle_observations` to trace connection state

2. **Verify charger schedule CSV integration** with CityLearn
   - Check `electric_vehicle_id` column format
   - Verify CSV columns match CityLearn expectations
   - Test with single EV first

3. **Add integration test** for end-to-end EV scoring with real adapter

4. **Update documentation** with final findings after root cause resolved

---

*Document created: 2026-10-29*  
*Branch: feature/ev-scoring-trace*  
*Author: Backend/Simulation Engineer A*

---

## Appendix: market/settlement side review (Backend/Simulation Engineer B)

# EV Scoring Trace ??B1 Market/Settlement Review

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
- **No action modification** ??controller actions already applied in CityLearn

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
| Market trades ??different grid flows ??grid violations ??controller re-dispatch scales EV_CHARGE | Possible but **controller re-dispatch** (multi_agent.py:90) handles this, not market |
| Community trades reduce grid import ??less grid stress ??fewer violations ??less EV scaling | Beneficial, not masking |
| Settlement at building level hides EV-specific savings | True but **by design** ??savings correctly attributed to building |

---

## EV Completion Rate = 0: Likely Root Causes (Outside B1)

1. **Simulation duration too short** ??50 steps ? 60 min = 2 days; EV arrival/departure cycles need full week
2. **Controller EV logic** ??rule_based/multi_agent may not charge sufficiently
3. **Metrics computation** ??`ev_completion_rate` in `src/evaluation/metrics.py` may need EV departure events that don't occur in short runs
4. **CityLearn EV configuration** ??arrival/departure times, target SOC, initial SOC

---

## Recommendation

**Focus investigation on:**
1. `src/evaluation/metrics.py` ??`compute_service_metrics()` EV completion logic
2. `experiments/run_experiment.py` ??simulation duration / max_steps
3. Controller EV charging policies (rule_based, multi_agent coordinator)
4. Full-week scenario runs (672 steps at 15-min intervals)

**No B1 code changes needed.** The market clearing and settlement correctly handle EV charging as part of building net demand.

---

## Files Verified (No Changes Required)

- `src/simulation/market.py` ??
- `src/simulation/settlement.py` ??
- `src/simulation/coupling.py` ??
- `src/controllers/multi_agent.py` (re-dispatch reviewed) ??