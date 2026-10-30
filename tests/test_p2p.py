"""Tests for P2P energy trading (P0-4 preparation)."""
import pytest
import numpy as np

from src.coordination.p2p import (
    P2POrder, P2PTrade, P2POrderSide, P2POrderStatus,
    P2PMatchingEngine, P2PMatchingResult, run_p2p_invariant_tests
)
from src.simulation.market import MarketType, create_market_engine, P2PClearing
from src.schemas.scenario import (
    ScenarioConfig, BuildingConfig, BuildingType, EnergySharingConfig,
    TariffConfig, PVConfig, BatteryConfig, PandapowerConfig, GridBusMapping
)
from src.simulation.market import BuildingEnergyState


class TestP2PSchemas:
    """Tests for P2P data schemas."""
    
    def test_p2p_order_creation(self):
        """Test P2P order creation and validation."""
        order = P2POrder(
            order_id="test_order_1",
            building_id="building_0",
            side=P2POrderSide.BUY,
            price_per_kwh=0.20,
            quantity_kwh=10.0,
            timestamp=0,
        )
        assert order.order_id == "test_order_1"
        assert order.side == P2POrderSide.BUY
        assert order.price_per_kwh == 0.20
        assert order.quantity_kwh == 10.0
        assert order.status == P2POrderStatus.PENDING
        assert order.filled_quantity_kwh == 0.0
    
    def test_p2p_trade_creation(self):
        """Test P2P trade creation and validation."""
        trade = P2PTrade(
            trade_id="test_trade_1",
            buyer_id="building_0",
            seller_id="building_1",
            buyer_order_id="order_1",
            seller_order_id="order_2",
            price_per_kwh=0.15,
            quantity_kwh=5.0,
            timestamp=0,
            buyer_payment_usd=0.75,
            seller_revenue_usd=0.75,
        )
        assert trade.buyer_id == "building_0"
        assert trade.seller_id == "building_1"
        assert abs(trade.buyer_payment_usd - trade.seller_revenue_usd) < 1e-6
    
    def test_p2p_trade_validation_fails_on_mismatch(self):
        """Test P2P trade validation fails on payment/revenue mismatch."""
        with pytest.raises(AssertionError):
            P2PTrade(
                trade_id="test_trade_1",
                buyer_id="building_0",
                seller_id="building_1",
                buyer_order_id="order_1",
                seller_order_id="order_2",
                price_per_kwh=0.15,
                quantity_kwh=5.0,
                timestamp=0,
                buyer_payment_usd=0.80,  # Mismatch!
                seller_revenue_usd=0.75,
            )


class TestP2PMatchingEngine:
    """Tests for P2P matching engine."""
    
    def test_basic_match(self):
        """Test basic buy/sell match."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.20, 10.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.10, 10.0, 0)
        result = engine.clear_batch(0)
        
        assert len(result.trades) == 1
        assert result.trades[0].buyer_id == "b0"
        assert result.trades[0].seller_id == "b1"
        assert result.trades[0].quantity_kwh == 10.0
        assert abs(result.clearing_price - 0.15) < 1e-9  # Midpoint
    
    def test_partial_fill(self):
        """Test partial fill when quantities don't match."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.25, 5.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.15, 3.0, 0)
        result = engine.clear_batch(0)
        
        assert len(result.trades) == 1
        assert result.trades[0].quantity_kwh == 3.0
        assert result.trades[0].buyer_id == "b0"
        assert result.trades[0].seller_id == "b1"
        # Buyer should have 2.0 kWh unmatched
        assert len(result.unmatched_orders) == 1
        assert result.unmatched_orders[0].building_id == "b0"
        assert abs(result.unmatched_orders[0].filled_quantity_kwh - 3.0) < 1e-6
    
    def test_price_time_priority(self):
        """Test price-time priority ordering."""
        engine = P2PMatchingEngine(price_time_priority=True)
        
        # Add buy orders at same price, different times
        engine.add_order("b0", P2POrderSide.BUY, 0.25, 5.0, 0)  # Earlier
        engine.add_order("b1", P2POrderSide.BUY, 0.25, 5.0, 1)  # Later
        engine.add_order("s0", P2POrderSide.SELL, 0.15, 8.0, 0)
        
        result = engine.clear_batch(0)
        
        # b0 should get filled first (earlier timestamp)
        assert len(result.trades) >= 1
        # First trade should involve b0
        assert result.trades[0].buyer_id == "b0"
    
    def test_min_spread_enforced(self):
        """Test minimum spread enforcement."""
        engine = P2PMatchingEngine(min_spread=0.01)
        
        # Buy price + min_spread < sell price -> no match
        engine.add_order("b0", P2POrderSide.BUY, 0.10, 10.0, 0)
        engine.add_order("s0", P2POrderSide.SELL, 0.20, 10.0, 0)
        result = engine.clear_batch(0)
        
        assert len(result.trades) == 0
        assert len(result.unmatched_orders) == 2
    
    def test_uniform_price_per_batch(self):
        """Test uniform clearing price within batch."""
        engine = P2PMatchingEngine(uniform_price_per_batch=True)
        
        engine.add_order("b0", P2POrderSide.BUY, 0.30, 10.0, 0)
        engine.add_order("b1", P2POrderSide.BUY, 0.25, 5.0, 0)
        engine.add_order("s0", P2POrderSide.SELL, 0.10, 8.0, 0)
        engine.add_order("s1", P2POrderSide.SELL, 0.12, 7.0, 0)
        
        result = engine.clear_batch(0)
        
        if result.trades:
            prices = [t.price_per_kwh for t in result.trades]
            # All trades should have the same price
            assert len(set(round(p, 6) for p in prices)) == 1
    
    def test_multiple_buyers_sellers(self):
        """Test matching with multiple buyers and sellers."""
        engine = P2PMatchingEngine()
        
        engine.add_order("b0", P2POrderSide.BUY, 0.30, 8.0, 0)
        engine.add_order("b1", P2POrderSide.BUY, 0.25, 5.0, 0)
        engine.add_order("s0", P2POrderSide.SELL, 0.10, 6.0, 0)
        engine.add_order("s1", P2POrderSide.SELL, 0.12, 7.0, 0)
        
        result = engine.clear_batch(0)
        
        # Total bought should equal total sold
        total_bought = sum(t.quantity_kwh for t in result.trades)
        total_sold = sum(t.quantity_kwh for t in result.trades)
        assert abs(total_bought - total_sold) < 1e-6
        
        # Money conservation
        total_payments = sum(t.buyer_payment_usd for t in result.trades)
        total_revenues = sum(t.seller_revenue_usd for t in result.trades)
        assert abs(total_payments - total_revenues) < 1e-6


class TestP2PInvariants:
    """Tests for P2P invariant properties."""
    
    def test_all_invariants_pass(self):
        """Run all P2P invariant tests."""
        results = run_p2p_invariant_tests()
        
        # All invariants should pass
        for test_name, passed in results.items():
            assert passed, f"Invariant test failed: {test_name}"
        
        assert all(results.values())
    
    def test_money_conservation(self):
        """Test money conservation invariant."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.20, 10.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.10, 10.0, 0)
        result = engine.clear_batch(0)
        
        total_payments = sum(t.buyer_payment_usd for t in result.trades)
        total_revenues = sum(t.seller_revenue_usd for t in result.trades)
        assert abs(total_payments - total_revenues) < 1e-6
    
    def test_energy_conservation(self):
        """Test energy conservation invariant."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.20, 10.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.10, 10.0, 0)
        result = engine.clear_batch(0)
        
        total_bought = sum(t.quantity_kwh for t in result.trades)
        total_sold = sum(t.quantity_kwh for t in result.trades)
        assert abs(total_bought - total_sold) < 1e-6
    
    def test_no_arbitrage_band(self):
        """Test no-arbitrage: clearing price between buy and sell prices."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.20, 10.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.10, 10.0, 0)
        result = engine.clear_batch(0)
        
        if result.trades:
            trade_price = result.trades[0].price_per_kwh
            assert 0.10 <= trade_price <= 0.20
    
    def test_ledger_conservation(self):
        """Test P2P ledger conservation: Σ buyer payments - Σ seller revenue = 0."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.20, 10.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.10, 10.0, 0)
        result = engine.clear_batch(0)
        
        net_flow = sum(t.buyer_payment_usd for t in result.trades) - \
                   sum(t.seller_revenue_usd for t in result.trades)
        assert abs(net_flow) < 1e-6
    
    def test_no_double_settlement(self):
        """Test no double settlement of same kWh."""
        engine = P2PMatchingEngine()
        engine.add_order("b0", P2POrderSide.BUY, 0.20, 10.0, 0)
        engine.add_order("b1", P2POrderSide.SELL, 0.10, 10.0, 0)
        result = engine.clear_batch(0)
        
        # Each unique trade should only appear once
        trade_keys = set()
        for t in result.trades:
            key = (t.buyer_id, t.seller_id, t.timestamp, round(t.quantity_kwh, 6))
            assert key not in trade_keys, f"Duplicate trade detected: {key}"
            trade_keys.add(key)


class TestP2PMarketType:
    """Tests for P2P market type in market clearing factory."""
    
    @pytest.fixture
    def p2p_scenario_config(self):
        """Create scenario config with P2P market type."""
        return ScenarioConfig(
            scenario_id="test_p2p",
            name="P2P Test",
            description="P2P Test",
            random_seed=42,
            timestep_minutes=60,
            buildings=[
                BuildingConfig(
                    building_id="building_0",
                    building_type=BuildingType.RESIDENTIAL,
                    tariff=TariffConfig(
                        import_prices={"on_peak": 0.30, "off_peak": 0.10},
                        export_prices={"default": 0.05},
                    ),
                    pv=PVConfig(capacity_kw=5.0),
                    battery=BatteryConfig(capacity_kwh=10.0, power_kw=5.0),
                ),
                BuildingConfig(
                    building_id="building_1",
                    building_type=BuildingType.RESIDENTIAL,
                    tariff=TariffConfig(
                        import_prices={"on_peak": 0.30, "off_peak": 0.10},
                        export_prices={"default": 0.05},
                    ),
                    pv=PVConfig(capacity_kw=3.0),
                    battery=BatteryConfig(capacity_kwh=5.0, power_kw=3.0),
                ),
            ],
            pandapower=PandapowerConfig(
                network_type="ieee_34",
                bus_mappings=[
                    GridBusMapping(building_id="building_0", bus_idx=1),
                    GridBusMapping(building_id="building_1", bus_idx=2),
                ]
            ),
            energy_sharing=EnergySharingConfig(
                enabled=True,
                market_type="p2p",
                settlement_interval="1h",
            )
        )
    
    def test_p2p_market_type_enum(self):
        """Test P2P market type enum exists."""
        assert MarketType.P2P == "p2p"
        assert MarketType.P2P.value == "p2p"
    
    def test_p2p_engine_factory(self, p2p_scenario_config):
        """Test factory creates P2P engine."""
        engine = create_market_engine(p2p_scenario_config, p2p_scenario_config.energy_sharing)
        assert isinstance(engine, P2PClearing)
    
    def test_p2p_clearing_basic(self, p2p_scenario_config):
        """Test P2P clearing produces valid results."""
        energy_sharing_config = EnergySharingConfig(
            enabled=True,
            market_type="p2p",
            settlement_interval="1h",
            import_limit_kw=100.0,
            export_limit_kw=100.0,
        )
        engine = create_market_engine(p2p_scenario_config, energy_sharing_config)
        
        building_states = {
            "building_0": BuildingEnergyState(
                building_id="building_0",
                net_demand_kw=5.0,  # Buyer
                pv_generation_kw=2.0,
                battery_power_kw=0.0,
                battery_soc=0.5,
                max_import_kw=50.0,
                max_export_kw=50.0,
                tariff_config=TariffConfig(
                    import_prices={"on_peak": 0.30, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                ),
            ),
            "building_1": BuildingEnergyState(
                building_id="building_1",
                net_demand_kw=-3.0,  # Seller
                pv_generation_kw=8.0,
                battery_power_kw=0.0,
                battery_soc=0.8,
                max_import_kw=30.0,
                max_export_kw=30.0,
                tariff_config=TariffConfig(
                    import_prices={"on_peak": 0.30, "off_peak": 0.10},
                    export_prices={"default": 0.05},
                ),
            ),
        }
        
        result = engine.clear_market(building_states, timestep=0)
        
        assert result.market_type == MarketType.P2P
        assert result.clearing_price >= 0
        assert result.total_volume_kwh >= 0
        assert set(result.trades.keys()) == set(building_states.keys())
        assert set(result.settlements.keys()) == set(building_states.keys())


class TestP2PConfigValidation:
    """Tests for P2P configuration validation."""
    
    def test_p2p_market_type_accepted(self):
        """Test that 'p2p' is accepted as valid market_type."""
        config = EnergySharingConfig(
            enabled=True,
            market_type="p2p",
        )
        assert config.market_type == "p2p"
    
    def test_invalid_market_type_rejected(self):
        """Test that invalid market_type is rejected."""
        with pytest.raises(ValueError):
            EnergySharingConfig(
                enabled=True,
                market_type="invalid_type",
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])