"""Database models for the application."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
    Enum as SQLEnum,
    Text,
    Integer,
    Float,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class ExperimentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REPAIR_NEEDED = "repair_needed"
    REPAIR_IN_PROGRESS = "repair_in_progress"


class ControllerType(str, enum.Enum):
    RULE_BASED = "rule_based"
    MPC = "mpc"
    RL_SINGLE = "rl_single"
    RL_MULTI = "rl_multi"
    LLM_AGENT = "llm_agent"
    LLM_AGENT_VERIFIED = "llm_agent_verified"
    CENTRALIZED = "centralized"
    MULTI_AGENT = "multi_agent"


class Experiment(Base):
    """Experiment run tracking."""

    __tablename__ = "experiments"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    run_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    scenario_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    controller_type: Mapped[ControllerType] = mapped_column(
        SQLEnum(ControllerType), nullable=False
    )
    controller_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[ExperimentStatus] = mapped_column(
        SQLEnum(ExperimentStatus), default=ExperimentStatus.PENDING, index=True
    )
    random_seed: Mapped[int] = mapped_column(Integer, default=42)

    # Metrics
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grid_import_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grid_export_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_demand_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    load_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pv_self_consumption_kwh: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    pv_curtailment_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pv_generation_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_throughput_kwh: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    battery_cycles: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carbon_emissions_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Service metrics
    comfort_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_charge_fulfillment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flexible_load_fulfillment: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    deadline_missed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Grid metrics
    voltage_violations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_overloads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transformer_overloads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    import_limit_violations: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    export_limit_violations: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    avg_voltage_pu: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_line_loading_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_transformer_loading_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    nodal_power_balance_violations: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Agent metrics
    agent_backend: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_steps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fallback_steps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fallback_step_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # KPIs (JSON)
    kpis: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    per_member: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    diagnostic_reports: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Controller code and diffs
    controller_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code_diffs: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    repair_iterations: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tasks: Mapped[list["AgentTask"]] = relationship(
        "AgentTask", back_populates="experiment", lazy="dynamic"
    )

    # Indexes
    __table_args__ = (
        Index("ix_experiments_status_created", "status", "created_at"),
        Index("ix_experiments_scenario_controller", "scenario_id", "controller_type"),
    )


class AgentTask(Base):
    """Agent task tracking for repair workflow."""

    __tablename__ = "agent_tasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    experiment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False, index=True
    )

    # Task definition
    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # planner, coder, executor, verifier, reporter
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Inputs
    input_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Outputs
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Retry
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    experiment: Mapped["Experiment"] = relationship(
        "Experiment", back_populates="tasks"
    )

    # Indexes
    __table_args__ = (
        Index("ix_agent_tasks_experiment_status", "experiment_id", "status"),
        Index("ix_agent_tasks_type_status", "task_type", "status"),
    )


class SimulationRun(Base):
    """Simulation run tracking for benchmark matrix."""

    __tablename__ = "simulation_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    run_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    scenario_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    controller: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    regime: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=42)

    # Configuration
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    config_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Results location
    output_dir: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_simulation_runs_scenario_controller_regime",
            "scenario_id",
            "controller",
            "regime",
        ),
        Index("ix_simulation_runs_status_created", "status", "created_at"),
    )


class RepairSession(Base):
    """Repair session tracking for multi-agent repair loop."""

    __tablename__ = "repair_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    experiment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False, index=True
    )

    # Session info
    max_iterations: Mapped[int] = mapped_column(Integer, default=3)
    current_iteration: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Results
    final_report: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    total_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Indexes
    __table_args__ = (
        Index("ix_repair_sessions_experiment_status", "experiment_id", "status"),
    )
