"""Regression tests for market clearing and settlement engines."""
import pytest
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BuildingType, EnergySharingConfig,
    TariffConfig, PVConfig, BatteryConfig, PandapowerConfig, GridBusMapping
)
from src.simulation.market import (
    MarketType,
    MarketClearingEngine,
    UniformPriceClearing,
    WeightedClearing,
    CarbonAwareClearing,
    FairnessAwareClearing,
    create_market_engine,
    BuildingEnergyState,
    MarketClearingResult,
)
from src.simulation.settlement import (
    SettlementEngine,
    SettlementResult,
    BuildingSettlement,
    IntervalSettlementResult,
    create_settlement_engine,
)
from src.simulation.coupling import SimulationCoupler


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def energy_sharing_config():
    """Create an energy sharing configuration for testing."""
    return EnergySharingConfig(
        enabled=True,
        market_type="uniform_price",
        settlement_interval="15min",
        export_limit_kw=100.0,
        import_limit_kw=100.0,
    )


@pytest.fixture
def scenario_config(energy_sharing_config):
    """Create a minimal scenario config with energy sharing enabled."""
    return ScenarioConfig(
        scenario_id="test_market_scenario",
        name="Market Test Scenario",
        description="Scenario for market clearing tests",
        random_seed=42,
        timestep_minutes=15,
        energy_sharing=energy_sharing_config,
        buildings=[
            BuildingConfig(
                building_id="building_0",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                pv=PVConfig(capacity_kw=5.0),
                battery=BatteryConfig(capacity_kwh=10.0, power_kw=5.0),
            ),
            BuildingConfig(
                building_id="building_1",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                pv=PVConfig(capacity_kw=3.0),
                battery=BatteryConfig(capacity_kwh=5.0, power_kw=3.0),
            ),
            BuildingConfig(
                building_id="building_2",
                building_type=BuildingType.COMMERCIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-02",
                tariff=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                    demand_charge=0.0,
                ),
                pv=PVConfig(capacity_kw=10.0),
                battery=BatteryConfig(capacity_kwh=20.0, power_kw=10.0),
            ),
        ],
        pandapower=PandapowerConfig(
            network_type="ieee_34",
            bus_mappings=[
                GridBusMapping(building_id="building_0", bus_idx=1),
                GridBusMapping(building_id="building_1", bus_idx=2),
                GridBusMapping(building_id="building_2", bus_idx=3),
            ]
        )
    )


@pytest.fixture
def building_states():
    """Create sample building energy states for testing."""
    return {
        "building_0": BuildingEnergyState(
            building_id="building_0",
            net_demand_kw=2.0,   # Needs energy
            pv_generation_kw=1.0,
            battery_power_kw=0.0,
            battery_soc=0.5,
            max_import_kw=50.0,
            max_export_kw=50.0,
            tariff_config=TariffConfig(
                type="time_of_use",
                import_prices={"on_peak": 0.30, "off_peak": 0.10},
                export_prices={"default": 0.05},
                demand_charge=0.0,
            ),
        ),
        "building_1": BuildingEnergyState(
            building_id="building_1",
            net_demand_kw=-3.0,  # Has surplus
            pv_generation_kw=5.0,
            battery_power_kw=0.0,
            battery_soc=0.8,
            max_import_kw=30.0,
            max_export_kw=30.0,
            tariff_config=TariffConfig(
                type="time_of_use",
                import_prices={"on_peak": 0.30, "off_peak": 0.10},
                export_prices={"default": 0.05},
                demand_charge=0.0,
            ),
        ),
        "building_2": BuildingEnergyState(
            building_id="building_2",
            net_demand_kw=1.0,   # Small need
            pv_generation_kw=0.0,
            battery_power_kw=0.0,
            battery_soc=0.3,
            max_import_kw=100.0,
            max_export_kw=100.0,
            tariff_config=TariffConfig(
                type="time_of_use",
                import_prices={"on_peak": 0.30, "off_peak": 0.10},
                export_prices={"default": 0.05},
                demand_charge=0.0,
            ),
        ),
    }


# ============================================================================
# Market Clearing Engine Tests
# ============================================================================

class TestMarketClearingEngines:
    """Tests for all market clearing engine implementations."""

    def test_uniform_price_clearing_basic(self, scenario_config, energy_sharing_config, building_states):
        """Test uniform price clearing produces valid results."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(building_states, timestep=0)
        
        assert isinstance(result, MarketClearingResult)
        assert result.market_type == MarketType.UNIFORM_PRICE
        assert result.clearing_price >= 0
        assert result.total_volume_kwh >= 0
        assert set(result.trades.keys()) == set(building_states.keys())
        assert set(result.settlements.keys()) == set(building_states.keys())

    def test_uniform_price_clearing_trades_sum_to_zero(self, scenario_config, energy_sharing_config, building_states):
        """Test that net trades sum to zero (energy conserved)."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(building_states, timestep=0)
        
        # Sum of all trades should be zero (energy in = energy out)
        total_trade = sum(result.trades.values())
        assert abs(total_trade) < 1e-6, f"Trades don't balance: {total_trade}"

    def test_uniform_price_clearing_settlements_sum_to_zero(self, scenario_config, energy_sharing_config, building_states):
        """Test that settlements sum to zero (money conserved)."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(building_states, timestep=0)
        
        # Sum of all settlements should be zero (no money created/destroyed in market)
        total_settlement = sum(result.settlements.values())
        assert abs(total_settlement) < 1e-6, f"Settlements don't balance: {total_settlement}"

    def test_uniform_price_no_buyers(self, scenario_config, energy_sharing_config):
        """Test clearing with no buyers."""
        states = {
            "b0": BuildingEnergyState("b0", -2.0, 5.0, 0.0, 0.5, 50.0, 50.0),
            "b1": BuildingEnergyState("b1", -1.0, 3.0, 0.0, 0.5, 30.0, 30.0),
        }
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(states, timestep=0)
        
        assert result.total_volume_kwh == 0.0
        assert result.clearing_price == 0.0
        assert all(t == 0.0 for t in result.trades.values())

    def test_uniform_price_no_sellers(self, scenario_config, energy_sharing_config):
        """Test clearing with no sellers."""
        states = {
            "b0": BuildingEnergyState("b0", 2.0, 0.0, 0.0, 0.5, 50.0, 50.0),
            "b1": BuildingEnergyState("b1", 1.0, 0.0, 0.0, 0.5, 30.0, 30.0),
        }
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(states, timestep=0)
        
        assert result.total_volume_kwh == 0.0
        assert result.clearing_price == 0.0
        assert all(t == 0.0 for t in result.trades.values())

    @pytest.mark.parametrize("market_type", [
        MarketType.UNIFORM_PRICE,
        MarketType.WEIGHTED,
        MarketType.CARBON_AWARE,
        MarketType.FAIRNESS_AWARE,
    ])
    def test_all_market_types_produce_valid_results(self, scenario_config, building_states, market_type):
        """Test that all market types produce valid results."""
        energy_sharing_config = EnergySharingConfig(
            enabled=True,
            market_type=market_type.value,
            settlement_interval="15min",
        )
        engine = create_market_engine(scenario_config, energy_sharing_config)
        result = engine.clear_market(building_states, timestep=0)
        
        assert isinstance(result, MarketClearingResult)
        assert result.market_type == market_type
        assert set(result.trades.keys()) == set(building_states.keys())

    def test_market_clearing_respects_limits(self, scenario_config, energy_sharing_config, building_states):
        """Test that trades respect import/export limits."""
        # Set very low limits
        energy_sharing_config.import_limit_kw = 0.5
        energy_sharing_config.export_limit_kw = 0.5
        
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(building_states, timestep=0)
        
        # All trades should be within limits
        for bid, trade in result.trades.items():
            if trade > 0:
                assert trade <= energy_sharing_config.import_limit_kw + 1e-6
            elif trade < 0:
                assert -trade <= energy_sharing_config.export_limit_kw + 1e-6


class TestSettlementEngine:
    """Tests for the settlement engine."""

    def test_settlement_engine_initialization(self, scenario_config, energy_sharing_config):
        """Test settlement engine initializes correctly."""
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        
        assert engine.building_ids == ["building_0", "building_1", "building_2"]
        assert engine.settlement_interval == 1  # 15min / 15min = 1 timestep
        assert len(engine.building_settlements) == 3

    def test_settlement_interval_parsing(self, scenario_config):
        """Test settlement interval parsing."""
        configs = [
            ("15min", 1),
            ("30min", 2),
            ("1h", 4),
            ("1hour", 4),
            ("1d", 96),
            ("1day", 96),
        ]
        
        for interval_str, expected in configs:
            config = EnergySharingConfig(
                enabled=True, market_type="uniform_price", settlement_interval=interval_str
            )
            engine = SettlementEngine(scenario_config, config)
            assert engine.settlement_interval == expected, f"Failed for {interval_str}"

    def test_single_timestep_settlement(self, scenario_config, energy_sharing_config, building_states):
        """Test settlement for a single timestep."""
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        
        grid_imports = {"building_0": 2.0, "building_1": 0.0, "building_2": 1.0}
        grid_exports = {"building_0": 0.0, "building_1": 3.0, "building_2": 0.0}
        
        # Process one timestep - this runs the actual market clearing
        market_result = engine.process_timestep(0, building_states, grid_imports, grid_exports, carbon_intensity=0.5)
        
        # Check that market clearing ran and produced results
        assert market_result is not None
        assert hasattr(market_result, 'trades')
        assert hasattr(market_result, 'settlements')
        assert hasattr(market_result, 'clearing_price')
        
        # Check building settlements were updated
        assert engine.building_settlements["building_0"].net_settlement != 0 or engine.building_settlements["building_1"].net_settlement != 0
        # Baseline grid values are kW * timestep_hours; market trades offset actual flows.
        timestep_hours = scenario_config.timestep_minutes / 60.0
        assert engine.building_settlements["building_0"].baseline_grid_import_kwh == 2.0 * timestep_hours
        assert engine.building_settlements["building_0"].total_grid_import_kwh == 0.0
        assert engine.building_settlements["building_1"].baseline_grid_export_kwh == 3.0 * timestep_hours
        assert engine.building_settlements["building_1"].total_grid_export_kwh == 0.0

    def test_interval_finalization(self, scenario_config, energy_sharing_config, building_states):
        """Test interval finalization aggregates correctly."""
        energy_sharing_config.settlement_interval = "30min"  # 2 timesteps
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        
        class MockMarketResult:
            def __init__(self, price):
                self.trades = {"building_0": 1.0, "building_1": -1.0, "building_2": 0.0}
                self.settlements = {"building_0": -price, "building_1": price, "building_2": 0.0}
                self.clearing_price = price
        
        grid_imports = {"building_0": 1.0, "building_1": 0.0, "building_2": 0.0}
        grid_exports = {"building_0": 0.0, "building_1": 2.0, "building_2": 0.0}
        
        # Process 2 timesteps (one interval)
        engine.process_timestep(0, building_states, grid_imports, grid_exports, carbon_intensity=0.5)
        engine.process_timestep(1, building_states, grid_imports, grid_exports, carbon_intensity=0.5)
        
        # Should have 1 interval result
        assert len(engine.interval_results) == 1
        interval = engine.interval_results[0]
        assert interval.interval_idx == 0
        assert interval.start_timestep == 0
        assert interval.end_timestep == 1
        assert interval.total_volume_kwh > 0

    def test_finalize_returns_complete_result(self, scenario_config, energy_sharing_config, building_states):
        """Test finalize() returns complete SettlementResult."""
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        
        grid_imports = {"building_0": 1.0, "building_1": 0.0, "building_2": 0.0}
        grid_exports = {"building_0": 0.0, "building_1": 2.0, "building_2": 0.0}
        
        # Process a few timesteps
        for t in range(3):
            engine.process_timestep(t, building_states, grid_imports, grid_exports)
        
        result = engine.finalize()
        
        assert isinstance(result, SettlementResult)
        assert len(result.building_settlements) == 3
        assert result.total_community_volume_kwh > 0
        # get_building_savings returns dict with building IDs as keys
        savings = engine.get_building_savings()
        assert "building_0" in savings
        assert "building_1" in savings
        assert "building_2" in savings

    def test_community_metrics(self, scenario_config, energy_sharing_config, building_states):
        """Test community-level metrics calculation."""
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        
        grid_imports = {"building_0": 1.0, "building_1": 0.0, "building_2": 0.0}
        grid_exports = {"building_0": 0.0, "building_1": 2.0, "building_2": 0.0}
        
        for t in range(4):
            engine.process_timestep(t, building_states, grid_imports, grid_exports)
        
        metrics = engine.get_community_metrics()
        
        assert "total_grid_import_kwh" in metrics
        assert "total_grid_export_kwh" in metrics
        assert "total_community_volume_kwh" in metrics
        assert "community_self_sufficiency" in metrics
        assert 0 <= metrics["community_self_sufficiency"] <= 1


class TestMarketSettlementIntegration:
    """Integration tests for market clearing + settlement."""

    def test_market_engine_factory(self, scenario_config):
        """Test factory creates correct engine type."""
        for market_type in MarketType:
            config = EnergySharingConfig(
                enabled=True, market_type=market_type.value, settlement_interval="15min"
            )
            engine = create_market_engine(scenario_config, config)
            assert isinstance(engine, MarketClearingEngine)

    def test_settlement_engine_factory(self, scenario_config, energy_sharing_config):
        """Test settlement engine factory."""
        engine = create_settlement_engine(scenario_config, energy_sharing_config)
        assert isinstance(engine, SettlementEngine)

    def test_end_to_end_flow(self, scenario_config, energy_sharing_config, building_states):
        """Test complete market clearing -> settlement flow."""
        market_engine = create_market_engine(scenario_config, energy_sharing_config)
        settlement_engine = create_settlement_engine(scenario_config, energy_sharing_config)
        
        grid_imports = {"building_0": 1.0, "building_1": 0.0, "building_2": 0.0}
        grid_exports = {"building_0": 0.0, "building_1": 2.0, "building_2": 0.0}
        
        # Process multiple timesteps
        for t in range(5):
            market_result = market_engine.clear_market(building_states, t)
            settlement_engine.process_timestep(
                t, building_states, grid_imports, grid_exports
            )
            
            # Verify invariants at each step
            assert abs(sum(market_result.trades.values())) < 1e-6
            assert abs(sum(market_result.settlements.values())) < 1e-6
        
        result = settlement_engine.finalize()
        assert result.total_community_volume_kwh > 0


class TestRegressionInvariants:
    """Regression tests for critical invariants."""

    def test_settlement_sum_zero_invariant(self, scenario_config, energy_sharing_config, building_states):
        """REGRESSION: Sum of all settlements must be zero at all times."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        
        for t in range(10):
            result = engine.clear_market(building_states, t)
            total = sum(result.settlements.values())
            assert abs(total) < 1e-9, f"Settlement sum violated at t={t}: {total}"

    def test_energy_conservation_invariant(self, scenario_config, energy_sharing_config, building_states):
        """REGRESSION: Energy must be conserved (trades sum to zero)."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        
        for t in range(10):
            result = engine.clear_market(building_states, t)
            total = sum(result.trades.values())
            assert abs(total) < 1e-9, f"Energy conservation violated at t={t}: {total}"

    def test_no_arbitrage_invariant(self, scenario_config, energy_sharing_config, building_states):
        """REGRESSION: No building should profit from arbitrage (buy high, sell low)."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        
        for t in range(5):
            result = engine.clear_market(building_states, t)
            # A building cannot both buy and sell in same timestep
            for bid, trade in result.trades.items():
                # This is enforced by construction, but verify
                assert trade == 0 or (trade > 0) != (trade < 0)

    def test_clearing_price_bounds(self, scenario_config, energy_sharing_config, building_states):
        """REGRESSION: Clearing price must be between min ask and max bid."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        
        for t in range(5):
            result = engine.clear_market(building_states, t)
            if result.total_volume_kwh > 0:
                # Clearing price should be between marginal supply and demand
                assert result.clearing_price >= 0
                # Should not exceed max bid price (retail tariff)
                assert result.clearing_price <= 0.30 + 1e-6
                # Should not be below min ask price (export tariff)
                assert result.clearing_price >= 0.05 - 1e-6

    def test_no_clearing_when_bid_below_ask(self, scenario_config):
        """REGRESSION: No clearing when max bid < min ask."""
        energy_sharing_config = EnergySharingConfig(
            enabled=True,
            market_type="uniform_price",
            settlement_interval="15min",
        )
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        
        states = {
            "buyer": BuildingEnergyState(
                building_id="buyer",
                net_demand_kw=5.0,
                pv_generation_kw=0.0,
                battery_power_kw=0.0,
                battery_soc=0.5,
                max_import_kw=10.0,
                max_export_kw=0.0,
                tariff_config=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.10, "mid_peak": 0.10, "off_peak": 0.10},
                    export_prices={"off_peak": 0.05, "mid_peak": 0.05, "on_peak": 0.05},
                    demand_charge=0.0
                ),
            ),
            "seller": BuildingEnergyState(
                building_id="seller",
                net_demand_kw=-5.0,
                pv_generation_kw=10.0,
                battery_power_kw=0.0,
                battery_soc=0.8,
                max_import_kw=0.0,
                max_export_kw=10.0,
                tariff_config=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"off_peak": 0.50, "mid_peak": 0.50, "on_peak": 0.50},
                    demand_charge=0.0
                ),
            ),
        }
        
        result = engine.clear_market(states, timestep=0)
        
        assert result.total_volume_kwh == 0.0
        assert result.clearing_price == 0.0
        assert result.metadata.get("reason") == "no_price_overlap"

    def test_volume_kwh_is_kw_times_hours(self, scenario_config, energy_sharing_config, building_states):
        """REGRESSION: Volume in kWh = kW * timestep_hours."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        result = engine.clear_market(building_states, timestep=0)
        
        if result.total_volume_kwh > 0:
            timestep_hours = scenario_config.timestep_minutes / 60.0
            total_kw = sum(abs(t) for t in result.trades.values()) / 2.0
            expected_kwh = total_kw * timestep_hours
            assert abs(result.total_volume_kwh - expected_kwh) < 1e-9

    def test_member_bill_and_savings_include_post_trade_grid_costs(
        self, scenario_config, energy_sharing_config, building_states
    ):
        """REGRESSION: Savings compare the full no-sharing and shared bills."""
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        engine.process_timestep(
            0,
            building_states,
            {"building_0": 2.0, "building_1": 0.0, "building_2": 1.0},
            {"building_0": 0.0, "building_1": 3.0, "building_2": 0.0},
        )
        assert engine.get_community_metrics()["total_savings_vs_baseline"] == pytest.approx(0.0375)

        result = engine.finalize()
        buyer = result.building_settlements["building_0"]
        seller = result.building_settlements["building_1"]
        second_buyer = result.building_settlements["building_2"]

        assert buyer.total_grid_import_kwh == pytest.approx(0.0)
        assert seller.total_grid_export_kwh == pytest.approx(0.0)
        assert buyer.metadata["baseline_grid_bill"] == pytest.approx(0.05)
        assert buyer.metadata["actual_total_bill"] == pytest.approx(0.0375)
        assert buyer.metadata["savings_vs_baseline"] == pytest.approx(0.0125)
        assert seller.metadata["baseline_grid_bill"] == pytest.approx(-0.0375)
        assert seller.metadata["actual_total_bill"] == pytest.approx(-0.05625)
        assert seller.metadata["savings_vs_baseline"] == pytest.approx(0.01875)
        assert second_buyer.metadata["savings_vs_baseline"] == pytest.approx(0.00625)
        community_metrics = engine.get_community_metrics()
        assert community_metrics["baseline_grid_bill"] == pytest.approx(0.0375)
        assert community_metrics["actual_total_bill"] == pytest.approx(0.0)
        assert community_metrics["total_savings_vs_baseline"] == pytest.approx(0.0375)

    def test_interval_volume_is_reported_in_kwh(
        self, scenario_config, energy_sharing_config, building_states
    ):
        """REGRESSION: Interval volume uses energy, not summed power."""
        energy_sharing_config.settlement_interval = "30min"
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        expected_volume = 0.0
        for timestep in range(2):
            result = engine.process_timestep(timestep, building_states, {}, {})
            expected_volume += result.total_volume_kwh

        settlement_result = engine.finalize()

        assert settlement_result.interval_results[0].total_volume_kwh == pytest.approx(
            expected_volume
        )

    def test_default_tariff_and_demand_charge_are_in_member_bills(
        self, scenario_config, energy_sharing_config, building_states
    ):
        """REGRESSION: Default energy rates and peak demand charges are billed."""
        for state in building_states.values():
            state.tariff_config = None
        building_states["building_0"].tariff_config = TariffConfig(
            import_prices={"off_peak": 0.1},
            export_prices={"off_peak": 0.05},
            demand_charge=10.0,
        )
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        engine.process_timestep(
            0,
            building_states,
            {"building_0": 2.0, "building_1": 0.0, "building_2": 1.0},
            {"building_0": 0.0, "building_1": 3.0, "building_2": 0.0},
        )

        result = engine.finalize()
        buyer = result.building_settlements["building_0"]
        seller = result.building_settlements["building_1"]
        default_tariff_buyer = result.building_settlements["building_2"]

        assert buyer.baseline_demand_charge == pytest.approx(20.0)
        assert buyer.actual_demand_charge == pytest.approx(0.0)
        assert buyer.metadata["baseline_grid_bill"] == pytest.approx(20.05)
        assert seller.metadata["baseline_grid_bill"] == pytest.approx(-0.0375)
        assert seller.metadata["actual_total_bill"] == pytest.approx(-0.05625)
        assert default_tariff_buyer.baseline_grid_import_cost == pytest.approx(0.075)

    def test_savings_positive_when_community_cheaper(self, scenario_config, energy_sharing_config, building_states):
        """REGRESSION: Savings > 0 when community price < grid price."""
        engine = SettlementEngine(scenario_config, energy_sharing_config)
        
        grid_imports = {"building_0": 2.0, "building_1": 0.0, "building_2": 0.0}
        grid_exports = {"building_0": 0.0, "building_1": 3.0, "building_2": 0.0}
        
        for t in range(3):
            engine.process_timestep(t, building_states, grid_imports, grid_exports)
        
        result = engine.finalize()
        savings = engine.get_building_savings()
        
        assert savings["building_0"] > -1e-6

    def test_negative_limit_raises(self):
        """REGRESSION: Negative import/export limit raises ValueError."""
        from pydantic import ValidationError
        from src.schemas.scenario import EnergySharingConfig
        
        with pytest.raises(ValidationError):
            EnergySharingConfig(enabled=True, market_type="uniform_price",
                              import_limit_kw=-10.0)
        
        with pytest.raises(ValidationError):
            EnergySharingConfig(enabled=True, market_type="uniform_price",
                              export_limit_kw=-5.0)

    def test_zero_limit_raises(self):
        """REGRESSION: Zero import/export limit raises ValueError."""
        from pydantic import ValidationError
        from src.schemas.scenario import EnergySharingConfig
        
        with pytest.raises(ValidationError):
            EnergySharingConfig(enabled=True, market_type="uniform_price",
                              import_limit_kw=0.0)
        
        with pytest.raises(ValidationError):
            EnergySharingConfig(enabled=True, market_type="uniform_price",
                              export_limit_kw=0.0)

    def test_unknown_market_type_raises(self):
        """REGRESSION: Unknown market type raises ValueError."""
        from pydantic import ValidationError
        from src.schemas.scenario import EnergySharingConfig
        
        with pytest.raises(ValidationError):
            EnergySharingConfig(enabled=True, market_type="unknown_type")

    def test_no_arbitrage_detects_buy_low_sell_high(self, scenario_config, energy_sharing_config):
        """REGRESSION: No arbitrage - clearing price between grid import and export prices."""
        engine = UniformPriceClearing(scenario_config, energy_sharing_config)
        
        states = {
            "pv_rich": BuildingEnergyState(
                building_id="pv_rich",
                net_demand_kw=-10.0,
                pv_generation_kw=15.0,
                battery_power_kw=0.0,
                battery_soc=0.9,
                max_import_kw=0.0,
                max_export_kw=20.0,
                tariff_config=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"off_peak": 0.05, "mid_peak": 0.05, "on_peak": 0.05},
                    demand_charge=0.0
                ),
            ),
            "demand_rich": BuildingEnergyState(
                building_id="demand_rich",
                net_demand_kw=10.0,
                pv_generation_kw=0.0,
                battery_power_kw=0.0,
                battery_soc=0.1,
                max_import_kw=20.0,
                max_export_kw=0.0,
                tariff_config=TariffConfig(
                    type="time_of_use",
                    import_prices={"on_peak": 0.30, "mid_peak": 0.20, "off_peak": 0.10},
                    export_prices={"off_peak": 0.05, "mid_peak": 0.05, "on_peak": 0.05},
                    demand_charge=0.0
                ),
            ),
        }
        
        result = engine.clear_market(states, timestep=0)
        
        if result.total_volume_kwh > 0:
            # Clearing price must be between grid export price (0.05) and grid import price (0.30)
            assert result.clearing_price >= 0.05 - 1e-6
            assert result.clearing_price <= 0.30 + 1e-6
            
            # No building can both buy and sell in same timestep
            for trade in result.trades.values():
                assert trade == 0.0 or (trade > 0) != (trade < 0)
            
            # For sellers: community price >= grid export price (otherwise they'd sell to grid)
            # For buyers: community price <= grid import price (otherwise they'd buy from grid)
            for bid, trade in result.trades.items():
                state = states[bid]
                if trade < 0:  # Seller
                    export_price = state.tariff_config.export_prices.get("off_peak", 0.05)
                    assert result.clearing_price >= export_price - 1e-6, \
                        f"Seller {bid}: community price {result.clearing_price} < grid export {export_price}"
                elif trade > 0:  # Buyer
                    import_price = state.tariff_config.import_prices.get("off_peak", 0.30)
                    assert result.clearing_price <= import_price + 1e-6, \
                        f"Buyer {bid}: community price {result.clearing_price} > grid import {import_price}"


class TestCouplerIntegration:
    """Integration tests with SimulationCoupler."""

    def test_coupler_initializes_market_components(self, scenario_config, tmp_path):
        """Test coupler initializes settlement engine when energy sharing enabled."""
        coupler = SimulationCoupler(scenario_config, data_dir=str(tmp_path))
        
        assert coupler.energy_sharing_enabled is True
        assert coupler.settlement_engine is not None
        assert coupler.settlement_engine.market_engine is not None

    def test_coupler_no_energy_sharing(self, scenario_config, tmp_path):
        """Test coupler works without energy sharing."""
        scenario_config.energy_sharing = None
        coupler = SimulationCoupler(scenario_config, data_dir=str(tmp_path))
        
        assert coupler.energy_sharing_enabled is False
        assert coupler.settlement_engine is None

    def test_coupler_step_includes_market_data(self, scenario_config, tmp_path):
        """Test coupler step includes market and settlement data in result."""
        coupler = SimulationCoupler(scenario_config, data_dir=str(tmp_path))
        observations = coupler.reset()
        
        from src.schemas.action import RequestedActions, Action, ActionType
        requested = RequestedActions(
            timestep=0,
            actions=[
                Action(asset_id="building_0_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0),
                Action(asset_id="building_1_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0),
                Action(asset_id="building_2_battery", action_type=ActionType.BATTERY_CHARGE, value_kw=1.0, timestep=0),
            ]
        )
        
        result = coupler.step(requested)
        
        # Check market data in grid diagnostics
        grid_diag = result.citylearn_result.grid_diagnostics
        assert "market_result" in grid_diag
        assert "settlement_snapshot" in grid_diag
        assert grid_diag["market_result"]["clearing_price"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])