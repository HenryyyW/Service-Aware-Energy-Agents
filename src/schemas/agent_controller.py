"""Agent-Controller interface schemas for the multi-agent code generation workflow.

Defines the contract between agents (Planner, Coder, Executor, Verifier, Reporter)
and the controllers they generate/validate/execute.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class AgentRole(str, Enum):
    """Roles in the multi-agent workflow."""

    PLANNER = "planner"
    CODER = "coder"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    REPORTER = "reporter"


class ControllerLanguage(str, Enum):
    """Supported controller implementation languages."""

    PYTHON = "python"


class ConstraintCheckResult(BaseModel):
    """Result of a constraint check on controller code."""

    constraint_id: str
    constraint_type: str
    passed: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ControllerCode(BaseModel):
    """Generated controller code with metadata."""

    code: str
    language: ControllerLanguage = ControllerLanguage.PYTHON
    entry_point: str = "Controller"
    imports: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)  # pip packages
    hash: Optional[str] = None  # SHA256 of code for caching

    def __post_init__(self):
        if self.hash is None:
            import hashlib

            self.hash = hashlib.sha256(self.code.encode()).hexdigest()[:16]


class ControllerInterface(BaseModel):
    """Required interface methods that a controller must implement."""

    required_methods: List[str] = Field(
        default_factory=lambda: [
            "get_actions",
            "reset",
            "update_grid_diagnostics",
        ]
    )
    optional_methods: List[str] = Field(
        default_factory=lambda: [
            "update_lmp_prices",
        ]
    )
    required_args: Dict[str, str] = Field(
        default_factory=lambda: {
            "get_actions": "(self, observations: Dict[str, Any], timestep: int) -> RequestedActions",
            "reset": "(self) -> None",
            "update_grid_diagnostics": "(self, grid_diagnostics: Dict[str, Any]) -> None",
        }
    )


class AgentTaskInput(BaseModel):
    """Input to an agent for a specific task."""

    task_id: str
    role: AgentRole
    task_spec: "TaskSpec"  # Forward reference
    context: Dict[str, Any] = Field(default_factory=dict)
    previous_outputs: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    timeout_seconds: int = 300


class AgentTaskOutput(BaseModel):
    """Output from an agent after completing a task."""

    task_id: str
    role: AgentRole
    success: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(
        default_factory=dict
    )  # code, diffs, reports, etc.
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now()


class PlannerOutput(BaseModel):
    """Planner agent output: task decomposition and execution plan."""

    task_id: str
    subtasks: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: Dict[str, List[str]] = Field(
        default_factory=dict
    )  # subtask_id -> [dep_ids]
    estimated_complexity: str = "medium"  # low, medium, high
    recommended_approach: str = ""


class CoderOutput(BaseModel):
    """Coder agent output: controller code and diffs."""

    task_id: str
    controller_code: ControllerCode
    diff: Optional[str] = None  # unified diff vs baseline
    constraint_checks: List[ConstraintCheckResult] = Field(default_factory=list)
    validation_passed: bool = False
    baseline_hash: Optional[str] = None


class ExecutorOutput(BaseModel):
    """Executor agent output: simulation run results."""

    task_id: str
    run_id: str
    experiment_result: Optional["ExperimentResult"] = None  # Forward reference
    simulation_logs: str = ""
    error: Optional[str] = None
    success: bool = False


class VerifierOutput(BaseModel):
    """Verifier agent output: repair validation."""

    task_id: str
    baseline_run_id: str
    repaired_run_id: str
    verification_passed: bool
    violation_targets_met: Dict[str, bool] = Field(default_factory=dict)
    improvement_summary: str = ""
    repair_iterations: int = 0


class ReporterOutput(BaseModel):
    """Reporter agent output: final report generation."""

    task_id: str
    report: "FinalReport"  # Forward reference
    markdown: str = ""
    artifacts: List[str] = Field(default_factory=list)


class AgentControllerMessage(BaseModel):
    """Message passed between agents in the workflow."""

    message_id: str
    sender: AgentRole
    recipient: AgentRole
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: Optional[str] = None


# Forward reference resolution
from src.schemas.task import TaskSpec
from src.schemas.report import ExperimentResult, FinalReport

AgentTaskInput.model_rebuild()
AgentTaskOutput.model_rebuild()
PlannerOutput.model_rebuild()
CoderOutput.model_rebuild()
ExecutorOutput.model_rebuild()
VerifierOutput.model_rebuild()
ReporterOutput.model_rebuild()


if __name__ == "__main__":
    # Quick validation

    # Test ControllerCode
    cc = ControllerCode(
        code="class Controller:\n    def get_actions(self, obs, ts):\n        return RequestedActions(actions=[])",
        hash="test",
    )
    print(f"ControllerCode valid: {cc.hash}")

    # Test AgentTaskInput
    from src.schemas.task import TaskSpec

    ts = TaskSpec(
        task_id="test",
        task_type="scenario_construction",
        description="Build a test scenario",
    )
    ati = AgentTaskInput(task_id="test", role=AgentRole.PLANNER, task_spec=ts)
    print(f"AgentTaskInput valid: {ati.task_id}")

    print("All agent_controller schemas validated successfully!")
