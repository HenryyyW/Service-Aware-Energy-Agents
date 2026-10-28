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
import statistics
from pathlib import Path
from typing import Dict, List, Optional

from experiments.run_benchmark import METRICS, compute_statistics


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
            cells = [
                format_cell(
                    compute_statistics([r.get(metric) for r in rows if r.get(metric) is not None])
                )
                for metric in metrics
            ]
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
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize benchmark results")
    parser.add_argument("--input", required=True, help="Benchmark output directory")
    parser.add_argument("--reference", default="rule_based", help="Reference controller")
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["total_cost", "grid_import_kwh", "peak_demand_kw",
                 "pv_self_consumption_kwh", "ev_completion_rate"],
    )
    parser.add_argument("--out", default=None, help="Markdown output path")
    args = parser.parse_args()

    unknown = [metric for metric in args.metrics if metric not in METRICS]
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
