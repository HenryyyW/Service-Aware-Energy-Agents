# Phase 2 Market Settlement Design

**Status**: Draft — for team review  
**Author**: Backend/Simulation Engineer B  
**Date**: 2026-10-29  
**Related**: PR #29 (settlement API contract), Backend A's LLM backend doc

---

## 1. Executive Summary

Phase 1 delivered a working uniform-price community clearing engine with per-member settlement accounting (PR #29). The current model uses static time-of-use tariffs and a single community-wide clearing price. Phase 2 evolves this into a **dynamic, multi-layered market architecture** that supports:

1. **Dynamic/local energy pricing** — moving beyond static TOU to real-time locational marginal pricing (LMP) and dynamic tariffs
2. **Peer-to-peer (P2P) trading** — bilateral contracts between members alongside/instead of community pool clearing
3. **Extended demand-charge & export-revenue models** — leveraging the per-member fields from PR #29
4. **Settlement guarantees** — formal invariants that service-aware agents must preserve under all market configurations

---

## 2. Current Baseline (Phase 1 Recap)

| Component | Implementation | Key Fields (PR #29) |
|-----------|----------------|---------------------|
| Market Type | Uniform-price, community pool | `member_settlements[]` with 21 fields |
| Pricing | Static TOU tariffs per building | `import_prices`, `export_prices` per period |
| Clearing | Single community-wide price per interval | `avg_clearing_price` per interval |
| Settlement | Net energy + demand charge | `savings_vs_baseline`, `self_sufficiency` |
| Invariants | Energy conserved (∑trades=0), Money conserved (∑settlements=0) | Enforced in `market.py` |

---

## 3. Dynamic / Local Energy Pricing Evolution

### 3.1 From Static TOU → Dynamic LMP

**Current**: Each building has fixed `import_prices` / `export_prices` per TOU period (`off_peak`, `mid_peak`, `on_peak`).

**Target**: Locational Marginal Pricing (LMP) per bus per interval.

```python
# New schema extension (add to EnergySharingConfig)
class DynamicPricingConfig(BaseModel):
    enabled: bool = False
    lmp_update_interval_minutes: int = 15
    congestion_cost_method: Literal["dc_approx", "ac_full"] = "dc_approx"
    loss_factor: float = 1.0
    price_cap_per_kwh: Optional[float] = 1.0  # $/kWh cap
```

**Mechanics**:
- Pandapower computes LMP at each bus: `LMP = energy_price + congestion_price + loss_price`
- Buildings import/export at their bus LMP (no longer fixed tariff)
- Community clearing still possible as a fallback layer
- Requires pandapower AC/DC OPF integration (already have network topology)

### 3.2 Dynamic Tariff Structures

Support utility programs beyond TOU:
- **Real-time pricing (RTP)**: Hourly/day-ahead prices from utility API
- **Critical peak pricing (CPP)**: Event-based surcharges
- **Subscription / capacity charges**: Fixed $/kW-month + variable energy

```python
class TariffConfig(BaseModel):
    type: Literal["tou", "rtp", "cpp", "subscription", "hybrid"] = "tou"
    # ... existing fields
    rtp_source: Optional[str] = None  # API endpoint or file
    cpp_events: List[CppEvent] = []   # (start, end, multiplier)
    subscription_capacity_kw: Optional[float] = None
    subscription_fee_per_kw_month: Optional[float] = None
```

---

## 4. P2P Trading Layer

### 4.1 Rationale

Current community pool = single clearing price for all. P2P enables:
- Bilateral contracts at negotiated prices
- Preference matching (green buyer ↔ solar seller)
- Reduced community pool volume → simpler clearing
- Member autonomy without leaving community

### 4.2 Architecture: Dual-Layer Market

```
┌─────────────────────────────────────────────────────┐
│                    COMMUNITY POOL                    │
│  (residual clearing after P2P matches)              │
│  Uniform price, residual energy balance             │
└─────────────────────────────────────────────────────┘
                         ↑
            P2P bids/offers not matched
                         ↓
┌─────────────────────────────────────────────────────┐
│                      P2P LAYER                       │
│  Bilateral matches: buyer ↔ seller @ negotiated $    │
│  Continuous double auction or discrete auctions      │
│  Smart contracts for delivery/settlement guarantees  │
└─────────────────────────────────────────────────────┘
```

### 4.3 P2P Data Structures

```python
class P2POrder(BaseModel):
    order_id: str
    member_id: str
    side: Literal["buy", "sell"]
    quantity_kwh: float
    price_per_kwh: float  # limit price
    start_interval: int
    end_interval: int
    status: Literal["open", "partial", "filled", "cancelled"]
    counterparty_id: Optional[str] = None

class P2PTrade(BaseModel):
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_id: str
    seller_id: str
    quantity_kwh: float
    price_per_kwh: float
    interval: int
    settlement_status: Literal["pending", "settled", "disputed"]
```

### 4.4 Matching Engine

- **Continuous double auction**: Price-time priority, min spread enforcement
- **Batch auctions**: Every N intervals (configurable), uniform price within batch
- **Preference filters**: Carbon intensity, locality, contract duration

```python
class P2PMatchingEngine:
    def __init__(self, config: P2PConfig):
        self.orders: Dict[str, P2POrder] = {}
        self.trades: List[P2PTrade] = []
    
    def submit_order(self, order: P2POrder) -> List[P2PTrade]:
        """Match against opposite-side orders; return executed trades."""
    
    def get_orderbook(self) -> Dict[str, List[P2POrder]]:
        """Return {buy: [...], sell: [...]} for UI."""
```

---

## 5. Demand-Charge & Export-Revenue Model Extensions

### 5.1 Current Model (Phase 1)

```
Member Bill = Grid_Import_Cost - Grid_Export_Revenue + Demand_Charge
Demand_Charge = peak_grid_import_kw × demand_charge_rate
```

**PR #29 fields**: `peak_grid_import_kw`, `baseline_peak_grid_import_kw`, `demand_charge_rate`, `actual_demand_charge`, `baseline_demand_charge`

### 5.2 Extensions

| Extension | Description | New Fields |
|-----------|-------------|------------|
| **Coincident peak** | Demand charge on community peak, not individual | `community_peak_import_kw`, `coincident_peak_share` |
| **Time-differentiated demand charge** | Higher $/kW during critical peaks | `demand_charge_schedule: Dict[period, float]` |
| **Export capacity payment** | Compensation for firm export capacity | `export_capacity_kw`, `export_capacity_rate` |
| **Voltage/reactive support** | Payment for VAR support | `reactive_energy_kvarh`, `reactive_rate` |
| **Subscription offset** | Fixed fee covers first N kW of demand | `subscription_capacity_kw`, `subscription_fee` |

### 5.3 Settlement Formula v2

```
Member_Bill = 
  Σ (grid_import_kwh_t × LMP_import_t) 
  - Σ (grid_export_kwh_t × LMP_export_t)
  + max_peak_kw × demand_charge_rate(period)
  + coincident_peak_share × community_demand_charge
  - export_capacity_kw × export_capacity_rate
  + reactive_energy_kvarh × reactive_rate
  - subscription_fee (if applicable)
  + P2P_settlements (separate ledger)
```

---

## 6. Settlement Guarantees (Agent Invariants)

Service-aware agents must preserve these **formal guarantees** under any market configuration:

### 6.1 Financial Invariants

| Invariant | Formal Statement | Test |
|-----------|------------------|------|
| **Money Conservation** | `∑_members net_settlement = 0` | `abs(sum(s.net_settlement)) < 1e-6` |
| **Energy Conservation** | `∑_members (grid_import - grid_export + community_import - community_export + P2P_buy - P2P_sell) = 0` | Per-interval |
| **No Arbitrage** | `∀m: community_price ∈ [export_price_m, import_price_m]` | Per-interval per-member |
| **P2P Settlement** | `∑_P2P_trades (buyer_payment - seller_revenue) = 0` | Per-trade |

### 6.2 Service Guarantees

| Guarantee | Definition | Enforcement |
|-----------|------------|-------------|
| **EV Completion** | `ev_completion_rate ≥ target` despite market actions | Agent policy constraint |
| **Comfort Bounds** | `comfort_violation_degree_hours ≤ threshold` | Hard constraint in controller |
| **Grid Limits** | `voltage ∈ [0.95, 1.05] pu`, `loading ≤ 1.0 pu` | Pandapower verification harness |
| **Fairness** | `Gini(savings_vs_baseline) ≤ threshold` | Post-settlement audit |

### 6.3 Recovery Guarantees

When failures inject (Scenario E), agents must:
1. **Detect** — Within N intervals via verification harness
2. **Repair** — Modify policy/bids to restore invariants
3. **Verify** — Harness confirms all guarantees restored
4. **Settlement Integrity** — No double-charge, no lost revenue during recovery

```python
class SettlementGuarantees:
    """Runtime assertions checked by verification harness."""
    
    def check_all(self, before: ExperimentResult, after: ExperimentResult) -> GuaranteeReport:
        return GuaranteeReport(
            money_conserved=self._check_money_conservation(before, after),
            energy_conserved=self._check_energy_conservation(before, after),
            no_arbitrage=self._check_no_arbitrage(after),
            service_guarantees=self._check_service_guarantees(after),
            fairness=self._check_fairness(after),
        )
```

---

## 7. Integration Points & Migration Path

### 7.1 Phase 2a: Dynamic Pricing (Weeks 10-12)
- Add `DynamicPricingConfig` to schema
- Integrate pandapower LMP calculation in `coupling.py` step
- New market type: `"lmp"` in `MarketType` enum
- Tests: LMP vs TOU price divergence, congestion signals

### 7.2 Phase 2b: P2P Layer (Weeks 12-14)
- Add `P2POrder`, `P2PTrade`, `P2PConfig` schemas
- Implement `P2PMatchingEngine` in `src/coordination/p2p.py`
- Dual-layer clearing in `SimulationCoupler.step()`
- UI: Orderbook view, trade history, preference settings

### 7.3 Phase 2c: Extended Settlement (Weeks 14-16)
- Extend `BuildingSettlement` with Phase 2 fields
- Update `SettlementEngine._calculate_savings()` for new formula
- Add `SettlementGuarantees` verification harness
- Migration: default configs preserve Phase 1 behavior

---

## 8. Open Questions

1. **LMP computation frequency**: Every interval (15 min) vs hourly? Trade-off: accuracy vs computation.
2. **P2P priority**: Does P2P clear before or after community pool? Affects price signals.
3. **Contract duration**: Minimum P2P contract length? 1 interval, 1 hour, 1 day?
4. **Regulatory**: Are P2P trades "retail" or "wholesale"? Impacts tariff applicability.
5. **Data privacy**: P2P orderbooks reveal member flexibility — aggregation/anonymization needed?

---

## 9. Acceptance Criteria (Phase 2 Gate)

- [ ] Dynamic LMP clearing runs end-to-end on Scenario D/E
- [ ] P2P orders match and settle alongside community pool
- [ ] Extended demand-charge model computes correctly (unit tests)
- [ ] All Phase 1 invariants + new guarantees pass verification harness
- [ ] Frontend can render LMP prices, P2P orderbook, extended settlement table
- [ ] Documentation: API contracts, config schemas, migration guide

---

## 10. References

- PR #29: Settlement API contract (per-member fields)
- PR #15: Scenario E fault signatures (verification harness)
- Backend A's LLM backend doc (parallel Phase 2 gate)
- `src/simulation/market.py` — current clearing engines
- `src/simulation/settlement.py` — current settlement engine
- `src/simulation/coupling.py` — co-simulation integration point