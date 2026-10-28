"""Agent task management API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime
import asyncio

router = APIRouter()

# In-memory storage for agent tasks
_tasks: Dict[str, dict] = {}


class AgentTaskCreate(BaseModel):
    description: str
    scenario_id: Optional[str] = None
    run_id: Optional[str] = None


class AgentTask(BaseModel):
    task_id: str
    description: str
    status: str = "planning"  # planning, coding, executing, verifying, repairing, reporting, completed, failed
    created_at: str
    updated_at: str
    scenario_id: Optional[str] = None
    run_id: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    code: Optional[str] = None
    execution_log: List[str] = []
    verification: Optional[Dict[str, Any]] = None
    repairs: List[Dict[str, Any]] = []
    report: Optional[str] = None


async def _run_agent_task(task_id: str, description: str, scenario_id: Optional[str], run_id: Optional[str]):
    """Background task to run agent workflow."""
    try:
        _tasks[task_id]["status"] = "planning"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Starting planning phase...")
        
        # Simulate planning
        await asyncio.sleep(1)
        _tasks[task_id]["plan"] = {
            "assets": ["battery", "ev", "pv"],
            "constraints": ["voltage_limits", "line_loading", "transformer_loading"],
            "kpis": ["total_cost", "carbon_emissions", "ev_completion_rate"],
            "simulations_needed": 3,
            "estimated_duration_seconds": 60,
        }
        _tasks[task_id]["execution_log"].append("Planning complete")
        
        _tasks[task_id]["status"] = "coding"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Generating controller code...")
        
        # Simulate coding
        await asyncio.sleep(2)
        _tasks[task_id]["code"] = f"""
# Generated controller for: {description}
class GeneratedController:
    def get_actions(self, observations, timestep):
        actions = []
        # TODO: Implement control logic based on {description}
        return actions
"""
        _tasks[task_id]["execution_log"].append("Code generation complete")
        
        _tasks[task_id]["status"] = "executing"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Running simulation with generated controller...")
        
        # Simulate execution
        await asyncio.sleep(3)
        _tasks[task_id]["execution_log"].append("Simulation execution complete")
        
        _tasks[task_id]["status"] = "verifying"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Verifying results against constraints...")
        
        # Simulate verification
        await asyncio.sleep(1)
        _tasks[task_id]["verification"] = {
            "passed": True,
            "diagnostics": {
                "physical": ["Power flow converged at all timesteps"],
                "electrical": ["Voltage within limits [0.95, 1.05] pu", "Line loading < 100%"],
                "service": ["EV departure SOC targets met", "Flexible loads completed"],
                "reporting": ["All metrics computed"],
            },
            "violations": [],
        }
        _tasks[task_id]["execution_log"].append("Verification passed")
        
        _tasks[task_id]["status"] = "reporting"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Generating report...")
        
        # Simulate report generation
        await asyncio.sleep(1)
        _tasks[task_id]["report"] = f"""
# Agent Task Report

**Task ID:** {task_id}
**Description:** {description}
**Scenario:** {scenario_id or 'N/A'}
**Run:** {run_id or 'N/A'}

## Plan
- Assets: Battery, EV, PV
- Constraints: Voltage limits, Line loading, Transformer loading
- KPIs: Total cost, Carbon emissions, EV completion rate

## Verification Results
✅ Power flow converged at all timesteps
✅ Voltage within limits [0.95, 1.05] pu
✅ Line loading < 100%
✅ EV departure SOC targets met
✅ Flexible loads completed

## Summary
The generated controller successfully operates the renewable energy community
within all physical and service constraints.
"""
        _tasks[task_id]["execution_log"].append("Report generated")
        
        _tasks[task_id]["status"] = "completed"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Task completed successfully")
        
    except Exception as e:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append(f"Error: {str(e)}")


@router.post("/agent/tasks", response_model=AgentTask, status_code=201)
async def create_agent_task(request: AgentTaskCreate, background_tasks: BackgroundTasks):
    """Create a new agent task."""
    task_id = f"task_{uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()
    
    task = AgentTask(
        task_id=task_id,
        description=request.description,
        scenario_id=request.scenario_id,
        run_id=request.run_id,
        created_at=now,
        updated_at=now,
    )
    
    _tasks[task_id] = task.model_dump()
    
    # Start background agent workflow
    background_tasks.add_task(_run_agent_task, task_id, request.description, request.scenario_id, request.run_id)
    
    return task


@router.get("/agent/tasks", response_model=List[AgentTask])
async def get_agent_tasks():
    """Get all agent tasks."""
    return list(_tasks.values())


@router.get("/agent/tasks/{task_id}", response_model=AgentTask)
async def get_agent_task(task_id: str):
    """Get a specific agent task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return _tasks[task_id]


@router.delete("/agent/tasks/{task_id}", status_code=204)
async def delete_agent_task(task_id: str):
    """Delete an agent task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    del _tasks[task_id]


@router.post("/agent/tasks/{task_id}/retry")
async def retry_agent_task(task_id: str, background_tasks: BackgroundTasks):
    """Retry a failed agent task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = _tasks[task_id]
    if task["status"] != "failed":
        raise HTTPException(status_code=400, detail="Can only retry failed tasks")
    
    # Reset task for retry
    now = datetime.utcnow().isoformat()
    task["status"] = "planning"
    task["updated_at"] = now
    task["execution_log"] = [f"Retry initiated at {now}"]
    task["plan"] = None
    task["code"] = None
    task["verification"] = None
    task["repairs"] = []
    task["report"] = None
    
    background_tasks.add_task(_run_agent_task, task_id, task["description"], task.get("scenario_id"), task.get("run_id"))
    
    return task