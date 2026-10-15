"""Tests for agent repair functionality."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.schemas.task import TaskSpec, TaskType, AssetSpec, AssetType, ConstraintSpec, ConstraintType
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.diagnostics import Diagnostic, DiagnosticCategory, Severity, DiagnosticReport
from src.schemas.report import ExperimentResult, ExperimentStatus, ControllerType


class MockRepairAgent:
    """Mock repair agent for testing."""
    
    def __init__(self):
        self.repair_calls = []
    
    def diagnose_and_repair(self, experiment_result: ExperimentResult) -> dict:
        """Mock diagnosis and repair."""
        self.repair_calls.append(experiment_result)
        
        # Return a mock repair patch
        return {
            "patch_id": "patch_001",
            "description": "Reduce EV charging during peak hours",
            "code_changes": [
                {
                    "file": "controllers/rule_based.py",
                    "function": "_control_ev",
                    "change": "Add peak hour reduction factor"
                }
            ],
            "expected_improvement": "Reduce peak demand by 15%"
        }


def test_repair_agent_diagnosis():
    """Test repair agent can diagnose issues."""
    repair_agent = MockRepairAgent()
    
    # Create experiment result with violations
    result = ExperimentResult(
        run_id="test_run",
        scenario_id="test_scenario",
        controller_type=ControllerType.RULE_BASED,
        status=ExperimentStatus.COMPLETED,
        start_time=datetime.now(),
        end_time=datetime.now()
    )
    
    # Add some grid violations
    result.grid.voltage_violations_count = 5
    result.grid.line_loading_violations = 3
    result.service.ev_completion_rate = 0.6  # Below target
    
    repair = repair_agent.diagnose_and_repair(result)
    
    assert "patch_id" in repair
    assert "description" in repair
    assert "code_changes" in repair
    assert len(repair_agent.repair_calls) == 1


def test_repair_agent_no_violations():
    """Test repair agent with no violations."""
    repair_agent = MockRepairAgent()
    
    result = ExperimentResult(
        run_id="test_run",
        scenario_id="test_scenario",
        controller_type=ControllerType.RULE_BASED,
        status=ExperimentStatus.COMPLETED,
        start_time=datetime.now(),
        end_time=datetime.now()
    )
    
    # No violations
    result.grid.voltage_violations_count = 0
    result.grid.line_loading_violations = 0
    result.service.ev_completion_rate = 1.0
    
    repair = repair_agent.diagnose_and_repair(result)
    
    assert repair is not None


def test_diagnostic_report_generation():
    """Test diagnostic report generation."""
    report = DiagnosticReport(
        scenario_id="test",
        run_id="test_run",
        timestep=10
    )
    
    # Add various diagnostics
    report.add_diagnostic(Diagnostic(
        diagnostic_id="v1",
        category=DiagnosticCategory.VOLTAGE,
        severity=Severity.VIOLATION,
        message="Undervoltage at bus 5",
        timestep=10,
        bus_indices=[5],
        values={"voltage_pu": 0.92},
        limits={"min": 0.95}
    ))
    
    report.add_diagnostic(Diagnostic(
        diagnostic_id="l1",
        category=DiagnosticCategory.LINE_LOADING,
        severity=Severity.WARNING,
        message="Line 3 at 95% loading",
        timestep=10,
        values={"loading_pct": 95},
        limits={"max": 100}
    ))
    
    assert report.total_violations == 1
    assert report.critical_violations == 0
    assert len(report.get_by_category(DiagnosticCategory.VOLTAGE)) == 1
    assert len(report.get_by_category(DiagnosticCategory.LINE_LOADING)) == 1


def test_task_spec_creation():
    """Test task specification creation."""
    task = TaskSpec(
        task_id="task_001",
        task_type=TaskType.SCENARIO_CONSTRUCTION,
        description="Create a 5-building REC with PV and batteries",
        assets=[
            AssetSpec(asset_id="b0_pv", asset_type=AssetType.PV, capacity_kw=10.0),
            AssetSpec(asset_id="b0_battery", asset_type=AssetType.BATTERY, capacity_kwh=13.5, capacity_kw=5.0),
        ],
        constraints=[
            ConstraintSpec(
                constraint_id="c1",
                constraint_type=ConstraintType.EV_DEADLINE,
                assets=["b0_ev_0"],
                parameters={"target_soc": 0.8, "departure": "07:00"}
            ),
            ConstraintSpec(
                constraint_id="c2",
                constraint_type=ConstraintType.POWER_IMPORT_LIMIT,
                assets=["community"],
                parameters={"limit_kw": 200}
            )
        ],
        random_seed=42
    )
    
    assert task.task_type == TaskType.SCENARIO_CONSTRUCTION
    assert len(task.assets) == 2
    assert len(task.constraints) == 2
    assert task.random_seed == 42


def test_action_comparison():
    """Test action comparison between requested/limited/applied."""
    from src.schemas.action import ActionComparison
    
    comparison = ActionComparison(
        timestep=5,
        asset_id="b0_battery",
        requested_kw=5.0,
        limited_kw=3.0,
        applied_kw=3.0,
        limit_reason="Grid import limit reached",
        deviation_pct=-40.0
    )
    
    assert comparison.deviation_pct == -40.0
    assert comparison.limited_kw < comparison.requested_kw


if __name__ == "__main__":
    pytest.main([__file__, "-v"])