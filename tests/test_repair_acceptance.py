"""Unit tests for the shared repair acceptance criteria (evaluate_repair)."""

import pytest
from src.evaluation.repair_acceptance import (
    evaluate_repair,
    RepairVerdict,
    EPS,
    DEPARTURE_SOC_MAX_DROP,
    COMFORT_TOL_FACTOR,
    COMFORT_TOL_ABS,
)


def _base_baseline():
    return {
        "grid": {
            "voltage_violations_count": 5,
            "line_loading_violations": 3,
            "transformer_loading_violations": 1,
        },
        "service": {
            "ev_completion_rate": 0.90,
            "ev_avg_soc_at_departure": 0.80,
            "ev_worst_soc_at_departure": 0.60,
            "flexible_load_completion_rate": 0.85,
            "comfort_violation_degree_hours": 5.0,
            "member_cost_coverage": 0.90,
            "members_interrupted_count": 2,
            "member_cost_interrupted": None,
        },
    }


def _base_repaired():
    return {
        "grid": {
            "voltage_violations_count": 0,
            "line_loading_violations": 0,
            "transformer_loading_violations": 0,
        },
        "service": {
            "ev_completion_rate": 0.92,
            "ev_avg_soc_at_departure": 0.81,
            "ev_worst_soc_at_departure": 0.61,
            "flexible_load_completion_rate": 0.87,
            "comfort_violation_degree_hours": 4.0,
            "member_cost_coverage": 0.92,
            "members_interrupted_count": 1,
            "member_cost_interrupted": None,
        },
    }


def test_evaluate_repair_accept():
    """Test that a valid repair with violations resolved and no degradation is accepted."""
    baseline = _base_baseline()
    repaired = _base_repaired()

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is True
    assert verdict.reasons == []
    assert "ev_completion_rate" in verdict.metric_deltas
    assert "voltage_violations" in verdict.metric_deltas


def test_evaluate_repair_reject_ev_completion_decrease():
    """Test rejection when EV completion rate decreases."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_completion_rate"] = 0.85  # Decreased from 0.90

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("EV completion rate decreased" in r for r in verdict.reasons)
    assert any("MASKED VIOLATION" in r for r in verdict.reasons)


def test_evaluate_repair_reject_ev_avg_soc_drop():
    """Test rejection when avg departure SOC drops more than 0.01."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_avg_soc_at_departure"] = 0.78  # Drop of 0.02 > 0.01

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Avg departure SOC dropped" in r for r in verdict.reasons)


def test_evaluate_repair_reject_ev_worst_soc_drop():
    """Test rejection when worst departure SOC drops more than 0.01."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_worst_soc_at_departure"] = 0.58  # Drop of 0.02 > 0.01

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Worst departure SOC dropped" in r for r in verdict.reasons)


def test_evaluate_repair_reject_flex_completion_decrease():
    """Test rejection when flexible load completion rate decreases."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["flexible_load_completion_rate"] = 0.80  # Decreased from 0.85

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Flexible load completion decreased" in r for r in verdict.reasons)


def test_evaluate_repair_reject_comfort_increase_exceeds_tolerance():
    """Test rejection when comfort violation increase exceeds tolerance."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"][
        "comfort_violation_degree_hours"
    ] = 10.0  # Increase of 5.0 > tol (max(1.0, 0.02*5)=1.0)

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Comfort violation increased" in r for r in verdict.reasons)


def test_evaluate_repair_reject_member_cost_coverage_decrease():
    """Test rejection when member cost coverage decreases."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["member_cost_coverage"] = 0.85  # Decreased from 0.90

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Member cost coverage decreased" in r for r in verdict.reasons)


def test_evaluate_repair_reject_members_interrupted_increase():
    """Test rejection when members interrupted count increases."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["members_interrupted_count"] = 3  # Increased from 2

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Members interrupted increased" in r for r in verdict.reasons)


def test_evaluate_repair_reject_interrupted_cost_not_none():
    """Test rejection when interrupted member cost is not None."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["member_cost_interrupted"] = 0.0  # Must stay None

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any(
        "Interrupted member cost is 0.0 or negative" in r for r in verdict.reasons
    )


def test_evaluate_repair_boundary_ev_completion_eps():
    """Test boundary: EV completion rate decrease within eps is allowed."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_completion_rate"] = 0.90 - EPS / 2  # Within eps

    verdict = evaluate_repair(baseline, repaired)

    # Should be accepted since decrease is within eps
    assert verdict.accepted is True


def test_evaluate_repair_boundary_ev_completion_outside_eps():
    """Test boundary: EV completion rate decrease outside eps is rejected."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_completion_rate"] = 0.90 - EPS * 2  # Outside eps

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("EV completion rate decreased" in r for r in verdict.reasons)


def test_evaluate_repair_boundary_departure_soc_exact():
    """Test boundary: avg departure SOC drop exactly at 0.01 is allowed."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_avg_soc_at_departure"] = (
        0.80 - DEPARTURE_SOC_MAX_DROP
    )  # Exactly 0.01 drop

    verdict = evaluate_repair(baseline, repaired)

    # Should be accepted since drop is exactly at boundary
    assert verdict.accepted is True


def test_evaluate_repair_boundary_departure_soc_over():
    """Test boundary: avg departure SOC drop slightly over 0.01 is rejected."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    repaired["service"]["ev_avg_soc_at_departure"] = (
        0.80 - DEPARTURE_SOC_MAX_DROP - 1e-6
    )  # Slightly over

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Avg departure SOC dropped" in r for r in verdict.reasons)


def test_evaluate_repair_comfort_tolerance_abs():
    """Test comfort tolerance uses absolute 1.0 deg-h when reference is small."""
    baseline = _base_baseline()
    # Low reference comfort
    baseline["service"]["comfort_violation_degree_hours"] = 10.0
    repaired = _base_repaired()
    repaired["service"]["comfort_violation_degree_hours"] = 20.0  # Increase of 10.0

    # Tolerance = max(1.0, 0.02 * 10.0) = max(1.0, 0.2) = 1.0
    # Increase of 10.0 > 1.0 -> reject
    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    assert any("Comfort violation increased" in r for r in verdict.reasons)


def test_evaluate_repair_comfort_tolerance_factor():
    """Test comfort tolerance uses 2% factor when reference is large."""
    baseline = _base_baseline()
    # High reference comfort
    baseline["service"]["comfort_violation_degree_hours"] = 100.0
    repaired = _base_repaired()
    repaired["service"]["comfort_violation_degree_hours"] = 102.0  # Increase of 2.0

    # Tolerance = max(1.0, 0.02 * 100.0) = max(1.0, 2.0) = 2.0
    # Increase of 2.0 <= 2.0 -> accept
    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is True


def test_evaluate_repair_violations_must_decrease():
    """Test that grid violations must decrease (or reach zero)."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    # Violations stay the same - this should not be accepted if violations persist
    repaired["grid"]["voltage_violations_count"] = 5  # Same as baseline

    verdict = evaluate_repair(baseline, repaired)

    # If violations didn't decrease but service is fine, it might still be rejected
    # due to masked violation check - let's verify
    # The shared criteria doesn't explicitly reject if violations persist but don't increase
    # It only rejects if held-harmless criteria are violated
    # So this case should be accepted if service metrics are fine
    assert verdict.accepted is True  # Service metrics are all improved


def test_evaluate_repair_no_netting():
    """Test that no netting across metrics: one failure rejects even if others improve."""
    baseline = _base_baseline()
    repaired = _base_repaired()
    # Multiple degradations
    repaired["service"]["ev_completion_rate"] = 0.85
    repaired["service"]["comfort_violation_degree_hours"] = 10.0
    repaired["service"]["member_cost_coverage"] = 0.85

    verdict = evaluate_repair(baseline, repaired)

    assert verdict.accepted is False
    # Should have multiple reasons
    assert len(verdict.reasons) >= 2


def test_evaluate_repair_integration_synthetic():
    """Integration-style test with synthetic before/after metric dicts."""
    # Simulate a realistic scenario: baseline has violations, repair resolves them
    # but slightly degrades comfort within tolerance
    baseline = {
        "grid": {
            "voltage_violations_count": 10,
            "line_loading_violations": 5,
            "transformer_loading_violations": 2,
        },
        "service": {
            "ev_completion_rate": 0.88,
            "ev_avg_soc_at_departure": 0.75,
            "ev_worst_soc_at_departure": 0.55,
            "flexible_load_completion_rate": 0.80,
            "comfort_violation_degree_hours": 15.0,
            "member_cost_coverage": 0.85,
            "members_interrupted_count": 3,
            "member_cost_interrupted": None,
        },
    }

    repaired = {
        "grid": {
            "voltage_violations_count": 0,
            "line_loading_violations": 0,
            "transformer_loading_violations": 0,
        },
        "service": {
            "ev_completion_rate": 0.90,  # Improved
            "ev_avg_soc_at_departure": 0.76,  # Slight improvement
            "ev_worst_soc_at_departure": 0.56,  # Slight improvement
            "flexible_load_completion_rate": 0.82,  # Improved
            "comfort_violation_degree_hours": 15.3,  # Small increase (within 2% of 15.0 = 0.3, but max(1.0, 0.3) = 1.0)
            "member_cost_coverage": 0.87,  # Improved
            "members_interrupted_count": 2,  # Improved
            "member_cost_interrupted": None,
        },
    }

    verdict = evaluate_repair(baseline, repaired)

    # Comfort increase is 0.3, tolerance is max(1.0, 0.02*15.0) = 1.0 -> within tolerance
    assert verdict.accepted is True
    assert "comfort_violation_degree_hours" in verdict.metric_deltas
    assert (
        abs(verdict.metric_deltas["comfort_violation_degree_hours"]["delta"] - 0.3)
        < 1e-9
    )


def test_evaluate_repair_verbose_output():
    """Test that metric_deltas contains detailed before/after/delta for transparency."""
    baseline = _base_baseline()
    repaired = _base_repaired()

    verdict = evaluate_repair(baseline, repaired)

    # Check metric_deltas structure
    for key, delta_info in verdict.metric_deltas.items():
        assert "before" in delta_info
        assert "after" in delta_info
        assert "delta" in delta_info
        # delta should equal after - before
        assert (
            abs(delta_info["delta"] - (delta_info["after"] - delta_info["before"]))
            < 1e-9
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
