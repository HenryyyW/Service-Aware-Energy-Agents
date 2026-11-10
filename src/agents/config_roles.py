"""Role definitions for the NL -> Scenario Config pipeline."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass, field
import time


class ConfigAgentRole(str, Enum):
    """Roles for the NL -> Scenario Config pipeline."""

    PLANNER = "planner"
    CODER = "coder"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    REPORTER = "reporter"


class ConfigMessage(BaseModel):
    """Inter-agent message for config pipeline."""

    role: ConfigAgentRole
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


@dataclass
class ConfigAgentState:
    """Shared state for the NL -> Scenario Config pipeline."""

    # Input
    nl_description: str = ""
    original_nl: str = ""

    # Plan
    config_plan: Optional[Dict[str, Any]] = None

    # Code/Config
    baseline_config: Optional[Dict[str, Any]] = None
    patched_config: Optional[Dict[str, Any]] = None
    config_changes: List[Dict[str, Any]] = field(default_factory=list)
    config_diff: str = ""

    # Execution/Validation
    scenario_config_path: str = ""
    execution_result: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None

    # Metadata
    iteration: int = 0
    max_iterations: int = 3
    messages: List["ConfigMessage"] = field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    manifest: Optional[Dict[str, Any]] = None

    # Mapping/Validation
    mapping_errors: List[Dict[str, Any]] = field(default_factory=list)
    schema_errors: List[Dict[str, Any]] = field(default_factory=list)

    def add_message(
        self, role: "ConfigAgentRole", content: str, metadata: Dict[str, Any] = None
    ):
        self.messages.append(
            ConfigMessage(role=role, content=content, metadata=metadata or {})
        )

    def add_audit(self, entry: Dict[str, Any]):
        self.audit_trail.append({"timestamp": time.time(), **entry})

    def add_manifest_entry(self, key: str, value: Any):
        if self.manifest is None:
            self.manifest = {}
        self.manifest[key] = value


class ConfigPlannerOutput(BaseModel):
    """Output from the Config Planner agent."""

    # Provenance: 'llm' when the planner produced this from a model response,
    # 'rule_based_fallback' when the keyword fallback produced it (never silent)
    plan_source: str = "llm"

    # What needs to be built/configured
    target_assets: List[str] = Field(
        default_factory=list
    )  # ["pv", "battery", "ev", "flexible_load", "tariff", "grid"]
    building_count: int = 1
    building_types: List[str] = Field(default_factory=list)

    # Specific configurations
    pv_configs: List[Dict[str, Any]] = Field(default_factory=list)
    battery_configs: List[Dict[str, Any]] = Field(default_factory=list)
    ev_configs: List[Dict[str, Any]] = Field(default_factory=list)
    flexible_load_configs: List[Dict[str, Any]] = Field(default_factory=list)
    tariff_configs: List[Dict[str, Any]] = Field(default_factory=list)
    grid_configs: List[Dict[str, Any]] = Field(default_factory=list)
    failure_injections: List[Dict[str, Any]] = Field(default_factory=list)

    # Community settings
    community_import_limit_kw: Optional[float] = None
    community_export_limit_kw: Optional[float] = None
    energy_sharing_enabled: bool = False
    dynamic_pricing_enabled: bool = False

    # Simulation settings
    timestep_minutes: int = 15
    simulation_duration_days: int = 7
    simulation_start: Optional[str] = None  # 'YYYY-MM-DD' when the NL states it
    simulation_end: Optional[str] = None  # 'YYYY-MM-DD' (derived from duration)
    random_seed: int = 42

    # Weather/Location
    location: Dict[str, Any] = Field(default_factory=dict)  # lat, lon, timezone
    climate_zone: Optional[str] = None  # CityLearn climate zone
    weather_file: Optional[str] = None  # CityLearn weather file (e.g. Singapore)

    # Metadata
    confidence: float = 0.8
    assumptions: List[str] = Field(default_factory=list)
    required_fields: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)


class ConfigCoderOutput(BaseModel):
    """Output from the Config Coder agent."""

    config_changes: List[Dict[str, Any]] = Field(default_factory=list)
    patched_config: Dict[str, Any] = Field(default_factory=dict)
    config_diff: str = ""
    implementation_notes: str = ""
    applied_count: int = 0
    failed_count: int = 0


class ConfigExecutorOutput(BaseModel):
    """Output from the Config Executor agent."""

    success: bool
    scenario_id: str = ""
    config_valid: bool = False
    simulation_steps: int = 0
    simulation_time_sec: float = 0.0
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    test_results: Dict[str, Any] = Field(default_factory=dict)

    # Quick simulation results
    violation_counts: Dict[str, int] = Field(default_factory=dict)
    power_flow_converged: bool = True
    energy_balance_ok: bool = True

    # Performance
    execution_time: float = 0.0


class ConfigVerifierOutput(BaseModel):
    """Output from the Config Verifier agent."""

    schema_valid: bool = False
    round_trip_valid: bool = False
    determinism_check: bool = False
    schema_complete: bool = False
    determinism_seed: Optional[int] = None
    determinism_tolerance: float = 1e-6

    schema_errors: List[str] = Field(default_factory=list)
    round_trip_errors: List[str] = Field(default_factory=list)
    determinism_errors: List[str] = Field(default_factory=list)
    completeness_issues: List[str] = Field(default_factory=list)

    required_fields_missing: List[str] = Field(default_factory=list)
    out_of_range_fields: List[str] = Field(default_factory=list)
    schema_rejections: List[str] = Field(default_factory=list)

    confidence: float = 0.0
    recommendation: str = ""  # "accept", "retry", "escalate"
    manifest: Dict[str, Any] = Field(default_factory=dict)


class ConfigReporterOutput(BaseModel):
    """Output from the Config Reporter agent."""

    summary: str
    detailed_report: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    manifest: Dict[str, Any] = Field(default_factory=dict)
