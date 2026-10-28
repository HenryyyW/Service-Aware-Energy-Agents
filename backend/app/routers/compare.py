"""Scenario comparison API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.routers.simulations import _runs, _couplers

router = APIRouter()


class ComparisonResult(BaseModel):
    run_id_a: str
    run_id_b: str
    scenario_id_a: str
    scenario_id_b: str
    controller_type_a: str
    controller_type_b: str
    metrics_comparison: Dict[str, Dict[str, Dict[str, float]]]
    summary: Dict[str, Any]


def _compare_metrics(metrics_a: Dict[str, float], metrics_b: Dict[str, float], group_name: str) -> Dict[str, Dict[str, float]]:
    """Compare two metric dictionaries."""
    comparison = {}
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
        run_a.get("energy_metrics", {}),
        run_b.get("energy_metrics", {}),
        "energy"
    )
    
    # Compare service metrics
    service_comparison = _compare_metrics(
        run_a.get("service_metrics", {}),
        run_b.get("service_metrics", {}),
        "service"
    )
    
    # Compare grid metrics
    grid_comparison = _compare_metrics(
        run_a.get("grid_metrics", {}),
        run_b.get("grid_metrics", {}),
        "grid"
    )
    
    # Combine all comparisons
    metrics_comparison = {}
    metrics_comparison.update(energy_comparison)
    metrics_comparison.update(service_comparison)
    metrics_comparison.update(grid_comparison)
    
    # Generate summary
    summary = {
        "run_a_better": [],
        "run_b_better": [],
        "similar": [],
    }
    
    for group_name, group_metrics in metrics_comparison.items():
        for metric_name, values in group_metrics.items():
            diff = values["difference"]
            if abs(diff) < 0.01 * max(abs(values["run_a"]), abs(values["run_b"]), 1):
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
            trajectories_a.append({
                "timestep": h.timestep,
                "costs": h.citylearn_result.costs,
                "grid_diagnostics": h.citylearn_result.grid_diagnostics,
            })
    
    if run_id_b in _couplers:
        for h in _couplers[run_id_b].co_sim_history:
            trajectories_b.append({
                "timestep": h.timestep,
                "costs": h.citylearn_result.costs,
                "grid_diagnostics": h.citylearn_result.grid_diagnostics,
            })
    
    # Time series comparison
    time_series = {
        "cost_comparison": [],
        "voltage_comparison": [],
        "loading_comparison": [],
    }
    
    min_steps = min(len(trajectories_a), len(trajectories_b))
    for i in range(min_steps):
        ta = trajectories_a[i]
        tb = trajectories_b[i]
        
        time_series["cost_comparison"].append({
            "timestep": i,
            "run_a": sum(ta["costs"].values()) if ta["costs"] else 0,
            "run_b": sum(tb["costs"].values()) if tb["costs"] else 0,
        })
        
        if ta.get("grid_diagnostics") and tb.get("grid_diagnostics"):
            gd_a = ta["grid_diagnostics"]
            gd_b = tb["grid_diagnostics"]
            
            time_series["voltage_comparison"].append({
                "timestep": i,
                "run_a_avg": sum(gd_a.get("voltage_profile", {}).values()) / max(len(gd_a.get("voltage_profile", {})), 1),
                "run_b_avg": sum(gd_b.get("voltage_profile", {}).values()) / max(len(gd_b.get("voltage_profile", {})), 1),
            })
            
            time_series["loading_comparison"].append({
                "timestep": i,
                "run_a_max_line": max(gd_a.get("loading_profile", {}).get("lines", {}).values(), default=0),
                "run_b_max_line": max(gd_b.get("loading_profile", {}).get("lines", {}).values(), default=0),
            })
    
    return {
        "basic_comparison": await compare_runs(run_id_a, run_id_b),
        "time_series": time_series,
        "trajectory_count": {"run_a": len(trajectories_a), "run_b": len(trajectories_b)},
    }