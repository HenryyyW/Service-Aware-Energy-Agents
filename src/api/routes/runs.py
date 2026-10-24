"""Persistent simulation run, report, and comparison routes."""
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from experiments.run_experiment import ExperimentRunner
from src.api.routes.scenarios import _load_config_scenario, _scenarios
from src.schemas.scenario import ScenarioConfig

ROOT = Path(__file__).resolve().parents[3]
RESULT_ROOTS = (ROOT / "results", ROOT / "experiments" / "results")
API_RESULTS = ROOT / "results" / "api_runs"
_active_runs: Dict[str, Dict[str, Any]] = {}

runs_router = APIRouter()
reports_router = APIRouter()
comparison_router = APIRouter()


class RunRequest(BaseModel):
    scenario_id: str
    controller_type: Literal["rule_based", "multi_agent", "centralized"] = "rule_based"
    parameters: Dict[str, Any] = Field(default_factory=dict)


def _iter_result_files():
    for root in RESULT_ROOTS:
        if root.exists():
            yield from root.rglob("result.json")


def _read_result(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail=f"Could not read run result: {error}") from error


def _json_safe(value: Any) -> Any:
    """Convert scientific Python values to strict JSON-compatible values."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _find_run(run_id: str):
    active = _active_runs.get(run_id)
    if active and active.get("status") in {"pending", "running", "failed"}:
        return active, None
    for result_path in _iter_result_files():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if result.get("run_id") == run_id:
            return result, result_path
    if active:
        return active, None
    raise HTTPException(status_code=404, detail="Simulation run not found")


def _summary(result: Dict[str, Any]) -> Dict[str, Any]:
    energy = result.get("energy") or {}
    service = result.get("service") or {}
    generated = energy.get("pv_generation_kwh", 0) or 0
    self_consumed = energy.get("pv_self_consumption_kwh", 0) or 0
    return {
        "run_id": result["run_id"],
        "scenario_id": result["scenario_id"],
        "controller_type": result.get("controller_type", "rule_based"),
        "status": result.get("status", "completed"),
        "start_time": result.get("start_time"),
        "end_time": result.get("end_time"),
        "random_seed": result.get("random_seed"),
        "energy_metrics": {
            **energy,
            "pv_self_consumption": self_consumed / generated if generated else 0,
            "pv_curtailment": energy.get("pv_curtailment_kwh", 0),
        },
        "service_metrics": {
            **service,
            "avg_ev_soc_at_departure": service.get("ev_avg_soc_at_departure", 0),
        },
        "grid_metrics": result.get("grid") or {},
        "energy_sharing_metrics": result.get("energy_sharing") or {},
    }


def _execute_run(run_id: str, scenario_data: Dict[str, Any], controller_type: str, max_steps: Optional[int]):
    _active_runs[run_id]["status"] = "running"
    try:
        scenario = ScenarioConfig.model_validate(scenario_data)
        runner = ExperimentRunner(scenario, output_dir=str(API_RESULTS), run_id=run_id)
        runner.setup(controller_type)
        runner.run(max_steps=max_steps)
        result_path = runner.run_dir / "result.json"
        _active_runs[run_id] = _summary(_read_result(result_path))
    except Exception as error:
        _active_runs[run_id] = {
            **_active_runs[run_id],
            "status": "failed",
            "error": str(error),
            "end_time": datetime.now(timezone.utc).isoformat(),
        }


@runs_router.get("")
async def list_runs():
    runs = {run_id: _summary(result) for run_id, result in _active_runs.items()}
    for result_path in _iter_result_files():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("run_id"):
                runs.setdefault(result["run_id"], _summary(result))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return sorted(runs.values(), key=lambda run: run.get("start_time") or "", reverse=True)


@runs_router.post("")
async def create_run(request: RunRequest, background_tasks: BackgroundTasks):
    source = _scenarios.get(request.scenario_id) or _load_config_scenario(request.scenario_id)
    parameters = request.parameters
    updates = {}
    for field in ("community_import_limit_kw", "community_export_limit_kw", "random_seed"):
        if field in parameters and parameters[field] is not None:
            updates[field] = parameters[field]
    scenario = source.model_copy(update=updates)
    run_id = f"api_{scenario.scenario_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    _active_runs[run_id] = {
        "run_id": run_id,
        "scenario_id": scenario.scenario_id,
        "controller_type": request.controller_type,
        "status": "pending",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "random_seed": scenario.random_seed,
    }
    background_tasks.add_task(_execute_run, run_id, scenario.model_dump(mode="json"), request.controller_type, parameters.get("max_steps"))
    return _active_runs[run_id]


@runs_router.get("/{run_id}")
async def get_run(run_id: str):
    result, _ = _find_run(run_id)
    if result.get("status") == "failed":
        return {**result, "error": result.get("error", "Simulation failed")}
    return _summary(result) if "energy" in result else result


@runs_router.get("/{run_id}/trajectories")
async def get_run_trajectories(run_id: str):
    result, result_path = _find_run(run_id)
    if result_path is None:
        if result.get("status") in {"pending", "running"}:
            raise HTTPException(status_code=409, detail="Simulation is still running")
        raise HTTPException(status_code=404, detail="Trajectory data not available")
    trajectory_path = result_path.parent / "trajectories.jsonl"
    if not trajectory_path.is_file():
        raise HTTPException(status_code=404, detail="Trajectory data not found")
    return _json_safe([
        json.loads(line)
        for line in trajectory_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ])


@runs_router.get("/{run_id}/grid")
async def get_run_grid_diagnostics(run_id: str):
    trajectories = await get_run_trajectories(run_id)
    return [{"timestep": item.get("timestep"), "grid_diagnostics": item.get("grid_diagnostics")} for item in trajectories]


def _markdown_report(run_id: str) -> str:
    result, _ = _find_run(run_id)
    if result.get("status") != "completed" and "energy" not in result:
        raise HTTPException(status_code=409, detail="Report is available after the run completes")
    data = result if "energy" in result else None
    if data is None:
        _, result_path = _find_run(run_id)
        data = _read_result(result_path)
    summary = _summary(data)
    energy = summary["energy_metrics"]
    service = summary["service_metrics"]
    grid = summary["grid_metrics"]
    sharing = summary["energy_sharing_metrics"]
    return "\n".join([
        f"# Simulation Report: {run_id}", "",
        f"- Scenario: {data.get('scenario_id')}",
        f"- Controller: {data.get('controller_type')}",
        f"- Seed: {data.get('random_seed')}",
        f"- Status: {data.get('status')}",
        f"- Started: {data.get('start_time')}", "",
        "## Energy and Cost", "",
        f"- Total cost: ${energy.get('total_cost', 0):.2f}",
        f"- Grid import: {energy.get('grid_import_kwh', 0):.2f} kWh",
        f"- Grid export: {energy.get('grid_export_kwh', 0):.2f} kWh",
        f"- Peak demand: {energy.get('peak_demand_kw', 0):.2f} kW", "",
        "## Service", "",
        f"- EV completion: {service.get('ev_completion_rate', 0):.1%}",
        f"- Average EV departure SOC: {service.get('avg_ev_soc_at_departure', 0)}",
        f"- Comfort violations: {service.get('comfort_violation_degree_hours', 0):.2f} degree-hours", "",
        "## Grid", "",
        f"- Power-flow convergence: {grid.get('power_flow_convergence_rate', 0):.1%}",
        f"- Voltage violations: {grid.get('voltage_violations_count', 0)}",
        f"- Maximum line loading: {grid.get('max_line_loading_pct', 0):.2f}%",
        f"- Maximum transformer loading: {grid.get('max_transformer_loading_pct', 0):.2f}%", "",
        "## Energy Sharing Settlement", "",
        f"- Market: {sharing.get('market_type', 'not enabled')}",
        f"- Community settlement volume: {sharing.get('total_community_volume_kwh', 0):.2f} kWh",
        f"- Baseline grid bill: ${sharing.get('baseline_grid_bill', 0):.2f}",
        f"- Actual grid bill: ${sharing.get('actual_grid_bill', 0):.2f}",
        f"- Actual total bill: ${sharing.get('actual_total_bill', 0):.2f}",
        f"- Savings vs. no-sharing baseline: ${sharing.get('total_savings_vs_baseline', 0):.2f}",
        "", "| Member | Baseline bill | Actual total bill | Savings |", "|---|---:|---:|---:|",
        *[
            f"| {member_id} | ${member.get('baseline_grid_bill', 0):.2f} | ${member.get('actual_total_bill', 0):.2f} | ${member.get('settlement_savings', 0):.2f} |"
            for member_id, member in sharing.get("per_member", {}).items()
        ], "",
        "> This report summarizes saved experiment outputs. Metrics marked as placeholders in the evaluation implementation should not be interpreted as validated measurements.", "",
    ])


@reports_router.get("/{run_id}")
async def get_report(run_id: str):
    return Response(_markdown_report(run_id), media_type="text/markdown; charset=utf-8")


@reports_router.get("/{run_id}/download")
async def download_report(run_id: str, format: Literal["markdown"] = Query("markdown")):
    content = _markdown_report(run_id)
    return Response(content, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="report_{run_id}.md"'})


@comparison_router.get("")
async def compare_runs(run_id_a: str, run_id_b: str):
    run_a, _ = _find_run(run_id_a)
    run_b, _ = _find_run(run_id_b)
    if "energy" not in run_a or "energy" not in run_b:
        raise HTTPException(status_code=409, detail="Both runs must be complete before comparison")
    summary_a, summary_b = _summary(run_a), _summary(run_b)
    groups = ("energy_metrics", "service_metrics", "grid_metrics", "energy_sharing_metrics")
    comparison = {}
    for group in groups:
        keys = set(summary_a[group]) & set(summary_b[group])
        comparison[group] = {
            key: {"run_a": summary_a[group][key], "run_b": summary_b[group][key]}
            for key in keys
            if isinstance(summary_a[group][key], (int, float)) and isinstance(summary_b[group][key], (int, float))
        }
    return {"run_a": summary_a, "run_b": summary_b, "metrics_comparison": comparison}
