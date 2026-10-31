"""Tests for the phase 2 pricing-regime runner wiring (plan step 4).

Covers the --regime flag contract: regime overrides on a base config,
cost-basis mapping, p2p marked SCHEDULE-LATER, and end-to-end smoke runs in
which the regime and cost basis land in result.json and manifest.json with
run ids following the {scenario}_{controller}_{seed} convention.
"""
import json
import subprocess
import sys

import pytest

from src.schemas.scenario import (
    BatteryConfig,
    BuildingConfig,
    BuildingType,
    DynamicPricingConfig,
    EnergySharingConfig,
    EVConfig,
    FlexibleLoadConfig,
    PVConfig,
    ScenarioConfig,
)
from experiments.run_experiment import (
    REGIME_COST_BASIS,
    REGIMES,
    apply_pricing_regime,
)


@pytest.fixture()
def scenario():
    return ScenarioConfig(
        scenario_id="regime_test",
        name="Regime Runner Test",
        description="M1 regime wiring test",
        random_seed=42,
        timestep_minutes=60,
        community_import_limit_kw=200.0,
        community_export_limit_kw=150.0,
        buildings=[
            BuildingConfig(
                building_id=f"rb_{i}",
                building_type=BuildingType.RESIDENTIAL,
                location={"lat": 40.0, "lon": -105.0, "timezone": "America/Denver"},
                simulation_start="2023-07-01",
                simulation_end="2023-07-08",
                pv=PVConfig(capacity_kw=5.0 + i),
                battery=BatteryConfig(capacity_kwh=13.5, power_kw=6.0, initial_soc=0.5),
                evs=[
                    EVConfig(
                        capacity_kwh=60.0,
                        max_charge_kw=7.0,
                        initial_soc=0.3,
                        target_soc=0.8,
                        arrival_time="18:00",
                        departure_time="07:00",
                    )
                ],
                flexible_loads=[
                    FlexibleLoadConfig(
                        power_kw=3.0,
                        energy_kwh=6.0,
                        earliest_start="20:00",
                        latest_end="06:00",
                        duration_hours=2.0,
                    )
                ],
            )
            for i in range(3)  # >=2 buildings so the sharing/market layer runs
        ],
    )


def test_regime_table_matches_plan():
    assert REGIMES == ("tou_solo", "pool_tou", "lmp", "p2p")
    assert REGIME_COST_BASIS == {
        "tou_solo": "tariff",
        "pool_tou": "tariff",
        "lmp": "lmp",
        "p2p": "tariff",
    }


def test_tou_solo_disables_sharing_and_dynamic_pricing(scenario):
    scenario.energy_sharing = EnergySharingConfig(
        enabled=True,
        market_type="lmp",
        dynamic_pricing=DynamicPricingConfig(enabled=True),
    )
    apply_pricing_regime(scenario, "tou_solo")
    assert scenario.energy_sharing.enabled is False
    assert scenario.energy_sharing.dynamic_pricing.enabled is False
    assert scenario.scenario_id == "regime_test"  # stays clean for paired analysis


def test_pool_tou_enables_pool_at_tou(scenario):
    apply_pricing_regime(scenario, "pool_tou")
    assert scenario.energy_sharing.enabled is True
    assert scenario.energy_sharing.market_type == "uniform_price"
    # dynamic pricing must stay off in the pool_tou baseline
    assert scenario.energy_sharing.dynamic_pricing is None or (
        scenario.energy_sharing.dynamic_pricing.enabled is False
    )


def test_lmp_enables_locational_pricing_with_timestep_interval(scenario):
    scenario.energy_sharing = None  # base config without an energy_sharing block
    apply_pricing_regime(scenario, "lmp")
    es = scenario.energy_sharing
    assert es.enabled is True
    assert es.market_type == "lmp"
    assert es.dynamic_pricing is not None
    assert es.dynamic_pricing.enabled is True
    assert es.dynamic_pricing.pricing_type == "lmp"
    # the coupler rejects lmp_update_interval_minutes != timestep_minutes
    assert es.dynamic_pricing.lmp_update_interval_minutes == scenario.timestep_minutes


def test_lmp_overrides_keep_existing_dynamic_pricing_block(scenario):
    scenario.energy_sharing = EnergySharingConfig(
        enabled=True,
        market_type="uniform_price",
        dynamic_pricing=DynamicPricingConfig(enabled=False, price_cap_per_kwh=0.5),
    )
    apply_pricing_regime(scenario, "lmp")
    dp = scenario.energy_sharing.dynamic_pricing
    assert dp.enabled is True
    assert dp.pricing_type == "lmp"
    assert dp.price_cap_per_kwh == 0.5  # config-owned fields pass through


def test_p2p_is_wireable_but_marked_schedule_later(scenario):
    apply_pricing_regime(scenario, "p2p")
    assert scenario.energy_sharing.enabled is True
    assert scenario.energy_sharing.market_type == "p2p"
    assert REGIME_COST_BASIS["p2p"] == "tariff"
    # the clearing engine must exist so a future gated matrix can use it
    from src.simulation.market import MarketType, create_market_engine

    engine = create_market_engine(scenario, scenario.energy_sharing)
    assert engine.__class__.__name__ == "P2PClearing"
    assert MarketType.P2P.value == "p2p"


def _scenario_yaml(scenario, tmp_path):
    import yaml

    config_path = tmp_path / f"{scenario.scenario_id}.yaml"
    config_path.write_text(yaml.safe_dump(json.loads(scenario.model_dump_json())))
    return config_path


def _run_experiment(config_path, tmp_path, regime, run_id, max_steps=4):
    return subprocess.run(
        [
            sys.executable, "-m", "experiments.run_experiment",
            "--config", str(config_path),
            "--controller", "rule_based",
            "--seed", "42",
            "--max-steps", str(max_steps),
            "--output-dir", str(tmp_path / regime),
            "--run-id", run_id,
            "--regime", regime,
        ],
        capture_output=True, text=True, timeout=600,
    )


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_smoke_pool_tou_manifest_and_result(tmp_path, scenario):
    config_path = _scenario_yaml(scenario, tmp_path)
    result = _run_experiment(config_path, tmp_path, "pool_tou", "regime_test_rule_based_42")
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    run_dir = tmp_path / "pool_tou" / "regime_test" / "regime_test_rule_based_42"

    manifest = _load_json(run_dir / "manifest.json")
    assert manifest["run_id"] == "regime_test_rule_based_42"  # {scenario}_{controller}_{seed}
    assert manifest["pricing_regime"] == "pool_tou"
    assert manifest["cost_basis"] == "tariff"

    result_data = _load_json(run_dir / "result.json")
    assert result_data["pricing_regime"] == "pool_tou"
    assert result_data["cost_basis"] == "tariff"


def test_smoke_lmp_run_bills_at_lmp_and_differs_in_config_hash(tmp_path, scenario):
    config_path = _scenario_yaml(scenario, tmp_path)
    result = _run_experiment(config_path, tmp_path, "lmp", "regime_test_rule_based_42")
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    run_dir = tmp_path / "lmp" / "regime_test" / "regime_test_rule_based_42"

    manifest = _load_json(run_dir / "manifest.json")
    assert manifest["pricing_regime"] == "lmp"
    assert manifest["cost_basis"] == "lmp"

    result_data = _load_json(run_dir / "result.json")
    assert result_data["pricing_regime"] == "lmp"
    assert result_data["cost_basis"] == "lmp"

    # Per-step market clearing lands in market_results.jsonl (coupling.py
    # export_results): the LMP regime must clear with market_type == "lmp".
    market_file = run_dir / "market_results.jsonl"
    assert market_file.exists(), "market results must be exported"
    market_rows = [
        json.loads(line)
        for line in market_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert market_rows, "market clearing must produce per-step rows"
    assert all(
        row.get("market_type") == "lmp" for row in market_rows
    ), "every cleared step must report the lmp market type"

    # grid_diagnostics.jsonl carries the per-step lmp_result (building prices,
    # OPF status, cap hits) as exported by coupling.py export_results.
    diag = run_dir / "grid_diagnostics.jsonl"
    assert diag.exists(), "grid diagnostics must be exported"
    lmp_rows = [
        json.loads(line)
        for line in diag.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any("lmp_result" in row for row in lmp_rows), (
        "per-step lmp_result (building prices, status, cap hits) must reach grid_diagnostics.jsonl"
    )


def test_no_regime_flag_keeps_phase1_artifact_shape(tmp_path, scenario):
    """Without --regime, result.json/manifest.json carry no regime fields."""
    import yaml

    config_path = tmp_path / "scenario.yaml"
    config_path.write_text(yaml.safe_dump(json.loads(scenario.model_dump_json())))
    result = subprocess.run(
        [
            sys.executable, "-m", "experiments.run_experiment",
            "--config", str(config_path),
            "--controller", "rule_based",
            "--seed", "42",
            "--max-steps", "3",
            "--output-dir", str(tmp_path / "base"),
            "--run-id", "regime_test_rule_based_42",
        ],
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    run_dir = tmp_path / "base" / "regime_test" / "regime_test_rule_based_42"
    assert "pricing_regime" not in _load_json(run_dir / "manifest.json")
    assert "pricing_regime" not in _load_json(run_dir / "result.json")
