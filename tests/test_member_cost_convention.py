"""Scenario E reporting convention for member costs under failure injection.

Convention (decided for the paper): a member whose per-step cost data is
corrupted by an injected failure gets per-member cost None (service
interrupted, cost undefined ??never 0.0, which would score a failed member as
free). Economic aggregates (gini, worst/best member) use valid members only,
and the interruption is reported explicitly via members_interrupted and
member_cost_coverage.
"""
import math

import pytest

from src.evaluation.fairness import FairnessAnalyzer
from src.schemas.action import (
    AppliedActions,
    LimitedActions,
    RequestedActions,
    SimulationStepResult,
)
from src.schemas.scenario import BuildingConfig, BuildingType, ScenarioConfig


def _scenario(*member_ids):
    return ScenarioConfig(
        scenario_id="member_cost_convention",
        name="Convention",
        description="Member-cost convention test",
        random_seed=42,
        timestep_minutes=60,
        buildings=[
            BuildingConfig(building_id=m, building_type=BuildingType.RESIDENTIAL)
            for m in member_ids
        ],
    )


def _step(member_costs):
    return SimulationStepResult(
        timestep=0,
        requested_actions=RequestedActions(timestep=0, actions=[]),
        limited_actions=LimitedActions(timestep=0, actions=[]),
        applied_actions=AppliedActions(timestep=0, actions=[]),
        costs=dict(member_costs),
    )


def test_interrupted_member_gets_none_not_zero():
    analyzer = FairnessAnalyzer(_scenario("m0", "m1", "m2"))
    history = [
        _step({"m0": 1.0, "m1": 2.0, "m2": float("nan")}),
        _step({"m0": 1.5, "m1": 2.5, "m2": float("nan")}),
    ]
    metrics = analyzer.analyze(history)

    assert metrics.per_member_costs["m0"] == 2.5
    assert metrics.per_member_costs["m1"] == 4.5
    assert metrics.per_member_costs["m2"] is None
    assert metrics.members_interrupted == ["m2"]
    assert metrics.member_cost_coverage == pytest.approx(2 / 3)
    # Economic aggregates exclude the interrupted member instead of propagating
    # NaN or scoring it as free.
    assert not math.isnan(metrics.gini_coefficient)
    assert metrics.worst_member_cost == 4.5
    assert metrics.best_member_cost == 2.5


def test_no_failures_is_unchanged_behavior():
    analyzer = FairnessAnalyzer(_scenario("m0", "m1"))
    history = [_step({"m0": 3.0, "m1": 1.0}), _step({"m0": 1.0, "m1": 1.0})]
    metrics = analyzer.analyze(history)

    assert metrics.members_interrupted == []
    assert metrics.member_cost_coverage == 1.0
    assert metrics.per_member_costs == {"m0": 4.0, "m1": 2.0}
    assert metrics.worst_member_cost == 4.0
    assert metrics.best_member_cost == 2.0


def test_savings_are_none_for_interrupted_members():
    analyzer = FairnessAnalyzer(_scenario("m0", "m1"))
    baseline = [_step({"m0": 10.0, "m1": 10.0})]
    analyzer.set_baseline(baseline)
    history = [_step({"m0": float("nan"), "m1": 5.0})]
    metrics = analyzer.analyze(history)

    assert metrics.per_member_savings["m0"] is None
    assert metrics.per_member_savings["m1"] == pytest.approx(5.0)


def test_interrupted_members_serialize_as_json_null():
    """result.json must stay strict-JSON: no NaN literals from member costs."""
    import json

    analyzer = FairnessAnalyzer(_scenario("m0", "m1"))
    history = [_step({"m0": float("nan"), "m1": 2.0})]
    metrics = analyzer.analyze(history)
    payload = json.dumps(metrics.per_member_costs, allow_nan=False)
    assert json.loads(payload) == {"m0": None, "m1": 2.0}
