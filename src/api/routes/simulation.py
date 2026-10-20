"""Simulation control routes."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from src.simulation.coupling import SimulationCoupler
from src.schemas.action import Action, ActionType

router = APIRouter()

# Get coupler from scenarios module
from src.api.routes.scenarios import _couplers


class StepRequest(BaseModel):
    """Request for simulation step."""
    actions: List[Dict[str, Any]]
    timestep: Optional[int] = None


@router.get("/{scenario_id}/status")
async def get_simulation_status(scenario_id: str) -> Dict[str, Any]:
    """Get simulation status."""
    if scenario_id not in _couplers:
        raise HTTPException(status_code=404, detail="Scenario not initialized")
    
    coupler = _couplers[scenario_id]
    return {
        "scenario_id": scenario_id,
        "current_timestep": coupler.current_timestep,
        "total_timesteps": len(coupler.co_sim_history),
        "energy_sharing_enabled": coupler.energy_sharing_enabled,
    }


@router.post("/{scenario_id}/reset")
async def reset_simulation(scenario_id: str, random_seed: Optional[int] = None) -> Dict[str, Any]:
    """Reset simulation to initial state."""
    if scenario_id not in _couplers:
        raise HTTPException(status_code=404, detail="Scenario not initialized")
    
    coupler = _couplers[scenario_id]
    observations = coupler.reset(random_seed)
    
    return {
        "status": "reset",
        "scenario_id": scenario_id,
        "observations": observations,
        "timestep": 0,
    }


@router.post("/{scenario_id}/step")
async def step_simulation(scenario_id: str, request: StepRequest) -> Dict[str, Any]:
    """Execute one simulation step."""
    if scenario_id not in _couplers:
        raise HTTPException(status_code=404, detail="Scenario not initialized")
    
    coupler = _couplers[scenario_id]
    
    # Convert actions to RequestedActions format
    from src.schemas.action import RequestedActions, Action
    actions = []
    for a in request.actions:
        actions.append(Action(
            asset_id=a["asset_id"],
            action_type=ActionType(a["action_type"]),
            value_kw=a["value_kw"],
        ))
    
    requested_actions = RequestedActions(actions=actions)
    result = coupler.step(requested_actions)
    
    # Get current observations
    observations = result.citylearn_result.observations
    rewards = result.citylearn_result.rewards
    costs = result.citylearn_result.costs
    grid_diagnostics = result.citylearn_result.grid_diagnostics
    
    return {
        "timestep": result.timestep,
        "observations": observations,
        "rewards": rewards,
        "costs": costs,
        "grid_diagnostics": grid_diagnostics,
        "market_result": result.market_result.model_dump() if result.market_result else None,
        "settlement_snapshot": result.settlement_snapshot,
        "terminated": result.terminated,
        "truncated": result.truncated,
        "violations": result.combined_violations,
    }


@router.post("/{scenario_id}/run")
async def run_simulation(scenario_id: str, max_steps: Optional[int] = None) -> Dict[str, Any]:
    """Run simulation for multiple steps with default actions."""
    if scenario_id not in _couplers:
        raise HTTPException(status_code=404, detail="Scenario not initialized")
    
    coupler = _couplers[scenario_id]
    
    # Get max steps from CityLearn environment
    if max_steps is None:
        max_steps = len(coupler.citylearn.env.data) - 1 if hasattr(coupler.citylearn.env, 'data') else 96
    
    results = []
    for i in range(max_steps):
        # Default: no actions (passive simulation)
        from src.schemas.action import RequestedActions
        requested_actions = RequestedActions(actions=[])
        result = coupler.step(requested_actions)
        
        results.append({
            "timestep": result.timestep,
            "observations": result.citylearn_result.observations,
            "rewards": result.citylearn_result.rewards,
            "costs": result.citylearn_result.costs,
            "grid_diagnostics": result.citylearn_result.grid_diagnostics,
        })
        
        if result.terminated or result.truncated:
            break
    
    # Get final KPIs
    kpis = coupler.get_kpis()
    settlement = coupler.get_settlement_result()
    
    return {
        "scenario_id": scenario_id,
        "steps_completed": len(results),
        "results": results,
        "kpis": kpis,
        "settlement": settlement.model_dump() if settlement else None,
    }


@router.get("/{scenario_id}/kpis")
async def get_kpis(scenario_id: str) -> Dict[str, Any]:
    """Get KPIs for completed simulation."""
    if scenario_id not in _couplers:
        raise HTTPException(status_code=404, detail="Scenario not initialized")
    
    coupler = _couplers[scenario_id]
    return coupler.get_kpis()


@router.get("/{scenario_id}/trajectories")
async def get_trajectories(scenario_id: str) -> List[Dict[str, Any]]:
    """Get full simulation trajectories."""
    if scenario_id not in _couplers:
        raise HTTPException(status_code=404, detail="Scenario not initialized")
    
    coupler = _couplers[scenario_id]
    
    trajectories = []
    for h in coupler.co_sim_history:
        traj = {
            "timestep": h.timestep,
            "requested_actions": [a.model_dump() for a in h.citylearn_result.requested_actions.actions],
            "limited_actions": [a.model_dump() for a in h.citylearn_result.limited_actions.actions],
            "applied_actions": [a.model_dump() for a in h.citylearn_result.applied_actions.actions],
            "observations": h.citylearn_result.observations,
            "rewards": h.citylearn_result.rewards,
            "costs": h.citylearn_result.costs,
            "constraint_violations": h.citylearn_result.constraint_violations,
            "grid_diagnostics": h.citylearn_result.grid_diagnostics,
        }
        trajectories.append(traj)
    
    return trajectories