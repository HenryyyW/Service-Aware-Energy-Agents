"""Task specification schemas for the code agent system."""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    SCENARIO_CONSTRUCTION = "scenario_construction"
    CONSTRAINT_DIAGNOSIS = "constraint_diagnosis"
    POLICY_IMPROVEMENT = "policy_improvement"
    MARKET_ANALYSIS = "market_analysis"


class AssetType(str, Enum):
    BUILDING = "building"
    PV = "pv"
    BATTERY = "battery"
    EV = "ev"
    FLEXIBLE_LOAD = "flexible_load"


class ConstraintType(str, Enum):
    EV_DEADLINE = "ev_deadline"
    COMFORT_BOUNDS = "comfort_bounds"
    BATTERY_SOC = "battery_soc"
    BATTERY_DEGRADATION = "battery_degradation"
    FLEXIBLE_LOAD_DEADLINE = "flexible_load_deadline"
    POWER_IMPORT_LIMIT = "power_import_limit"
    POWER_EXPORT_LIMIT = "power_export_limit"
    VOLTAGE_LIMITS = "voltage_limits"
    LINE_LOADING = "line_loading"
    TRANSFORMER_LOADING = "transformer_loading"
    DR_DELIVERY = "dr_delivery"
    ENERGY_SHARING = "energy_sharing"


class AssetSpec(BaseModel):
    """Specification for a single asset in the community."""
    asset_id: str
    asset_type: AssetType
    building_id: Optional[str] = None
    capacity_kw: Optional[float] = None
    capacity_kwh: Optional[float] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ConstraintSpec(BaseModel):
    """Specification for a constraint."""
    constraint_id: str
    constraint_type: ConstraintType
    assets: List[str] = Field(default_factory=list)  # asset_ids this applies to
    parameters: Dict[str, Any] = Field(default_factory=dict)
    hard: bool = True  # if False, violation incurs penalty


class KPISpec(BaseModel):
    """Specification for a KPI to track."""
    kpi_id: str
    name: str
    description: str
    target: Optional[float] = None
    direction: str = "minimize"  # minimize, maximize, target


class TaskSpec(BaseModel):
    """Complete task specification from natural language or config."""
    task_id: str
    task_type: TaskType
    description: str
    assets: List[AssetSpec] = Field(default_factory=list)
    constraints: List[ConstraintSpec] = Field(default_factory=list)
    kpis: List[KPISpec] = Field(default_factory=list)
    scenario_config: Optional[str] = None  # path to scenario YAML
    baseline_controller: Optional[str] = None  # path to baseline controller
    experiment_config: Dict[str, Any] = Field(default_factory=dict)
    random_seed: int = 42