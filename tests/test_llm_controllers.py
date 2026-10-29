"""Tests for the verified-vs-unverified LLM agent ablation controllers.

Covers the traceability contract from experiments/ABLATION_DESIGN.md section 4:
agent_backend, prompt hash and sampling parameters must be recorded, fallback
mode must be labelled, and the verified variant must repair out-of-bounds
proposals within budget.
"""
import json
import os
import subprocess
import sys

import pytest

from src.controllers import LLMAgentController, LLMVerifiedController, RuleBasedController
from src.schemas.scenario import (
    BatteryConfig,
    BuildingConfig,
    BuildingType,
    EVConfig,
    FlexibleLoadConfig,
    PVConfig,
    ScenarioConfig,
)


@pytest.fixture()
def scenario():
    return ScenarioConfig(
        scenario_id="llm_ablation_test",
        name="LLM Ablation",
        description="Ablation controller test",
        random_seed=42,
        timestep_minutes=60,
        buildings=[
            BuildingConfig(
                building_id="ab_building_0",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "UTC"},
                simulation_start="2023-01-01",
                simulation_end="2023-01-08",
                pv=PVConfig(capacity_kw=4.0),
                battery=BatteryConfig(capacity_kwh=10.0, power_kw=6.0),
                evs=[
                    EVConfig(
                        capacity_kwh=60.0,
                        max_charge_kw=11.0,
                        arrival_time="17:00",
                        departure_time="09:00",
                        target_soc=0.9,
                        initial_soc=0.2,
                    ),
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=5.0,
                        energy_kwh=10.0,
                        earliest_start="22:00",
                        latest_end="06:00",
                        duration_hours=2.0,
                    ),
                ],
            ),
        ],
    )


def _metadata():
    return {
        "ab_building_0": {
            "battery": {"capacity_kwh": 10.0, "power_kw": 6.0, "efficiency": 0.95},
            "chargers": [{"charger_id": "charger_0", "max_charge_kw": 11.0}],
            "deferrable": [{"power_kw": 5.0}],
            "pv_kw": 4.0,
            "hours_per_step": 1.0,
        }
    }


def _observations(timestep=0):
    return {
        "ab_building_0_net_electricity_consumption": 3.0,
        "ab_building_0_solar_generation": 1.0,
        "ab_building_0_non_shiftable_load": 2.0,
        "ab_building_0_electrical_storage_soc": 0.5,
    }


def test_fallback_mode_is_labelled_and_matches_rule_based(scenario):
    llm = LLMAgentController(scenario, device_metadata=_metadata())
    rule = RuleBasedController(scenario)
    assert llm.agent_backend == "fallback"
    assert llm.prompt_hash
    assert llm.sampling_seed == 42

    obs = _observations()
    llm_actions = llm.get_actions(obs, 0)
    rule_actions = rule.get_actions(obs, 0)
    assert llm_actions.timestep == 0
    assert {(a.asset_id, round(a.value_kw, 6)) for a in llm_actions.actions} == {
        (a.asset_id, round(a.value_kw, 6)) for a in rule_actions.actions
    }
    stats = llm.agent_stats()
    assert stats["agent_backend"] == "fallback"
    assert stats["first_attempt_validity"] == 1.0


def test_llm_backend_proposals_are_parsed_and_applied(scenario):
    payload = json.dumps([
        {"asset_id": "ab_building_0_battery", "value_kw": 2.0},
        {"asset_id": "ab_building_0_ev_0", "value_kw": 5.0},
    ])
    llm = LLMAgentController(
        scenario, device_metadata=_metadata(), backend=lambda prompt: payload
    )
    assert llm.agent_backend == "llm"
    actions = llm.get_actions(_observations(), 0).actions
    by_id = {a.asset_id: a.value_kw for a in actions}
    assert by_id["ab_building_0_battery"] == 2.0
    assert by_id["ab_building_0_ev_0"] == 5.0
    stats = llm.agent_stats()
    assert stats["first_attempt_validity"] == 1.0
    assert stats["repair_iterations"] == 0
    assert stats["unparseable_outputs"] == 0


def test_out_of_bounds_proposal_is_verified_and_repaired(scenario):
    # 99 kW exceeds every device bound; the verified variant must clamp it.
    payload = json.dumps([{"asset_id": "ab_building_0_battery", "value_kw": 99.0}])
    verified = LLMVerifiedController(
        scenario, device_metadata=_metadata(), backend=lambda prompt: payload
    )
    actions = verified.get_actions(_observations(), 0).actions
    assert actions[0].value_kw == 6.0  # battery power bound
    stats = verified.agent_stats()
    assert stats["repair_iterations"] >= 1
    assert stats["verification_failures"].get("bound_violation", 0) >= 1
    assert stats["first_attempt_validity"] == 0.0


def test_unparseable_llm_output_falls_back_and_runs_continue(scenario):
    llm = LLMAgentController(
        scenario, device_metadata=_metadata(), backend=lambda prompt: "not-json"
    )
    actions = llm.get_actions(_observations(), 0).actions
    assert actions, "fallback must produce actions for the step"
    stats = llm.agent_stats()
    assert stats["unparseable_outputs"] == 1
    assert stats["verification_failures"].get("unparseable_output", 0) == 1


def test_verified_fallback_mode_records_comparable_accounting(scenario):
    verified = LLMVerifiedController(scenario, device_metadata=_metadata())
    for step in range(3):
        verified.get_actions(_observations(), step)
    stats = verified.agent_stats()
    assert stats["total_steps"] == 3
    assert stats["first_attempt_validity"] == 1.0
    assert stats["agent_backend"] == "fallback"


def test_run_manifest_records_agent_traceability(scenario, tmp_path):
    """End-to-end: run_experiment writes agent fields into manifest.json."""
    import yaml

    config_path = tmp_path / "scenario.yaml"
    # model_dump_json() stringifies enums (BuildingType) for safe YAML dumping.
    config_path.write_text(yaml.safe_dump(json.loads(scenario.model_dump_json())))
    out_dir = tmp_path / "runs"
    result = subprocess.run(
        [
            sys.executable, "-m", "experiments.run_experiment",
            "--config", str(config_path),
            "--controller", "llm_agent",
            "--seed", "42",
            "--max-steps", "6",
            "--output-dir", str(out_dir),
            "--run-id", "llm_manifest_check",
        ],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    # The runner nests runs under <output_dir>/<scenario_id>/<run_id>/.
    run_dir = out_dir / "llm_ablation_test" / "llm_manifest_check"
    with open(run_dir / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["agent"]["agent_backend"] == "fallback"
    assert manifest["agent"]["prompt_hash"]
    assert manifest["agent"]["sampling_seed"] == 42
    with open(run_dir / "result.json", encoding="utf-8") as handle:
        result_data = json.load(handle)
    assert result_data["controller_config"]["type"] == "llm_agent"
    assert result_data["controller_config"]["prompt_hash"]
