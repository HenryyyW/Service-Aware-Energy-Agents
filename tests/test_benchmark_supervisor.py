"""Unit tests for the benchmark supervisor (scripts/run_benchmark_supervisor.py)."""
import json
from pathlib import Path

from scripts import run_benchmark_supervisor as sup


def test_build_plan_is_deterministic():
    plan = sup.build_plan(["configs/scenario_a.yaml"], ["rule_based", "multi_agent"], [42, 123])
    assert [spec.run_id for spec in plan] == [
        "scenario_a_rule_based_42",
        "scenario_a_rule_based_123",
        "scenario_a_multi_agent_42",
        "scenario_a_multi_agent_123",
    ]
    assert plan[0].scenario_id == "scenario_a"
    assert plan[0].config == "configs/scenario_a.yaml"


def test_is_complete_requires_result_and_manifest(tmp_path: Path):
    spec = sup.RunSpec("scenario_a", "configs/scenario_a.yaml", "rule_based", 42)
    result_file, manifest_file = sup.result_paths(tmp_path, spec)

    assert sup.is_complete(tmp_path, spec) is False

    result_file.parent.mkdir(parents=True)
    result_file.write_text("{}")
    assert sup.is_complete(tmp_path, spec) is False
    assert sup.is_complete(tmp_path, spec, require_manifest=False) is True

    manifest_file.write_text("{}")
    assert sup.is_complete(tmp_path, spec) is True


def test_build_command_uses_requested_run_id(tmp_path: Path):
    spec = sup.RunSpec("scenario_b", "configs/scenario_b.yaml", "centralized", 7)
    cmd = sup.build_command(spec, tmp_path, 12, "python", "experiments.run_experiment")
    assert cmd[:3] == ["python", "-m", "experiments.run_experiment"]
    assert cmd[cmd.index("--run-id") + 1] == "scenario_b_centralized_7"
    assert cmd[cmd.index("--output-dir") + 1] == str(tmp_path)
    assert cmd[cmd.index("--max-steps") + 1] == "12"


def test_dry_run_lists_pending_runs(tmp_path: Path, capsys):
    code = sup.main([
        "--scenarios", "configs/scenario_a.yaml",
        "--controllers", "rule_based",
        "--seeds", "42",
        "--output-dir", str(tmp_path),
        "--dry-run",
    ])
    assert code == 0
    assert "would run scenario_a_rule_based_42" in capsys.readouterr().out


def test_completed_runs_are_skipped_without_launching(tmp_path: Path):
    spec = sup.RunSpec("scenario_a", "configs/scenario_a.yaml", "rule_based", 42)
    result_file, manifest_file = sup.result_paths(tmp_path, spec)
    result_file.parent.mkdir(parents=True)
    result_file.write_text(json.dumps({"energy": {"total_cost": 1.0}}))
    manifest_file.write_text("{}")

    # A non-existent module would fail if the supervisor tried to launch it.
    code = sup.main([
        "--scenarios", "configs/scenario_a.yaml",
        "--controllers", "rule_based",
        "--seeds", "42",
        "--output-dir", str(tmp_path),
        "--experiment-module", "module_that_does_not_exist",
        "--no-manifest-check",
    ])
    assert code == 0
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["counts"] == {"skipped": 1}
    assert status["runs"][0]["state"] == "skipped"


def test_rl_policy_path_resolves_prefix_and_scenario(tmp_path: Path):
    assert sup.rl_policy_path(None, "", "scenario_a") is None
    assert sup.rl_policy_path(str(tmp_path), "", "scenario_a") is None
    policy = tmp_path / "lmp_scenario_a.json"
    policy.write_text("{}")
    resolved = sup.rl_policy_path(str(tmp_path), "lmp_", "scenario_a")
    assert resolved == str(policy)


def test_rl_runs_without_policy_are_skipped_with_reason(tmp_path: Path, capsys):
    code = sup.main([
        "--scenarios", "configs/scenario_a.yaml",
        "--controllers", "rl",
        "--seeds", "42",
        "--output-dir", str(tmp_path),
        "--dry-run",
    ])
    assert code == 0
    assert "would run" not in capsys.readouterr().out
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["counts"] == {"skipped": 1}
    assert "no RL policy" in (status["runs"][0]["error"] or "")


def test_rl_run_with_policy_is_planned_and_carries_flag(tmp_path: Path, capsys):
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "lmp_scenario_a.json").write_text("{}")

    code = sup.main([
        "--scenarios", "configs/scenario_a.yaml",
        "--controllers", "rl",
        "--seeds", "42",
        "--output-dir", str(tmp_path / "out"),
        "--rl-policy-dir", str(policy_dir),
        "--rl-policy-prefix", "lmp_",
        "--dry-run",
    ])
    assert code == 0
    assert "would run scenario_a_rl_42" in capsys.readouterr().out

    spec = sup.RunSpec("scenario_a", "configs/scenario_a.yaml", "rl", 42)
    cmd = sup.build_command(spec, tmp_path, 12, "python", "experiments.run_experiment",
                            rl_policy=str(policy_dir / "lmp_scenario_a.json"))
    assert cmd[cmd.index("--rl-policy") + 1].endswith("lmp_scenario_a.json")


def test_build_command_carries_regime(tmp_path: Path):
    spec = sup.RunSpec("scenario_a", "configs/m1/lmp/scenario_a.yaml", "mpc", 42)
    cmd = sup.build_command(spec, tmp_path, None, "python", "experiments.run_experiment",
                            regime="lmp")
    assert cmd[cmd.index("--regime") + 1] == "lmp"
    # No regime -> no flag (phase 1 runs keep their manifest shape).
    assert "--regime" not in sup.build_command(spec, tmp_path, None, "python",
                                               "experiments.run_experiment")


def test_workers_execute_runs_in_parallel_and_count_failures(tmp_path: Path):
    # Two pending runs against a non-existent module: both must fail (exit 1)
    # through the worker pool, without corrupting the status file.
    code = sup.main([
        "--scenarios", "configs/scenario_a.yaml",
        "--controllers", "rule_based", "multi_agent",
        "--seeds", "42",
        "--output-dir", str(tmp_path),
        "--experiment-module", "module_that_does_not_exist",
        "--retries", "0",
        "--workers", "2",
        "--regime", "pool_tou",
    ])
    assert code == 1
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["counts"] == {"failed": 2}
    assert status["finished"] is True


def test_workers_skip_completed_runs_without_launching(tmp_path: Path):
    spec = sup.RunSpec("scenario_a", "configs/scenario_a.yaml", "rule_based", 42)
    result_file, manifest_file = sup.result_paths(tmp_path, spec)
    result_file.parent.mkdir(parents=True)
    result_file.write_text("{}")
    manifest_file.write_text("{}")

    code = sup.main([
        "--scenarios", "configs/scenario_a.yaml",
        "--controllers", "rule_based",
        "--seeds", "42",
        "--output-dir", str(tmp_path),
        "--experiment-module", "module_that_does_not_exist",
        "--workers", "2",
    ])
    assert code == 0
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["counts"] == {"skipped": 1}
