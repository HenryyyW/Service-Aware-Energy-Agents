"""Regression tests for settlement data flowing into experiment reports."""
from pathlib import Path
from types import SimpleNamespace

from src.api.routes import runs as runs_api
from src.schemas.report import (
    AgentMetrics,
    EnergyMetrics,
    GridMetrics,
    PerMemberMetrics,
    ServiceMetrics,
)
from src.schemas.scenario import BuildingConfig, ScenarioConfig
from src.simulation.settlement import BuildingSettlement, SettlementResult
from experiments import run_experiment as runner_module


def _settlement_result() -> SettlementResult:
    member = BuildingSettlement(
        building_id="building_0",
        net_settlement=-0.04,
        baseline_grid_import_kwh=1.0,
        total_grid_import_kwh=0.5,
        baseline_grid_import_cost=0.1,
        total_grid_import_cost=0.05,
        total_community_import_cost=0.04,
        metadata={
            "baseline_grid_bill": 0.1,
            "actual_grid_bill": 0.05,
            "actual_total_bill": 0.09,
            "savings_vs_baseline": 0.01,
        },
    )
    return SettlementResult(
        building_settlements={"building_0": member},
        interval_results=[],
        total_community_volume_kwh=0.5,
        total_community_revenue=0.0,
        metadata={
            "market_type": "uniform_price",
            "settlement_interval_timesteps": 1,
            "timestep_minutes": 15,
        },
    )


def test_experiment_result_includes_settlement_metrics(monkeypatch):
    scenario = ScenarioConfig(
        scenario_id="settlement_report_test",
        name="Settlement report test",
        description="",
        buildings=[BuildingConfig(building_id="building_0")],
    )
    monkeypatch.setattr(
        runner_module,
        "compute_all_metrics",
        lambda **kwargs: {
            "energy": EnergyMetrics(),
            "service": ServiceMetrics(),
            "grid": GridMetrics(),
            "agent": AgentMetrics(),
        },
    )
    monkeypatch.setattr(
        runner_module,
        "compute_per_member_metrics",
        lambda *args: [PerMemberMetrics(member_id="building_0", building_id="building_0")],
    )
    runner = object.__new__(runner_module.ExperimentRunner)
    runner.scenario_config = scenario
    runner.history = []
    runner.start_time = 1.0
    runner.end_time = 2.0
    runner.coupler = SimpleNamespace(get_settlement_result=_settlement_result)
    runner.controller = None
    runner.run_id = "settlement-report-test"
    runner.run_dir = Path(".")

    result = runner._create_result()
    saved_result = result.model_dump(mode="json")

    assert result.energy_sharing is not None
    assert result.energy_sharing.total_savings_vs_baseline == 0.01
    assert result.energy_sharing.per_member["building_0"].actual_total_bill == 0.09
    assert result.per_member[0].settlement_savings == 0.01
    assert result.service.per_member_savings["building_0"] == 0.01
    assert {kpi.kpi_id for kpi in result.kpis} >= {
        "community_savings",
        "community_settlement_volume",
        "community_actual_bill",
    }
    assert saved_result["energy_sharing"]["per_member"]["building_0"]["settlement_savings"] == 0.01


def test_markdown_report_shows_community_and_member_settlement(monkeypatch):
    result = {
        "run_id": "settlement-report-test",
        "scenario_id": "settlement_report_test",
        "controller_type": "rule_based",
        "status": "completed",
        "energy": {},
        "service": {},
        "grid": {},
        "energy_sharing": {
            "market_type": "uniform_price",
            "total_community_volume_kwh": 0.5,
            "baseline_grid_bill": 0.1,
            "actual_grid_bill": 0.05,
            "actual_total_bill": 0.09,
            "total_savings_vs_baseline": 0.01,
            "per_member": {
                "building_0": {
                    "baseline_grid_bill": 0.1,
                    "actual_total_bill": 0.09,
                    "settlement_savings": 0.01,
                }
            },
        },
    }
    monkeypatch.setattr(runs_api, "_find_run", lambda run_id: (result, None))

    report = runs_api._markdown_report("settlement-report-test")

    assert "## Energy Sharing Settlement" in report
    assert "Savings vs. no-sharing baseline: $0.01" in report
    assert "| building_0 | $0.10 | $0.09 | $0.01 |" in report