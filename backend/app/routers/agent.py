"""Agent task management API endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Header
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timezone
import time

from app.state import (
    get_task_queue,
    TASK_DURATION,
    TASKS_TOTAL,
    TASK_RETRIES,
)

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
    status: str = (
        "planning"  # planning, coding, executing, verifying, repairing, reporting, completed, failed
    )
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


async def _run_agent_task(
    task_id: str, description: str, scenario_id: Optional[str], run_id: Optional[str]
):
    """Background task to run the real multi-agent repair workflow."""
    PROJECT_ROOT = "/home/box/OpenBot/Shared/Service-Aware-Energy-Agents"

    # Check timeout
    task_data = _tasks.get(task_id, {})
    started_at = task_data.get("started_at")
    timeout_seconds = task_data.get("timeout_seconds", 30 * 60)

    if started_at:
        from datetime import datetime
        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        if elapsed > timeout_seconds:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            _tasks[task_id]["execution_log"].append(
                f"Task timed out after {timeout_seconds}s"
            )
            TASK_DURATION.labels(status="timeout").observe(timeout_seconds)
            TASKS_TOTAL.labels(status="timeout").inc()
            return

    start_time = time.time()

    try:
        _tasks[task_id]["status"] = "planning"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["execution_log"].append(
            "Starting multi-agent repair workflow..."
        )

        # Load scenario
        from src.schemas.scenario import ScenarioConfig
        from src.schemas.report import ExperimentResult
        import yaml

        scenario_path = (
            f"{PROJECT_ROOT}/configs/{scenario_id}.yaml"
            if scenario_id
            else f"{PROJECT_ROOT}/configs/scenario_a.yaml"
        )
        with open(scenario_path, "r") as f:
            scenario_dict = yaml.safe_load(f)
        scenario_config = ScenarioConfig(**scenario_dict)

        # Load or create experiment result (for failed experiment that needs repair)
        from src.schemas.report import (
            ExperimentStatus,
            EnergyMetrics,
            ServiceMetrics,
            GridMetrics,
        )
        from src.schemas.diagnostics import DiagnosticReport

        # Create a failed experiment result that needs repair

        energy = EnergyMetrics(
            total_cost=100.0,
            grid_import_kwh=1000,
            grid_export_kwh=500,
            peak_demand_kw=50.0,
            pv_self_consumption_kwh=200.0,
            load_factor=0.5,
            pv_curtailment_kwh=0.0,
            battery_throughput_kwh=100.0,
            carbon_emissions_kg=50.0,
        )
        service = ServiceMetrics(
            ev_completion_rate=0.5,
            comfort_violation_degree_hours=10.0,
            flexible_load_completion_rate=0.5,
            demand_response_delivery_rate=0.5,
        )
        grid = GridMetrics(
            voltage_violations_count=5,
            line_loading_violations=3,
            transformer_loading_violations=1,
            power_flow_convergence_rate=0.95,
            max_voltage_pu=1.08,
            min_voltage_pu=0.92,
            max_line_loading_pct=110.0,
            max_transformer_loading_pct=105.0,
        )

        experiment_result = ExperimentResult(
            run_id=f"repair_{uuid4().hex[:8]}",
            scenario_id="scenario_e",
            controller_type="rule_based",
            controller_config={},
            status=ExperimentStatus.FAILED,
            random_seed=42,
            energy=energy,
            service=service,
            grid=grid,
            agent={},
            kpis=[],
            per_member=[],
            diagnostic_reports=[],
        )

        # Create diagnostic reports from the failed experiment
        diagnostic_reports = []

        # Create diagnostic reports for the failed experiment
        from src.schemas.diagnostics import (
            Diagnostic,
            DiagnosticCategory,
            Severity,
        )

        diagnostic_reports = [
            DiagnosticReport(
                scenario_id=scenario_id or "scenario_e",
                run_id=f"repair_{uuid4().hex[:8]}",
                timestep=100,
                diagnostics=[
                    Diagnostic(
                        diagnostic_id="diag_1",
                        category=DiagnosticCategory.VOLTAGE,
                        severity=Severity.VIOLATION,
                        timestep=100,
                        message="Voltage violations detected at multiple buses",
                        values={"max_voltage_pu": 1.08, "min_voltage_pu": 0.92},
                        limits={"min": 0.95, "max": 1.05},
                        bus_indices=[1, 3, 5],
                    ),
                    Diagnostic(
                        diagnostic_id="diag_2",
                        category=DiagnosticCategory.LINE_LOADING,
                        severity=Severity.VIOLATION,
                        timestep=100,
                        message="Line loading exceeds thermal limits",
                        values={"line_loading_pct": 110.0},
                        limits={"max": 100.0},
                        bus_indices=[2, 4],
                    ),
                ],
            )
        ]

        # Get baseline controller code
        with open(f"{PROJECT_ROOT}/src/controllers/__init__.py", "r") as f:
            baseline_controller_code = f.read()

        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["execution_log"].append("Running multi-agent repair loop...")

        # Run the actual multi-agent repair loop
        from src.agents.multi_agent_loop import run_multi_agent_repair

        result = run_multi_agent_repair(
            experiment_result=experiment_result,
            diagnostic_reports=diagnostic_reports,
            controller_code=baseline_controller_code,
            controller_file="src/controllers/__init__.py",
            scenario_config=scenario_config.model_dump(),
            scenario_config_path=scenario_path,
            max_iterations=3,
            project_root=PROJECT_ROOT,
        )

        # Update task with results
        _tasks[task_id]["status"] = "completed" if result.success else "failed"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["plan"] = (
            result.iterations[0].planner_output.model_dump()
            if result.iterations
            else {}
        )
        _tasks[task_id]["code"] = (
            result.iterations[0].coder_output.patched_code if result.iterations else ""
        )
        _tasks[task_id]["verification"] = (
            result.iterations[0].verifier_output.model_dump()
            if result.iterations
            else {}
        )
        _tasks[task_id]["repairs"] = [
            iter.coder_output.code_changes for iter in result.iterations
        ]
        _tasks[task_id]["report"] = result.final_report
        _tasks[task_id]["execution_log"].append(
            f"Repair {'succeeded' if result.success else 'failed'} after {result.total_iterations} iterations"
        )
        _tasks[task_id]["execution_log"].append(f"Total time: {result.total_time:.1f}s")

        # Record metrics
        duration = time.time() - start_time
        TASK_DURATION.labels(status=_tasks[task_id]["status"]).observe(duration)
        TASKS_TOTAL.labels(status=_tasks[task_id]["status"]).inc()

        if result.success:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["execution_log"].append("Task completed successfully")
        else:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["execution_log"].append(
                "Repair loop did not resolve all violations"
            )

        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
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
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Create a new agent task with idempotency support."""
    # Check idempotency key
    if idempotency_key:
        if idempotency_key in _idempotency_keys:
            existing_task_id = _idempotency_keys[idempotency_key]
            if existing_task_id in _tasks:
                existing_task = _tasks[existing_task_id]
                existing_task["updated_at"] = datetime.now(timezone.utc).isoformat()
                return existing_task
        else:
            # Store idempotency key (will be linked after task creation)
            pass

    task_id = f"task_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

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
    task_data["started_at"] = datetime.now(timezone.utc).isoformat()
    task_data["timeout_seconds"] = 30 * 60  # 30 minutes

    # Start background agent workflow
    queue = get_task_queue()
    if queue:
        # Use RQ for production queue
        queue.enqueue(
            _run_agent_task,
            task_id,
            request.description,
            request.scenario_id,
            request.run_id,
            job_timeout=30 * 60,  # 30 minutes
            job_id=task_id,
        )
    else:
        # Fallback to in-memory background tasks
        background_tasks.add_task(
            _run_agent_task,
            task_id,
            request.description,
            request.scenario_id,
            request.run_id,
        )

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
    if retry_count >= MAX_RETRIES:
        raise HTTPException(
            status_code=400, detail=f"Max retries ({MAX_RETRIES}) exceeded"
        )

    # Increment retry counter
    _task_retries[task_id] = retry_count + 1
    TASK_RETRIES.labels(task_id=task_id).inc()

    # Reset task for retry
    now = datetime.now(timezone.utc).isoformat()
    task["status"] = "planning"
    task["updated_at"] = now
    task["execution_log"] = [f"Retry {retry_count + 1} initiated at {now}"]
    task["plan"] = None
    task["code"] = None
    task["verification"] = None
    task["repairs"] = []
    task["report"] = None
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    # Start background agent workflow
    queue = get_task_queue()
    if queue:
        queue.enqueue(
            _run_agent_task,
            task_id,
            task["description"],
            task.get("scenario_id"),
            task.get("run_id"),
            job_timeout=30 * 60,
            job_id=f"{task_id}_retry_{_task_retries[task_id]}",
        )
    else:
        background_tasks.add_task(
            _run_agent_task,
            task_id,
            task["description"],
            task.get("scenario_id"),
            task.get("run_id"),
        )

    return task
