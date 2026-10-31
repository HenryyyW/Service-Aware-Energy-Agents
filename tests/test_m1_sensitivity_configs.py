"""Tests for M1 cap-sensitivity and no-sharing configs (plan 4.3, 4.4)."""
from experiments.run_experiment import load_scenario


def test_scenario_c_lmp_cap035_parses_and_has_correct_cap():
    cfg = load_scenario("configs/m1/lmp/scenario_c_lmp_cap035.yaml")
    assert cfg.scenario_id == "scenario_c"
    assert cfg.energy_sharing.enabled is True
    assert cfg.energy_sharing.dynamic_pricing is not None
    assert cfg.energy_sharing.dynamic_pricing.price_cap_per_kwh == 0.35


def test_scenario_c_lmp_cap050_parses_and_has_correct_cap():
    cfg = load_scenario("configs/m1/lmp/scenario_c_lmp_cap050.yaml")
    assert cfg.scenario_id == "scenario_c"
    assert cfg.energy_sharing.enabled is True
    assert cfg.energy_sharing.dynamic_pricing is not None
    assert cfg.energy_sharing.dynamic_pricing.price_cap_per_kwh == 0.50


def test_scenario_d_solo_parses_and_sharing_disabled():
    cfg = load_scenario("configs/m1/scenario_d_solo.yaml")
    assert cfg.scenario_id == "scenario_d"
    assert cfg.energy_sharing.enabled is False
    # price_cap should be unchanged from base (1.0) since dynamic_pricing still exists
    assert cfg.energy_sharing.dynamic_pricing.price_cap_per_kwh == 1.0
