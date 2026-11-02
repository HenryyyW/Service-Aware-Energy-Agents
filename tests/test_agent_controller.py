"""Tests for agent_controller schemas."""
import pytest
from datetime import datetime

from src.schemas import (
    AgentRole, ControllerLanguage, ControllerCode, ControllerInterface,
    ConstraintCheckResult, AgentTaskInput, AgentTaskOutput,
    PlannerOutput, CoderOutput, ExecutorOutput, VerifierOutput, ReporterOutput,
    AgentControllerMessage,
    TaskSpec, TaskType, ExperimentResult, ExperimentStatus, ControllerType,
)


class TestAgentControllerSchemas:
    """Test agent-controller interface schemas."""

    def test_controller_code(self):
        """Test ControllerCode schema."""
        cc = ControllerCode(
            code="class MyController:\n    def get_actions(self, obs, ts): return []",
            hash="abc123"
        )
        assert cc.hash == "abc123"
        assert cc.language == ControllerLanguage.PYTHON
        assert "get_actions" in cc.code

    def test_controller_interface(self):
        """Test ControllerInterface defaults."""
        ci = ControllerInterface()
        assert "get_actions" in ci.required_methods
        assert "reset" in ci.required_methods
        assert "update_grid_diagnostics" in ci.required_methods
        assert "get_actions" in ci.required_args

    def test_agent_task_input(self):
        """Test AgentTaskInput with proper TaskSpec."""
        ts = TaskSpec(
            task_id="task_1",
            task_type=TaskType.SCENARIO_CONSTRUCTION,
            description="Build scenario"
        )
        ati = AgentTaskInput(
            task_id="task_1",
            role=AgentRole.PLANNER,
            task_spec=ts,
            context={"key": "value"},
            constraints=["constraint1", "constraint2"],
            timeout_seconds=120
        )
        assert ati.task_id == "task_1"
        assert ati.role == AgentRole.PLANNER
        assert ati.task_spec.task_type == TaskType.SCENARIO_CONSTRUCTION

    def test_agent_task_output(self):
        """Test AgentTaskOutput."""
        ato = AgentTaskOutput(
            task_id="task_1",
            role=AgentRole.CODER,
            success=True,
            output={"controller_code": "class C: pass"},
            artifacts={"diff": "+++ new code"},
            errors=[],
            warnings=["warning1"],
            metadata={"tokens": 100}
        )
        assert ato.success is True
        assert ato.role == AgentRole.CODER
        assert "diff" in ato.artifacts

    def test_planner_output(self):
        """Test PlannerOutput."""
        po = PlannerOutput(
            task_id="task_1",
            subtasks=[
                {"id": "sub1", "type": "coder", "description": "Write controller"},
                {"id": "sub2", "type": "executor", "description": "Run simulation"}
            ],
            dependencies={"sub2": ["sub1"]},
            estimated_complexity="high",
            recommended_approach="Write controller first, then test"
        )
        assert len(po.subtasks) == 2
        assert po.dependencies["sub2"] == ["sub1"]

    def test_coder_output(self):
        """Test CoderOutput."""
        cc = ControllerCode(code="class C: pass", hash="hash123")
        co = CoderOutput(
            task_id="task_1",
            controller_code=cc,
            diff="+ new line",
            constraint_checks=[
                ConstraintCheckResult(
                    constraint_id="c1",
                    constraint_type="interface",
                    passed=True,
                    message="All good"
                )
            ],
            validation_passed=True,
            baseline_hash="base123"
        )
        assert co.validation_passed is True
        assert len(co.constraint_checks) == 1

    def test_executor_output(self):
        """Test ExecutorOutput."""
        eo = ExecutorOutput(
            task_id="task_1",
            run_id="run_123",
            success=True,
            simulation_logs="Simulation completed",
            error=None
        )
        assert eo.success is True
        assert eo.run_id == "run_123"

    def test_verifier_output(self):
        """Test VerifierOutput."""
        vo = VerifierOutput(
            task_id="task_1",
            baseline_run_id="base_1",
            repaired_run_id="repair_1",
            verification_passed=True,
            violation_targets_met={"voltage": True, "loading": True},
            improvement_summary="Fixed voltage violations",
            repair_iterations=2
        )
        assert vo.verification_passed is True
        assert vo.repair_iterations == 2

    def test_reporter_output(self):
        """Test ReporterOutput."""
        from src.schemas import FinalReport
        fr = FinalReport(
            report_id="report_1",
            title="Test Report",
            description="A test report"
        )
        ro = ReporterOutput(
            task_id="task_1",
            report=fr,
            markdown="# Report\n\nContent",
            artifacts=["report.json", "report.md"]
        )
        assert ro.report.title == "Test Report"
        assert len(ro.artifacts) == 2

    def test_agent_controller_message(self):
        """Test AgentControllerMessage."""
        acm = AgentControllerMessage(
            message_id="msg_1",
            sender=AgentRole.PLANNER,
            recipient=AgentRole.CODER,
            message_type="task_assignment",
            payload={"task_id": "task_1", "instructions": "Write controller"},
            correlation_id="corr_123"
        )
        assert acm.sender == AgentRole.PLANNER
        assert acm.recipient == AgentRole.CODER
        assert acm.payload["task_id"] == "task_1"

    def test_constraint_check_result(self):
        """Test ConstraintCheckResult."""
        ccr = ConstraintCheckResult(
            constraint_id="c1",
            constraint_type="voltage_limit",
            passed=False,
            message="Voltage exceeds 1.05 pu",
            details={"bus": 5, "voltage_pu": 1.06}
        )
        assert ccr.passed is False
        assert ccr.details["bus"] == 5

    def test_all_agent_roles_covered(self):
        """Test all AgentRole enum values."""
        roles = list(AgentRole)
        assert AgentRole.PLANNER in roles
        assert AgentRole.CODER in roles
        assert AgentRole.EXECUTOR in roles
        assert AgentRole.VERIFIER in roles
        assert AgentRole.REPORTER in roles

    def test_controller_language_enum(self):
        """Test ControllerLanguage enum."""
        assert ControllerLanguage.PYTHON == "python"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])