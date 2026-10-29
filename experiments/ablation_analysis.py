#!/usr/bin/env python3
"""T4/T5 analysis for the paper: ablation execution metrics and reproducibility.

``summarize_results`` works on ``raw_results.json`` from the matrix runner. The
ablation has extra evidence that only exists per run directory (prompt hash,
backend, first-attempt validity, repairs, wall time) and the reproducibility
table needs the manifests themselves. This module scans a benchmark directory
of run folders and produces those two tables, reusing the same CI/Holm helpers
as T2/T3 so a delta can never be computed two different ways.

Subcommands::

    python -m experiments.ablation_analysis ablation \
        --input experiments/ablation_fallback --out experiments/ablation_fallback
    python -m experiments.ablation_analysis repro \
        --input experiments/matrix_full_v2 --out experiments/matrix_full_v2

Both write a Markdown table and a JSON payload; neither writes trajectories.
"""

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from experiments.run_benchmark import (
    SUMMARY_METRICS,
    compute_statistics,
    extract_run_metrics,
)
from experiments.summarize_results import build_markdown

# Agent-execution fields the ablation reports (ABLATION_DESIGN.md).
AGENT_FIELDS = (
    "agent_backend",
    "first_attempt_validity",
    "repair_iterations",
    "total_steps",
    "verification_failures",
    "unparseable_outputs",
)

# KPIs shown in the T4 table; the full set stays in the JSON payload.
T4_METRICS = (
    "total_cost",
    "grid_import_kwh",
    "peak_demand_kw",
    "ev_completion_rate",
    "member_cost_coverage",
    "members_interrupted_count",
)


def parse_run_id(run_id: str) -> Optional[Dict[str, Any]]:
    """Split ``<scenario>_<controller>_<seed>`` without breaking controller names.

    Both parts contain underscores (``scenario_a``, ``multi_agent``,
    ``llm_agent_verified``), so the scenario is matched as ``scenario_<token>``
    and the seed is the trailing integer.
    """
    match = re.match(r"^(scenario_[A-Za-z0-9]+)_(.+)_(\d+)$", run_id)
    if not match:
        return None
    scenario, controller, seed = match.groups()
    return {"scenario": scenario, "controller": controller, "seed": int(seed)}


def iter_run_dirs(directory: Path) -> List[Path]:
    """Run directories containing a result.json, deterministically ordered."""
    return sorted(
        path.parent for path in Path(directory).rglob("result.json")
    )


def _duration_seconds(result: Dict[str, Any]) -> Optional[float]:
    start, end = result.get("start_time"), result.get("end_time")
    if not start or not end:
        return None
    try:
        return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    except (TypeError, ValueError):
        return None


def load_run(run_dir: Path) -> Optional[Dict[str, Any]]:
    """Read result.json + manifest.json for one run, tolerating missing files."""
    try:
        with open(run_dir / "result.json", "r") as handle:
            result = json.load(handle)
    except (OSError, ValueError):
        return None
    manifest = {}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError):
            manifest = {}
    return {"result": result, "manifest": manifest, "run_dir": str(run_dir)}


def agent_block(run: Dict[str, Any]) -> Dict[str, Any]:
    """Agent accounting from the manifest, falling back to result.controller_config."""
    manifest_agent = (run.get("manifest") or {}).get("agent") or {}
    if manifest_agent:
        return manifest_agent
    config = (run.get("result") or {}).get("controller_config") or {}
    return config if "agent_backend" in config else {}


def ablation_row(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One T4/T5 row: standard KPIs plus the agent-execution fields."""
    result = run["result"]
    run_id = result.get("run_id") or Path(run["run_dir"]).name
    parsed = parse_run_id(run_id)
    if not parsed:
        return None

    row = extract_run_metrics(
        result,
        parsed["scenario"],
        parsed["controller"],
        int(result.get("random_seed", parsed["seed"])),
        _duration_seconds(result) or 0.0,
        run_id,
    )
    row["wall_seconds"] = _duration_seconds(result)

    agent = agent_block(run)
    for field in AGENT_FIELDS:
        row[field] = agent.get(field)
    row["prompt_hash"] = agent.get("prompt_hash")
    row["sampling_seed"] = agent.get("sampling_seed")
    row["run_id"] = run_id
    return row


def load_ablation_rows(directory: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for run_dir in iter_run_dirs(directory):
        run = load_run(run_dir)
        if not run:
            continue
        row = ablation_row(run)
        if row and row.get("status") in (None, "completed"):
            rows.append(row)
    return rows


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    clean = [float(value) for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def _failures_total(value: Any) -> Optional[float]:
    """verification_failures is a {category: count} dict per run."""
    if value is None:
        return None
    if isinstance(value, dict):
        numbers = [float(v) for v in value.values() if isinstance(v, (int, float))]
        return float(sum(numbers))
    return float(value)


def agent_execution_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate agent-execution metrics per (scenario, controller)."""
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["scenario"], row["controller"]), []).append(row)

    summary: List[Dict[str, Any]] = []
    for (scenario, controller) in sorted(grouped):
        runs = grouped[(scenario, controller)]
        backends = sorted({str(row["agent_backend"]) for row in runs if row["agent_backend"]})
        repairs = _mean(row.get("repair_iterations") for row in runs)
        steps = _mean(row.get("total_steps") for row in runs)
        summary.append(
            {
                "scenario": scenario,
                "controller": controller,
                "n": len(runs),
                "backends": backends,
                "first_attempt_validity": _mean(
                    row.get("first_attempt_validity") for row in runs
                ),
                "repair_iterations": repairs,
                "repairs_per_step": (
                    repairs / steps if repairs is not None and steps else None
                ),
                "verification_failures": _mean(
                    _failures_total(row.get("verification_failures")) for row in runs
                ),
                "unparseable_outputs": _mean(row.get("unparseable_outputs") for row in runs),
                "wall_seconds": _mean(row.get("wall_seconds") for row in runs),
            }
        )
    return summary


def _fmt(value: Optional[float], digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def build_agent_execution_markdown(rows: Sequence[Dict[str, Any]], source: str) -> str:
    lines = [
        f"# Ablation agent execution ({source})",
        "",
        "Fallback mode is labelled explicitly: `agent_backend: fallback` means no",
        "LLM backend was configured, so these numbers measure the verification",
        "machinery under a deterministic proposer, not LLM proposal quality.",
        "",
        "| Scenario | Controller | n | backend | first-attempt validity | repairs/run | repairs/step | verification failures | unparseable | wall s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['scenario']} | {row['controller']} | {row['n']} "
            f"| {', '.join(row['backends']) or '—'} "
            f"| {_fmt(row['first_attempt_validity'])} "
            f"| {_fmt(row['repair_iterations'], 2)} "
            f"| {_fmt(row['repairs_per_step'], 4)} "
            f"| {_fmt(row['verification_failures'], 2)} "
            f"| {_fmt(row['unparseable_outputs'], 2)} "
            f"| {_fmt(row['wall_seconds'], 1)} |"
        )
    return "\n".join(lines) + "\n"


def repro_report(directory: Path) -> Dict[str, Any]:
    """T5 inputs: commits, dirtiness, config hashes, seeding and backend mix."""
    run_dirs = iter_run_dirs(directory)
    commits, dirty, pythons = set(), set(), set()
    hashes: Dict[str, set] = {}
    run_counts: Dict[str, int] = {}
    seed_mismatches: List[str] = []
    backends: Dict[str, int] = {}
    missing_agent = 0
    sampled = 0
    manifests_seen = 0

    for run_dir in run_dirs:
        run = load_run(run_dir)
        if not run:
            continue
        manifest = run["manifest"]
        if not manifest:
            continue
        manifests_seen += 1
        commits.add(str(manifest.get("git_commit")))
        dirty.add(bool(manifest.get("git_dirty")))
        pythons.add(str(manifest.get("python")))
        scenario = str(manifest.get("scenario_id") or run_dir.parent.name)
        if manifest.get("scenario_config_sha256"):
            hashes.setdefault(scenario, set()).add(manifest["scenario_config_sha256"])
        run_counts[scenario] = run_counts.get(scenario, 0) + 1

        agent = agent_block(run)
        if agent:
            sampled += 1
            backends[str(agent.get("agent_backend"))] = (
                backends.get(str(agent.get("agent_backend")), 0) + 1
            )
            if agent.get("sampling_seed") != manifest.get("random_seed"):
                seed_mismatches.append(str(manifest.get("run_id") or run_dir.name))
        else:
            missing_agent += 1

    failed_path = Path(directory) / "failed_runs.json"
    failed_runs = []
    if failed_path.exists():
        try:
            with open(failed_path, "r") as handle:
                failed_runs = json.load(handle)
        except (OSError, ValueError):
            failed_runs = []

    return {
        "directory": str(directory),
        "runs_with_manifest": manifests_seen,
        "git_commits": sorted(commits),
        "git_dirty_values": sorted(dirty),
        "config_hashes": {scenario: sorted(values) for scenario, values in sorted(hashes.items())},
        "run_counts": dict(sorted(run_counts.items())),
        "python_versions": sorted(pythons),
        "agent_backend_counts": backends,
        "runs_with_sampling_seed": sampled,
        "sampling_seed_mismatches": seed_mismatches,
        "runs_without_agent_stats": missing_agent,
        "failed_runs": failed_runs,
    }


def build_repro_markdown(report: Dict[str, Any]) -> str:
    commits = ", ".join(f"`{commit}`" for commit in report["git_commits"]) or "—"
    dirty = ", ".join(str(value).lower() for value in report["git_dirty_values"]) or "—"
    lines = [
        "# Reproducibility sweep (T5)",
        "",
        f"Directory: `{report['directory']}`  ",
        f"Runs with a manifest: {report['runs_with_manifest']}  ",
        f"Git commit(s): {commits}  ",
        f"`git_dirty`: {dirty}  ",
        f"Python: {', '.join(report['python_versions']) or '—'}  ",
        f"Agent backends: "
        f"{', '.join(f'{k}={v}' for k, v in sorted(report['agent_backend_counts'].items())) or '—'}  ",
        f"Failed runs: {len(report['failed_runs'])}",
        "",
        "| Scenario | runs | distinct config SHA-256 | status |",
        "|---|---|---|---|",
    ]
    for scenario, values in report["config_hashes"].items():
        status = "ok" if len(values) == 1 else f"**{len(values)} hashes**"
        runs = report["run_counts"].get(scenario, 0)
        lines.append(f"| {scenario} | {runs} | {len(values)} | {status} |")

    lines.append("")
    if report["sampling_seed_mismatches"]:
        lines.append(
            "Sampling-seed mismatches (expected 0 in fallback mode): "
            + ", ".join(report["sampling_seed_mismatches"])
        )
    else:
        lines.append(
            "Sampling seed equals the run seed in every agent run "
            f"({report['runs_with_sampling_seed']} runs) — no independent RNG stream."
        )
    if report["runs_without_agent_stats"]:
        lines.append(
            f"{report['runs_without_agent_stats']} runs carry no agent block "
            "(non-ablation controllers); expected outside the ablation directory."
        )
    if len(report["git_commits"]) > 1:
        lines.append(
            "**Warning:** runs came from more than one commit; T5 must report each "
            "subset separately."
        )
    return "\n".join(lines) + "\n"


def run_ablation(input_dir: Path, out_dir: Path, reference: str = "multi_agent") -> Dict[str, Any]:
    rows = load_ablation_rows(input_dir)
    if not rows:
        raise ValueError(f"no completed runs with result.json under {input_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = [metric for metric in T4_METRICS if metric in SUMMARY_METRICS]
    kpi_markdown = build_markdown(rows, metrics, reference)
    agent_markdown = build_agent_execution_markdown(
        agent_execution_rows(rows), f"fallback ablation, reference {reference}"
    )
    (out_dir / "ablation_kpis.md").write_text(kpi_markdown)
    (out_dir / "ablation_agent_execution.md").write_text(agent_markdown)

    payload = {
        "reference": reference,
        "metrics": metrics,
        "per_run": rows,
        "kpis": {},
        "agent_execution": agent_execution_rows(rows),
    }
    # Per-group KPI stats, computed independently of the markdown formatting.
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(f"{row['scenario']}::{row['controller']}", []).append(row)
    for key, group_rows in sorted(grouped.items()):
        payload["kpis"][key] = {
            metric: compute_statistics(
                [r[metric] for r in group_rows if r.get(metric) is not None]
            )
            for metric in metrics
        }
        payload["kpis"][key]["n"] = len(group_rows)
    (out_dir / "ablation_stats.json").write_text(json.dumps(payload, indent=2))
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ablation = sub.add_parser("ablation", help="T4 tables for an ablation directory")
    ablation.add_argument("--input", required=True)
    ablation.add_argument("--out", default=None)
    ablation.add_argument("--reference", default="multi_agent")

    repro = sub.add_parser("repro", help="T5 reproducibility sweep")
    repro.add_argument("--input", required=True)
    repro.add_argument("--out", default=None)

    args = parser.parse_args(argv)

    if args.command == "ablation":
        out_dir = Path(args.out or args.input)
        payload = run_ablation(Path(args.input), out_dir, args.reference)
        print(f"wrote {out_dir}/ablation_kpis.md, ablation_agent_execution.md, ablation_stats.json")
        print(f"runs: {len(payload['per_run'])}")
        return 0

    out_dir = Path(args.out or args.input)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = repro_report(Path(args.input))
    (out_dir / "reproducibility.md").write_text(build_repro_markdown(report))
    (out_dir / "reproducibility.json").write_text(json.dumps(report, indent=2))
    print(f"wrote {out_dir}/reproducibility.md and reproducibility.json")
    print(f"runs: {report['runs_with_manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
