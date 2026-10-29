#!/usr/bin/env python3
"""Seed reproducibility gate for experiment runs.

Runs the same scenario/controller/seed combination several times and checks that
the normalized result summary and the trajectory file are byte-identical. The
check is intentionally run from the repository root so that ``load_scenario``,
the ``data/`` lookups and the ``src`` imports behave exactly as they do for a
normal experiment.

Usage::

    python -m experiments.check_reproducibility \
        --config configs/scenario_a.yaml \
        --controller rule_based \
        --seeds 42 123 \
        --replicates 2 \
        --max-steps 8

Exit code is 0 when every seed reproduces exactly, 1 otherwise. A JSON report
can be written with ``--report`` so CI can archive it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Fields that legitimately change between runs of the same seed.
VOLATILE_KEYS = {
    "run_id",
    "start_time",
    "end_time",
    "trajectories_file",
    "logs_file",
    "plots_dir",
    "wall_clock_seconds",
}

# Metric blocks whose values must match exactly across replicates.
COMPARED_BLOCKS = (
    "energy",
    "service",
    "grid",
    "agent",
    "kpis",
    "per_member",
    "energy_sharing",
    "diagnostic_reports",
)


def _normalize(value: Any) -> Any:
    """Recursively drop volatile fields so only scientific content is hashed."""
    if isinstance(value, dict):
        return {
            key: _normalize(item)
            for key, item in value.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return _sha256_bytes(path.read_bytes())


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256_bytes(payload.encode("utf-8"))


def _package_versions() -> Dict[str, str]:
    versions: Dict[str, str] = {"python": platform.python_version()}
    for name in ("citylearn", "pandapower", "numpy", "pandas"):
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "unknown")
        except Exception:  # pragma: no cover - diagnostic only
            versions[name] = "missing"
    return versions


def run_once(
    config: str,
    controller: str,
    seed: int,
    replicate: int,
    output_dir: Path,
    max_steps: Optional[int],
) -> Dict[str, Any]:
    run_id = f"repro_seed{seed}_r{replicate}"
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_experiment",
        "--config",
        config,
        "--controller",
        controller,
        "--seed",
        str(seed),
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
    ]
    if max_steps is not None:
        cmd.extend(["--max-steps", str(max_steps)])

    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{run_id} failed with code {completed.returncode}\n"
            f"--- stdout (tail) ---\n{completed.stdout[-4000:]}\n"
            f"--- stderr (tail) ---\n{completed.stderr[-4000:]}"
        )

    scenario_id = Path(config).stem
    run_dir = output_dir / scenario_id / run_id
    result_path = run_dir / "result.json"
    if not result_path.exists():
        raise RuntimeError(f"missing result file: {result_path}")

    result = json.loads(result_path.read_text())
    trajectory_path = run_dir / "trajectories.jsonl"
    return {
        "run_id": run_id,
        "result": result,
        "result_hash": _sha256_json(_normalize(result)),
        "trajectory_hash": _sha256_file(trajectory_path),
        "trajectory_bytes": trajectory_path.stat().st_size if trajectory_path.exists() else 0,
        "metrics": {block: _normalize(result.get(block)) for block in COMPARED_BLOCKS},
    }


def check_seed(
    config: str,
    controller: str,
    seed: int,
    replicates: int,
    output_dir: Path,
    max_steps: Optional[int],
) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    for replicate in range(1, replicates + 1):
        runs.append(run_once(config, controller, seed, replicate, output_dir, max_steps))

    reference = runs[0]
    problems: List[str] = []
    for run in runs[1:]:
        if run["result_hash"] != reference["result_hash"]:
            problems.append(f"{run['run_id']}: result.json differs from {reference['run_id']}")
        if run["trajectory_hash"] != reference["trajectory_hash"]:
            problems.append(
                f"{run['run_id']}: trajectories.jsonl differs from {reference['run_id']}"
            )
        for block in COMPARED_BLOCKS:
            if run["metrics"].get(block) != reference["metrics"].get(block):
                problems.append(f"{run['run_id']}: metric block '{block}' differs")

    return {
        "seed": seed,
        "replicates": replicates,
        "ok": not problems,
        "problems": problems,
        "result_hash": reference["result_hash"],
        "trajectory_hash": reference["trajectory_hash"],
        "trajectory_bytes": reference["trajectory_bytes"],
        "runs": [run["run_id"] for run in runs],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/scenario_a.yaml")
    parser.add_argument("--controller", default="rule_based",
                        choices=["rule_based", "multi_agent", "centralized"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=8,
                        help="Keep CI runs short; use 0/omit for a full episode")
    parser.add_argument("--output-dir", default=None,
                        help="Where runs are written (default: a temp directory)")
    parser.add_argument("--keep-output", action="store_true",
                        help="Do not delete the temp output directory")
    parser.add_argument("--report", default=None, help="Optional JSON report path")
    args = parser.parse_args()

    if args.replicates < 2:
        parser.error("--replicates must be at least 2 to compare runs")

    output_dir = Path(args.output_dir) if args.output_dir else Path(
        tempfile.mkdtemp(prefix="repro-check-")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    max_steps = args.max_steps if args.max_steps and args.max_steps > 0 else None
    config_hash = _sha256_file(Path(args.config)) or "missing"

    seed_results = []
    for seed in args.seeds:
        print(f"[repro] seed={seed} config={args.config} controller={args.controller}")
        seed_results.append(
            check_seed(
                config=args.config,
                controller=args.controller,
                seed=seed,
                replicates=args.replicates,
                output_dir=output_dir,
                max_steps=max_steps,
            )
        )

    # Different seeds should generally diverge; report as information only.
    divergence_note = None
    if len(seed_results) >= 2:
        hashes = {item["result_hash"] for item in seed_results}
        divergence_note = (
            "seeds produced identical results; the scenario may not be seed-sensitive"
            if len(hashes) == 1
            else "seeds produced distinct results"
        )

    report = {
        "config": args.config,
        "config_sha256": config_hash,
        "controller": args.controller,
        "max_steps": max_steps,
        "versions": _package_versions(),
        "seeds": seed_results,
        "seed_sensitivity": divergence_note,
        "ok": all(item["ok"] for item in seed_results),
    }

    for item in seed_results:
        status = "PASS" if item["ok"] else "FAIL"
        print(
            f"[repro] {status} seed={item['seed']} "
            f"result={item['result_hash'][:12]} trajectory={str(item['trajectory_hash'])[:12]} "
            f"({item['trajectory_bytes']} bytes)"
        )
        for problem in item["problems"]:
            print(f"[repro]   - {problem}")
    if divergence_note:
        print(f"[repro] note: {divergence_note}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))
        print(f"[repro] report written to {report_path}")

    if not args.keep_output and not args.output_dir:
        import shutil

        shutil.rmtree(output_dir, ignore_errors=True)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
