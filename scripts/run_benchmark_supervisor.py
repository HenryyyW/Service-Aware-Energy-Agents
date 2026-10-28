#!/usr/bin/env python3
"""Resumable, monitored runner for a benchmark matrix.

Runs one ``experiments.run_experiment`` process per
(scenario, controller, seed) combination, writes a per-run log, keeps a
heartbeat ``status.json`` current, retries a failed run, and skips runs that
already finished. Designed for multi-hour benchmark sweeps on a single machine:
if the process dies, rerun the same command and it continues where it stopped.

Examples::

    # dry run: show the plan without launching anything
    python scripts/run_benchmark_supervisor.py \
        --scenarios configs/scenario_a.yaml configs/scenario_b.yaml \
        --controllers rule_based multi_agent \
        --seeds 42 123 456 \
        --output-dir experiments/benchmark_phase1 \
        --dry-run

    # real run
    python scripts/run_benchmark_supervisor.py \
        --scenarios configs/scenario_a.yaml configs/scenario_b.yaml \
        --controllers rule_based multi_agent \
        --seeds 42 123 456 \
        --output-dir experiments/benchmark_phase1 \
        --max-steps 672 --retries 1

Output layout::

    <output-dir>/
    ├── logs/<run_id>.log        # stdout + stderr for the attempt
    ├── status.json              # live state, safe to poll
    ├── summary.json             # written at the end
    └── <scenario_id>/<run_id>/
        ├── result.json
        ├── manifest.json
        └── trajectories.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_EXPERIMENT_MODULE = "experiments.run_experiment"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RunSpec:
    scenario_id: str
    config: str
    controller: str
    seed: int

    @property
    def run_id(self) -> str:
        return f"{self.scenario_id}_{self.controller}_{self.seed}"


@dataclass
class RunState:
    run_id: str
    scenario_id: str
    controller: str
    seed: int
    state: str = "pending"  # pending | running | completed | failed | skipped
    attempts: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    exit_code: Optional[int] = None
    log: Optional[str] = None
    error: Optional[str] = None
    heartbeat: Optional[str] = None
    metrics: dict = field(default_factory=dict)


def build_plan(
    scenarios: Iterable[str],
    controllers: Iterable[str],
    seeds: Iterable[int],
) -> list[RunSpec]:
    plan: list[RunSpec] = []
    for config in scenarios:
        scenario_id = Path(config).stem
        for controller in controllers:
            for seed in seeds:
                plan.append(RunSpec(scenario_id, config, controller, seed))
    return plan


def result_paths(output_dir: Path, spec: RunSpec) -> tuple[Path, Path]:
    run_dir = output_dir / spec.scenario_id / spec.run_id
    return run_dir / "result.json", run_dir / "manifest.json"


def is_complete(output_dir: Path, spec: RunSpec, require_manifest: bool = True) -> bool:
    result_file, manifest_file = result_paths(output_dir, spec)
    if not result_file.is_file() or result_file.stat().st_size == 0:
        return False
    return manifest_file.is_file() if require_manifest else True


def build_command(
    spec: RunSpec,
    output_dir: Path,
    max_steps: Optional[int],
    python: str,
    module: str,
) -> list[str]:
    cmd = [
        python,
        "-m",
        module,
        "--config",
        spec.config,
        "--controller",
        spec.controller,
        "--seed",
        str(spec.seed),
        "--run-id",
        spec.run_id,
        "--output-dir",
        str(output_dir),
    ]
    if max_steps is not None:
        cmd.extend(["--max-steps", str(max_steps)])
    return cmd


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, path)


def snapshot(
    specs: list[RunSpec],
    states: dict[str, RunState],
    output_dir: Path,
    started_at: str,
    finished: bool = False,
) -> dict:
    counts: dict[str, int] = {}
    for state in states.values():
        counts[state.state] = counts.get(state.state, 0) + 1
    return {
        "updated_at": utc_now(),
        "started_at": started_at,
        "finished": finished,
        "output_dir": str(output_dir),
        "total": len(specs),
        "counts": counts,
        "runs": [asdict(states[spec.run_id]) for spec in specs],
    }


def read_metrics(output_dir: Path, spec: RunSpec) -> dict:
    result_file, _ = result_paths(output_dir, spec)
    try:
        result = json.loads(result_file.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    metrics: dict = {}
    for block, key in (
        ("energy", "total_cost"),
        ("energy", "grid_import_kwh"),
        ("service", "ev_completion_rate"),
        ("grid", "voltage_violations_count"),
    ):
        value = (result.get(block) or {}).get(key)
        if value is not None:
            metrics[f"{block}.{key}"] = value
    return metrics


def run_matrix(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    plan = build_plan(args.scenarios, args.controllers, args.seeds)
    states = {
        spec.run_id: RunState(
            run_id=spec.run_id,
            scenario_id=spec.scenario_id,
            controller=spec.controller,
            seed=spec.seed,
        )
        for spec in plan
    }
    started_at = utc_now()
    status_file = output_dir / "status.json"

    pending: list[RunSpec] = []
    for spec in plan:
        if not args.force and is_complete(output_dir, spec, require_manifest=not args.no_manifest_check):
            states[spec.run_id].state = "skipped"
            states[spec.run_id].error = "already complete"
        else:
            pending.append(spec)

    write_json_atomic(status_file, snapshot(plan, states, output_dir, started_at))
    print(
        f"[supervisor] {len(plan)} run(s): {len(pending)} to run, "
        f"{len(plan) - len(pending)} already complete"
    )
    if args.dry_run:
        for spec in pending:
            print(f"[supervisor] would run {spec.run_id} ({spec.config})")
        return 0

    failures = 0
    for index, spec in enumerate(pending, start=1):
        state = states[spec.run_id]
        log_path = logs_dir / f"{spec.run_id}.log"
        state.log = str(log_path)
        cmd = build_command(
            spec, output_dir, args.max_steps, args.python, args.experiment_module
        )
        print(f"[supervisor] ({index}/{len(pending)}) {spec.run_id}")

        for attempt in range(1, args.retries + 2):
            state.state = "running"
            state.attempts = attempt
            state.started_at = utc_now()
            state.heartbeat = state.started_at
            state.finished_at = None
            state.duration_seconds = None
            state.exit_code = None
            state.error = None
            write_json_atomic(status_file, snapshot(plan, states, output_dir, started_at))

            start = time.monotonic()
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"\n=== attempt {attempt} at {state.started_at} ===\n")
                log.flush()
                try:
                    completed = subprocess.run(
                        cmd,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=args.timeout or None,
                    )
                    exit_code = completed.returncode
                except subprocess.TimeoutExpired:
                    exit_code = 124
                    log.write(f"\n=== timeout after {args.timeout}s ===\n")
                except OSError as exc:
                    exit_code = 127
                    log.write(f"\n=== launch error: {exc} ===\n")

            state.exit_code = exit_code
            state.finished_at = utc_now()
            state.duration_seconds = round(time.monotonic() - start, 2)
            state.heartbeat = state.finished_at

            if exit_code == 0 and is_complete(
                output_dir, spec, require_manifest=not args.no_manifest_check
            ):
                state.state = "completed"
                state.metrics = read_metrics(output_dir, spec)
                write_json_atomic(status_file, snapshot(plan, states, output_dir, started_at))
                break

            state.state = "failed"
            state.error = f"exit code {exit_code}"
            write_json_atomic(status_file, snapshot(plan, states, output_dir, started_at))
            if attempt <= args.retries:
                print(f"[supervisor]   retrying after exit {exit_code}")
            else:
                failures += 1
                print(f"[supervisor]   failed after {attempt} attempt(s); see {log_path}")
                if args.fail_fast:
                    write_json_atomic(
                        status_file,
                        snapshot(plan, states, output_dir, started_at, finished=True),
                    )
                    write_json_atomic(
                        output_dir / "summary.json",
                        snapshot(plan, states, output_dir, started_at, finished=True),
                    )
                    return 1

        if args.fail_fast and state.state == "failed":
            break

    final = snapshot(plan, states, output_dir, started_at, finished=True)
    final["failed_runs"] = [s.run_id for s in plan if states[s.run_id].state == "failed"]
    write_json_atomic(status_file, final)
    write_json_atomic(output_dir / "summary.json", final)

    counts = final["counts"]
    print(
        "[supervisor] finished: "
        + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    )
    if failures:
        print(f"[supervisor] {failures} run(s) failed; inspect {logs_dir}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", nargs="+", required=True,
                        help="Scenario YAML paths")
    parser.add_argument("--controllers", nargs="+", required=True,
                        choices=["rule_based", "multi_agent", "centralized"])
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=None,
                        help="Cap each episode (omit for a full episode)")
    parser.add_argument("--retries", type=int, default=1,
                        help="Retries per run after the first failure (default 1)")
    parser.add_argument("--timeout", type=int, default=0,
                        help="Per-attempt timeout in seconds (0 = no limit)")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop the matrix at the first exhausted run")
    parser.add_argument("--force", action="store_true",
                        help="Re-run combinations even if a result exists")
    parser.add_argument("--no-manifest-check", action="store_true",
                        help="Treat result.json alone as completion (legacy runs)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--experiment-module", default=DEFAULT_EXPERIMENT_MODULE)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return run_matrix(args)


if __name__ == "__main__":
    sys.exit(main())
