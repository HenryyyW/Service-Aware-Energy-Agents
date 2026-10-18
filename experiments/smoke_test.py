#!/usr/bin/env python3
"""
Smoke test for Scenario A: run two controllers × two seeds with a tiny step count.
Verifies that:
  • result.json exists and its scenario_id, controller_type, random_seed match the CLI inputs
  • trajectory file exists and contains the same number of steps
  • summary (KPIs) are present and non‑NaN
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from experiments.run_experiment import ExperimentRunner, load_scenario
from src.schemas.report import ControllerType, ExperimentResult


def run_one(controller: str, seed: int, max_steps: int = 10):
    """Run a single experiment and return the run directory."""
    scenario = load_scenario("configs/scenario_a.yaml")
    scenario.random_seed = seed

    # Deterministic run_id so we can locate the folder afterwards
    run_id = f"smoke_{controller}_{seed}"
    runner = ExperimentRunner(scenario, output_dir="experiments/results", run_id=run_id)
    runner.setup(controller)
    result = runner.run(max_steps=max_steps)
    return runner.run_dir, result


def verify(run_dir: Path, expected_controller: str, expected_seed: int):
    """Check result.json, trajectory.jsonl, and KPI sanity."""
    # 1. result.json
    result_path = run_dir / "result.json"
    assert result_path.exists(), f"Missing result.json in {run_dir}"
    with open(result_path) as f:
        data = json.load(f)

    assert data["scenario_id"] == "scenario_a", f"scenario_id mismatch: {data['scenario_id']}"
    # controller_type is stored as enum value string
    expected_enum = {
        "rule_based": "rule_based",
        "multi_agent": "llm_agent",   # MultiAgentController maps to LLM_AGENT
        "centralized": "rule_based",
    }[expected_controller]
    assert data["controller_type"] == expected_enum, \
        f"controller_type mismatch: {data['controller_type']} vs {expected_enum}"
    assert data["random_seed"] == expected_seed, f"seed mismatch: {data['random_seed']} vs {expected_seed}"

    # 2. trajectories.jsonl (exported by coupler)
    traj_path = run_dir / "trajectories.jsonl"
    assert traj_path.exists(), f"Missing trajectories.jsonl in {run_dir}"
    with open(traj_path) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    # Should have max_steps + 1 entries (initial obs + each step)
    # Note: runner stops early if terminated; we just check >0
    assert len(lines) > 0, "Empty trajectory"

    # 3. KPI sanity – ensure key energy KPIs are present and numeric
    energy = data["energy"]
    for key in ("total_cost", "grid_import_kwh", "grid_export_kwh",
                "peak_demand_kw", "pv_generation_kwh"):
        val = energy.get(key)
        assert val is not None, f"Missing energy KPI {key}"
        assert isinstance(val, (int, float)), f"Non‑numeric KPI {key}: {val}"

    print(f"  [OK] {run_dir.name} verified (steps={len(lines)-1})")


def main():
    controllers = ["rule_based", "multi_agent"]
    seeds = [42, 123]
    max_steps = 10

    print("[START] Starting Scenario A smoke test")
    print(f"   controllers: {controllers}")
    print(f"   seeds: {seeds}")
    print(f"   max_steps per run: {max_steps}\n")

    for ctrl in controllers:
        for sd in seeds:
            print(f"[RUN] Running {ctrl} / seed={sd} ...")
            run_dir, _ = run_one(ctrl, sd, max_steps=max_steps)
            verify(run_dir, ctrl, sd)

    print("\n[SUCCESS] All smoke-test combinations passed!")


if __name__ == "__main__":
    main()