#!/usr/bin/env python3
"""Paper figures F1-F3 from a benchmark directory.

Reads ``raw_results.json`` written by ``experiments/run_benchmark.py`` and
renders the three quantitative figures described in
``docs/paper_results_outline.md``:

* F1 -- per-scenario KPI bars with 95% CI whiskers (one file per metric).
* F2 -- per-seed value strips, one panel per scenario.
* F3 -- cost vs EV-completion Pareto scatter, annotated with peak demand.

Numbers are aggregated with the same Student-t half-width used by the summary
tables, so a figure can never disagree with T2/T3 for the same input directory.

Usage::

    python -m experiments.make_figures --input experiments/matrix_full_v2 \
        --out experiments/figures

Figures are generated artifacts and are not committed; only this script is.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from experiments.run_benchmark import compute_statistics

# Colour-blind-safe categorical palette (Okabe-Ito), assigned in controller
# order so a controller keeps its colour across every figure.
CONTROLLER_COLORS: Dict[str, str] = {
    "rule_based": "#0072B2",
    "multi_agent": "#D55E00",
    "centralized": "#009E73",
    "mpc": "#CC79A7",
    "rl": "#E69F00",
    "llm_agent": "#56B4E9",
    "llm_agent_verified": "#000000",
}

SCENARIO_LABELS = {
    "scenario_a": "A",
    "scenario_b": "B",
    "scenario_c": "C",
    "scenario_d": "D",
    "scenario_e": "E",
}

CONTROLLER_LABELS = {
    "rule_based": "Rule-based",
    "multi_agent": "Multi-agent",
    "centralized": "Centralized",
    "mpc": "MPC",
    "rl": "RL",
    "llm_agent": "LLM",
    "llm_agent_verified": "LLM+verif.",
}

METRIC_LABELS = {
    "total_cost": "Total cost (USD)",
    "peak_demand_kw": "Peak demand (kW)",
    "ev_completion_rate": "EV completion rate",
    "grid_import_kwh": "Grid import (kWh)",
    "carbon_emissions_kg": "Carbon emissions (kg)",
}


def _pyplot():
    """Import pyplot with a headless backend (no display needed in CI)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def load_results(input_dir: Path) -> List[Dict[str, Any]]:
    """Load per-run rows, dropping failed runs that carry no metrics."""
    with open(Path(input_dir) / "raw_results.json", "r") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list):
        raise ValueError(f"{input_dir}/raw_results.json must be a list of runs")
    return [row for row in rows if row.get("status", "completed") == "completed"]


def summarize(
    rows: Sequence[Dict[str, Any]],
    metrics: Sequence[str],
) -> List[Dict[str, Any]]:
    """Aggregate rows into one record per (scenario, controller).

    Returns a deterministic list ordered by scenario then controller so figures
    are byte-stable across runs (important for diffing regenerated artifacts).
    """
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["scenario"], row["controller"]), []).append(row)

    summary: List[Dict[str, Any]] = []
    for (scenario, controller) in sorted(grouped):
        runs = grouped[(scenario, controller)]
        record: Dict[str, Any] = {
            "scenario": scenario,
            "controller": controller,
            "n": len(runs),
            "seeds": [run.get("seed") for run in runs],
        }
        for metric in metrics:
            values = [run[metric] for run in runs if run.get(metric) is not None]
            record[metric] = compute_statistics(values)
            record[f"{metric}__values"] = values
        summary.append(record)
    return summary


def scenarios_in(summary: Sequence[Dict[str, Any]]) -> List[str]:
    return sorted({record["scenario"] for record in summary})


def controllers_in(summary: Sequence[Dict[str, Any]]) -> List[str]:
    """Controller order is fixed (rule_based first, then others sorted)."""
    present = {record["controller"] for record in summary}
    known = [name for name in CONTROLLER_COLORS if name in present]
    rest = sorted(present.difference(known))
    return known + rest


def style_for(controller: str) -> Dict[str, Any]:
    return {
        "color": CONTROLLER_COLORS.get(controller, "#666666"),
        "label": CONTROLLER_LABELS.get(controller, controller),
    }


def scenario_label(scenario: str) -> str:
    return SCENARIO_LABELS.get(scenario, scenario)


def metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def seed_strip_offsets(count: int) -> List[float]:
    """Symmetric, deterministic x-offsets so seed points never overlap."""
    if count <= 1:
        return [0.0]
    span = 0.3
    step = (2 * span) / (count - 1)
    return [-span + index * step for index in range(count)]


def save_figure(figure, out_dir: Path, stem: str) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for suffix in ("png", "pdf"):
        path = out_dir / f"{stem}.{suffix}"
        figure.savefig(path, dpi=200, bbox_inches="tight")
        written.append(path)
    return written


def plot_metric_bars(summary, metric: str, out_dir: Path) -> List[Path]:
    """F1: grouped bars per scenario with 95% CI whiskers."""
    plt = _pyplot()
    scenarios = scenarios_in(summary)
    controllers = controllers_in(summary)

    width = 0.8 / max(len(controllers), 1)
    positions = list(range(len(scenarios)))
    figure, axes = plt.subplots(figsize=(7.2, 3.6))
    for offset, controller in enumerate(controllers):
        style = style_for(controller)
        means, errors = [], []
        for scenario in scenarios:
            stats = next(
                (
                    item[metric]
                    for item in summary
                    if item["scenario"] == scenario and item["controller"] == controller
                ),
                None,
            )
            means.append(stats["mean"] if stats else 0.0)
            errors.append(stats["ci95"] if stats else 0.0)
        xs = [position - 0.4 + width / 2 + offset * width for position in positions]
        axes.bar(
            xs,
            means,
            width=width,
            yerr=errors,
            capsize=2,
            color=style["color"],
            label=style["label"],
            error_kw={"linewidth": 0.9},
        )

    axes.set_xticks(positions)
    axes.set_xticklabels([f"Scenario {scenario_label(s)}" for s in scenarios])
    axes.set_ylabel(metric_label(metric))
    axes.set_title(f"{metric_label(metric)} by scenario (mean, 95% CI)")
    axes.grid(axis="y", linewidth=0.4, alpha=0.4)
    axes.set_axisbelow(True)
    if len(controllers) > 1:
        axes.legend(frameon=False, fontsize=8, ncol=min(3, len(controllers)))
    figure.tight_layout()
    written = save_figure(figure, out_dir, f"f1_{metric}")
    plt.close(figure)
    return written


def plot_seed_strips(summary, metric: str, out_dir: Path) -> List[Path]:
    """F2: per-seed values, one panel per scenario, mean marked."""
    plt = _pyplot()
    scenarios = scenarios_in(summary)
    controllers = controllers_in(summary)
    figure, axes_grid = plt.subplots(
        1, len(scenarios), figsize=(2.4 * len(scenarios), 3.2), sharey=True
    )
    axes_list = list(axes_grid) if len(scenarios) > 1 else [axes_grid]

    for axis, scenario in zip(axes_list, scenarios):
        for position, controller in enumerate(controllers):
            record = next(
                (
                    item
                    for item in summary
                    if item["scenario"] == scenario and item["controller"] == controller
                ),
                None,
            )
            if not record:
                continue
            values = record.get(f"{metric}__values") or []
            style = style_for(controller)
            offsets = seed_strip_offsets(len(values))
            axis.scatter(
                [position + delta for delta in offsets],
                values,
                s=18,
                color=style["color"],
                alpha=0.85,
                edgecolors="none",
            )
            if values:
                axis.hlines(
                    record[metric]["mean"],
                    position - 0.32,
                    position + 0.32,
                    colors=style["color"],
                    linewidth=1.6,
                )
        axis.set_xticks(range(len(controllers)))
        axis.set_xticklabels(
            [CONTROLLER_LABELS.get(c, c) for c in controllers], rotation=40, ha="right"
        )
        axis.set_title(f"Scenario {scenario_label(scenario)}", fontsize=9)
        axis.grid(axis="y", linewidth=0.4, alpha=0.4)
        axis.set_axisbelow(True)

    axes_list[0].set_ylabel(metric_label(metric))
    figure.suptitle(f"{metric_label(metric)}: per-seed values (line = mean)", fontsize=9)
    figure.tight_layout()
    written = save_figure(figure, out_dir, f"f2_{metric}")
    plt.close(figure)
    return written


def pareto_points(summary, cost_metric="total_cost", service_metric="ev_completion_rate"):
    """Points for F3: mean cost, mean service, mean peak demand per record."""
    points = []
    for record in summary:
        cost = record.get(cost_metric) or {}
        service = record.get(service_metric) or {}
        peak = record.get("peak_demand_kw") or {}
        if cost.get("count", 0) == 0 or service.get("count", 0) == 0:
            continue
        points.append(
            {
                "scenario": record["scenario"],
                "controller": record["controller"],
                "cost": cost["mean"],
                "service": service["mean"],
                "peak": peak.get("mean", 0.0),
            }
        )
    return points


def plot_pareto(summary, out_dir: Path) -> List[Path]:
    """F3: cost vs EV-completion scatter, marker area encodes peak demand."""
    plt = _pyplot()
    points = pareto_points(summary)
    scenarios = sorted({point["scenario"] for point in points})
    controllers = controllers_in(summary)

    figure, axis = plt.subplots(figsize=(6.4, 4.2))
    markers = ["o", "s", "^", "D", "v", "P", "X"]
    for controller_index, controller in enumerate(controllers):
        subset = [point for point in points if point["controller"] == controller]
        if not subset:
            continue
        style = style_for(controller)
        for scenario in scenarios:
            scenario_points = [point for point in subset if point["scenario"] == scenario]
            if not scenario_points:
                continue
            axis.scatter(
                [point["cost"] for point in scenario_points],
                [point["service"] for point in scenario_points],
                s=[min(max(point["peak"], 1.0) * 2.5, 120) for point in scenario_points],
                marker=markers[controller_index % len(markers)],
                color=style["color"],
                alpha=0.85,
                edgecolors="white",
                linewidths=0.6,
            )
            for point in scenario_points:
                axis.annotate(
                    scenario_label(point["scenario"]),
                    (point["cost"], point["service"]),
                    textcoords="offset points",
                    xytext=(4, 4),
                    fontsize=6,
                    color="#444444",
                )

    for controller_index, controller in enumerate(controllers):
        if not any(point["controller"] == controller for point in points):
            continue
        style = style_for(controller)
        axis.scatter([], [], marker=markers[controller_index % len(markers)],
                     color=style["color"], label=style["label"], s=36)

    axis.set_xlabel("Total cost (USD, mean)")
    axis.set_ylabel("EV completion rate (mean)")
    axis.set_title("Cost vs EV service (marker area = peak demand)")
    axis.grid(linewidth=0.4, alpha=0.4)
    axis.set_axisbelow(True)
    axis.legend(frameon=False, fontsize=8, ncol=2)
    figure.tight_layout()
    written = save_figure(figure, out_dir, "f3_cost_vs_ev_completion")
    plt.close(figure)
    return written


def make_figures(
    input_dir: Path,
    out_dir: Path,
    metrics: Optional[Sequence[str]] = None,
) -> Dict[str, List[Path]]:
    """Render F1 (per metric), F2 (per metric) and F3 into ``out_dir``."""
    metrics = list(metrics or ("total_cost", "peak_demand_kw", "ev_completion_rate"))
    rows = load_results(Path(input_dir))
    if not rows:
        raise ValueError(f"no completed runs in {input_dir}/raw_results.json")
    summary = summarize(rows, list(dict.fromkeys([*metrics, "peak_demand_kw"])))

    written: Dict[str, List[Path]] = {"f1": [], "f2": [], "f3": []}
    for metric in metrics:
        written["f1"] += plot_metric_bars(summary, metric, Path(out_dir))
        written["f2"] += plot_seed_strips(summary, metric, Path(out_dir))
    written["f3"] += plot_pareto(summary, Path(out_dir))
    return written


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="benchmark output directory")
    parser.add_argument("--out", default="experiments/figures", help="figure directory")
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=None,
        help="metrics to render for F1/F2 (default: total_cost peak_demand_kw "
        "ev_completion_rate)",
    )
    args = parser.parse_args(argv)

    written = make_figures(Path(args.input), Path(args.out), args.metrics)
    for group, paths in written.items():
        print(f"{group}: {len(paths)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
