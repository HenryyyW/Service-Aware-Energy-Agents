"""Paper-figure pipeline (F1-F3) and the Scenario E failure covariate.

The figures are generated artifacts, so these tests check the data assembly
(aggregation, ordering, Pareto points) and that a synthetic benchmark directory
renders end-to-end. They do not compare pixel output.
"""
import json

import pytest

from experiments.make_figures import (
    load_results,
    make_figures,
    pareto_points,
    seed_strip_offsets,
    summarize,
)
from experiments.run_benchmark import SUMMARY_METRICS, extract_run_metrics


def _row(scenario, controller, seed, cost, completion, peak=10.0, status="completed"):
    return {
        "scenario": scenario,
        "controller": controller,
        "seed": seed,
        "status": status,
        "total_cost": cost,
        "ev_completion_rate": completion,
        "peak_demand_kw": peak,
    }


def test_summarize_is_ordered_and_keeps_raw_values():
    rows = [
        _row("scenario_b", "mpc", 42, 150.0, 1.0),
        _row("scenario_a", "rule_based", 123, 100.0, 0.1),
        _row("scenario_a", "rule_based", 42, 102.0, 0.2),
        _row("scenario_a", "mpc", 42, 160.0, 1.0),
    ]
    summary = summarize(rows, ["total_cost"])

    assert [(item["scenario"], item["controller"]) for item in summary] == [
        ("scenario_a", "mpc"),
        ("scenario_a", "rule_based"),
        ("scenario_b", "mpc"),
    ]
    rule_based = next(item for item in summary if item["controller"] == "rule_based")
    assert rule_based["n"] == 2
    assert rule_based["total_cost"]["mean"] == pytest.approx(101.0)
    assert rule_based["total_cost__values"] == [100.0, 102.0]
    # CI comes from the shared Student-t helper used by T2/T3.
    assert rule_based["total_cost"]["ci95"] > 0


def test_summarize_skips_missing_metric_values_without_losing_the_run():
    rows = [
        _row("scenario_e", "multi_agent", 42, 95.0, 0.0),
        {**_row("scenario_e", "multi_agent", 123, 0.0, 0.0), "total_cost": None},
    ]
    summary = summarize(rows, ["total_cost"])
    record = summary[0]

    assert record["n"] == 2
    assert record["total_cost"]["count"] == 1
    assert record["total_cost"]["mean"] == pytest.approx(95.0)


def test_pareto_points_exclude_records_without_metrics():
    rows = [
        _row("scenario_a", "rule_based", 42, 100.0, 0.1, 20.0),
        _row("scenario_a", "mpc", 42, 160.0, 1.0, 18.0),
    ]
    summary = summarize(rows, ["total_cost", "ev_completion_rate", "peak_demand_kw"])
    points = pareto_points(summary)

    assert [point["controller"] for point in points] == ["mpc", "rule_based"]
    assert points[1]["cost"] == pytest.approx(100.0)
    assert points[1]["service"] == pytest.approx(0.1)
    assert points[1]["peak"] == pytest.approx(20.0)


def test_seed_strip_offsets_are_symmetric_and_stable():
    assert seed_strip_offsets(1) == [0.0]
    offsets = seed_strip_offsets(5)
    assert offsets == pytest.approx([-0.3, -0.15, 0.0, 0.15, 0.3])
    assert seed_strip_offsets(5) == offsets


def test_load_results_drops_failed_runs(tmp_path):
    rows = [
        _row("scenario_a", "rule_based", 42, 100.0, 0.1),
        _row("scenario_a", "mpc", 42, 160.0, 1.0, status="failed"),
    ]
    (tmp_path / "raw_results.json").write_text(json.dumps(rows))
    loaded = load_results(tmp_path)
    assert [row["controller"] for row in loaded] == ["rule_based"]


def test_make_figures_renders_all_panels(tmp_path):
    rows = []
    for scenario in ("scenario_a", "scenario_e"):
        for controller, cost, completion in (
            ("rule_based", 100.0, 0.1),
            ("mpc", 160.0, 1.0),
        ):
            for seed in (42, 123):
                rows.append(
                    _row(scenario, controller, seed, cost + seed / 1000.0, completion)
                )
    (tmp_path / "raw_results.json").write_text(json.dumps(rows))
    out_dir = tmp_path / "figures"

    written = make_figures(tmp_path, out_dir, ["total_cost", "ev_completion_rate"])

    assert len(written["f1"]) == 4  # 2 metrics x (png + pdf)
    assert len(written["f2"]) == 4
    assert len(written["f3"]) == 2
    assert all(path.exists() and path.stat().st_size > 0 for paths in written.values() for path in paths)


def test_extract_run_metrics_reports_scenario_e_covariate():
    """Members interrupted by an injected failure surface as a count column."""
    result_data = {
        "run_id": "scenario_e_rule_based_42",
        "status": "completed",
        "energy": {"total_cost": 95.5},
        "service": {
            "ev_completion_rate": 0.5,
            "member_cost_coverage": 0.75,
            "members_interrupted": ["m3"],
        },
    }
    metrics = extract_run_metrics(
        result_data, "scenario_e", "rule_based", 42, 12.34
    )

    assert metrics["members_interrupted_count"] == 1
    assert metrics["member_cost_coverage"] == pytest.approx(0.75)
    assert metrics["total_cost"] == pytest.approx(95.5)
    assert metrics["runtime_seconds"] == pytest.approx(12.3)
    # The covariate is part of what the summary tables aggregate.
    assert "members_interrupted_count" in SUMMARY_METRICS
    assert "member_cost_coverage" in SUMMARY_METRICS


def test_extract_run_metrics_defaults_covariate_for_older_artifacts():
    result_data = {"status": "completed", "energy": {"total_cost": 90.0}}
    metrics = extract_run_metrics(result_data, "scenario_a", "mpc", 42, 1.0)

    assert metrics["members_interrupted_count"] == 0
    assert metrics["member_cost_coverage"] is None
