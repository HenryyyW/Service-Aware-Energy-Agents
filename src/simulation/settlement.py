"""Settlement computation and aggregation for local energy sharing."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict
import numpy as np

from src.schemas.scenario import ScenarioConfig, EnergySharingConfig, TariffConfig
from .market import MarketClearingResult, create_market_engine, BuildingEnergyState


@dataclass
class BuildingSettlement:
    """Per-building settlement tracking."""
    building_id: str
    net_settlement: float = 0.0  # Positive = revenue, Negative = cost
    total_bought_kwh: float = 0.0
    total_sold_kwh: float = 0.0
    total_grid_import_kwh: float = 0.0
    total_grid_export_kwh: float = 0.0
    baseline_grid_import_kwh: float = 0.0
    baseline_grid_export_kwh: float = 0.0
    peak_grid_import_kw: float = 0.0
    baseline_peak_grid_import_kw: float = 0.0
    demand_charge_rate: float = 0.0
    actual_demand_charge: float = 0.0
    baseline_demand_charge: float = 0.0
    total_community_import_kwh: float = 0.0
    total_community_export_kwh: float = 0.0
    total_grid_import_cost: float = 0.0
    total_grid_export_revenue: float = 0.0
    baseline_grid_import_cost: float = 0.0
    baseline_grid_export_revenue: float = 0.0
    total_community_import_cost: float = 0.0
    total_community_export_revenue: float = 0.0
    # LMP-specific fields
    cost_basis: str = "tariff"  # "tariff" or "lmp"
    lmp_cost_usd: float = 0.0  # Total cost billed at building LMP
    lmp_revenue_usd: float = 0.0  # Total revenue at building LMP
    interval_settlements: Dict[int, float] = field(default_factory=dict)  # interval_idx -> settlement
    clearing_prices: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettlementResult:
    """Complete settlement result for a simulation run."""
    building_settlements: Dict[str, BuildingSettlement]
    interval_results: List['IntervalSettlementResult']
    total_community_volume_kwh: float
    total_community_revenue: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntervalSettlementResult:
    """Settlement for one interval (15min/hourly/daily)."""
    interval_idx: int
    start_timestep: int
    end_timestep: int
    building_settlements: Dict[str, float]
    clearing_prices: List[float]
    total_volume_kwh: float
    avg_clearing_price: float


class SettlementEngine:
    """Engine for computing and accumulating settlements over simulation."""
    
    def __init__(
        self, 
        scenario_config: ScenarioConfig, 
        energy_sharing_config: EnergySharingConfig
    ):
        self.scenario_config = scenario_config
        self.config = energy_sharing_config
        self.building_ids = [b.building_id for b in scenario_config.buildings]
        self.timestep_minutes = scenario_config.timestep_minutes
        self.settlement_interval = self._parse_interval(energy_sharing_config.settlement_interval)
        
        # Initialize per-building settlement tracking
        self.building_settlements = {
            bid: BuildingSettlement(building_id=bid) 
            for bid in self.building_ids
        }
        
        # Market clearing engine
        self.market_engine = create_market_engine(scenario_config, energy_sharing_config)
        
        # Interval tracking
        self.interval_results: List[IntervalSettlementResult] = []
        self.current_interval_idx = 0
        self.interval_start_timestep = 0
        self.interval_clearing_prices: List[float] = []
        self.interval_trades: Dict[int, Dict[str, float]] = defaultdict(dict)
        self.interval_settlements: Dict[int, Dict[str, float]] = defaultdict(dict)
        self.total_community_volume_kwh = 0.0
    
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
    
    def _parse_interval(self, interval_str: str) -> int:
        """Parse settlement interval string to number of timesteps."""
        if interval_str.endswith("min"):
            minutes = int(interval_str[:-3])
        elif interval_str.endswith("h"):
            minutes = int(interval_str[:-1]) * 60
        elif interval_str.endswith("hour") or interval_str.endswith("hourly"):
            minutes = int(interval_str[:-4] if interval_str.endswith("hour") else interval_str[:-6]) * 60
        elif interval_str.endswith("d"):
            minutes = int(interval_str[:-1]) * 24 * 60
        elif interval_str.endswith("day") or interval_str.endswith("daily"):
            minutes = int(interval_str[:-3] if interval_str.endswith("day") else interval_str[:-5]) * 24 * 60
        else:
            minutes = 15  # Default 15 minutes
        
        return max(1, minutes // self.timestep_minutes)
    
    def process_timestep(
        self,
        timestep: int,
        building_states: Dict[str, BuildingEnergyState],
        grid_imports: Dict[str, float],  # Positive = import from grid
        grid_exports: Dict[str, float],  # Positive = export to grid
        carbon_intensity: Optional[float] = None
    ) -> MarketClearingResult:
        """Process one timestep: clear market, update settlements."""
        
        # Clear market
        market_result = self.market_engine.clear_market(
            building_states, timestep, carbon_intensity
        )
        
        # Update building settlement tracking
        timestep_hours = self.scenario_config.timestep_minutes / 60.0
        for bid, settlement in self.building_settlements.items():
            trade_kw = market_result.trades.get(bid, 0.0)
            trade_kwh = trade_kw * timestep_hours
            
            if trade_kw > 0:  # Bought from community
                settlement.total_bought_kwh += trade_kwh
                settlement.total_community_import_kwh += trade_kwh
            elif trade_kw < 0:  # Sold to community
                settlement.total_sold_kwh += -trade_kwh
                settlement.total_community_export_kwh += -trade_kwh
            
            # Inputs are the no-sharing grid flows; trades offset those flows.
            baseline_import_kw = max(0.0, grid_imports.get(bid, 0.0))
            baseline_export_kw = max(0.0, grid_exports.get(bid, 0.0))
            actual_import_kw = max(0.0, baseline_import_kw - max(trade_kw, 0.0))
            actual_export_kw = max(0.0, baseline_export_kw - max(-trade_kw, 0.0))
            baseline_import_kwh = baseline_import_kw * timestep_hours
            baseline_export_kwh = baseline_export_kw * timestep_hours
            actual_import_kwh = actual_import_kw * timestep_hours
            actual_export_kwh = actual_export_kw * timestep_hours
            settlement.baseline_grid_import_kwh += baseline_import_kwh
            settlement.baseline_grid_export_kwh += baseline_export_kwh
            settlement.total_grid_import_kwh += actual_import_kwh
            settlement.total_grid_export_kwh += actual_export_kwh
            settlement.baseline_peak_grid_import_kw = max(
                settlement.baseline_peak_grid_import_kw, baseline_import_kw
            )
            settlement.peak_grid_import_kw = max(
                settlement.peak_grid_import_kw, actual_import_kw
            )

            # Track baseline and post-trade grid bills at this timestep's tariff.
            state = building_states.get(bid)
            tariff = state.tariff_config if state else None
            period = self._timestep_to_period(timestep)
            import_price = tariff.import_prices.get(period, 0.3) if tariff else 0.3
            export_price = tariff.export_prices.get(period, 0.05) if tariff else 0.05
            settlement.demand_charge_rate = tariff.demand_charge if tariff else 0.0
            settlement.baseline_grid_import_cost += baseline_import_kwh * import_price
            settlement.baseline_grid_export_revenue += baseline_export_kwh * export_price
            settlement.total_grid_import_cost += actual_import_kwh * import_price
            settlement.total_grid_export_revenue += actual_export_kwh * export_price
            
            # Determine cost basis and billing price
            is_lmp_regime = (self.config.market_type == "lmp" and 
                            self.config.dynamic_pricing is not None and 
                            self.config.dynamic_pricing.enabled)
            
            if is_lmp_regime and state and state.lmp_price is not None:
                # Bill at building's LMP price
                settlement.cost_basis = "lmp"
                lmp_price = state.lmp_price
                # Grid import/export billed at LMP
                settlement.total_grid_import_cost = actual_import_kwh * lmp_price
                settlement.total_grid_export_revenue = actual_export_kwh * lmp_price
                # Track LMP-specific costs
                settlement.lmp_cost_usd += actual_import_kwh * lmp_price
                settlement.lmp_revenue_usd += actual_export_kwh * lmp_price
            else:
                settlement.cost_basis = "tariff"
            
            # Settlement (community trades)
            settlement_amount = market_result.settlements.get(bid, 0.0)
            settlement.net_settlement += settlement_amount
            if settlement_amount < 0:
                settlement.total_community_import_cost += -settlement_amount
            else:
                settlement.total_community_export_revenue += settlement_amount
            
            # Track clearing price
            if market_result.clearing_price > 0:
                settlement.clearing_prices.append(market_result.clearing_price)
        
        # Track interval data
        self.interval_clearing_prices.append(market_result.clearing_price)
        for bid, trade in market_result.trades.items():
            self.interval_trades[timestep][bid] = trade
        for bid, settlement_amt in market_result.settlements.items():
            self.interval_settlements[timestep][bid] = settlement_amt
        
        # Check if interval ended
        if (timestep + 1) % self.settlement_interval == 0:
            self._finalize_interval(timestep)
        
        return market_result
    
    def _finalize_interval(self, timestep: int):
        """Finalize current settlement interval."""
        interval_end = timestep
        interval_start = self.interval_start_timestep
        
        # Aggregate building settlements for this interval
        interval_building_settlements = {}
        for bid in self.building_ids:
            # Sum settlements in this interval
            interval_settlement = sum(
                self.interval_settlements[ts].get(bid, 0.0)
                for ts in range(interval_start, interval_end + 1)
            )
            interval_building_settlements[bid] = interval_settlement
            
            # Store in building settlement
            self.building_settlements[bid].interval_settlements[self.current_interval_idx] = interval_settlement
        
        # Calculate interval stats
        valid_prices = [p for p in self.interval_clearing_prices if p > 0]
        avg_price = float(np.mean(valid_prices)) if valid_prices else 0.0
        total_volume = sum(
            abs(trade) 
            for ts in range(interval_start, interval_end + 1)
            for trade in self.interval_trades[ts].values()
        ) / 2.0 * (self.timestep_minutes / 60.0)
        
        interval_result = IntervalSettlementResult(
            interval_idx=self.current_interval_idx,
            start_timestep=interval_start,
            end_timestep=interval_end,
            building_settlements=interval_building_settlements,
            clearing_prices=self.interval_clearing_prices.copy(),
            total_volume_kwh=total_volume,
            avg_clearing_price=avg_price
        )
        
        self.interval_results.append(interval_result)
        
        # Reset for next interval
        self.current_interval_idx += 1
        self.interval_start_timestep = timestep + 1
        self.interval_clearing_prices.clear()
    
    def finalize(self) -> SettlementResult:
        """Finalize any partial interval and compute final results."""
        # Finalize last partial interval if needed
        last_timestep = max(self.interval_trades.keys()) if self.interval_trades else 0
        if last_timestep >= self.interval_start_timestep:
            self._finalize_interval(last_timestep)
        
        # Compute totals
        total_volume = sum(r.total_volume_kwh for r in self.interval_results)
        self.total_community_volume_kwh = total_volume  # Store for community metrics
        total_revenue = sum(s.net_settlement for s in self.building_settlements.values())
        
        # Calculate savings vs. no-sharing baseline
        for settlement in self.building_settlements.values():
            settlement.metadata["savings_vs_baseline"] = self._calculate_savings(settlement)
            settlement.metadata["self_sufficiency"] = self._calculate_self_sufficiency(settlement)
        
        return SettlementResult(
            building_settlements=self.building_settlements,
            interval_results=self.interval_results,
            total_community_volume_kwh=total_volume,
            total_community_revenue=total_revenue,
            metadata={
                "num_intervals": len(self.interval_results),
                "settlement_interval_timesteps": self.settlement_interval,
                "timestep_minutes": self.timestep_minutes,
                "market_type": self.config.market_type,
            }
        )
    
    def _calculate_savings(self, settlement: BuildingSettlement) -> float:
        """Calculate savings vs. baseline (no community sharing)."""
        baseline_bill = (
            settlement.baseline_grid_import_cost
            - settlement.baseline_grid_export_revenue
            + settlement.baseline_peak_grid_import_kw * settlement.demand_charge_rate
        )
        settlement.baseline_demand_charge = (
            settlement.baseline_peak_grid_import_kw * settlement.demand_charge_rate
        )
        settlement.actual_demand_charge = (
            settlement.peak_grid_import_kw * settlement.demand_charge_rate
        )
        actual_grid_bill = (
            settlement.total_grid_import_cost
            - settlement.total_grid_export_revenue
            + settlement.actual_demand_charge
        )
        actual_total_bill = (
            actual_grid_bill
            + settlement.total_community_import_cost
            - settlement.total_community_export_revenue
        )
        settlement.metadata.update({
            "baseline_grid_bill": baseline_bill,
            "actual_grid_bill": actual_grid_bill,
            "actual_total_bill": actual_total_bill,
        })
        return baseline_bill - actual_total_bill
    
    def _calculate_self_sufficiency(self, settlement: BuildingSettlement) -> float:
        """Calculate self-sufficiency ratio (community energy / total energy)."""
        total_community = settlement.total_community_import_kwh
        total_energy = settlement.total_grid_import_kwh + settlement.total_community_import_kwh
        if total_energy <= 0:
            return 1.0
        return min(1.0, total_community / total_energy)
    
    def get_building_savings(self) -> Dict[str, float]:
        """Get per-building savings vs. baseline."""
        return {
            bid: self._calculate_savings(s)
            for bid, s in self.building_settlements.items()
        }
    
    def get_community_metrics(self) -> Dict[str, float]:
        """Get community-level metrics."""
        total_import = sum(s.total_grid_import_kwh for s in self.building_settlements.values())
        total_export = sum(s.total_grid_export_kwh for s in self.building_settlements.values())
        total_community = sum(s.total_community_import_kwh for s in self.building_settlements.values())
        baseline_grid_bill = sum(
            s.baseline_grid_import_cost
            - s.baseline_grid_export_revenue
            + s.baseline_peak_grid_import_kw * s.demand_charge_rate
            for s in self.building_settlements.values()
        )
        actual_grid_bill = sum(
            s.total_grid_import_cost
            - s.total_grid_export_revenue
            + s.peak_grid_import_kw * s.demand_charge_rate
            for s in self.building_settlements.values()
        )
        actual_total_bill = sum(
            s.total_grid_import_cost
            - s.total_grid_export_revenue
            + s.peak_grid_import_kw * s.demand_charge_rate
            + s.total_community_import_cost
            - s.total_community_export_revenue
            for s in self.building_settlements.values()
        )
        
        # LMP-specific metrics
        lmp_costs = [s.lmp_cost_usd for s in self.building_settlements.values() if s.cost_basis == "lmp"]
        lmp_prices = []
        for s in self.building_settlements.values():
            if s.cost_basis == "lmp" and s.total_grid_import_kwh > 0:
                lmp_prices.append(s.lmp_cost_usd / s.total_grid_import_kwh)
            elif s.cost_basis == "lmp" and s.total_grid_export_kwh > 0:
                lmp_prices.append(s.lmp_revenue_usd / s.total_grid_export_kwh)
        
        lmp_price_mean = float(np.mean(lmp_prices)) if lmp_prices else 0.0
        lmp_price_spread = float(np.max(lmp_prices) - np.min(lmp_prices)) if lmp_prices else 0.0
        lmp_price_spread_pct = (lmp_price_spread / lmp_price_mean * 100) if lmp_price_mean > 0 else 0.0
        
        return {
            "total_grid_import_kwh": total_import,
            "total_grid_export_kwh": total_export,
            "total_community_volume_kwh": total_community,
            "community_self_sufficiency": total_community / (total_import + total_community) if (total_import + total_community) > 0 else 0.0,
            "total_settlement_volume_kwh": self.total_community_volume_kwh,
            "baseline_grid_bill": baseline_grid_bill,
            "actual_grid_bill": actual_grid_bill,
            "actual_total_bill": actual_total_bill,
            "total_savings_vs_baseline": sum(self.get_building_savings().values()),
            "avg_clearing_price": np.mean([
                s for s in self.building_settlements.values() 
                for s in s.clearing_prices if s > 0
            ]) if any(s.clearing_prices for s in self.building_settlements.values()) else 0.0,
            # LMP metrics
            "lmp_price_mean": lmp_price_mean,
            "lmp_price_spread": lmp_price_spread,
            "lmp_price_spread_pct": lmp_price_spread_pct,
            "lmp_total_cost_usd": sum(lmp_costs),
            "lmp_regime_buildings": len(lmp_costs),
        }


def create_settlement_engine(
    scenario_config: ScenarioConfig,
    energy_sharing_config: EnergySharingConfig
) -> SettlementEngine:
    """Factory function to create settlement engine."""
    return SettlementEngine(scenario_config, energy_sharing_config)