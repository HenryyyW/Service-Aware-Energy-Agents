"""T4/T5 analysis on synthetic run directories.

Fixtures mirror the layout written by ``experiments/run_experiment.py``:
``<scenario>/<run_id>/result.json`` plus ``manifest.json`` with the agent block.
"""
import json

import pytest

from experiments.ablation_analysis import (
    ablation_row,
    agent_execution_rows,
    build_agent_execution_markdown,
    build_repro_markdown,
    load_ablation_rows,
    parse_run_id,
    repro_report,
    run_ablation,
)


def _write_run(
    root,
    scenario,
    controller,
    seed,
    cost=100.0,
    completion=0.5,
    backend="fallback",
    first_attempt=1.0,
    repairs=0,
    steps=24,
    commit="571bdfd",
    dirty=False,
    sampling_seed=None,
    duration=30.0,
    with_agent_block=True,
):
    run_id = f"{scenario}_{controller}_{seed}"
    run_dir = root / scenario / run_id
    run_dir.mkdir(parents=True)
    result = {
        "run_id": run_id,
        "scenario_id": scenario,
        "random_seed": seed,
        "status": "completed",
        "start_time": "2026-10-29T10:00:00",
        "end_time": "2026-10-29T10:00:30",
        "energy": {"total_cost": cost, "grid_import_kwh": cost * 10, "peak_demand_kw": cost / 10},
        "service": {
            "ev_completion_rate": completion,
            "member_cost_coverage": 1.0,
            "members_interrupted": [],
        },
        "grid": {},
        "controller_config": {"type": controller},
    }
    (run_dir / "result.json").write_text(json.dumps(result))
    manifest = {
        "run_id": run_id,
        "scenario_id": scenario,
        "controller": {"type": controller, "agent_backend": backend},
        "random_seed": seed,
        "scenario_config_sha256": f"hash-{scenario}",
        "git_commit": commit,
        "git_dirty": dirty,
        "python": "3.12.0",
    }
    if with_agent_block:
        manifest["agent"] = {
            "agent_backend": backend,
            "prompt_version": "v1",
            "prompt_hash": "abc123",
            "sampling_seed": seed if sampling_seed is None else sampling_seed,
            "first_attempt_validity": first_attempt,
            "repair_iterations": repairs,
            "total_steps": steps,
            "verification_failures": {},
            "unparseable_outputs": 0,
        }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    return run_dir


def test_parse_run_id_handles_controller_names_with_underscores():
    assert parse_run_id("scenario_e_multi_agent_999") == {
        "scenario": "scenario_e",
        "controller": "multi_agent",
        "seed": 999,
    }
    assert parse_run_id("scenario_a_llm_agent_verified_42")["controller"] == (
        "llm_agent_verified"
    )
    assert parse_run_id("not_a_run") is None


def test_ablation_row_merges_kpis_with_agent_accounting(tmp_path):
    run_dir = _write_run(
        tmp_path, "scenario_a", "llm_agent_verified", 42, cost=120.0, repairs=2
    )
    from experiments.ablation_analysis import load_run

    row = ablation_row(load_run(run_dir))
    assert row["scenario"] == "scenario_a"
    assert row["controller"] == "llm_agent_verified"
    assert row["seed"] == 42
    assert row["total_cost"] == pytest.approx(120.0)
    assert row["agent_backend"] == "fallback"
    assert row["first_attempt_validity"] == pytest.approx(1.0)
    assert row["repair_iterations"] == 2
    assert row["wall_seconds"] == pytest.approx(30.0)


def test_load_ablation_rows_skips_missing_and_failed_runs(tmp_path):
    _write_run(tmp_path, "scenario_a", "llm_agent", 42)
    broken = tmp_path / "scenario_a" / "scenario_a_llm_agent_123"
    broken.mkdir(parents=True)
    (broken / "result.json").write_text("{not json")

    rows = load_ablation_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["controller"] == "llm_agent"


def test_agent_execution_rows_average_per_group(tmp_path):
    _write_run(tmp_path, "scenario_a", "llm_agent", 42, first_attempt=1.0, repairs=0)
    _write_run(tmp_path, "scenario_a", "llm_agent", 123, first_attempt=0.5, repairs=4)
    _write_run(tmp_path, "scenario_a", "llm_agent_verified", 42, first_attempt=1.0, repairs=2)

    rows = agent_execution_rows(load_ablation_rows(tmp_path))
    llm = next(row for row in rows if row["controller"] == "llm_agent")
    assert llm["n"] == 2
    assert llm["first_attempt_validity"] == pytest.approx(0.75)
    assert llm["repair_iterations"] == pytest.approx(2.0)
    assert llm["repairs_per_step"] == pytest.approx(2.0 / 24.0)
    assert llm["backends"] == ["fallback"]


def test_agent_execution_markdown_labels_fallback_mode(tmp_path):
    _write_run(tmp_path, "scenario_a", "llm_agent", 42)
    markdown = build_agent_execution_markdown(
        agent_execution_rows(load_ablation_rows(tmp_path)), "test"
    )
    assert "agent_backend: fallback" in markdown
    assert "not LLM proposal quality" in markdown
    assert "| scenario_a | llm_agent | 1 | fallback |" in markdown


def test_run_ablation_writes_tables_and_paired_tests(tmp_path):
    root = tmp_path / "ablation"
    for seed, delta in ((42, 5.0), (123, 7.0), (456, 6.0)):
        _write_run(root, "scenario_a", "multi_agent", seed, cost=100.0)
        _write_run(
            root, "scenario_a", "llm_agent_verified", seed, cost=100.0 + delta, repairs=1
        )
    payload = run_ablation(root, root, reference="multi_agent")

    assert payload["kpis"]["scenario_a::llm_agent_verified"]["n"] == 3
    assert (root / "ablation_kpis.md").exists()
    assert (root / "ablation_agent_execution.md").exists()
    assert (root / "ablation_stats.json").exists()
    markdown = (root / "ablation_kpis.md").read_text()
    assert "Paired t-tests vs `multi_agent`" in markdown
    assert "| scenario_a | llm_agent_verified | total_cost | 3 | +6.00" in markdown


def test_repro_report_flags_seed_mismatch_and_dirty_tree(tmp_path):
    _write_run(tmp_path, "scenario_a", "llm_agent", 42, sampling_seed=999)
    _write_run(tmp_path, "scenario_a", "multi_agent", 123)
    report = repro_report(tmp_path)

    assert report["runs_with_manifest"] == 2
    assert report["git_commits"] == ["571bdfd"]
    assert report["git_dirty_values"] == [False]
    assert report["sampling_seed_mismatches"] == ["scenario_a_llm_agent_42"]
    assert report["config_hashes"]["scenario_a"] == ["hash-scenario_a"]
    assert report["run_counts"]["scenario_a"] == 2
    markdown = build_repro_markdown(report)
    assert "Sampling-seed mismatches" in markdown


def test_repro_report_accepts_clean_matrix(tmp_path):
    for seed in (42, 123):
        _write_run(tmp_path, "scenario_a", "rule_based", seed, with_agent_block=False)
    report = repro_report(tmp_path)

    assert report["sampling_seed_mismatches"] == []
    assert report["runs_without_agent_stats"] == 2  # matrices have no agent block
    markdown = build_repro_markdown(report)
    assert "0 failed" not in markdown  # phrased as "Failed runs: 0"
    assert "Failed runs: 0" in markdown
