"""Unit tests for the hostile proposer (M2b) -- no LLM calls: stub backend."""

import json
import os
import sys

import pytest

REPO = os.environ.get(
    "SAEA_REPO",
    "/home/box/OpenBot/Agents/agent-af498092-f4e0-4fe8-a864-954882d74abf/Service-Aware-Energy-Agents",
)
sys.path.insert(0, REPO)

from src.controllers.llm_agent import (  # noqa: E402
    HOSTILE_MODES,
    LLMAgentController,
    LLMVerifiedController,
)

METADATA = {
    bid: {"battery": {"power_kw": 5.0}, "chargers": [{"max_charge_kw": 4.0}]}
    for bid in ("building_0", "building_1", "building_2", "building_3", "building_4")
}


class StubBackend:
    """Deterministic in-bounds proposer (no network)."""

    call_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    model_digest = "stub-model"

    def __init__(self, assets, value_kw=0.5):
        self.assets = assets
        self.value_kw = value_kw

    def __call__(self, prompt):
        self.call_count += 1
        return json.dumps(
            [{"asset_id": a, "value_kw": self.value_kw} for a in self.assets]
        )


@pytest.fixture
def scenario_a():
    from experiments.run_experiment import load_scenario

    return load_scenario("configs/scenario_a.yaml")


def _controller(cls, scenario_a, monkeypatch, mode, stub_value=0.5):
    monkeypatch.setenv("SAEA_LLM_HOSTILE", mode)
    controller = cls(scenario_a)
    controller.device_metadata = METADATA
    assets = [
        asset_id
        for entry in controller._build_asset_list()
        for asset_id in entry["asset_ids"]
    ]
    assert assets, "device metadata must define the asset list"
    controller._backend = StubBackend(assets, stub_value)
    observations = {f"{b}_non_shiftable_load": 1.0 for b in controller.building_ids}
    return controller, controller.get_actions(observations, 0), assets


def test_default_off(scenario_a, monkeypatch):
    monkeypatch.delenv("SAEA_LLM_HOSTILE", raising=False)
    for cls in (LLMAgentController, LLMVerifiedController):
        controller = cls(scenario_a)
        assert controller.hostile_mode == ""
        assert controller.agent_stats()["hostile_mode"] == ""


def test_invalid_mode_rejected(scenario_a, monkeypatch):
    monkeypatch.setenv("SAEA_LLM_HOSTILE", "bogus")
    with pytest.raises(ValueError):
        LLMAgentController(scenario_a)


def test_modes_are_known():
    assert HOSTILE_MODES == ("", "out_of_bounds", "malformed")


def test_out_of_bounds_forces_verifier(scenario_a, monkeypatch):
    for cls in (LLMAgentController, LLMVerifiedController):
        controller, requested, assets = _controller(
            cls, scenario_a, monkeypatch, "out_of_bounds"
        )
        applied = {a.asset_id: a.value_kw for a in requested.actions}
        stats = controller.agent_stats()
        limits = {a: controller._asset_power_limit(a) for a in assets}

        assert stats["hostile_mode"] == "out_of_bounds"
        assert stats["hostile_corrupted_proposals"] >= 1, stats
        if cls is LLMAgentController:
            # unverified arm: corrupted proposal applied as proposed, counted,
            # never repaired
            for asset, kw in applied.items():
                lim = limits.get(asset)
                if lim is not None:
                    assert abs(kw) > lim + 1e-9, (asset, kw, lim)
            assert stats["llm_unrepaired_violations"] == len(applied)
            assert stats["repair_iterations"] == 0
        else:
            # verified arm: the bounds check fired, the repair path acted, and no
            # LLM-path value was applied uncorrected. (The deterministic
            # replacement dispatch can itself exceed a device limit -- the
            # adapter clamps downstream -- which is pre-existing behaviour, not
            # a hostile-mode effect, so it is not asserted here.)
            assert stats["verification_failures"], stats
            assert stats["repair_iterations"] >= 1
            assert stats["llm_unrepaired_violations"] == 0


def test_malformed_forces_fallback(scenario_a, monkeypatch):
    for cls in (LLMAgentController, LLMVerifiedController):
        controller, requested, _ = _controller(
            cls, scenario_a, monkeypatch, "malformed"
        )
        stats = controller.agent_stats()
        assert stats["llm_raw_parse_failures"] == 1, stats
        assert stats["llm_fallback_steps"] == 1, stats
        assert stats["hostile_mode"] == "malformed"
        assert stats["llm_unrepaired_violations"] == 0


def test_verified_arm_repairs_a_valid_proposal(scenario_a, monkeypatch):
    """Control: with the hostile mode OFF the stub's in-bounds proposal passes."""
    for cls in (LLMAgentController, LLMVerifiedController):
        controller, requested, assets = _controller(
            cls, scenario_a, monkeypatch, "", stub_value=0.5
        )
        stats = controller.agent_stats()
        assert stats["hostile_corrupted_proposals"] == 0
        assert stats["first_attempt_validity"] == 1.0, stats
        assert stats["repair_iterations"] == 0
        assert stats["llm_unrepaired_violations"] == 0
        for action in requested.actions:
            limit = controller._asset_power_limit(action.asset_id)
            if limit is not None:
                assert abs(action.value_kw) <= limit + 1e-9
