"""Market clearing and settlement for local energy sharing."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import numpy as np

from src.schemas.scenario import ScenarioConfig, EnergySharingConfig, TariffConfig


class MarketType(str, Enum):
    """Supported market clearing mechanisms."""
    UNIFORM_PRICE = "uniform_price"
    WEIGHTED = "weighted"
    CARBON_AWARE = "carbon_aware"
    FAIRNESS_AWARE = "fairness_aware"


@dataclass
class BuildingEnergyState:
    """Energy state of a building for market clearing."""
    building_id: str
    net_demand_kw: float  # Positive = needs energy, Negative = has surplus
    pv_generation_kw: float
    battery_power_kw: float  # Positive = discharge, Negative = charge
    battery_soc: float
    max_import_kw: float
    max_export_kw: float
    tariff_config: Optional[TariffConfig] = None


@dataclass
class MarketClearingResult:
    """Result of market clearing."""
    clearing_price: float  # $/kWh
    trades: Dict[str, float]  # building_id -> energy traded (positive = buy, negative = sell)
    settlements: Dict[str, float]  # building_id -> settlement amount ($)
    total_volume_kwh: float
    market_type: MarketType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettlementIntervalResult:
    """Aggregated settlement for an interval (15min/hourly/daily)."""
    interval_start: int
    interval_end: int
    building_settlements: Dict[str, float]  # building_id -> net settlement ($)
    clearing_prices: List[float]
    total_volume_kwh: float


class MarketClearingEngine(ABC):
    """Abstract base class for market clearing engines."""
    
    def __init__(self, scenario_config: ScenarioConfig, energy_sharing_config: EnergySharingConfig):
        self.scenario_config = scenario_config
        self.config = energy_sharing_config
        self.building_ids = [b.building_id for b in scenario_config.buildings]
        self.import_limit = energy_sharing_config.import_limit_kw or float('inf')
        self.export_limit = energy_sharing_config.export_limit_kw or float('inf')
    
    @abstractmethod
    def clear_market(
        self, 
        building_states: Dict[str, BuildingEnergyState],
        timestep: int,
        carbon_intensity: Optional[float] = None
    ) -> MarketClearingResult:
        """Clear the market for one timestep.
        
        Args:
            building_states: Current energy state of each building
            timestep: Current timestep index
            carbon_intensity: Current grid carbon intensity (kgCO2/kWh)
        
        Returns:
            MarketClearingResult with prices, trades, and settlements
        """
        pass
    
    def _validate_trades(self, trades: Dict[str, float]) -> Dict[str, float]:
        """Validate and clip trades to limits."""
        validated = {}
        total_import = 0.0
        total_export = 0.0
        
        for bid, trade in trades.items():
            if trade > 0:  # Buying
                validated[bid] = min(trade, self.import_limit)
                total_import += validated[bid]
            elif trade < 0:  # Selling
                validated[bid] = max(trade, -self.export_limit)
                total_export += -validated[bid]
            else:
                validated[bid] = 0.0
        
        # If total import != total export, scale proportionally
        if abs(total_import - total_export) > 1e-6:
            if total_import > total_export:
                scale = total_export / total_import if total_import > 0 else 0
                for bid, trade in validated.items():
                    if trade > 0:
                        validated[bid] *= scale
            else:
                scale = total_import / total_export if total_export > 0 else 0
                for bid, trade in validated.items():
                    if trade < 0:
                        validated[bid] *= scale
        
        return validated
    
    def _validate_trades_balanced(self, trades: Dict[str, float], target_volume: float) -> Dict[str, float]:
        """Validate trades while preserving buy/sell balance."""
        # Clip to individual limits first
        validated = {}
        total_import = 0.0
        total_export = 0.0
        
        for bid, trade in trades.items():
            if trade > 0:  # Buying
                validated[bid] = min(trade, self.import_limit)
                total_import += validated[bid]
            elif trade < 0:  # Selling
                validated[bid] = max(trade, -self.export_limit)
                total_export += -validated[bid]
            else:
                validated[bid] = 0.0
        
        # If imbalanced, scale proportionally to maintain balance
        if abs(total_import - total_export) > 1e-6:
            if total_import > total_export:
                scale = total_export / total_import if total_import > 0 else 0
                for bid, trade in validated.items():
                    if trade > 0:
                        validated[bid] *= scale
            else:
                scale = total_import / total_export if total_export > 0 else 0
                for bid, trade in validated.items():
                    if trade < 0:
                        validated[bid] *= scale
        
        return validated
    
    def _calculate_settlements(
        self, 
        trades: Dict[str, float], 
        clearing_price: float,
        building_states: Dict[str, BuildingEnergyState]
    ) -> Dict[str, float]:
        """Calculate monetary settlements for each building."""
        settlements = {}
        for bid, trade in trades.items():
            if trade > 0:  # Buying energy
                settlements[bid] = -trade * clearing_price  # Cost
            elif trade < 0:  # Selling energy
                settlements[bid] = -trade * clearing_price  # Revenue (negative trade = positive revenue)
            else:
                settlements[bid] = 0.0
        return settlements


class UniformPriceClearing(MarketClearingEngine):
    """Uniform price (marginal cost) market clearing.
    
    All trades clear at a single price equal to the marginal bid.
    Sellers bid their marginal cost, buyers bid their willingness to pay.
    """
    
    def clear_market(
        self, 
        building_states: Dict[str, BuildingEnergyState],
        timestep: int,
        carbon_intensity: Optional[float] = None
    ) -> MarketClearingResult:
        # Separate buyers and sellers
        buyers = []  # (bid_price, building_id, max_quantity)
        sellers = []  # (ask_price, building_id, max_quantity)
        
        for bid, state in building_states.items():
            if state.net_demand_kw > 1e-3:  # Net buyer
                # Willingness to pay = retail tariff price
                bid_price = self._get_bid_price(state, timestep)
                max_qty = min(state.net_demand_kw, state.max_import_kw, self.import_limit)
                if max_qty > 0:
                    buyers.append((bid_price, bid, max_qty))
            elif state.net_demand_kw < -1e-3:  # Net seller
                # Marginal cost = avoided export tariff (or zero if no export tariff)
                ask_price = self._get_ask_price(state, timestep)
                max_qty = min(-state.net_demand_kw, state.max_export_kw, self.export_limit)
                if max_qty > 0:
                    sellers.append((ask_price, bid, max_qty))
        
        if not buyers or not sellers:
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.UNIFORM_PRICE,
                metadata={"reason": "no_buyers_or_sellers"}
            )
        
        # Sort buyers by bid price descending, sellers by ask price ascending
        buyers.sort(key=lambda x: x[0], reverse=True)
        sellers.sort(key=lambda x: x[0])
        
        # Build supply and demand curves
        supply_qty = np.cumsum([s[2] for s in sellers])
        supply_price = [s[0] for s in sellers]
        demand_qty = np.cumsum([b[2] for b in buyers])
        demand_price = [b[0] for b in buyers]
        
        # Find clearing quantity and price (intersection)
        max_qty = min(supply_qty[-1], demand_qty[-1])
        
        if max_qty <= 1e-6:
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.UNIFORM_PRICE,
                metadata={"reason": "no_overlapping_volume"}
            )
        
        # Find marginal price at clearing quantity
        # Supply side marginal price
        supply_idx = np.searchsorted(supply_qty, max_qty, side='left')
        supply_idx = min(supply_idx, len(supply_price) - 1)
        marginal_supply_price = supply_price[supply_idx]
        
        # Demand side marginal price
        demand_idx = np.searchsorted(demand_qty, max_qty, side='left')
        demand_idx = min(demand_idx, len(demand_price) - 1)
        marginal_demand_price = demand_price[demand_idx]
        
        # Price compatibility check: only clear if demand price >= supply price
        if marginal_demand_price < marginal_supply_price - 1e-6:
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.UNIFORM_PRICE,
                metadata={"reason": "no_price_overlap",
                          "marginal_supply_price": marginal_supply_price,
                          "marginal_demand_price": marginal_demand_price}
            )
        
        # Uniform price = average of marginal supply and demand (or configurable)
        clearing_price = (marginal_supply_price + marginal_demand_price) / 2.0
        
        # Allocate trades at clearing price - single pass to ensure balance
        trades = {b: 0.0 for b in building_states}
        
        # Allocate to sellers (lowest ask first) up to clearing quantity
        remaining = max_qty
        seller_allocations = {}
        for ask_price, bid, max_qty_seller in sellers:
            if remaining <= 1e-6:
                break
            qty = min(max_qty_seller, remaining)
            seller_allocations[bid] = qty
            trades[bid] = -qty
            remaining -= qty
        
        actual_cleared = max_qty - remaining
        
        # Allocate to buyers (highest bid first) to match actual cleared quantity
        remaining = actual_cleared
        for bid_price, bid, max_qty_buyer in buyers:
            if remaining <= 1e-6:
                break
            qty = min(max_qty_buyer, remaining)
            trades[bid] += qty
            remaining -= qty
        
        # Validate trades (clip to limits but preserve balance)
        trades = self._validate_trades_balanced(trades, actual_cleared)
        
        # Convert kW to kWh: multiply by timestep_hours
        timestep_hours = self.scenario_config.timestep_minutes / 60.0
        total_volume_kwh = sum(abs(t) for t in trades.values()) / 2.0 * timestep_hours
        
        # Apply kWh conversion to trades for settlement calculation
        trades_kwh = {b: t * timestep_hours for b, t in trades.items()}
        settlements = self._calculate_settlements(trades_kwh, clearing_price, building_states)
        
        return MarketClearingResult(
            clearing_price=clearing_price,
            trades=trades,  # Keep trades in kW for power flow
            settlements=settlements,
            total_volume_kwh=total_volume_kwh,
            market_type=MarketType.UNIFORM_PRICE,
            metadata={
                "buyers_count": len(buyers),
                "sellers_count": len(sellers),
                "clearing_quantity_kw": max_qty,
                "marginal_supply_price": marginal_supply_price,
                "marginal_demand_price": marginal_demand_price,
            }
        )
    
    def _timestep_to_period(self, timestep: int) -> str:
        """Convert timestep to tariff period (on_peak, mid_peak, off_peak)."""
        current_hour = (timestep * self.scenario_config.timestep_minutes) / 60.0
        hour_of_day = current_hour % 24.0
        if hour_of_day < 7 or hour_of_day >= 23:
            return "off_peak"
        elif hour_of_day < 12 or (hour_of_day >= 18 and hour_of_day < 21):
            return "mid_peak"
        else:
            return "on_peak"
    
    def _get_bid_price(self, state: BuildingEnergyState, timestep: int) -> float:
        """Get buyer's willingness to pay (retail tariff at current timestep)."""
        if state.tariff_config and state.tariff_config.import_prices:
            period = self._timestep_to_period(timestep)
            return state.tariff_config.import_prices.get(period, 0.3)
        return 0.3  # Default $/kWh
    
    def _get_ask_price(self, state: BuildingEnergyState, timestep: int) -> float:
        """Get seller's marginal cost (avoided export tariff at current timestep)."""
        if state.tariff_config and state.tariff_config.export_prices:
            period = self._timestep_to_period(timestep)
            return state.tariff_config.export_prices.get(period, 0.05)
        return 0.05  # Default $/kWh


class WeightedClearing(MarketClearingEngine):
    """Weighted market clearing - pro-rata allocation based on bid/ask quantities."""
    
    def clear_market(
        self, 
        building_states: Dict[str, BuildingEnergyState],
        timestep: int,
        carbon_intensity: Optional[float] = None
    ) -> MarketClearingResult:
        # Use uniform price as base for clearing price reference
        base_engine = UniformPriceClearing(self.scenario_config, self.config)
        base_result = base_engine.clear_market(building_states, timestep, carbon_intensity)
        
        if base_result.total_volume_kwh <= 1e-6:
            # Return result with correct market type even when no volume
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.WEIGHTED,
                metadata={"reason": "no_overlapping_volume", "base_reason": base_result.metadata.get("reason", "unknown")}
            )
        
        # Weighted allocation respecting per-building limits
        trades = {b: 0.0 for b in building_states}
        
        # Collect sellers and buyers with their max quantities respecting limits
        sellers = []  # (building_id, max_qty_kw)
        buyers = []   # (building_id, max_qty_kw)
        
        for bid, state in building_states.items():
            if state.net_demand_kw < -1e-3:  # Net seller
                max_qty = min(-state.net_demand_kw, state.max_export_kw, self.export_limit)
                if max_qty > 0:
                    sellers.append((bid, max_qty))
            elif state.net_demand_kw > 1e-3:  # Net buyer
                max_qty = min(state.net_demand_kw, state.max_import_kw, self.import_limit)
                if max_qty > 0:
                    buyers.append((bid, max_qty))
        
        if not buyers or not sellers:
            return MarketClearingResult(
                clearing_price=0.0,
                trades=trades,
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.WEIGHTED,
                metadata={"reason": "no_buyers_or_sellers"}
            )
        
        total_surplus = sum(qty for _, qty in sellers)
        total_deficit = sum(qty for _, qty in buyers)
        total_volume_kw = min(total_surplus, total_deficit)
        
        if total_volume_kw <= 1e-6:
            return MarketClearingResult(
                clearing_price=0.0,
                trades=trades,
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.WEIGHTED,
                metadata={"reason": "no_overlapping_volume"}
            )
        
        # Pro-rata allocation: each seller/buyer gets proportional share
        for bid, max_qty in sellers:
            weight = max_qty / total_surplus
            trades[bid] = -weight * total_volume_kw
        
        for bid, max_qty in buyers:
            weight = max_qty / total_deficit
            trades[bid] = weight * total_volume_kw
        
        trades = self._validate_trades(trades)
        
        timestep_hours = self.scenario_config.timestep_minutes / 60.0
        total_volume_kwh = sum(abs(t) for t in trades.values()) / 2.0 * timestep_hours
        trades_kwh = {b: t * timestep_hours for b, t in trades.items()}
        clearing_price = base_result.clearing_price
        settlements = self._calculate_settlements(trades_kwh, clearing_price, building_states)
        
        return MarketClearingResult(
            clearing_price=clearing_price,
            trades=trades,
            settlements=settlements,
            total_volume_kwh=total_volume_kwh,
            market_type=MarketType.WEIGHTED,
            metadata={"allocation": "pro_rata", "total_volume_kw": total_volume_kw}
        )


class CarbonAwareClearing(UniformPriceClearing):
    """Carbon-aware market clearing - prioritizes low-carbon energy."""
    
    def clear_market(
        self, 
        building_states: Dict[str, BuildingEnergyState],
        timestep: int,
        carbon_intensity: Optional[float] = None
    ) -> MarketClearingResult:
        # Adjust prices based on carbon intensity
        # Sellers with PV (low carbon) get reduced ask prices
        # Buyers get carbon-adjusted bid prices
        
        if carbon_intensity is None:
            carbon_intensity = 0.5  # Default kgCO2/kWh
        
        # Separate buyers and sellers with carbon-adjusted prices
        buyers = []  # (bid_price, building_id, max_quantity)
        sellers = []  # (ask_price, building_id, max_quantity)
        
        for bid, state in building_states.items():
            if state.net_demand_kw > 1e-3:  # Net buyer
                bid_price = self._get_bid_price(state, timestep)
                # Buyers pay premium for low-carbon energy
                # Add carbon cost to bid price
                adjusted_bid = bid_price + carbon_intensity * 0.1  # Carbon premium
                max_qty = min(state.net_demand_kw, state.max_import_kw, self.import_limit)
                if max_qty > 0:
                    buyers.append((adjusted_bid, bid, max_qty))
            elif state.net_demand_kw < -1e-3:  # Net seller
                ask_price = self._get_ask_price(state, timestep)
                # Sellers with PV get carbon discount (negative carbon cost)
                pv_share = state.pv_generation_kw / max(abs(state.net_demand_kw), 1e-6)
                carbon_discount = carbon_intensity * 0.1 * min(pv_share, 1.0)
                adjusted_ask = max(0.0, ask_price - carbon_discount)
                max_qty = min(-state.net_demand_kw, state.max_export_kw, self.export_limit)
                if max_qty > 0:
                    sellers.append((adjusted_ask, bid, max_qty))
        
        if not buyers or not sellers:
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.CARBON_AWARE,
                metadata={"reason": "no_buyers_or_sellers"}
            )
        
        # Sort buyers by adjusted bid price descending, sellers by adjusted ask price ascending
        buyers.sort(key=lambda x: x[0], reverse=True)
        sellers.sort(key=lambda x: x[0])
        
        # Build supply and demand curves
        supply_qty = np.cumsum([s[2] for s in sellers])
        supply_price = [s[0] for s in sellers]
        demand_qty = np.cumsum([b[2] for b in buyers])
        demand_price = [b[0] for b in buyers]
        
        # Find clearing quantity and price (intersection)
        max_qty = min(supply_qty[-1], demand_qty[-1])
        
        if max_qty <= 1e-6:
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.CARBON_AWARE,
                metadata={"reason": "no_overlapping_volume"}
            )
        
        # Find marginal price at clearing quantity
        supply_idx = np.searchsorted(supply_qty, max_qty, side='left')
        supply_idx = min(supply_idx, len(supply_price) - 1)
        marginal_supply_price = supply_price[supply_idx]
        
        demand_idx = np.searchsorted(demand_qty, max_qty, side='left')
        demand_idx = min(demand_idx, len(demand_price) - 1)
        marginal_demand_price = demand_price[demand_idx]
        
        # Price compatibility check
        if marginal_demand_price < marginal_supply_price - 1e-6:
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.CARBON_AWARE,
                metadata={"reason": "no_price_overlap",
                          "marginal_supply_price": marginal_supply_price,
                          "marginal_demand_price": marginal_demand_price}
            )
        
        clearing_price = (marginal_supply_price + marginal_demand_price) / 2.0
        
        # Allocate trades at clearing price
        trades = {b: 0.0 for b in building_states}
        
        remaining_qty = max_qty
        for ask_price, bid, max_qty_seller in sellers:
            if remaining_qty <= 1e-6:
                break
            qty = min(max_qty_seller, remaining_qty)
            trades[bid] = -qty
            remaining_qty -= qty
        
        remaining_qty = max_qty
        for bid_price, bid, max_qty_buyer in buyers:
            if remaining_qty <= 1e-6:
                break
            qty = min(max_qty_buyer, remaining_qty)
            trades[bid] += qty
            remaining_qty -= qty
        
        trades = self._validate_trades(trades)
        
        timestep_hours = self.scenario_config.timestep_minutes / 60.0
        total_volume_kwh = sum(abs(t) for t in trades.values()) / 2.0 * timestep_hours
        trades_kwh = {b: t * timestep_hours for b, t in trades.items()}
        settlements = self._calculate_settlements(trades_kwh, clearing_price, building_states)
        
        return MarketClearingResult(
            clearing_price=clearing_price,
            trades=trades,
            settlements=settlements,
            total_volume_kwh=total_volume_kwh,
            market_type=MarketType.CARBON_AWARE,
            metadata={
                "buyers_count": len(buyers),
                "sellers_count": len(sellers),
                "clearing_quantity_kw": max_qty,
                "marginal_supply_price": marginal_supply_price,
                "marginal_demand_price": marginal_demand_price,
                "carbon_intensity": carbon_intensity,
            }
        )


class FairnessAwareClearing(UniformPriceClearing):
    """Fairness-aware market clearing - ensures equitable benefit distribution."""
    
    def clear_market(
        self, 
        building_states: Dict[str, BuildingEnergyState],
        timestep: int,
        carbon_intensity: Optional[float] = None
    ) -> MarketClearingResult:
        # Use uniform price as base for clearing price reference
        base_engine = UniformPriceClearing(self.scenario_config, self.config)
        base_result = base_engine.clear_market(building_states, timestep, carbon_intensity)
        
        if base_result.total_volume_kwh <= 1e-6:
            # Return result with correct market type even when no volume
            return MarketClearingResult(
                clearing_price=0.0,
                trades={b: 0.0 for b in building_states},
                settlements={b: 0.0 for b in building_states},
                total_volume_kwh=0.0,
                market_type=MarketType.FAIRNESS_AWARE,
                metadata={"reason": "no_overlapping_volume", "base_reason": base_result.metadata.get("reason", "unknown")}
            )
        
        # Fairness-aware: minimize Gini coefficient of net benefits
        # Net benefit = settlement (revenue for sellers, -cost for buyers)
        # We adjust allocations to reduce inequality
        
        trades = base_result.trades.copy()
        
        # Calculate each building's net benefit from market
        net_benefits = {}
        for bid, trade in trades.items():
            state = building_states[bid]
            if trade > 0:  # Buyer
                # Benefit = avoided grid cost - community cost
                grid_price = self._get_bid_price(state, timestep)
                net_benefits[bid] = trade * (grid_price - base_result.clearing_price)
            elif trade < 0:  # Seller
                # Benefit = community revenue - avoided grid revenue
                grid_price = self._get_ask_price(state, timestep)
                net_benefits[bid] = -trade * (base_result.clearing_price - grid_price)
            else:
                net_benefits[bid] = 0.0
        
        # Iteratively adjust trades to reduce Gini of net benefits
        # while respecting power balance and limits
        for _ in range(10):  # Max 10 iterations
            # Compute Gini of net benefits
            benefits_list = list(net_benefits.values())
            gini = self._gini_coefficient(benefits_list)
            
            if gini < 0.1:  # Already fair enough
                break
            
            # Find building with highest benefit and lowest benefit
            max_bid = max(net_benefits, key=net_benefits.get)
            min_bid = min(net_benefits, key=net_benefits.get)
            
            # Small transfer from max to min if possible
            transfer_kw = 0.01  # Small increment
            max_state = building_states[max_bid]
            min_state = building_states[min_bid]
            
            # Check if transfer respects limits
            can_reduce_max = False
            can_increase_min = False
            
            if trades[max_bid] > 0:  # Max is buyer
                if trades[max_bid] - transfer_kw >= -min_state.max_export_kw:
                    can_reduce_max = True
            elif trades[max_bid] < 0:  # Max is seller
                if trades[max_bid] + transfer_kw <= max_state.max_import_kw:
                    can_reduce_max = True
            
            if trades[min_bid] > 0:  # Min is buyer
                if trades[min_bid] + transfer_kw <= min_state.max_import_kw:
                    can_increase_min = True
            elif trades[min_bid] < 0:  # Min is seller
                if trades[min_bid] - transfer_kw >= -min_state.max_export_kw:
                    can_increase_min = True
            
            if can_reduce_max and can_increase_min:
                trades[max_bid] -= transfer_kw if trades[max_bid] > 0 else -transfer_kw
                trades[min_bid] += transfer_kw if trades[min_bid] > 0 else -transfer_kw
            else:
                break
        
        trades = self._validate_trades(trades)
        
        timestep_hours = self.scenario_config.timestep_minutes / 60.0
        total_volume_kwh = sum(abs(t) for t in trades.values()) / 2.0 * timestep_hours
        trades_kwh = {b: t * timestep_hours for b, t in trades.items()}
        settlements = self._calculate_settlements(trades_kwh, base_result.clearing_price, building_states)
        
        return MarketClearingResult(
            clearing_price=base_result.clearing_price,
            trades=trades,
            settlements=settlements,
            total_volume_kwh=total_volume_kwh,
            market_type=MarketType.FAIRNESS_AWARE,
            metadata={"fairness_adjustment": True, "gini_before": self._gini_coefficient(list(base_result.settlements.values()))}
        )
    
    def _gini_coefficient(self, values: list) -> float:
        """Calculate Gini coefficient."""
        if not values or len(values) < 2:
            return 0.0
        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = np.cumsum(sorted_values)
        return (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n if cumsum[-1] > 0 else 0.0


def create_market_engine(
    scenario_config: ScenarioConfig, 
    energy_sharing_config: EnergySharingConfig
) -> MarketClearingEngine:
    """Factory function to create market clearing engine."""
    market_type = MarketType(energy_sharing_config.market_type)
    
    engines = {
        MarketType.UNIFORM_PRICE: UniformPriceClearing,
        MarketType.WEIGHTED: WeightedClearing,
        MarketType.CARBON_AWARE: CarbonAwareClearing,
        MarketType.FAIRNESS_AWARE: FairnessAwareClearing,
    }
    
    engine_class = engines.get(market_type, UniformPriceClearing)
    return engine_class(scenario_config, energy_sharing_config)