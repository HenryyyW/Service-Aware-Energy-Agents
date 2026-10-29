"""Simulation management API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime
import asyncio
import numpy as np
import hashlib
import json
import traceback
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

def _compute_config_hash(scenario_id: str, controller_type: str, parameters: Optional[Dict[str, Any]], random_seed: int) -> str:
    """Compute a hash for deduplication."""
    config = {
        "scenario_id": scenario_id,
        "controller_type": controller_type,
        "parameters": parameters or {},
        "random_seed": random_seed,
    }
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]

from src.schemas.scenario import ScenarioConfig
from src.simulation.coupling import SimulationCoupler
from src.schemas.action import RequestedActions
from src.controllers import RuleBasedController, CentralizedController, MultiAgentController
from app.routers.scenarios import _scenarios, _load_scenario_from_disk, SCENARIO_DATA_DIR

router = APIRouter()

# In-memory storage for simulation runs
_runs: Dict[str, dict] = {}
_couplers: Dict[str, SimulationCoupler] = {}
_controllers: Dict[str, Any] = {}
# Config hash -> run_id mapping for deduplication
_config_hash_index: Dict[str, str] = {}


class SimulationCreateRequest(BaseModel):
    scenario_id: str
    controller_type: str = "rule_based"
    parameters: Optional[Dict[str, Any]] = None
    run_name: Optional[str] = None
    run_description: Optional[str] = None


class SimulationRun(BaseModel):
    run_id: str
    scenario_id: str
    controller_type: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    start_time: str
    end_time: Optional[str] = None
    energy_metrics: Optional[Dict[str, Any]] = None
    service_metrics: Optional[Dict[str, Any]] = None
    grid_metrics: Optional[Dict[str, Any]] = None
    random_seed: Optional[int] = None
    max_steps: Optional[int] = None
    current_step: int = 0
    total_steps: Optional[int] = None
    # New fields for Phase 1
    run_name: Optional[str] = None
    run_description: Optional[str] = None
    generation_status: str = "pending"  # pending, computing, ready, failed
    outcome_sentence: Optional[str] = None
    config_hash: Optional[str] = None
    stage: Optional[str] = None
    eta_seconds: Optional[int] = None
    progress: float = 0.0


def _get_controller(controller_type: str, scenario: ScenarioConfig):
    """Get controller instance by type."""
    if controller_type == "centralized":
        return CentralizedController(scenario)
    elif controller_type == "multi_agent":
        return MultiAgentController(scenario)
    else:
        return RuleBasedController(scenario)


async def _run_simulation_background(run_id: str, scenario: ScenarioConfig, controller_type: str, max_steps: int, random_seed: int, start_step: int = 0):
    """Background task to run simulation."""
    try:
        _runs[run_id]["status"] = "running"
        _runs[run_id]["stage"] = "initializing"
        _runs[run_id]["progress"] = 0.0
        
        # Use the same data directory resolution as scenarios router
        data_dir = str(SCENARIO_DATA_DIR.parent)
        # Write debug info to file
        import os
        debug_log = os.path.join(os.environ.get("TEMP", "C:\\tmp"), "debug_sim.log")
        with open(debug_log, "a") as f:
            f.write(f"DEBUG: data_dir = {data_dir}\n")
            f.write(f"DEBUG: SCENARIO_DATA_DIR = {SCENARIO_DATA_DIR}\n")
            f.write(f"DEBUG: scenario = {scenario.scenario_id}\n")
        
        # Disable colorama to prevent stdout flush issues in background task
        import colorama
        colorama.deinit()
        
        # Initialize coupler and controller
        try:
            coupler = SimulationCoupler(scenario, data_dir=data_dir)
            with open(debug_log, "a") as f:
                f.write(f"DEBUG: Coupler created successfully\n")
        except Exception as e:
            with open(debug_log, "a") as f:
                f.write(f"DEBUG: Coupler creation failed: {e}\n")
                f.write(traceback.format_exc())
            raise
        
        controller = _get_controller(controller_type, scenario)
        
        _couplers[run_id] = coupler
        _controllers[run_id] = controller
        
        # Reset with seed
        observations = coupler.reset(random_seed)
        
        # Run simulation loop
        for step in range(start_step, max_steps):
            if _runs[run_id].get("cancelled", False):
                _runs[run_id]["status"] = "cancelled"
                _runs[run_id]["stage"] = "cancelled"
                return
            
            # Update stage and progress
            _runs[run_id]["stage"] = "simulating"
            _runs[run_id]["progress"] = (step + 1) / max_steps
            
            # Estimate ETA
            if step > 0:
                import time
                start = datetime.fromisoformat(_runs[run_id]["start_time"].replace('Z', '+00:00'))
                elapsed = (datetime.utcnow() - start).total_seconds()
                progress = (step + 1) / max_steps
                if progress > 0:
                    _runs[run_id]["eta_seconds"] = int(elapsed / progress - elapsed)
            
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
        
        # Generate outcome sentence
        total_cost = kpis.get("total_cost", 0)
        grid_import = kpis.get("grid_import_kwh", 0)
        pv_self = kpis.get("pv_self_consumption", 0) * 100
        ev_rate = kpis.get("ev_completion_rate", 0) * 100
        convergence = kpis.get("grid_convergence_rate", 0) * 100
        
        outcome_parts = []
        outcome_parts.append(f"Total cost: ${total_cost:,.0f}")
        outcome_parts.append(f"Grid import: {grid_import:,.0f} kWh")
        outcome_parts.append(f"PV self-consumption: {pv_self:.0f}%")
        outcome_parts.append(f"EV completion: {ev_rate:.0f}%")
        outcome_parts.append(f"Power flow convergence: {convergence:.0f}%")
        outcome_sentence = " | ".join(outcome_parts)
        
        _runs[run_id]["status"] = "completed"
        _runs[run_id]["end_time"] = datetime.utcnow().isoformat()
        _runs[run_id]["stage"] = "completed"
        _runs[run_id]["progress"] = 1.0
        _runs[run_id]["generation_status"] = "ready"
        _runs[run_id]["outcome_sentence"] = outcome_sentence
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
            # Extract per-member settlement data for frontend table
            member_settlements = []
            for member_id, member_settlement in settlement.building_settlements.items():
                member_settlements.append({
                    "member_id": member_id,
                    "net_settlement": member_settlement.net_settlement,
                    "total_bought_kwh": member_settlement.total_bought_kwh,
                    "total_sold_kwh": member_settlement.total_sold_kwh,
                    "total_grid_import_kwh": member_settlement.total_grid_import_kwh,
                    "total_grid_export_kwh": member_settlement.total_grid_export_kwh,
                    "baseline_grid_import_kwh": member_settlement.baseline_grid_import_kwh,
                    "baseline_grid_export_kwh": member_settlement.baseline_grid_export_kwh,
                    "total_community_import_kwh": member_settlement.total_community_import_kwh,
                    "total_community_export_kwh": member_settlement.total_community_export_kwh,
                    "peak_grid_import_kw": member_settlement.peak_grid_import_kw,
                    "baseline_peak_grid_import_kw": member_settlement.baseline_peak_grid_import_kw,
                    "demand_charge_rate": member_settlement.demand_charge_rate,
                    "actual_demand_charge": member_settlement.actual_demand_charge,
                    "baseline_demand_charge": member_settlement.baseline_demand_charge,
                    "total_grid_import_cost": member_settlement.total_grid_import_cost,
                    "total_grid_export_revenue": member_settlement.total_grid_export_revenue,
                    "baseline_grid_import_cost": member_settlement.baseline_grid_import_cost,
                    "baseline_grid_export_revenue": member_settlement.baseline_grid_export_revenue,
                    "total_community_import_cost": member_settlement.total_community_import_cost,
                    "total_community_export_revenue": member_settlement.total_community_export_revenue,
                    "savings_vs_baseline": member_settlement.metadata.get("savings_vs_baseline", 0),
                    "self_sufficiency": member_settlement.metadata.get("self_sufficiency", 0),
                })
            
            _runs[run_id]["settlement"] = {
                "total_community_volume_kwh": settlement.total_community_volume_kwh,
                "total_community_revenue": settlement.total_community_revenue,
                "member_settlements": member_settlements,
                "interval_results": [
                    {
                        "interval_idx": r.interval_idx,
                        "start_timestep": r.start_timestep,
                        "end_timestep": r.end_timestep,
                        "building_settlements": r.building_settlements,
                        "avg_clearing_price": r.avg_clearing_price,
                        "total_volume_kwh": r.total_volume_kwh,
                    }
                    for r in settlement.interval_results
                ],
                "metadata": settlement.metadata,
            }
        
    except Exception as e:
        _runs[run_id]["status"] = "failed"
        _runs[run_id]["error"] = str(e)
        _runs[run_id]["end_time"] = datetime.utcnow().isoformat()
        _runs[run_id]["stage"] = "error"
        _runs[run_id]["generation_status"] = "failed"
        _runs[run_id]["outcome_sentence"] = f"Simulation failed: {str(e)}"


@router.post("/simulations", response_model=SimulationRun, status_code=201)
async def create_simulation(request: SimulationCreateRequest, background_tasks: BackgroundTasks):
    """Start a new simulation run (idempotent per config_hash + seed)."""
    # Validate scenario exists
    from app.routers.scenarios import _scenarios, _load_scenario_from_disk
    
    if request.scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(request.scenario_id)
        if scenario:
            _scenarios[request.scenario_id] = scenario
        else:
            raise HTTPException(status_code=404, detail=f"Scenario {request.scenario_id} not found")
    
    scenario = _scenarios[request.scenario_id]
    max_steps = request.parameters.get("max_steps", 672) if request.parameters else 672
    random_seed = request.parameters.get("random_seed", scenario.random_seed) if request.parameters else scenario.random_seed
    
    # Compute config hash for deduplication
    config_hash = _compute_config_hash(request.scenario_id, request.controller_type, request.parameters, random_seed)
    
    # Check for existing run with same config
    if config_hash in _config_hash_index:
        existing_run_id = _config_hash_index[config_hash]
        existing_run = _runs[existing_run_id]
        # Return existing run (idempotent)
        existing_run["config_hash"] = config_hash
        return existing_run
    
    run_id = f"run_{uuid4().hex[:12]}"
    
    run = SimulationRun(
        run_id=run_id,
        scenario_id=request.scenario_id,
        controller_type=request.controller_type,
        start_time=datetime.utcnow().isoformat(),
        random_seed=random_seed,
        max_steps=max_steps,
        run_name=request.run_name,
        run_description=request.run_description,
        config_hash=config_hash,
        generation_status="computing",
    )
    
    _runs[run_id] = run.model_dump()
    _config_hash_index[config_hash] = run_id
    
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


@router.post("/simulations/{run_id}/resume")
async def resume_simulation(run_id: str, background_tasks: BackgroundTasks):
    """Resume a cancelled/failed simulation from last checkpoint."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    if run["status"] not in ["cancelled", "failed", "completed"]:
        raise HTTPException(status_code=400, detail="Can only resume cancelled, failed, or completed simulations")
    
    # Validate scenario exists
    from app.routers.scenarios import _scenarios, _load_scenario_from_disk
    scenario_id = run["scenario_id"]
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    
    scenario = _scenarios[scenario_id]
    max_steps = run.get("max_steps", 672)
    random_seed = run.get("random_seed", scenario.random_seed)
    controller_type = run.get("controller_type", "rule_based")
    current_step = run.get("current_step", 0)
    
    # Reset status for resume
    run["status"] = "running"
    run["cancelled"] = False
    run["end_time"] = None
    run["generation_status"] = "computing"
    
    # Start background simulation from current_step
    background_tasks.add_task(_run_simulation_background, run_id, scenario, controller_type, max_steps, random_seed, current_step)
    
    return run


@router.get("/simulations/{run_id}/status")
async def get_simulation_status(run_id: str):
    """Get detailed simulation status with stage, ETA, progress."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run = _runs[run_id]
    current_step = run.get("current_step", 0)
    total_steps = run.get("total_steps", max_steps if (max_steps := run.get("max_steps")) else 1)
    progress = current_step / max(total_steps, 1) if total_steps else 0
    
    # Estimate ETA based on current progress
    eta_seconds = None
    if run["status"] == "running" and current_step > 0 and progress > 0:
        import time
        start = datetime.fromisoformat(run["start_time"].replace('Z', '+00:00'))
        elapsed = (datetime.utcnow() - start).total_seconds()
        if progress > 0:
            eta_seconds = int(elapsed / progress - elapsed)
    
    stage_map = {
        "pending": "initializing",
        "running": "simulating",
        "completed": "finalizing",
        "failed": "error",
        "cancelled": "cancelled",
    }
    
    return {
        "run_id": run_id,
        "status": run["status"],
        "stage": stage_map.get(run["status"], "unknown"),
        "progress": progress,
        "current_step": current_step,
        "total_steps": total_steps,
        "eta_seconds": eta_seconds,
        "generation_status": run.get("generation_status", "pending"),
        "cancelable": run["status"] == "running",
        "resumable": run["status"] in ["cancelled", "failed"],
    }


import json  # Add import at top if not present