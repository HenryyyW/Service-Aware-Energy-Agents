"""Report schemas for experiment results and final reports."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REPAIR_NEEDED = "repair_needed"
    REPAIR_IN_PROGRESS = "repair_in_progress"


class ControllerType(str, Enum):
    RULE_BASED = "rule_based"
    MPC = "mpc"
    RL_SINGLE = "rl_single"
    RL_MULTI = "rl_multi"
    LLM_AGENT = "llm_agent"
    LLM_AGENT_VERIFIED = "llm_agent_verified"


class KPIResult(BaseModel):
    """Single KPI result."""
    kpi_id: str
    name: str
    value: float
    unit: str
    target: Optional[float] = None
    target_met: Optional[bool] = None
    baseline_value: Optional[float] = None
    improvement_pct: Optional[float] = None


class EnergyMetrics(BaseModel):
    """Energy and cost metrics."""
    total_cost: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    peak_demand_kw: float = 0.0
    load_factor: float = 0.0
    pv_self_consumption_kwh: float = 0.0
    pv_curtailment_kwh: float = 0.0
    pv_generation_kwh: float = 0.0
    battery_throughput_kwh: float = 0.0
    battery_cycles: float = 0.0
    carbon_emissions_kg: float = 0.0
    carbon_intensity_weighted_kg: float = 0.0
    # Scenario E failure convention: an injected sensor failure returns NaN for
    # the affected building's readings. Those building-steps cannot contribute a
    # cost, so the totals cover valid data only and this ratio reports how much
    # of the episode that was (1.0 = every building-step had valid data).
    cost_coverage: float = 1.0
    invalid_cost_steps: int = 0


class ServiceMetrics(BaseModel):
    """Service and fairness metrics."""
    ev_completion_rate: float = 0.0
    ev_avg_soc_at_departure: float = 0.0
    ev_worst_soc_at_departure: float = 0.0
    comfort_violation_degree_hours: float = 0.0
    flexible_load_completion_rate: float = 0.0
    flexible_load_avg_delay_hours: float = 0.0
    dr_requested_kw: float = 0.0
    dr_delivered_kw: float = 0.0
    dr_credited_kw: float = 0.0
    per_member_costs: Dict[str, Optional[float]] = Field(default_factory=dict)
    per_member_savings: Dict[str, Optional[float]] = Field(default_factory=dict)
    # Scenario E failure-reporting convention: members whose cost data is
    # interrupted by an injected failure get per-member cost None (service
    # interrupted, cost undefined — never 0.0); economic aggregates use valid
    # members only, and the interruption is reported explicitly.
    members_interrupted: List[str] = Field(default_factory=list)
    member_cost_coverage: float = 1.0
    gini_coefficient: float = 0.0
    worst_member_cost: float = 0.0
    best_member_cost: float = 0.0


class GridMetrics(BaseModel):
    """Grid feasibility metrics."""
    power_flow_convergence_rate: float = 0.0
    voltage_violations_count: int = 0
    voltage_violation_duration_hours: float = 0.0
    max_voltage_pu: float = 0.0
    min_voltage_pu: float = 0.0
    line_loading_violations: int = 0
    transformer_loading_violations: int = 0
    max_line_loading_pct: float = 0.0
    max_transformer_loading_pct: float = 0.0
    nodal_power_balance_violations: int = 0


class AgentMetrics(BaseModel):
    """Code agent performance metrics."""
    task_success_rate: float = 0.0
    first_attempt_validity: float = 0.0
    simulation_success_rate: float = 0.0
    repair_success_rate: float = 0.0
    repair_iterations: int = 0
    token_consumption: int = 0
    wall_clock_seconds: float = 0.0
    constraint_violation_rate: float = 0.0
    report_completeness: float = 0.0


class PerMemberMetrics(BaseModel):
    """Per-member detailed metrics."""
    member_id: str
    building_id: str
    total_cost: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    pv_self_consumption_kwh: float = 0.0
    battery_cycles: float = 0.0
    ev_completion_rate: float = 0.0
    comfort_violations_hours: float = 0.0
    settlement_savings: float = 0.0
    service_score: float = 0.0  # 0-1 composite


class MemberSettlementMetrics(BaseModel):
    """Member-level grid and community settlement totals."""
    baseline_grid_bill: float = 0.0
    actual_grid_bill: float = 0.0
    actual_total_bill: float = 0.0
    settlement_savings: float = 0.0
    baseline_grid_import_kwh: float = 0.0
    baseline_grid_export_kwh: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    grid_import_cost: float = 0.0
    grid_export_revenue: float = 0.0
    demand_charge: float = 0.0
    community_import_cost: float = 0.0
    community_export_revenue: float = 0.0
    net_settlement: float = 0.0


class EnergySharingMetrics(BaseModel):
    """Community-level settlement summary and member breakdown."""
    market_type: str = "uniform_price"
    settlement_interval_timesteps: int = 0
    timestep_minutes: int = 0
    total_community_volume_kwh: float = 0.0
    total_community_revenue: float = 0.0
    baseline_grid_bill: float = 0.0
    actual_grid_bill: float = 0.0
    actual_total_bill: float = 0.0
    total_savings_vs_baseline: float = 0.0
    per_member: Dict[str, MemberSettlementMetrics] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    """Complete experiment result."""
    run_id: str
    scenario_id: str
    controller_type: ControllerType
    controller_config: Dict[str, Any] = Field(default_factory=dict)
    status: ExperimentStatus = ExperimentStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    random_seed: int = 42
    
    # Metrics
    energy: EnergyMetrics = Field(default_factory=EnergyMetrics)
    service: ServiceMetrics = Field(default_factory=ServiceMetrics)
    grid: GridMetrics = Field(default_factory=GridMetrics)
    agent: AgentMetrics = Field(default_factory=AgentMetrics)
    energy_sharing: Optional[EnergySharingMetrics] = None
    kpis: List[KPIResult] = Field(default_factory=list)
    per_member: List[PerMemberMetrics] = Field(default_factory=list)
    
    # Diagnostics
    diagnostic_reports: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Code artifacts
    controller_code: Optional[str] = None
    controller_code_hash: Optional[str] = None
    code_diffs: List[Dict[str, str]] = Field(default_factory=list)
    
    # Repair history
    repair_iterations: List[Dict[str, Any]] = Field(default_factory=list)
    
    # File paths
    trajectories_file: Optional[str] = None
    logs_file: Optional[str] = None
    plots_dir: Optional[str] = None
    
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class ComparisonReport(BaseModel):
    """Comparison between multiple experiment runs."""
    comparison_id: str
    scenario_id: str
    baseline_run_id: str
    comparison_run_ids: List[str] = Field(default_factory=list)
    metrics_comparison: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    statistical_tests: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    summary: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)


class FinalReport(BaseModel):
    """Final comprehensive report."""
    report_id: str
    title: str
    description: str
    scenario_configs: List[Dict[str, Any]] = Field(default_factory=list)
    experiment_results: List[ExperimentResult] = Field(default_factory=list)
    comparisons: List[ComparisonReport] = Field(default_factory=list)
    conclusions: str = ""
    limitations: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)
    git_commit: Optional[str] = None
    environment_hash: Optional[str] = None