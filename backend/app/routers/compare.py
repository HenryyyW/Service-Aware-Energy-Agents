"""Scenario comparison API endpoints."""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.routers.simulations import _runs, _couplers

router = APIRouter()


class ComparisonResult(BaseModel):
    run_id_a: str
    run_id_b: str
    scenario_id_a: str
    scenario_id_b: str
    controller_type_a: str
    controller_type_b: str
    controller_fallback_a: Optional[Dict[str, Any]] = None
    controller_fallback_b: Optional[Dict[str, Any]] = None
    metrics_comparison: Dict[str, Dict[str, Dict[str, float]]]
    summary: Dict[str, Any]


def _compare_metrics(
    metrics_a: Dict[str, float], metrics_b: Dict[str, float], group_name: str
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Compare two metric dictionaries."""
    comparison: Dict[str, Dict[str, float]] = {}
    all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
    for key in all_keys:
        val_a = metrics_a.get(key, 0)
        val_b = metrics_b.get(key, 0)
        diff = val_b - val_a
        pct_change = (diff / val_a * 100) if val_a != 0 else 0
        comparison[key] = {
            "run_a": val_a,
            "run_b": val_b,
            "difference": diff,
            "pct_change": pct_change,
        }
    return {group_name: comparison}


@router.get("/compare", response_model=ComparisonResult)
async def compare_runs(
    run_id_a: str = Query(..., description="First run ID"),
    run_id_b: str = Query(..., description="Second run ID"),
):
    """Compare two simulation runs."""
    if run_id_a not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id_a} not found")
    if run_id_b not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id_b} not found")

    run_a = _runs[run_id_a]
    run_b = _runs[run_id_b]

    # Compare energy metrics
    energy_comparison = _compare_metrics(
        run_a.get("energy_metrics", {}), run_b.get("energy_metrics", {}), "energy"
    )

    # Compare service metrics
    service_comparison = _compare_metrics(
        run_a.get("service_metrics", {}), run_b.get("service_metrics", {}), "service"
    )

    # Compare grid metrics
    grid_comparison = _compare_metrics(
        run_a.get("grid_metrics", {}), run_b.get("grid_metrics", {}), "grid"
    )

    # Combine all comparisons
    metrics_comparison = {}
    metrics_comparison.update(energy_comparison)
    metrics_comparison.update(service_comparison)
    metrics_comparison.update(grid_comparison)

    # Generate summary
    summary: Dict[str, List[str]] = {
        "run_a_better": [],
        "run_b_better": [],
        "similar": [],
    }

    for group_name, group_metrics in metrics_comparison.items():
        for metric_name, values in group_metrics.items():
            values_dict: Dict[str, float] = values
            diff = values_dict["difference"]
            if abs(diff) < 0.01 * max(
                abs(values_dict["run_a"]), abs(values_dict["run_b"]), 1
            ):
                summary["similar"].append(f"{group_name}.{metric_name}")
            elif diff > 0:
                summary["run_b_better"].append(f"{group_name}.{metric_name}")
            else:
                summary["run_a_better"].append(f"{group_name}.{metric_name}")

    return ComparisonResult(
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        scenario_id_a=run_a["scenario_id"],
        scenario_id_b=run_b["scenario_id"],
        controller_type_a=run_a["controller_type"],
        controller_type_b=run_b["controller_type"],
        controller_fallback_a={
            "fallback_steps": run_a.get("controller_fallback_steps", 0),
            "fallback_reason": run_a.get("controller_fallback_reason"),
        } if run_a.get("controller_fallback_steps", 0) > 0 else None,
        controller_fallback_b={
            "fallback_steps": run_b.get("controller_fallback_steps", 0),
            "fallback_reason": run_b.get("controller_fallback_reason"),
        } if run_b.get("controller_fallback_steps", 0) > 0 else None,
        metrics_comparison=metrics_comparison,
        summary=summary,
    )


@router.get("/compare/detailed/{run_id_a}/{run_id_b}")
async def compare_runs_detailed(run_id_a: str, run_id_b: str):
    """Get detailed comparison including trajectories."""
    if run_id_a not in _runs or run_id_b not in _runs:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    run_a = _runs[run_id_a]
    run_b = _runs[run_id_b]

    # Get trajectories if available
    trajectories_a = []
    trajectories_b = []

    if run_id_a in _couplers:
        for h in _couplers[run_id_a].co_sim_history:
            trajectories_a.append(
                {
                    "timestep": h.timestep,
                    "costs": h.citylearn_result.costs,
                    "grid_diagnostics": h.citylearn_result.grid_diagnostics,
                }
            )

    if run_id_b in _couplers:
        for h in _couplers[run_id_b].co_sim_history:
            trajectories_b.append(
                {
                    "timestep": h.timestep,
                    "costs": h.citylearn_result.costs,
                    "grid_diagnostics": h.citylearn_result.grid_diagnostics,
                }
            )

    # Time series comparison
    time_series: Dict[str, List[Dict[str, Any]]] = {
        "cost_comparison": [],
        "voltage_comparison": [],
        "loading_comparison": [],
    }

    min_steps = min(len(trajectories_a), len(trajectories_b))
    for i in range(min_steps):
        ta: Dict[str, Any] = trajectories_a[i]
        tb: Dict[str, Any] = trajectories_b[i]

        costs_a = ta.get("costs", {})
        costs_b = tb.get("costs", {})
        time_series["cost_comparison"].append(
            {
                "timestep": i,
                "run_a": sum(costs_a.values()) if costs_a else 0,
                "run_b": sum(costs_b.values()) if costs_b else 0,
            }
        )

        if ta.get("grid_diagnostics") and tb.get("grid_diagnostics"):
            gd_a: Dict[str, Any] = ta["grid_diagnostics"]  # type: ignore[assignment]
            gd_b: Dict[str, Any] = tb["grid_diagnostics"]  # type: ignore[assignment]

            vp_a = gd_a.get("voltage_profile", {})
            vp_b = gd_b.get("voltage_profile", {})
            time_series["voltage_comparison"].append(
                {
                    "timestep": i,
                    "run_a_avg": sum(vp_a.values()) / max(len(vp_a), 1),
                    "run_b_avg": sum(vp_b.values()) / max(len(vp_b), 1),
                }
            )

            lp_a = gd_a.get("loading_profile", {}).get("lines", {})
            lp_b = gd_b.get("loading_profile", {}).get("lines", {})
            time_series["loading_comparison"].append(
                {
                    "timestep": i,
                    "run_a_max_line": max(lp_a.values(), default=0),
                    "run_b_max_line": max(lp_b.values(), default=0),
                }
            )

    return {
        "basic_comparison": await compare_runs(run_id_a, run_id_b),
        "time_series": time_series,
        "trajectory_count": {
            "run_a": len(trajectories_a),
            "run_b": len(trajectories_b),
        },
    }
