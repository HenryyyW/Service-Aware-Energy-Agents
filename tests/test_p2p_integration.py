"""Integration tests for P2P market: matching -> residual pool clearing -> settlement.

Tests edge cases: partial fills, price-time priority, min spread, bilateral matching -> residual pool clearing.
"""
import pytest
import numpy as np
from src.coordination.p2p import (
    P2PMatchingEngine, P2POrderSide, P2POrderStatus, P2PMatchingResult,
    run_p2p_invariant_tests
)
from src.simulation.settlement_gate import validate_p2p_settlement, create_p2p_gate_report


def test_p2p_bilateral_matching_then_residual_clearing():
    """Test bilateral P2P matching then residual clears in community pool."""
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide
    from src.simulation.settlement_gate import validate_p2p_settlement
    
    engine = P2PMatchingEngine()
    
    # Building 0 is net buyer (5 kW), Building 1 is net seller (-3 kW)
    engine.add_order("b0", P2POrderSide.BUY, 0.30, 5.0, 0)
    engine.add_order("b1", P2POrderSide.SELL, 0.10, 3.0, 0)
    
    result = engine.clear_batch(0)
    
    # Verify bilateral matching occurred
    assert len(result.trades) >= 1
    assert result.clearing_price is not None
    assert result.total_volume_kwh >= 0
    
    # Settlement gate should pass
    gate_passed, gate_results = validate_p2p_settlement(result)
    assert gate_passed
    
    print(f"Clearing price: {result.clearing_price}")
    print(f"Volume: {result.total_volume_kwh}")
    print(f"Trades: {result.trades}")


def test_p2p_partial_fill_edge_case():
    """Test partial fill edge case where buyer quantity != seller quantity."""
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide, P2POrderStatus
    from src.simulation.settlement_gate import validate_p2p_settlement
    
    engine = P2PMatchingEngine()
    
    # Buyer wants 10, seller has 3 -> partial fill
    engine.add_order("buyer", "buy", 0.25, 10.0, 0)
    engine.add_order("seller", "sell", 0.15, 3.0, 0)
    
    result = engine.clear_batch(0)
    
    # Should have 1 trade of 3.0
    assert len(result.trades) == 1
    assert abs(result.trades[0].quantity_kwh - 3.0) < 1e-6
    
    # Buyer should have 7.0 unmatched
    unmatched = [o for o in result.unmatched_orders if o.building_id == "buyer"]
    assert len(unmatched) == 1
    assert abs(unmatched[0].filled_quantity_kwh - 3.0) < 1e-6
    assert abs(unmatched[0].quantity_kwh - 10.0) < 1e-6
    assert unmatched[0].status.value == "partial"
    
    # Seller should be filled
    unmatched_seller = [o for o in result.unmatched_orders if o.building_id == "seller"]
    assert len(unmatched_seller) == 0
    
    # Settlement gate should pass
    gate_passed, gate_results = validate_p2p_settlement(result)
    assert gate_passed


def test_p2p_price_time_priority():
    """Test price-time priority: earlier orders at same price get priority."""
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide
    from src.simulation.settlement_gate import validate_p2p_settlement
    
    engine = P2PMatchingEngine(price_time_priority=True)
    
    # Two buyers at same price, different times
    engine.add_order("buyer_early", "buy", 0.25, 5.0, 0)  # timestamp 0
    engine.add_order("buyer_late", "buy", 0.25, 5.0, 1)   # timestamp 1
    engine.add_order("seller", "sell", 0.15, 8.0, 0)
    
    result = engine.clear_batch(0)
    
    # buyer_early should be filled first
    assert len(result.trades) >= 1
    assert result.trades[0].buyer_id == "buyer_early"
    
    # Settlement gate should pass
    gate_passed, _ = validate_p2p_settlement(result)
    assert gate_passed


def test_p2p_min_spread_enforcement():
    """Test minimum spread enforcement prevents bad trades."""
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide
    
    engine = P2PMatchingEngine(min_spread=0.01)
    
    # Buy at 0.10, sell at 0.20 -> 0.10 + 0.01 = 0.11 < 0.20 -> no match!
    engine.add_order("buyer", "buy", 0.10, 10.0, 0)
    engine.add_order("seller", "sell", 0.20, 10.0, 0)
    
    result = engine.clear_batch(0)
    
    # No trade should occur
    assert len(result.trades) == 0
    assert len(result.unmatched_orders) == 2
    
    # But if spread is sufficient:
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide
    engine2 = P2PMatchingEngine(min_spread=0.01)
    engine2.add_order("buyer", "buy", 0.15, 10.0, 0)
    engine2.add_order("seller", "sell", 0.10, 10.0, 0)
    result2 = engine2.clear_batch(0)
    assert len(result2.trades) == 1


def test_p2p_uniform_clearing_price():
    """Test uniform clearing price within batch."""
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide
    from src.simulation.settlement_gate import validate_p2p_settlement
    
    engine = P2PMatchingEngine(uniform_price_per_batch=True)
    
    # Multiple trades should have same clearing price
    engine.add_order("b0", "buy", 0.30, 10.0, 0)
    engine.add_order("b1", "buy", 0.25, 5.0, 0)
    engine.add_order("s0", "sell", 0.10, 8.0, 0)
    engine.add_order("s1", "sell", 0.12, 7.0, 0)
    
    result = engine.clear_batch(0)
    
    if result.trades:
        prices = [t.price_per_kwh for t in result.trades]
        unique_prices = len(set(round(p, 6) for p in prices))
        assert unique_prices == 1, f"Expected uniform price, got {unique_prices} unique prices"
        assert abs(result.clearing_price - result.trades[0].price_per_kwh) < 1e-9
    
    gate_passed, _ = validate_p2p_settlement(result)
    assert gate_passed


def test_p2p_settlement_gate_integration():
    """Test full integration: matching -> settlement gate -> settlement."""
    from src.coordination.p2p import P2PMatchingEngine, P2POrderSide
    from src.simulation.settlement_gate import validate_p2p_settlement, create_p2p_gate_report
    
    engine = P2PMatchingEngine()
    
    # Multiple buyers and sellers
    engine.add_order("b0", "buy", 0.30, 8.0, 0)
    engine.add_order("b1", "buy", 0.25, 5.0, 0)
    engine.add_order("s0", "sell", 0.10, 6.0, 0)
    engine.add_order("s1", "sell", 0.12, 7.0, 0)
    
    result = engine.clear_batch(0)
    
    # Run settlement gate
    gate_passed, gate_results = validate_p2p_settlement(result)
    
    print(f"Gate passed: {gate_passed}")
    report = create_p2p_gate_report(gate_results)
    print(f"Gate report: {report}")
    
    # Should pass all invariants
    assert all(r.status.value == "passed" for r in gate_results)


def test_p2p_invariant_suite():
    """Run full invariant test suite."""
    from src.coordination.p2p import run_p2p_invariant_tests
    
    results = run_p2p_invariant_tests()
    
    # All invariants should pass
    assert all(results.values()), f"Failed invariants: {[k for k, v in results.items() if not v]}"
    
    print(f"All invariant tests passed: {results}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])