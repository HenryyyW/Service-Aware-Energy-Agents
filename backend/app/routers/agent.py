"""Agent task management API endpoints."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, timezone
import asyncio

from src.agents.multi_agent_loop import run_multi_agent_repair
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType
from src.schemas.diagnostics import DiagnosticReport
from src.schemas.scenario import ScenarioConfig
from src.agents.backend.config import load_llm_config
from src.agents.backend.registry import create_backend_from_config
from src.simulation import SimulationCoupler

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
    """Background task to run the real multi-agent repair workflow."""
    PROJECT_ROOT = "/home/box/OpenBot/Shared/Service-Aware-Energy-Agents"
    
    try:
        _tasks[task_id]["status"] = "planning"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["execution_log"].append("Starting planning phase...")
        
        # Load scenario
        from src.schemas.scenario import ScenarioConfig
        from src.schemas.report import ExperimentResult
        import yaml
        
        scenario_path = f"{PROJECT_ROOT}/configs/{scenario_id}.yaml" if scenario_id else f"{PROJECT_ROOT}/configs/scenario_a.yaml"
        with open(scenario_path, 'r') as f:
            scenario_dict = yaml.safe_load(f)
        scenario_config = ScenarioConfig(**scenario_dict)
        
        # Load or create experiment result (for failed experiment that needs repair)
        from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType, EnergyMetrics, ServiceMetrics, GridMetrics
        from src.schemas.diagnostics import DiagnosticReport
        
        # Create a failed experiment result that needs repair
        from src.schemas.report import EnergyMetrics, ServiceMetrics, GridMetrics
        energy = EnergyMetrics(
            total_cost=100.0, grid_import_kwh=1000, grid_export_kwh=500,
            peak_demand_kw=50.0, pv_self_consumption_kwh=200.0,
            load_factor=0.5, pv_curtailment_kwh=0.0, battery_throughput_kwh=100.0, carbon_emissions_kg=50.0
        )
        service = ServiceMetrics(
            ev_completion_rate=0.5, comfort_violation_degree_hours=10.0,
            flexible_load_completion_rate=0.5, demand_response_delivery_rate=0.5
        )
        grid = GridMetrics(
            voltage_violations_count=5, line_loading_violations=3,
            transformer_loading_violations=1, power_flow_convergence_rate=0.95,
            max_voltage_pu=1.08, min_voltage_pu=0.92, max_line_loading_pct=110.0, max_transformer_loading_pct=105.0
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
            agent={}, kpis=[], per_member=[], diagnostic_reports=[],
        )
        
        # Create diagnostic reports from the failed experiment
        diagnostic_reports = []
        
        # Create diagnostic reports for the failed experiment
        from src.schemas.diagnostics import DiagnosticReport, Diagnostic, DiagnosticCategory, Severity
        diagnostic_reports = [
            DiagnosticReport(
                scenario_id=scenario_id or "scenario_e",
                run_id=f"repair_{uuid4().hex[:8]}",
                timestep=100,
                diagnostics=[
                    Diagnostic(diagnostic_id="diag_1", category=DiagnosticCategory.VOLTAGE, severity=Severity.VIOLATION, timestep=100,
                              message="Voltage violations detected at multiple buses",
                              values={"max_voltage_pu": 1.08, "min_voltage_pu": 0.92},
                              limits={"min": 0.95, "max": 1.05},
                              bus_indices=[1, 3, 5]),
                    Diagnostic(diagnostic_id="diag_2", category=DiagnosticCategory.LINE_LOADING, severity=Severity.VIOLATION, timestep=100,
                              message="Line loading exceeds thermal limits",
                              values={"line_loading_pct": 110.0},
                              limits={"max": 100.0},
                              bus_indices=[2, 4]),
                ]
            )
        ]
        
        # Get baseline controller code
        with open(f"{PROJECT_ROOT}/src/controllers/__init__.py", 'r') as f:
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
            project_root=PROJECT_ROOT
        )
        
        # Update task with results
        _tasks[task_id]["status"] = "completed" if result.success else "failed"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["plan"] = result.iterations[0].planner_output.model_dump() if result.iterations else {}
        _tasks[task_id]["code"] = result.iterations[0].coder_output.patched_code if result.iterations else ""
        _tasks[task_id]["verification"] = result.iterations[0].verifier_output.model_dump() if result.iterations else {}
        _tasks[task_id]["repairs"] = [iter.coder_output.code_changes for iter in result.iterations]
        _tasks[task_id]["report"] = result.final_report
        _tasks[task_id]["execution_log"].append(f"Repair {'succeeded' if result.success else 'failed'} after {result.total_iterations} iterations")
        _tasks[task_id]["execution_log"].append(f"Total time: {result.total_time:.1f}s")
        
    except Exception as e:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["execution_log"].append(f"Error: {str(e)}")
        import traceback
        _tasks[task_id]["execution_log"].append(traceback.format_exc())


@router.post("/agent/tasks", response_model=AgentTask, status_code=201)
async def create_agent_task(request: AgentTaskCreate, background_tasks: BackgroundTasks):
    """Create a new agent task."""
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