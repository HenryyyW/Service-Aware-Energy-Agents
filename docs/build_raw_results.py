#!/usr/bin/env python3
"""Build ``raw_results.json`` (the layout ``experiments/run_benchmark.py``
writes and ``experiments/make_figures.py`` reads) from a matrix directory
produced by ``scripts/run_benchmark_supervisor.py``.

The B-axis matrices were produced by the supervisor (per-run
``<matrix>/<scenario>/<run_id>/result.json`` + ``manifest.json``), which does
not emit the aggregated ``raw_results.json``. This script flattens every
result with the same ``run_benchmark.extract_run_metrics`` mapping, so figures
and tables can never disagree with the summaries computed from the same
directory.

Usage::

    python -m docs.build_raw_results --matrix experiments/matrix_full \
        [--matrix experiments/matrix_d_rerun ...]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from experiments.run_benchmark import SUMMARY_METRICS, compute_statistics, extract_run_metrics

ROOT = Path(__file__).resolve().parents[1]


def build(matrix_dir: Path) -> Path:
    rows: List[Dict[str, Any]] = []
    for result_file in sorted(matrix_dir.glob("scenario_*/*/result.json")):
        scenario_id = result_file.parent.parent.name
        run_id = result_file.parent.name
        if not run_id.startswith(f"{scenario_id}_"):
            continue
        remainder = run_id[len(scenario_id) + 1 :]
        controller, _, seed = remainder.rpartition("_")
        if not controller or not seed.isdigit():
            continue
        data = json.loads(result_file.read_text())
        rows.append(
            extract_run_metrics(
                data, scenario_id, controller, int(seed), runtime=0.0, run_id=run_id
            )
        )

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(f"{row['scenario']}::{row['controller']}", []).append(row)

    summary_stats: Dict[str, Dict[str, Dict[str, float]]] = {}
    for key, group in grouped.items():
        summary_stats[key] = {}
        for metric in SUMMARY_METRICS:
            values = [row.get(metric) for row in group if row.get(metric) is not None]
            if values:
                summary_stats[key][metric] = compute_statistics(values)

    scenarios = sorted({row["scenario"] for row in rows})
    controllers = sorted({row["controller"] for row in rows})
    seeds = sorted({row["seed"] for row in rows})
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scenarios": scenarios,
        "controllers": controllers,
        "seeds": seeds,
        "total_runs": len(rows),
        "successful_runs": len(rows),
        "wall_clock_seconds": 0.0,
        "confidence_level": 0.95,
        "ci_method": "student_t_half_width",
        "summary_statistics": summary_stats,
    }
    out = matrix_dir / "raw_results.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"{matrix_dir}: {len(rows)} runs -> {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="append", required=True)
    args = parser.parse_args()
    for matrix in args.matrix:
        build(ROOT / matrix if not Path(matrix).is_absolute() else Path(matrix))


if __name__ == "__main__":
    main()
