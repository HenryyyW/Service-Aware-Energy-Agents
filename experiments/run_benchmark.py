#!/usr/bin/env python3
"""Benchmark runner for the service-aware energy community experiments.

Runs each scenario x controller x seed combination as an isolated
``experiments.run_experiment`` subprocess, then aggregates the result JSONs
into summary statistics with 95% confidence intervals.

Design notes
------------
* Every run is a separate process, so seeds and hardware noise cannot leak
  between configurations.
* The run_id is deterministic (``{scenario}_{controller}_{seed}``), so a lost
  or timed-out run is easy to reproduce by hand.
* The 95% CI uses the Student-t critical value for the observed sample size,
  not the 1.96 normal approximation, because the paper's matrix uses 3-5 runs.
"""

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from types import SimpleNamespace

# Metrics collected for every run. (section, field) pairs tolerate older or
# newer result files instead of raising KeyError.
METRICS: Dict[str, tuple[str, str]] = {
    "total_cost": ("energy", "total_cost"),
    "grid_import_kwh": ("energy", "grid_import_kwh"),
    "grid_export_kwh": ("energy", "grid_export_kwh"),
    "peak_demand_kw": ("energy", "peak_demand_kw"),
    "pv_self_consumption_kwh": ("energy", "pv_self_consumption_kwh"),
    "pv_curtailment_kwh": ("energy", "pv_curtailment_kwh"),
    "battery_throughput_kwh": ("energy", "battery_throughput_kwh"),
    "carbon_emissions_kg": ("energy", "carbon_emissions_kg"),
    "ev_completion_rate": ("service", "ev_completion_rate"),
    "ev_avg_soc_at_departure": ("service", "ev_avg_soc_at_departure"),
    "comfort_violations": ("service", "comfort_violation_degree_hours"),
    "gini_coefficient": ("service", "gini_coefficient"),
    "pf_convergence": ("grid", "power_flow_convergence_rate"),
    "voltage_violations": ("grid", "voltage_violations_count"),
    "line_violations": ("grid", "line_loading_violations"),
    "nodal_power_balance_violations": ("grid", "nodal_power_balance_violations"),
}

STAT_KEYS = ("mean", "std", "min", "max", "count", "ci95")


def _t_critical(count: int, confidence: float = 0.95) -> float:
    """Two-sided Student-t critical value, with a small fallback table."""
    if count < 2:
        return 0.0
    try:
        from scipy.stats import t as student_t

        return float(student_t.ppf(0.5 + confidence / 2.0, count - 1))
    except Exception:  # pragma: no cover - scipy is a project dependency
        table = {
            2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571,
            7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262,
        }
        return table.get(count, 1.96)


def compute_statistics(values: List[float]) -> Dict[str, float]:
    """Mean, sample std, min/max, and the 95% half-width for a metric.

    Non-finite values (NaN/Inf — e.g. a member cost after an injected failure)
    are excluded before aggregating; if nothing remains the zero dict is
    returned so the summary never crashes on failed sub-metrics.
    """
    clean = [
        float(v)
        for v in values
        if v is not None and math.isfinite(float(v))
    ]
    count = len(clean)
    if count == 0:
        return {key: 0.0 for key in STAT_KEYS}
    mean_value = statistics.mean(clean)
    if count < 2:
        return {
            "mean": mean_value,
            "std": 0.0,
            "min": clean[0],
            "max": clean[0],
            "count": count,
            "ci95": 0.0,
        }
    stdev_value = statistics.stdev(clean)
    half_width = _t_critical(count) * stdev_value / (count ** 0.5)
    return {
        "mean": mean_value,
        "std": stdev_value,
        "min": min(clean),
        "max": max(clean),
        "count": count,
        "ci95": half_width,
    }


def rl_policy_path(policy_dir: Optional[str], scenario_name: str) -> Optional[str]:
    """Resolve the per-scenario RL policy JSON, if one exists."""
    if not policy_dir:
        return None
    candidate = Path(policy_dir) / f"{scenario_name}.json"
    return str(candidate) if candidate.exists() else None


def _kill_process_tree(process: "subprocess.Popen") -> None:
    """Kill a timed-out child and everything it spawned.

    Without tree-kill a grandchild that inherited the log-file handle keeps the
    run's artifacts locked and can keep CPU busy after the runner moved on.
    """
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True, timeout=30,
            )
        else:
            import signal

            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except Exception as exc:  # pragma: no cover - best-effort cleanup
        print(f"Warning: failed to kill process tree for PID {process.pid}: {exc}",
              file=sys.stderr)
    try:
        process.wait(timeout=30)
    except Exception:  # pragma: no cover
        process.kill()


def _run_with_timeout(cmd, env, timeout: int, result_file: Path):
    """Run one experiment, enforcing the timeout even when pipes are inherited.

    Capturing via pipes is unsafe for long runs: ``subprocess.run(timeout=...)``
    kills the direct child on expiry but then blocks in ``communicate()`` until
    every handle to the pipe closes, so a grandchild (or an unkillable child)
    turns the 900 s timeout into a 33,000 s hang — what the first full matrix's
    three scenario_e multi_agent runs did. Writing stdout/stderr to a per-run
    log file removes the pipe from the equation, and the timeout kills the
    whole process tree.
    """
    log_path = result_file.parent / "run_output.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: Dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with open(log_path, "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd, stdout=log_file, stderr=subprocess.STDOUT, env=env, **kwargs
        )
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(process)
            raise
    with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
        tail = "".join(log_file.readlines()[-15:])
    return SimpleNamespace(returncode=returncode), tail


def run_experiment(
    scenario_file: str,
    controller: str,
    seed: int,
    output_base: str,
    timeout: int = 900,
    policy_dir: Optional[str] = None,
    max_steps: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Run one experiment subprocess and return its metrics."""
    scenario_name = Path(scenario_file).stem
    run_id = f"{scenario_name}_{controller}_{seed}"
    result_file = Path(output_base) / scenario_name / run_id / "result.json"

    cmd = [
        sys.executable, "-m", "experiments.run_experiment",
        "--config", scenario_file,
        "--controller", controller,
        "--seed", str(seed),
        "--run-id", run_id,
        "--output-dir", output_base,
    ]
    if controller in ("rl", "rl_single"):
        policy = rl_policy_path(policy_dir, scenario_name)
        if not policy:
            print(
                f"Skipping {run_id}: no RL policy at {policy_dir}/{scenario_name}.json",
                file=sys.stderr,
            )
            return None
        cmd.extend(["--rl-policy", policy])
    if max_steps:
        cmd.extend(["--max-steps", str(max_steps)])

    env = os.environ.copy()
    env["PYTHONHASHSEED"] = str(seed)
    # Keep each parallel run's generated CityLearn schema separate.
    env["SAEA_RUN_ID"] = run_id

    started = time.time()
    try:
        completed, stderr_tail = _run_with_timeout(cmd, env, timeout, result_file)
    except subprocess.TimeoutExpired:
        print(f"Timeout after {timeout}s: {run_id}", file=sys.stderr)
        return None
    runtime = time.time() - started

    if completed.returncode != 0:
        print(f"Error running {run_id}:\n{stderr_tail}", file=sys.stderr)
        return None

    if not result_file.exists():
        print(f"Result file missing for {run_id}: {result_file}", file=sys.stderr)
        return None

    try:
        with open(result_file, "r") as handle:
            result_data = json.load(handle)
    except Exception as exc:  # pragma: no cover - corrupt artefact guard
        print(f"Error loading {result_file}: {exc}", file=sys.stderr)
        return None

    metrics: Dict[str, Any] = {
        "scenario": scenario_name,
        "controller": controller,
        "seed": seed,
        "run_id": result_data.get("run_id", run_id),
        "runtime_seconds": round(runtime, 1),
        "status": result_data.get("status"),
    }
    for name, (section, field) in METRICS.items():
        block = result_data.get(section) or {}
        metrics[name] = block.get(field)
    return metrics


def run_benchmark(
    scenarios: List[str],
    controllers: List[str],
    seeds: List[int],
    output_base: str = "experiments/benchmark",
    workers: int = 1,
    timeout: int = 900,
    policy_dir: Optional[str] = None,
    max_steps: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the matrix and write raw results, summary JSON, CSV and LaTeX."""
    Path(output_base).mkdir(parents=True, exist_ok=True)

    tasks = [
        (scenario, controller, seed)
        for scenario in scenarios
        for controller in controllers
        for seed in seeds
    ]
    total_runs = len(tasks)
    print(
        f"Starting benchmark: {len(scenarios)} scenarios x {len(controllers)} controllers "
        f"x {len(seeds)} seeds = {total_runs} runs (workers={workers})"
    )
    print(f"Output directory: {output_base}")

    started = time.time()
    completed_runs = 0

    def _run(task: tuple) -> Optional[Dict[str, Any]]:
        scenario, controller, seed = task
        return run_experiment(
            scenario,
            controller,
            seed,
            output_base,
            timeout=timeout,
            policy_dir=policy_dir,
            max_steps=max_steps,
        )

    all_results: List[Dict[str, Any]] = []
    if workers <= 1:
        for task in tasks:
            result = _run(task)
            completed_runs += 1
            if result:
                all_results.append(result)
            print(f"[{completed_runs}/{total_runs}] {Path(task[0]).stem} {task[1]} seed={task[2]} "
                  f"{'ok' if result else 'FAILED'}")
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(_run, tasks):
                completed_runs += 1
                if result:
                    all_results.append(result)
                print(f"[{completed_runs}/{total_runs}] {'ok' if result else 'FAILED'}")

    # Aggregate by (scenario, controller). The "::" separator keeps names with
    # underscores (e.g. multi_agent) intact; the old split("_", 1) corrupted them.
    summary_stats: Dict[str, Dict[str, Dict[str, float]]] = {}
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for result in all_results:
        grouped.setdefault((result["scenario"], result["controller"]), []).append(result)

    for (scenario_name, controller), rows in grouped.items():
        key = f"{scenario_name}::{controller}"
        summary_stats[key] = {}
        for metric in METRICS:
            values = [row.get(metric) for row in rows if row.get(metric) is not None]
            if values:
                summary_stats[key][metric] = compute_statistics(values)

    failing_runs = [
        {"scenario": Path(s).stem, "controller": c, "seed": seed}
        for scenario, controller, seed in tasks
        if not any(
            r["scenario"] == Path(scenario).stem
            and r["controller"] == controller
            and r["seed"] == seed
            for r in all_results
        )
    ]

    wall_clock = round(time.time() - started, 1)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scenarios": scenarios,
        "controllers": controllers,
        "seeds": seeds,
        "total_runs": total_runs,
        "successful_runs": len(all_results),
        "wall_clock_seconds": wall_clock,
        "confidence_level": 0.95,
        "ci_method": "student_t_half_width",
        "summary_statistics": summary_stats,
    }

    with open(Path(output_base) / "raw_results.json", "w") as handle:
        json.dump(all_results, handle, indent=2)
    with open(Path(output_base) / "summary_statistics.json", "w") as handle:
        json.dump(payload, handle, indent=2)
    with open(Path(output_base) / "failed_runs.json", "w") as handle:
        json.dump(failing_runs, handle, indent=2)

    with open(Path(output_base) / "summary.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "controller", "metric", *STAT_KEYS])
        for key, stats in summary_stats.items():
            scenario_name, controller = key.split("::", 1)
            for metric, values in stats.items():
                writer.writerow(
                    [scenario_name, controller, metric, *[values[k] for k in STAT_KEYS]]
                )

    with open(Path(output_base) / "summary_table.tex", "w") as handle:
        handle.write("% Auto-generated by experiments/run_benchmark.py\n")
        handle.write("\\begin{table}[htbp]\n\\centering\n")
        handle.write("\\caption{Benchmark results across scenarios and controllers}\n")
        handle.write("\\label{tab:benchmark-results}\n")
        handle.write("\\begin{tabular}{llrrrr}\n\\hline\n")
        handle.write("Scenario & Controller & Metric & Mean & 95\\% CI & n \\\\\n\\hline\n")
        key_metrics = [
            "total_cost", "grid_import_kwh", "peak_demand_kw",
            "pv_self_consumption_kwh", "ev_completion_rate",
        ]
        for key, stats in summary_stats.items():
            scenario_name, controller = key.split("::", 1)
            for metric in key_metrics:
                if metric in stats:
                    values = stats[metric]
                    label = metric.replace("_", r"\_")
                    handle.write(
                        f"{scenario_name} & {controller} & {label} & "
                        f"{values['mean']:.3f} & $\\pm${values['ci95']:.3f} & "
                        f"{int(values['count'])} \\\\\n"
                    )
        handle.write("\\hline\n\\end{tabular}\n\\end{table}\n")

    print(
        f"\nBenchmark completed: {len(all_results)}/{total_runs} successful runs "
        f"in {wall_clock}s"
    )
    if failing_runs:
        print(f"Failed runs recorded in {Path(output_base) / 'failed_runs.json'}")

    return {
        "raw_results": all_results,
        "summary_statistics": summary_stats,
        "failed_runs": failing_runs,
        "output_directory": str(output_base),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark experiments for energy agents")
    parser.add_argument(
        "--scenarios", nargs="+",
        default=[f"configs/scenario_{letter}.yaml" for letter in "abcde"],
        help="List of scenario YAML files",
    )
    parser.add_argument(
        "--controllers", nargs="+",
        default=["rule_based", "multi_agent", "centralized", "mpc", "rl"],
        help="Controller types to test (mpc/rl need the baselines from src/controllers)",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, default=[42, 123, 456, 789, 999],
        help="Random seeds; the brief requires >=3 runs per configuration",
    )
    parser.add_argument("--output", type=str, default="experiments/benchmark",
                        help="Base output directory")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel experiment subprocesses")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Per-run timeout in seconds")
    parser.add_argument("--rl-policy-dir", type=str, default="experiments/rl_policy",
                        help="Directory containing {scenario}.json RL policies")
    parser.add_argument("--max-steps", type=int, default=None,
                        help="Optional step cap (smoke tests)")
    parser.add_argument("--quick-test", action="store_true",
                        help="Run a two-seed smoke matrix")
    args = parser.parse_args()

    if args.quick_test:
        args.seeds = [42, 123]
        print("Running quick test mode with 2 seeds")

    missing = [scenario for scenario in args.scenarios if not Path(scenario).exists()]
    if missing:
        print("Error: missing scenario files:")
        for scenario in missing:
            print(f"  - {scenario}")
        return 1

    run_benchmark(
        scenarios=args.scenarios,
        controllers=args.controllers,
        seeds=args.seeds,
        output_base=args.output,
        workers=args.workers,
        timeout=args.timeout,
        policy_dir=args.rl_policy_dir,
        max_steps=args.max_steps,
    )
    print(f"\nBenchmark results saved to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
