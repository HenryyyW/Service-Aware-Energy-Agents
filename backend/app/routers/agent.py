"""Agent task management API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Header
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime
import asyncio
import json
import os
import hashlib
from pathlib import Path

router = APIRouter()

# In-memory storage for agent tasks (fallback when Redis not available)
_tasks: Dict[str, dict] = {}

# Idempotency key storage (in-memory, use Redis in production)
_idempotency_keys: Dict[str, str] = {}

# Task retry tracking
_task_retries: Dict[str, int] = {}
MAX_RETRIES = 3
TASK_TIMEOUT_SECONDS = 30 * 60  # 30 minutes


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


async def _load_experiment_result(run_id: str) -> Optional[Dict[str, Any]]:
    """Load experiment result from disk."""
    # Try to find result files in results/ directory
    results_dir = Path("results")
    if results_dir.exists():
        for run_dir in results_dir.iterdir():
            if run_dir.is_dir() and run_id in run_dir.name:
                result_file = run_dir / "result.json"
                if result_file.exists():
                    with open(result_file) as f:
                        return json.load(f)
    return None


async def _load_scenario_config(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Load scenario config from disk."""
    # Try to find scenario config in data/schemas/
    project_root = Path(__file__).parent.parent.parent.parent.parent
    schema_path = project_root / "data" / "schemas" / scenario_id / "schema.json"
    if schema_path.exists():
        with open(schema_path) as f:
            return json.load(f)
    return None


async def _load_baseline_controller(scenario_id: str) -> Optional[str]:
    """Load baseline controller code for a scenario."""
    # Try to find controller in agents/controllers/ or similar
    project_root = Path(__file__).parent.parent.parent.parent.parent
    controller_paths = [
        project_root / "src" / "controllers" / f"{scenario_id}_controller.py",
        project_root / "agents" / "controllers" / f"{scenario_id}_controller.py",
        project_root / "agents" / "baseline_controller.py",
    ]
    for path in controller_paths:
        if path.exists():
            with open(path) as f:
                return f.read()
    # Return a basic controller template if none found
    return """
class BaselineController:
    def __init__(self, scenario_config):
        self.scenario_config = scenario_config
    
    def get_actions(self, observations, timestep):
        # No-op baseline controller
        from src.schemas.action import RequestedActions
        return RequestedActions(actions=[])
    
    def reset(self):
        pass
"""


async def _run_agent_task(task_id: str, description: str, scenario_id: Optional[str], run_id: Optional[str]):
    """Background task to run agent workflow using real multi-agent repair loop."""
    from src.agents import run_multi_agent_repair
    from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType
    from src.schemas.diagnostics import DiagnosticReport
    from src.schemas.scenario import ScenarioConfig
    import time
    
    # Check timeout
    task_data = _tasks.get(task_id, {})
    started_at = task_data.get("started_at")
    timeout_seconds = task_data.get("timeout_seconds", 30 * 60)
    
    if started_at:
        from datetime import datetime
        start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        elapsed = (datetime.utcnow() - start_time.replace(tzinfo=None)).total_seconds()
        if elapsed > timeout_seconds:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
            _tasks[task_id]["execution_log"].append(f"Task timed out after {timeout_seconds}s")
            TASK_DURATION.labels(status="timeout").observe(timeout_seconds)
            TASKS_TOTAL.labels(status="timeout").inc()
            return
    
    try:
        _tasks[task_id]["status"] = "planning"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append("Starting multi-agent repair workflow...")
        
        # Load required data
        _tasks[task_id]["execution_log"].append("Loading experiment result and scenario config...")
        
        experiment_result_dict = None
        if run_id:
            experiment_result_dict = await _load_experiment_result(run_id)
        
        scenario_config_dict = None
        if scenario_id:
            scenario_config_dict = await _load_scenario_config(scenario_id)
        
        baseline_controller = await _load_baseline_controller(scenario_id or "default")
        
        # Build experiment result if not loaded
        if experiment_result_dict is None:
            _tasks[task_id]["execution_log"].append("No existing experiment result found, creating minimal result from scenario...")
            # Create a minimal experiment result for the repair loop
            scenario_config = {}
            if scenario_config_dict:
                # Convert ScenarioConfig to dict if needed
                if hasattr(scenario_config_dict, 'model_dump'):
                    scenario_config = scenario_config_dict.model_dump()
                else:
                    scenario_config = scenario_config_dict
            
            experiment_result = ExperimentResult(
                run_id=f"agent_task_{task_id}",
                scenario_id=scenario_id or "unknown",
                controller_type=ControllerType.LLM_AGENT,
                controller_config={},
                status=ExperimentStatus.COMPLETED,
                random_seed=42,
                controller_code=baseline_controller,
            )
        else:
            # Convert dict to ExperimentResult
            experiment_result = ExperimentResult(**experiment_result_dict)
        
        # Load diagnostic reports
        diagnostic_reports = []
        if experiment_result_dict and experiment_result_dict.get("diagnostic_reports"):
            for diag_dict in experiment_result_dict["diagnostic_reports"]:
                diagnostic_reports.append(DiagnosticReport(**diag_dict))
        else:
            # Create minimal diagnostic reports for the repair loop
            _tasks[task_id]["execution_log"].append("Creating minimal diagnostic reports for repair loop...")
            # We need at least some diagnostic reports for the repair loop to work
            if scenario_id:
                diagnostic_reports.append(DiagnosticReport(
                    scenario_id=scenario_id,
                    run_id=f"agent_task_{task_id}",
                    timestep=0,
                    diagnostics=[],
                    power_flow_converged=True,
                    total_violations=0,
                    critical_violations=0,
                ))
        
        # Load scenario config
        scenario_config = {}
        if scenario_config_dict:
            if hasattr(scenario_config_dict, 'model_dump'):
                scenario_config = scenario_config_dict.model_dump()
            else:
                scenario_config = scenario_config_dict
        
        # Find controller file path
        controller_file = f"agents/controllers/{scenario_id or 'default'}_controller.py"
        
        _tasks[task_id]["execution_log"].append("Starting multi-agent repair loop...")
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # Run the real multi-agent repair loop
        start_time = time.time()
        try:
            result = run_multi_agent_repair(
                experiment_result=experiment_result,
                diagnostic_reports=diagnostic_reports,
                controller_code=baseline_controller,
                controller_file=controller_file,
                scenario_config=scenario_config,
                scenario_config_path=f"data/schemas/{scenario_id}/schema.json" if scenario_id else "data/schemas/default/schema.json",
                max_iterations=3,
                project_root=str(Path(__file__).parent.parent.parent.parent.parent)
            )
        except Exception as e:
            _tasks[task_id]["execution_log"].append(f"Repair loop error: {str(e)}")
            raise
        
        # Populate task with results
        _tasks[task_id]["plan"] = {
            "iterations": len(result.iterations),
            "total_time": result.total_time,
            "success": result.success,
        }
        
        _tasks[task_id]["code"] = result.final_report.get("final_controller_code", "") if result.final_report else ""
        
        _tasks[task_id]["verification"] = {
            "passed": result.success,
            "iterations": result.total_iterations,
            "total_time": result.total_time,
            "iterations": [
                {
                    "iteration": iter_rec.iteration,
                    "primary_issue": iter_rec.planner_output.primary_issue,
                    "strategy": iter_rec.planner_output.repair_strategy,
                    "executor_success": iter_rec.executor_output.success,
                    "violations_resolved": iter_rec.verifier_output.violations_resolved,
                    "confidence": iter_rec.verifier_output.confidence,
                    "duration_sec": iter_rec.duration
                }
                for iter_rec in result.iterations
            ]
        }
        
        _tasks[task_id]["repairs"] = [
            {
                "iteration": iter_rec.iteration,
                "changes": len(iter_rec.coder_output.code_changes),
                "diff": iter_rec.coder_output.diff,
                "executor_success": iter_rec.executor_output.success,
                "verifier_recommendation": iter_rec.verifier_output.recommendation,
            }
            for iter_rec in result.iterations
        ]
        
        _tasks[task_id]["report"] = result.final_report.get("markdown", "") if result.final_report else "Repair completed."
        
        _tasks[task_id]["execution_log"].append(f"Multi-agent repair loop completed in {time.time() - start_time:.1f}s")
        
        # Record metrics
        duration = time.time() - start_time
        TASK_DURATION.labels(status=_tasks[task_id]["status"]).observe(duration)
        TASKS_TOTAL.labels(status=_tasks[task_id]["status"]).inc()
        
        if result.success:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["execution_log"].append("Task completed successfully")
        else:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["execution_log"].append("Repair loop did not resolve all violations")
        
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        _tasks[task_id]["execution_log"].append(f"Error: {str(e)}")
        import traceback
        _tasks[task_id]["execution_log"].append(traceback.format_exc())
        TASK_DURATION.labels(status="error").observe(time.time() - start_time)
        TASKS_TOTAL.labels(status="error").inc()


@router.post("/agent/tasks", response_model=AgentTask, status_code=201)
async def create_agent_task(
    request: AgentTaskCreate, 
    background_tasks: BackgroundTasks,
    request_obj: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """Create a new agent task with idempotency support."""
    # Check idempotency key
    if idempotency_key:
        if idempotency_key in _idempotency_keys:
            existing_task_id = _idempotency_keys[idempotency_key]
            if existing_task_id in _tasks:
                existing_task = _tasks[existing_task_id]
                existing_task["updated_at"] = datetime.utcnow().isoformat()
                return existing_task
        else:
            # Store idempotency key (will be linked after task creation)
            pass
    
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
    
    # Store idempotency key mapping
    if idempotency_key:
        _idempotency_keys[idempotency_key] = task_id
    
    # Initialize retry counter
    _task_retries[task_id] = 0
    
    # Add timeout tracking
    task_data = _tasks[task_id]
    task_data["started_at"] = datetime.utcnow().isoformat()
    task_data["timeout_seconds"] = 30 * 60  # 30 minutes
    
    # Start background agent workflow
    from app.main import get_task_queue, get_redis_client
    
    queue = get_task_queue()
    if queue:
        # Use RQ for production queue
        from rq import Queue
        queue.enqueue(
            _run_agent_task, 
            task_id, 
            request.description, 
            request.scenario_id, 
            request.run_id,
            job_timeout=30 * 60,  # 30 minutes
            job_id=task_id
        )
    else:
        # Fallback to in-memory background tasks
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()
        bg.add_task(_run_agent_task, task_id, request.description, request.scenario_id, request.run_id)
        # Note: In production, use RQ worker instead
    
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
    """Retry a failed agent task with retry tracking."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = _tasks[task_id]
    if task["status"] != "failed":
        raise HTTPException(status_code=400, detail="Can only retry failed tasks")
    
    # Check retry limit
    retry_count = _task_retries.get(task_id, 0)
    if retry_count >= 3:
        raise HTTPException(status_code=400, detail="Max retries (3) exceeded")
    
    # Increment retry counter
    _task_retries[task_id] = retry_count + 1
    TASK_RETRIES.labels(task_id=task_id).inc()
    
    # Reset task for retry
    now = datetime.utcnow().isoformat()
    task["status"] = "planning"
    task["updated_at"] = now
    task["execution_log"] = [f"Retry {retry_count + 1} initiated at {now}"]
    task["plan"] = None
    task["code"] = None
    task["verification"] = None
    task["repairs"] = []
    task["report"] = None
    task["started_at"] = datetime.utcnow().isoformat()
    
    # Start background agent workflow
    from app.main import get_task_queue
    
    queue = get_task_queue()
    if queue:
        queue.enqueue(
            _run_agent_task, 
            task_id, 
            task["description"], 
            task.get("scenario_id"), 
            task.get("run_id"),
            job_timeout=30 * 60,
            job_id=f"{task_id}_retry_{_task_retries[task_id]}"
        )
    else:
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()
        bg.add_task(_run_agent_task, task_id, task["description"], task.get("scenario_id"), task.get("run_id"))
    
    return task