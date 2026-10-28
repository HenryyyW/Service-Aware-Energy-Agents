"""Simulation management API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime
import asyncio
import numpy as np
from fastapi.encoders import jsonable_encoder

def _convert_numpy(obj):
    """Recursively convert numpy types to Python native types."""
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: _convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_numpy(v) for v in obj)
    else:
        return obj

from src.schemas.scenario import ScenarioConfig
from src.simulation.coupling import SimulationCoupler
from src.schemas.action import RequestedActions
from src.controllers import RuleBasedController, CentralizedController, MultiAgentController

router = APIRouter()

# In-memory storage for simulation runs
_runs: Dict[str, dict] = {}
_couplers: Dict[str, SimulationCoupler] = {}
_controllers: Dict[str, Any] = {}


class SimulationCreateRequest(BaseModel):
    scenario_id: str
    controller_type: str = "rule_based"
    parameters: Optional[Dict[str, Any]] = None


class SimulationRun(BaseModel):
    run_id: str
    scenario_id: str
    controller_type: str
    status: str = "pending"  # pending, running, completed, failed
    start_time: str
    end_time: Optional[str] = None
    energy_metrics: Optional[Dict[str, Any]] = None
    service_metrics: Optional[Dict[str, Any]] = None
    grid_metrics: Optional[Dict[str, Any]] = None
    random_seed: Optional[int] = None
    max_steps: Optional[int] = None
    current_step: int = 0
    total_steps: Optional[int] = None


def _get_controller(controller_type: str, scenario: ScenarioConfig):
    """Get controller instance by type."""
    if controller_type == "centralized":
        return CentralizedController(scenario)
    elif controller_type == "multi_agent":
        return MultiAgentController(scenario)
    else:
        return RuleBasedController(scenario)


async def _run_simulation_background(run_id: str, scenario: ScenarioConfig, controller_type: str, max_steps: int, random_seed: int):
    """Background task to run simulation."""
    try:
        _runs[run_id]["status"] = "running"
        
        # Initialize coupler and controller
        coupler = SimulationCoupler(scenario)
        controller = _get_controller(controller_type, scenario)
        
        _couplers[run_id] = coupler
        _controllers[run_id] = controller
        
        # Reset with seed
        observations = coupler.reset(random_seed)
        
        # Run simulation loop
        for step in range(max_steps):
            if _runs[run_id].get("cancelled", False):
                _runs[run_id]["status"] = "cancelled"
                return
            
            # Get actions from controller
            requested_actions = controller.get_actions(observations, step)
            
            # Step the co-simulation
            result = coupler.step(requested_actions)
            
            # Update progress
            _runs[run_id]["current_step"] = step + 1
            _runs[run_id]["total_steps"] = max_steps
            
            # Check termination
            if result.terminated or result.truncated:
                break
            
            # Small delay to prevent blocking
            await asyncio.sleep(0.01)
        
        # Get final KPIs
        kpis = coupler.get_kpis()
        settlement = coupler.get_settlement_result()
        
        _runs[run_id]["status"] = "completed"
        _runs[run_id]["end_time"] = datetime.utcnow().isoformat()
        _runs[run_id]["energy_metrics"] = {
            "total_cost": kpis.get("total_cost", 0),
            "grid_import_kwh": kpis.get("grid_import_kwh", 0),
            "grid_export_kwh": kpis.get("grid_export_kwh", 0),
            "peak_demand_kw": kpis.get("peak_demand_kw", 0),
            "pv_self_consumption": kpis.get("pv_self_consumption", 0),
            "pv_generation_kwh": kpis.get("pv_generation_kwh", 0),
            "pv_curtailment": kpis.get("pv_curtailment", 0),
            "battery_throughput_kwh": kpis.get("battery_throughput_kwh", 0),
            "carbon_emissions_kg": kpis.get("carbon_emissions_kg", 0),
        }
        _runs[run_id]["service_metrics"] = {
            "ev_completion_rate": kpis.get("ev_completion_rate", 0),
            "avg_ev_soc_at_departure": kpis.get("avg_ev_soc_at_departure", 0),
            "comfort_violation_degree_hours": kpis.get("comfort_violation_degree_hours", 0),
            "flexible_load_completion_rate": kpis.get("flexible_load_completion_rate", 0),
            "dr_delivery_rate": kpis.get("dr_delivery_rate", 0),
            "gini_coefficient": kpis.get("gini_coefficient", 0),
            "worst_member_savings": kpis.get("worst_member_savings", 0),
        }
        _runs[run_id]["grid_metrics"] = {
            "power_flow_convergence_rate": kpis.get("grid_convergence_rate", 0),
            "voltage_violations_count": kpis.get("grid_voltage_violations", 0),
            "max_voltage_pu": kpis.get("max_voltage_pu", 1.0),
            "min_voltage_pu": kpis.get("min_voltage_pu", 1.0),
            "max_line_loading_pct": kpis.get("max_line_loading_pct", 0),
            "max_transformer_loading_pct": kpis.get("max_trafo_loading_pct", 0),
        }
        
        if settlement:
            _runs[run_id]["settlement"] = {
                "total_community_volume_kwh": settlement.total_community_volume_kwh,
                "total_community_revenue": settlement.total_community_revenue,
            }
        
    except Exception as e:
        _runs[run_id]["status"] = "failed"
        _runs[run_id]["error"] = str(e)
        _runs[run_id]["end_time"] = datetime.utcnow().isoformat()


@router.post("/simulations", response_model=SimulationRun, status_code=201)
async def create_simulation(request: SimulationCreateRequest, background_tasks: BackgroundTasks):
    """Start a new simulation run."""
    # Validate scenario exists
    from app.routers.scenarios import _scenarios, _load_scenario_from_disk
    
    if request.scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(request.scenario_id)
        if scenario:
            _scenarios[request.scenario_id] = scenario
        else:
            raise HTTPException(status_code=404, detail=f"Scenario {request.scenario_id} not found")
    
    scenario = _scenarios[request.scenario_id]
    run_id = f"run_{uuid4().hex[:12]}"
    max_steps = request.parameters.get("max_steps", 672) if request.parameters else 672  # 7 days at 15-min intervals
    random_seed = request.parameters.get("random_seed", scenario.random_seed) if request.parameters else scenario.random_seed
    
    run = SimulationRun(
        run_id=run_id,
        scenario_id=request.scenario_id,
        controller_type=request.controller_type,
        start_time=datetime.utcnow().isoformat(),
        random_seed=random_seed,
        max_steps=max_steps,
    )
    
    _runs[run_id] = run.model_dump()
    
    # Start background simulation
    background_tasks.add_task(_run_simulation_background, run_id, scenario, request.controller_type, max_steps, random_seed)
    
    return run


@router.get("/simulations", response_model=List[SimulationRun])
async def get_simulations():
    """Get all simulation runs."""
    return list(_runs.values())


@router.get("/simulations/{run_id}", response_model=SimulationRun)
async def get_simulation(run_id: str):
    """Get a specific simulation run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _runs[run_id]


@router.get("/simulations/{run_id}/trajectories")
async def get_trajectories(run_id: str):
    """Get trajectories for a simulation run."""
    if run_id not in _couplers:
        # Try to load from exported results
        import os
        output_dir = f"results/{run_id}"
        trajectories_file = os.path.join(output_dir, "trajectories.jsonl")
        if os.path.exists(trajectories_file):
            trajectories = []
            with open(trajectories_file) as f:
                for line in f:
                    if line.strip():
                        trajectories.append(json.loads(line))
            return trajectories
        raise HTTPException(status_code=404, detail=f"Trajectories for run {run_id} not found")
    
    coupler = _couplers[run_id]
    trajectories = []
    for h in coupler.co_sim_history:
        traj = {
            "timestep": h.timestep,
            "timestamp": f"2023-01-01T{h.timestep * 0.25:02.0f}:00:00",  # Convert 15-min steps to timestamps
            "observations": _convert_numpy(h.citylearn_result.observations),
            "applied_actions": [_convert_numpy(a.model_dump()) for a in h.citylearn_result.applied_actions.actions],
            "costs": _convert_numpy(h.citylearn_result.costs),
            "grid_diagnostics": _convert_numpy(h.citylearn_result.grid_diagnostics),
        }
        trajectories.append(traj)
    
    return _convert_numpy(trajectories)


@router.get("/simulations/{run_id}/grid")
async def get_grid_diagnostics(run_id: str):
    """Get grid diagnostics for a simulation run."""
    if run_id not in _couplers:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    coupler = _couplers[run_id]
    diagnostics = []
    for h in coupler.co_sim_history:
        for d in h.grid_diagnostics.diagnostics:
            diagnostics.append({
                "timestep": h.timestep,
                "diagnostic": _convert_numpy(d.model_dump()),
            })
    return _convert_numpy(diagnostics)


@router.post("/simulations/{run_id}/cancel")
async def cancel_simulation(run_id: str):
    """Cancel a running simulation."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    if _runs[run_id]["status"] != "running":
        raise HTTPException(status_code=400, detail="Can only cancel running simulations")
    
    _runs[run_id]["cancelled"] = True
    return {"message": "Simulation cancellation requested"}


import json  # Add import at top if not present