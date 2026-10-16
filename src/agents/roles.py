"""Role definitions for the code-agent workflow."""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass, field
import time


class AgentRole(str, Enum):
    PLANNER = "planner"
    CODER = "coder"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    REPORTER = "reporter"


class Message(BaseModel):
    """Inter-agent message."""
    role: AgentRole
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


@dataclass
class AgentState:
    """Shared state between agents."""
    experiment_result: Any = None
    diagnostic_reports: List[Any] = field(default_factory=list)
    controller_code: str = ""
    controller_file: str = ""
    scenario_config: Dict[str, Any] = field(default_factory=dict)
    scenario_config_path: str = ""
    repair_plan: Optional[Dict[str, Any]] = None
    code_changes: List[Dict[str, Any]] = field(default_factory=list)
    patched_code: str = ""
    sandbox_result: Optional[Any] = None
    verification_result: Optional[Dict[str, Any]] = None
    final_report: Optional[Dict[str, Any]] = None
    iteration: int = 0
    max_iterations: int = 3
    messages: List[Message] = field(default_factory=list)
    
    def add_message(self, role: AgentRole, content: str, metadata: Dict[str, Any] = None):
        self.messages.append(Message(role=role, content=content, metadata=metadata or {}))


class PlannerOutput(BaseModel):
    """Output from the Planner agent."""
    primary_issue: str
    secondary_issues: List[str] = Field(default_factory=list)
    root_cause_analysis: str
    repair_strategy: str
    target_functions: List[str] = Field(default_factory=list)
    success_criteria: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: str = ""


class CoderOutput(BaseModel):
    """Output from the Coder agent."""
    code_changes: List[Dict[str, Any]] = Field(default_factory=list)
    patched_code: str = ""
    diff: str = ""
    implementation_notes: str = ""


class ExecutorOutput(BaseModel):
    """Output from the Executor agent."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    execution_time: float = 0.0
    test_results: Dict[str, Any] = Field(default_factory=dict)


class VerifierOutput(BaseModel):
    """Output from the Verifier agent."""
    violations_resolved: bool
    remaining_violations: List[Dict[str, Any]] = Field(default_factory=list)
    new_violations: List[Dict[str, Any]] = Field(default_factory=list)
    metrics_comparison: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    recommendation: str = ""  # "accept", "retry", "escalate"


class ReporterOutput(BaseModel):
    """Output from the Reporter agent."""
    summary: str
    detailed_report: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)