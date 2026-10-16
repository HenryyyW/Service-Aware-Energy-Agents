#!/usr/bin/env python3
"""
Benchmark script for running multiple experiment configurations with statistical analysis.
Runs each scenario-controller combination multiple times with different random seeds
and produces summary statistics.
"""

import os
import json
import csv
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import argparse

def run_experiment(scenario_file: str, controller: str, seed: int, output_base: str) -> Dict[str, Any]:
    """Run a single experiment and return the result metrics."""
    output_dir = f"{output_base}/seed_{seed}"
    
    # Run the experiment
    cmd = [
        sys.executable, "-m", "experiments.run_experiment",
        "--config", scenario_file,
        "--controller", controller,
        "--output-dir", output_dir
    ]
    
    # Set the random seed in the environment
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = str(seed)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            print(f"Error running scenario {scenario_file} with controller {controller} seed {seed}:")
            print(result.stderr)
            return None
            
    except subprocess.TimeoutExpired:
        print(f"Timeout running scenario {scenario_file} with controller {controller} seed {seed}")
        return None
    
    # Load the result JSON
    # Find the actual output directory (it includes timestamp and seed)
    output_path = Path(output_base)
    scenario_name = Path(scenario_file).stem
    
    # Look for all result.json files under the output base
    all_result_files = list(output_path.glob("*/**/result.json"))
    
    # Filter for files that belong to this scenario
    result_files = []
    for f in all_result_files:
        # Check if the file path contains the scenario name in the right place
        # Expected pattern: {output_base}/{seed}/{scenario_name}/{timestamp}/result.json
        parts = f.parts
        try:
            # Find the scenario_name in the path
            scenario_index = parts.index(scenario_name)
            # Check that we have enough path components: output_base, seed, scenario, timestamp, result.json
            if len(parts) >= scenario_index + 3 and parts[scenario_index + 1].endswith('.json') == False:
                # The component after scenario_name should be the timestamp directory (not result.json yet)
                # And the final component should be result.json
                if f.name == "result.json":
                    result_files.append(f)
        except ValueError:
            # scenario_name not in path
            continue
    
    if not result_files:
        print(f"No result file found for {scenario_file} in {output_base}")
        # Debug: show what we found
        all_files = list(output_path.glob("*/**/result.json"))
        print(f"  Found {len(all_files)} total result files:")
        for f in all_files[:5]:  # Show first 5
            print(f"    {f}")
        if len(all_files) > 5:
            print(f"    ... and {len(all_files) - 5} more")
        return None
        
    # Get the most recent result file
    result_file = max(result_files, key=lambda f: f.stat().st_mtime)
    
    if not result_file.exists():
        print(f"Result file not found: {result_file}")
        return None
    
    try:
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        
        # Extract key metrics
        metrics = {
            "scenario": scenario_name,
            "controller": controller,
            "seed": seed,
            "total_cost": result_data["energy"]["total_cost"],
            "grid_import_kwh": result_data["energy"]["grid_import_kwh"],
            "peak_demand_kw": result_data["energy"]["peak_demand_kw"],
            "pv_self_consumption_kwh": result_data["energy"]["pv_self_consumption_kwh"],
            "ev_completion_rate": result_data["service"]["ev_completion_rate"],
            "comfort_violations": result_data["service"]["comfort_violation_degree_hours"],
            "pf_convergence": result_data["grid"]["power_flow_convergence_rate"],
            "voltage_violations": result_data["grid"]["voltage_violations_count"],
            "line_violations": result_data["grid"]["line_loading_violations"],
            "run_id": result_data["run_id"]
        }
        
        return metrics
        
    except Exception as e:
        print(f"Error loading result from {result_file}: {e}")
        return None

def compute_statistics(values: List[float]) -> Dict[str, float]:
    """Compute basic statistics for a list of values."""
    if len(values) < 2:
        return {
            "mean": values[0] if values else 0.0,
            "std": 0.0,
            "min": values[0] if values else 0.0,
            "max": values[0] if values else 0.0,
            "count": len(values)
        }
    
    mean_val = statistics.mean(values)
    stdev_val = statistics.stdev(values)
    
    return {
        "mean": mean_val,
        "std": stdev_val,
        "min": min(values),
        "max": max(values),
        "count": len(values),
        "confidence_interval_95": 1.96 * stdev_val / (len(values) ** 0.5) if len(values) > 1 else 0.0
    }

def run_benchmark(scenarios: List[str], controllers: List[str], seeds: List[int], 
                  output_base: str = "experiments/benchmark") -> Dict[str, Any]:
    """Run benchmark experiments and return statistical summary."""
    
    # Create output directory
    Path(output_base).mkdir(parents=True, exist_ok=True)
    
    all_results = []
    summary_stats = {}
    
    total_runs = len(scenarios) * len(controllers) * len(seeds)
    completed_runs = 0
    
    print(f"Starting benchmark: {len(scenarios)} scenarios × {len(controllers)} controllers × {len(seeds)} seeds = {total_runs} total runs")
    print(f"Output directory: {output_base}")
    print("-" * 60)
    
    for scenario in scenarios:
        scenario_name = Path(scenario).stem
        print(f"\nScenario: {scenario_name}")
        
        for controller in controllers:
            print(f"  Controller: {controller}", end=" ", flush=True)
            
            controller_results = []
            
            for seed in seeds:
                completed_runs += 1
                print(".", end="", flush=True)
                
                result = run_experiment(scenario, controller, seed, output_base)
                if result:
                    all_results.append(result)
                    controller_results.append(result)
                
                # Progress indicator
                if completed_runs % 10 == 0:
                    print(f"\n  Progress: {completed_runs}/{total_runs} runs completed")
            
            print(f" Done ({len(controller_results)}/{len(seeds)} successful)")
            
            # Compute statistics for this scenario-controller combination
            if controller_results:
                scenario_controller_key = f"{scenario_name}_{controller}"
                summary_stats[scenario_controller_key] = {}
                
                # Compute statistics for each metric
                metrics_to_analyze = [
                    "total_cost", "grid_import_kwh", "peak_demand_kw", 
                    "pv_self_consumption_kwh", "ev_completion_rate", 
                    "comfort_violations", "pf_convergence", 
                    "voltage_violations", "line_violations"
                ]
                
                for metric in metrics_to_analyze:
                    values = [r[metric] for r in controller_results if metric in r]
                    if values:
                        summary_stats[scenario_controller_key][metric] = compute_statistics(values)
    
    print(f"\nBenchmark completed: {len(all_results)}/{total_runs} successful runs")
    
    # Save raw results
    raw_results_file = Path(output_base) / "raw_results.json"
    with open(raw_results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Save summary statistics
    summary_file = Path(output_base) / "summary_statistics.json"
    with open(summary_file, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    
    # Generate CSV summary for easy analysis
    csv_file = Path(output_base) / "summary.csv"
    with open(csv_file, 'w', newline='') as f:
        if summary_stats:
            # Determine all metrics present
            all_metrics = set()
            for stats in summary_stats.values():
                all_metrics.update(stats.keys())
            
            writer = csv.writer(f)
            # Header
            header = ["scenario", "controller", "metric"]
            for stat in ["mean", "std", "min", "max", "count", "confidence_interval_95"]:
                header.extend([f"{stat}"])
            writer.writerow(header)
            
            # Data rows
            for scenario_controller, stats in summary_stats.items():
                scenario_name, controller_name = scenario_controller.split("_", 1)
                for metric in all_metrics:
                    if metric in stats:
                        row = [scenario_name, controller_name, metric]
                        for stat in ["mean", "std", "min", "max", "count", "confidence_interval_95"]:
                            row.append(stats[metric].get(stat, 0.0))
                        writer.writerow(row)
    
    # Generate LaTeX table for paper
    latex_file = Path(output_base) / "summary_table.tex"
    with open(latex_file, 'w') as f:
        f.write("% Benchmark Results Summary Table\\n")
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Benchmark results across scenarios and controllers}\\n")
        f.write("\\label{tab:benchmark-results}\n")
        f.write("\\begin{tabular}{lrrrrrr}\n")
        f.write("\\hline\n")
        f.write("Scenario & Controller & Metric & Mean & Std & Min & Max \\\\\n")
        f.write("\\hline\n")
        
        # Add data rows (limit to key metrics for readability)
        key_metrics = ["total_cost", "grid_import_kwh", "peak_demand_kw", 
                      "pv_self_consumption_kwh", "ev_completion_rate"]
        
        for scenario_controller, stats in summary_stats.items():
            if "_" in scenario_controller:
                scenario_name, controller_name = scenario_controller.split("_", 1)
                for metric in key_metrics:
                    if metric in stats:
                        s = stats[metric]
                        f.write(f"{scenario_name} & {controller_name} & {metric} & ")
                        f.write(f"{s['mean']:.3f} & {s['std']:.3f} & ")
                        f.write(f"{s['min']:.3f} & {s['max']:.3f} \\\\\n")
        
        f.write("\\hline\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")
    
    return {
        "raw_results": all_results,
        "summary_statistics": summary_stats,
        "output_directory": str(output_base)
    }

def main():
    parser = argparse.ArgumentParser(description="Run benchmark experiments for energy agents")
    parser.add_argument("--scenarios", nargs="+", 
                       default=["configs/scenario_a.yaml", "configs/scenario_b.yaml", 
                               "configs/scenario_c.yaml", "configs/scenario_d.yaml", 
                               "configs/scenario_e.yaml"],
                       help="List of scenario YAML files")
    parser.add_argument("--controllers", nargs="+",
                       default=["rule_based", "multi_agent", "centralized"],
                       help="List of controller types to test")
    parser.add_argument("--seeds", nargs="+", type=int,
                       default=[42, 123, 456, 789, 999],
                       help="List of random seeds to use")
    parser.add_argument("--output", type=str, default="experiments/benchmark",
                       help="Base output directory")
    parser.add_argument("--quick-test", action="store_true",
                       help="Run quick test with fewer seeds")
    
    args = parser.parse_args()
    
    if args.quick_test:
        args.seeds = [42, 123]
        print("Running quick test mode with 2 seeds")
    
    # Verify scenario files exist
    missing_scenarios = []
    for scenario in args.scenarios:
        if not Path(scenario).exists():
            missing_scenarios.append(scenario)
    
    if missing_scenarios:
        print(f"Error: The following scenario files do not exist:")
        for scenario in missing_scenarios:
            print(f"  - {scenario}")
        return 1
    
    # Run benchmark
    results = run_benchmark(
        scenarios=args.scenarios,
        controllers=args.controllers,
        seeds=args.seeds,
        output_base=args.output
    )
    
    print(f"\nBenchmark results saved to: {args.output}")
    print(f"Raw results: {Path(args.output) / 'raw_results.json'}")
    print(f"Summary statistics: {Path(args.output) / 'summary_statistics.json'}")
    print(f"CSV summary: {Path(args.output) / 'summary.csv'}")
    print(f"LaTeX table: {Path(args.output) / 'summary_table.tex'}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())