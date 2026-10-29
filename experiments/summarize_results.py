#!/usr/bin/env python3
"""Summarize a benchmark directory into a paper-ready Markdown table.

Reads ``raw_results.json`` from ``experiments/run_benchmark.py`` and writes
mean +/- 95% CI per scenario/controller, plus paired deltas against a reference
controller (same seed, same scenario). Paired deltas cancel scenario-level
noise, which matters when only 3-5 seeds are affordable.

Usage::

    python -m experiments.summarize_results --input experiments/phase1_pilot \
        --reference rule_based --out experiments/phase1_pilot/summary.md
"""

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional

from experiments.run_benchmark import SUMMARY_METRICS, compute_statistics


def holm_adjust(pvalues: List[float]) -> List[float]:
    """Holm step-down adjusted p-values (family-wise error rate controlled).

    Order the raw p-values ascending, compare the i-th to alpha/(m-i), and
    enforce monotonicity so no adjusted p is smaller than a previous one.
    """
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted_sorted: List[float] = []
    running_max = 0.0
    for rank, idx in enumerate(order):
        value = pvalues[idx] * (m - rank)
        running_max = max(running_max, value)
        adjusted_sorted.append(min(1.0, running_max))
    adjusted = [0.0] * m
    for rank, idx in enumerate(order):
        adjusted[idx] = adjusted_sorted[rank]
    return adjusted


def paired_t_test(deltas: List[float]) -> Optional[Dict[str, float]]:
    """Two-sided paired t-test on per-seed deltas (null: mean delta = 0)."""
    n = len(deltas)
    if n < 2:
        return None
    try:
        from scipy import stats as scipy_stats
    except ImportError:
        return None
    mean = statistics.fmean(deltas)
    if all(d == 0 for d in deltas):
        return {"n": float(n), "mean": 0.0, "t": 0.0, "p": 1.0}
    if statistics.stdev(deltas) == 0:
        # Zero seed variance: the difference is deterministic for these seeds.
        # Report an infinite t rather than a numerically meaningless huge one.
        return {"n": float(n), "mean": mean, "t": math.copysign(math.inf, mean), "p": 0.0}
    result = scipy_stats.ttest_rel(deltas, [0.0] * n)
    return {"n": float(n), "mean": mean, "t": float(result.statistic), "p": float(result.pvalue)}


def load_results(directory: Path) -> List[Dict]:
    with open(directory / "raw_results.json", "r") as handle:
        return json.load(handle)


def group(results: List[Dict]) -> Dict[tuple, List[Dict]]:
    grouped: Dict[tuple, List[Dict]] = {}
    for row in results:
        grouped.setdefault((row["scenario"], row["controller"]), []).append(row)
    return grouped


def format_cell(stats: Optional[Dict[str, float]], digits: int = 2) -> str:
    if not stats:
        return "—"
    return f"{stats['mean']:.{digits}f} ± {stats['ci95']:.{digits}f}"


def cell(rows: List[Dict], metric: str) -> str:
    """Format one mean ± CI cell; a metric with no data renders as an em dash.

    Missing data must not render as 0.00: a 0.00 member_cost_coverage would read
    as "every member was interrupted", which is the opposite of "not recorded".
    """
    values = [row.get(metric) for row in rows if row.get(metric) is not None]
    return format_cell(compute_statistics(values) if values else None)


def build_markdown(
    results: List[Dict],
    metrics: List[str],
    reference: str,
) -> str:
    grouped = group(results)
    scenarios = sorted({scenario for scenario, _ in grouped})
    controllers = sorted({controller for _, controller in grouped})

    lines: List[str] = ["| Scenario | Controller | n | " + " | ".join(metrics) + " |"]
    lines.append("|---|---|---|" + "|".join(["---"] * len(metrics)) + "|")
    for scenario in scenarios:
        for controller in controllers:
            rows = grouped.get((scenario, controller))
            if not rows:
                continue
            cells = [cell(rows, metric) for metric in metrics]
            lines.append(
                f"| {scenario} | {controller} | {len(rows)} | " + " | ".join(cells) + " |"
            )

    # Paired deltas against the reference controller, matched on seed.
    lines.append("")
    lines.append(f"Paired deltas vs `{reference}` (negative cost/import/peak is better):")
    lines.append("")
    lines.append("| Scenario | Controller | n pairs | " + " | ".join(metrics) + " |")
    lines.append("|---|---|---|" + "|".join(["---"] * len(metrics)) + "|")
    for scenario in scenarios:
        reference_rows = {
            row["seed"]: row for row in grouped.get((scenario, reference), [])
        }
        for controller in controllers:
            if controller == reference:
                continue
            rows = grouped.get((scenario, controller), [])
            paired = [
                (row, reference_rows[row["seed"]])
                for row in rows
                if row["seed"] in reference_rows
            ]
            if not paired:
                continue
            cells = []
            for metric in metrics:
                deltas = [
                    row[metric] - baseline[metric]
                    for row, baseline in paired
                    if row.get(metric) is not None and baseline.get(metric) is not None
                ]
                stats = compute_statistics(deltas) if deltas else None
                if stats is None:
                    cells.append("—")
                else:
                    sign = "+" if stats["mean"] >= 0 else ""
                    cells.append(f"{sign}{stats['mean']:.2f} ± {stats['ci95']:.2f}")
            lines.append(
                f"| {scenario} | {controller} | {len(paired)} | " + " | ".join(cells) + " |"
            )

    lines.append("")
    lines.append(
        "Each cell is mean ± 95% confidence half-width (Student-t, sample std). "
        "A paired delta whose interval excludes zero is evidence of a difference "
        "for these seeds; it is not yet a paper-level claim."
    )

    # Holm-corrected paired t-tests. Family = the controller comparisons within
    # one (scenario, metric) cell, matching the protocol in BENCHMARK_MATRIX.md
    # section 4 ("with 4 comparisons per scenario, apply Holm correction").
    test_rows: List[Dict] = []
    for scenario in scenarios:
        reference_rows = {
            row["seed"]: row for row in grouped.get((scenario, reference), [])
        }
        for metric in metrics:
            family: List[Dict] = []
            for controller in controllers:
                if controller == reference:
                    continue
                paired = [
                    (row, reference_rows[row["seed"]])
                    for row in grouped.get((scenario, controller), [])
                    if row["seed"] in reference_rows
                    and row.get(metric) is not None
                    and reference_rows[row["seed"]].get(metric) is not None
                ]
                deltas = [row[metric] - baseline[metric] for row, baseline in paired]
                test = paired_t_test(deltas)
                family.append(
                    {
                        "scenario": scenario,
                        "comparison": controller,
                        "metric": metric,
                        "n": len(paired),
                        "delta": statistics.fmean(deltas) if deltas else float("nan"),
                        "p": test["p"] if test else None,
                        "t": test["t"] if test else None,
                    }
                )
            tested = [row for row in family if row["p"] is not None]
            adjusted = holm_adjust([row["p"] for row in tested])
            for row, p_adj in zip(tested, adjusted):
                row["p_holm"] = p_adj
            test_rows.extend(family)

    significant = [row for row in test_rows if row.get("p_holm") is not None]
    if significant:
        lines.append("")
        lines.append("Paired t-tests vs `" + reference + "` (Holm within scenario x metric family):")
        lines.append("")
        lines.append("| Scenario | Comparison | Metric | n | mean delta | t | p | p (Holm) | sig 0.05 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for row in significant:
            sign = "+" if row["delta"] >= 0 else ""
            sig = "yes" if row["p_holm"] < 0.05 else "no"
            lines.append(
                f"| {row['scenario']} | {row['comparison']} | {row['metric']} | {row['n']} "
                f"| {sign}{row['delta']:.2f} | {row['t']:.2f} | {row['p']:.4f} "
                f"| {row['p_holm']:.4f} | {sig} |"
            )
        lines.append("")
        lines.append(
            "With n = 3-5 seeds these tests are sensitive only to large effects; "
            "report interval widths alongside significance."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize benchmark results")
    parser.add_argument("--input", required=True, help="Benchmark output directory")
    parser.add_argument("--reference", default="rule_based", help="Reference controller")
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["total_cost", "grid_import_kwh", "peak_demand_kw",
                 "pv_self_consumption_kwh", "ev_completion_rate",
                 "member_cost_coverage", "members_interrupted_count"],
    )
    parser.add_argument("--out", default=None, help="Markdown output path")
    args = parser.parse_args()

    unknown = [metric for metric in args.metrics if metric not in SUMMARY_METRICS]
    if unknown:
        parser.error(f"unknown metrics: {unknown}")

    results = load_results(Path(args.input))
    markdown = build_markdown(results, args.metrics, args.reference)

    if args.out:
        Path(args.out).write_text(markdown)
        print(f"Wrote {args.out}")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
