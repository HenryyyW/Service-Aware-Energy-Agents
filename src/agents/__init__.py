"""Agents package for code-agent workflow."""
from src.agents.roles import (
    AgentRole, AgentState, Message,
    PlannerOutput, CoderOutput, ExecutorOutput, VerifierOutput, ReporterOutput
)
from src.agents.planner import PlannerAgent
from src.agents.coder import CoderAgent
from src.agents.executor import ExecutorAgent, create_executor_agent
from src.agents.verifier import VerifierAgent
from src.agents.reporter import ReporterAgent
from src.agents.multi_agent_loop import (
    MultiAgentRepairLoop, IterationRecord, MultiAgentRepairResult, run_multi_agent_repair
)
from src.agents.repair_agent import RepairAgent, RepairPatch, RepairContext, create_repair_agent_from_config
from src.agents.sandbox import Sandbox, SandboxResult, validate_controller_in_sandbox
from src.agents.repair_loop import RepairLoop, RepairIteration, RepairLoopResult, run_repair_loop

__all__ = [
    # Roles
    "AgentRole", "AgentState", "Message",
    "PlannerOutput", "CoderOutput", "ExecutorOutput", "VerifierOutput", "ReporterOutput",
    # Individual agents
    "PlannerAgent", "CoderAgent", "ExecutorAgent", "create_executor_agent",
    "VerifierAgent", "ReporterAgent",
    # Multi-agent loop
    "MultiAgentRepairLoop", "IterationRecord", "MultiAgentRepairResult", "run_multi_agent_repair",
    # Legacy single-agent (for backward compatibility)
    "RepairAgent", "RepairPatch", "RepairContext", "create_repair_agent_from_config",
    "Sandbox", "SandboxResult", "validate_controller_in_sandbox",
    "RepairLoop", "RepairIteration", "RepairLoopResult", "run_repair_loop",
]