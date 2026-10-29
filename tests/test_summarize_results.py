"""Tests for the statistical summary helpers in experiments/summarize_results.py."""
import math

from experiments.summarize_results import build_markdown, holm_adjust, paired_t_test
def test_paired_t_test_handles_zero_variance_deltas():
    deterministic = paired_t_test([2.0, 2.0, 2.0])
    assert deterministic is not None
    assert deterministic["t"] == math.inf and deterministic["p"] == 0.0
    deterministic_neg = paired_t_test([-2.0, -2.0, -2.0])
    assert deterministic_neg is not None and deterministic_neg["t"] == -math.inf


def test_holm_adjust_matches_reference_values():
    # Worked example: m=4, raw p = [0.01, 0.04, 0.03, 0.20].
    # Sorted: 0.01*(4)=0.04; 0.03*3=0.09; 0.04*2=0.08 -> monotone max 0.09; 0.20*1=0.20.
    adjusted = holm_adjust([0.01, 0.04, 0.03, 0.20])
    assert [round(p, 4) for p in adjusted] == [0.04, 0.09, 0.09, 0.20]


def test_holm_adjust_caps_at_one_and_is_monotone_in_raw_p():
    adjusted = holm_adjust([0.5, 0.6, 0.9])
    assert adjusted == [1.0, 1.0, 1.0]
    single = holm_adjust([0.03])
    assert single == [0.03]


def test_paired_t_test_detects_shift_and_null():
    shifted = paired_t_test([10.0, 12.0, 11.0, 13.0])
    assert shifted is not None and shifted["p"] < 0.001 and shifted["t"] > 10
    null = paired_t_test([1.0, -1.0, 0.5, -0.5])
    assert null is not None and null["p"] > 0.05
    assert paired_t_test([5.0]) is None  # too few pairs


def _row(scenario, controller, seed, cost):
    return {
        "scenario": scenario,
        "controller": controller,
        "seed": seed,
        "run_id": f"{scenario}_{controller}_{seed}",
        "total_cost": cost,
        "grid_import_kwh": cost * 10,
        "peak_demand_kw": cost / 10,
        "pv_self_consumption_kwh": 100.0,
        "ev_completion_rate": 0.5,
    }


def test_build_markdown_emits_holm_table_for_synthetic_results():
    results = []
    for seed, (base, delta) in {42: (100.0, 20.0), 123: (102.0, 18.0), 456: (101.0, 22.0)}.items():
        results.append(_row("scenario_a", "rule_based", seed, base))
        results.append(_row("scenario_a", "mpc", seed, base + delta))
    markdown = build_markdown(results, ["total_cost"], "rule_based")
    assert "Paired t-tests vs `rule_based`" in markdown
    assert "p (Holm)" in markdown
    # A consistent +20 delta over 3 seeds is a strong effect: significant after Holm.
    assert "| scenario_a | mpc | total_cost | 3 | +20.00" in markdown
    assert "| yes |" in markdown


def test_build_markdown_skips_tests_without_reference_pairs():
    results = [_row("scenario_a", "mpc", 42, 120.0)]  # no rule_based rows
    markdown = build_markdown(results, ["total_cost"], "rule_based")
    assert "Paired t-tests" not in markdown
