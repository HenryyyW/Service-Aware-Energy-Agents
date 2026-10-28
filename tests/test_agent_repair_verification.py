"""Tests for agent repair with verification harness."""
import pytest
from src.agents.repair_agent import RepairAgent, RepairContext, RepairPatch
from src.agents.repair_loop import RepairLoop
from src.agents.sandbox import Sandbox
from src.evaluation.verification_harness import VerificationHarness, create_harness_for_grid_violation
from src.schemas.report import (
    ExperimentResult, ExperimentStatus, ControllerType, 
    EnergyMetrics, ServiceMetrics, GridMetrics, AgentMetrics, KPIResult
)
from src.schemas.diagnostics import DiagnosticReport, Diagnostic, DiagnosticCategory, Severity
from src.schemas.scenario import ScenarioConfig, BuildingConfig, BatteryConfig, PandapowerConfig
from src.schemas.action import ActionType
import tempfile
import os


def create_mock_experiment_result_with_violations():
    """Create a mock experiment result with grid violations."""
    energy = EnergyMetrics(
        total_cost=100.0,
        grid_import_kwh=500.0,
        grid_export_kwh=100.0,
        peak_demand_kw=50.0,
        pv_self_consumption_kwh=200.0,
        load_factor=0.5,
        battery_throughput_kwh=50.0,
        battery_cycles=10.0
    )
    
    service = ServiceMetrics(
        ev_completion_rate=0.8,  # Below target
        ev_avg_soc_at_departure=0.7,
        ev_worst_soc_at_departure=0.5,
        comfort_violation_degree_hours=5.0,  # Comfort violations
        comfort_violations_count=10,
        flexible_load_completion_rate=0.9,
        load_shedding_total_kw=0.0
    )
    
    grid = GridMetrics(
        power_flow_convergence_rate=1.0,
        voltage_violations_count=10,  # Voltage violations
        voltage_violation_duration_hours=2.0,
        max_voltage_pu=1.08,
        min_voltage_pu=0.92,
        line_loading_violations=5,  # Line loading violations
        max_line_loading_pct=110.0,
        transformer_loading_violations=0,
        max_transformer_loading_pct=80.0,
        community_import_limit_violations=0,
        community_export_limit_violations=0
    )
    
    agent = AgentMetrics(
        total_tokens=1000,
        total_cost=0.01,
        wall_clock_seconds=10.0,
        repair_iterations=0,
        patches_applied=0,
        patches_rejected=0
    )
    
    kpis = [
        KPIResult(kpi_id="voltage_violations", name="Voltage Violations", value=10, unit="count", direction="minimize"),
        KPIResult(kpi_id="line_loading_violations", name="Line Loading Violations", value=5, unit="count", direction="minimize"),
        KPIResult(kpi_id="ev_completion_rate", name="EV Completion Rate", value=0.8, unit="-", direction="maximize"),
        KPIResult(kpi_id="comfort_violations", name="Comfort Violations", value=5.0, unit="degree-hours", direction="minimize"),
    ]
    
    return ExperimentResult(
        run_id="test_run_001",
        scenario_id="scenario_a",
        controller_type=ControllerType.RULE_BASED,
        controller_config={"type": "rule_based"},
        status=ExperimentStatus.COMPLETED,
        random_seed=42,
        energy=energy,
        service=service,
        grid=grid,
        agent=agent,
        kpis=kpis,
        per_member=[],
        diagnostic_reports=[]
    )


def create_mock_diagnostic_reports():
    """Create mock diagnostic reports with violations."""
    report = DiagnosticReport(
        scenario_id="scenario_a",
        run_id="test_run_001",
        timestep=100
    )
    
    # Add voltage violation
    report.add_diagnostic(Diagnostic(
        diagnostic_id="v1",
        category=DiagnosticCategory.VOLTAGE,
        severity=Severity.VIOLATION,
        message="Overvoltage at bus 3",
        timestep=100,
        values={"voltage_pu": 1.08},
        limits={"max_pu": 1.05}
    ))
    
    # Add line loading violation
    report.add_diagnostic(Diagnostic(
        diagnostic_id="l1",
        category=DiagnosticCategory.LINE_LOADING,
        severity=Severity.VIOLATION,
        message="Line 5 overloaded",
        timestep=100,
        values={"loading_pct": 110.0},
        limits={"max_pct": 100.0}
    ))
    
    # Add EV deadline violation
    report.add_diagnostic(Diagnostic(
        diagnostic_id="ev1",
        category=DiagnosticCategory.EV_DEADLINE,
        severity=Severity.WARNING,
        message="EV not charged to target",
        timestep=100,
        values={"target_soc": 0.8, "actual_soc": 0.6},
        limits={"target_soc": 0.8}
    ))
    
    return [report]


def test_repair_agent_diagnose_and_repair():
    """Test that repair agent can diagnose violations and create patches."""
    experiment_result = create_mock_experiment_result_with_violations()
    diagnostic_reports = create_mock_diagnostic_reports()
    
    # Create a simple controller code for testing
    controller_code = '''
from src.controllers import RuleBasedController
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import ScenarioConfig

class TestController(RuleBasedController):
    def get_actions(self, observations, timestep):
        return super().get_actions(observations, timestep)
'''
    
    scenario_config = {
        "scenario_id": "scenario_a",
        "community_import_limit_kw": 100.0,
        "community_export_limit_kw": 50.0
    }
    
    context = RepairContext(
        experiment_result=experiment_result,
        diagnostic_reports=diagnostic_reports,
        baseline_controller_code=controller_code,
        controller_file="src/controllers/test_controller.py",
        scenario_config=scenario_config,
        iteration=0,
        max_iterations=3
    )
    
    agent = RepairAgent()
    patch = agent.diagnose_and_repair(context)
    
    assert patch is not None
    assert patch.patch_id is not None
    assert patch.description is not None
    assert len(patch.code_changes) > 0
    assert patch.confidence > 0


def test_repair_agent_apply_patch_ast():
    """Test that repair agent applies patches using AST."""
    controller_code = '''
from src.controllers import RuleBasedController
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import ScenarioConfig

class TestController(RuleBasedController):
    def _apply_grid_limits(self, actions):
        return actions
    
    def _control_ev(self, ev_id, ev, net_demand, pv_gen, hour_of_day, timestep):
        return None
'''
    
    patch = RepairPatch(
        patch_id="test_patch_001",
        description="Add voltage-aware load reduction",
        code_changes=[
            {
                "file": "src/controllers/test_controller.py",
                "function": "_apply_grid_limits",
                "change": "Add voltage-aware load reduction when voltage exceeds 1.03 pu",
                "type": "modification"
            },
            {
                "file": "src/controllers/test_controller.py",
                "function": "_control_ev",
                "change": "Start charging earlier and use maximum available power when deadline approaches",
                "type": "modification"
            }
        ],
        expected_improvement="Reduce voltage violations by 50-80%",
        confidence=0.7,
        target_files=["src/controllers/test_controller.py"]
    )
    
    agent = RepairAgent()
    modified_code = agent.apply_patch(patch, controller_code)
    
    # Verify the code was modified
    assert modified_code != controller_code
    # Check that voltage-aware logic was added
    assert "voltage_high" in modified_code or "voltage_aware" in modified_code.lower()


def test_sandbox_apply_changes():
    """Test that sandbox can apply changes to code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test controller file
        controller_file = os.path.join(tmpdir, "test_controller.py")
        controller_code = '''
from src.controllers import RuleBasedController
from src.schemas.action import RequestedActions, Action, ActionType
from src.schemas.scenario import ScenarioConfig

class TestController(RuleBasedController):
    def _apply_grid_limits(self, actions):
        return actions
    
    def _control_ev(self, ev_id, ev, net_demand, pv_gen, hour_of_day, timestep):
        return None
'''
        with open(controller_file, 'w') as f:
            f.write(controller_code)
        
        sandbox = Sandbox(project_root=tmpdir)
        sandbox.create_sandbox()
        
        changes = [
            {
                "file": "test_controller.py",
                "function": "_apply_grid_limits",
                "change": "Add voltage-aware load reduction when voltage exceeds 1.03 pu",
                "type": "modification"
            }
        ]
        
        result = sandbox.apply_changes(changes)
        assert result is True
        
        # Verify the file was modified
        with open(os.path.join(sandbox.temp_dir, "test_controller.py"), 'r') as f:
            modified_code = f.read()
        
        assert modified_code != controller_code
        assert "voltage_high" in modified_code or "voltage_aware" in modified_code.lower()
        
        sandbox.cleanup()


def test_verification_harness_integration():
    """Test that verification harness can verify repairs."""
    before_result = create_mock_experiment_result_with_violations()
    
    # Create an "after" result with fewer violations
    after_result = create_mock_experiment_result_with_violations()
    after_result.grid.voltage_violations_count = 2  # Reduced from 10
    after_result.grid.line_loading_violations = 1   # Reduced from 5
    after_result.service.ev_completion_rate = 0.95  # Improved
    after_result.service.comfort_violation_degree_hours = 1.0  # Reduced
    
    harness = create_harness_for_grid_violation('voltage')
    harness.add_target(create_harness_for_grid_violation('line_loading').targets[0])
    harness.add_target(create_harness_for_grid_violation('ev_deadline').targets[0])
    harness.add_target(create_harness_for_grid_violation('comfort').targets[0])
    
    report = harness.verify_repair(before_result, after_result)
    
    assert report is not None
    assert report.run_id_before == before_result.run_id
    assert report.run_id_after == after_result.run_id
    assert len(report.verification_results) == 4
    
    # Check that violations were fixed
    for vr in report.verification_results:
        assert vr.improved or vr.fixed, f"Metric {vr.target.metric_key} not improved"


def test_repair_loop_creates_verification_harness():
    """Test that repair loop creates verification harness from violations."""
    experiment_result = create_mock_experiment_result_with_violations()
    diagnostic_reports = create_mock_diagnostic_reports()
    
    controller_code = '''
from src.controllers import RuleBasedController
class TestController(RuleBasedController):
    def _apply_grid_limits(self, actions):
        return actions
'''
    
    scenario_config = {
        "scenario_id": "scenario_a",
        "community_import_limit_kw": 100.0,
        "community_export_limit_kw": 50.0
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        loop = RepairLoop(project_root=tmpdir)
        
        # Test harness creation
        harness = loop._create_verification_harness(experiment_result, diagnostic_reports)
        
        assert harness is not None
        assert len(harness.targets) >= 3  # voltage, line_loading, ev_deadline, comfort


if __name__ == "__main__":
    test_repair_agent_diagnose_and_repair()
    test_repair_agent_apply_patch_ast()
    test_sandbox_apply_changes()
    test_verification_harness_integration()
    test_repair_loop_creates_verification_harness()
    print("All repair verification tests passed!")