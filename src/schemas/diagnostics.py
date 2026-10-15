"""Diagnostics schemas for grid and service constraint violations."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    VIOLATION = "violation"
    CRITICAL = "critical"


class DiagnosticCategory(str, Enum):
    POWER_FLOW = "power_flow"
    VOLTAGE = "voltage"
    LINE_LOADING = "line_loading"
    TRANSFORMER_LOADING = "transformer_loading"
    EV_DEADLINE = "ev_deadline"
    COMFORT = "comfort"
    BATTERY_SOC = "battery_soc"
    BATTERY_DEGRADATION = "battery_degradation"
    FLEXIBLE_LOAD = "flexible_load"
    DR_DELIVERY = "dr_delivery"
    ENERGY_SHARING = "energy_sharing"
    GRID_LIMIT = "grid_limit"
    CONVERGENCE = "convergence"


class Diagnostic(BaseModel):
    """Single diagnostic entry."""
    diagnostic_id: str
    category: DiagnosticCategory
    severity: Severity
    message: str
    timestep: int
    asset_ids: List[str] = Field(default_factory=list)
    bus_indices: List[int] = Field(default_factory=list)
    values: Dict[str, float] = Field(default_factory=dict)  # measured values
    limits: Dict[str, float] = Field(default_factory=dict)  # violated limits
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PowerFlowDiagnostic(Diagnostic):
    """Power flow specific diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.POWER_FLOW
    converged: bool = True
    iterations: int = 0
    max_mismatch: float = 0.0


class VoltageDiagnostic(Diagnostic):
    """Voltage violation diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.VOLTAGE
    bus_idx: int
    phase: str
    voltage_pu: float
    limit_min_pu: float
    limit_max_pu: float


class LineLoadingDiagnostic(Diagnostic):
    """Line loading diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.LINE_LOADING
    line_idx: int
    loading_pct: float
    limit_pct: float


class TransformerLoadingDiagnostic(Diagnostic):
    """Transformer loading diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.TRANSFORMER_LOADING
    trafo_idx: int
    loading_pct: float
    limit_pct: float


class EVDeadlineDiagnostic(Diagnostic):
    """EV charging deadline diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.EV_DEADLINE
    ev_id: str
    departure_timestep: int
    target_soc: float
    actual_soc: float
    shortfall_kwh: float


class ComfortDiagnostic(Diagnostic):
    """Thermal comfort diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.COMFORT
    building_id: str
    zone_id: str
    temperature: float
    setpoint_min: float
    setpoint_max: float
    violation_hours: float


class BatterySOCDiagnostic(Diagnostic):
    """Battery SOC diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.BATTERY_SOC
    battery_id: str
    soc: float
    soc_min: float
    soc_max: float


class FlexibleLoadDiagnostic(Diagnostic):
    """Flexible load completion diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.FLEXIBLE_LOAD
    load_id: str
    deadline_timestep: int
    energy_delivered_kwh: float
    energy_required_kwh: float
    completion_rate: float


class DRDeliveryDiagnostic(Diagnostic):
    """Demand response delivery diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.DR_DELIVERY
    dr_event_id: str
    requested_kw: float
    delivered_kw: float
    credited_kw: float


class GridLimitDiagnostic(Diagnostic):
    """Grid import/export limit diagnostic."""
    category: DiagnosticCategory = DiagnosticCategory.GRID_LIMIT
    limit_type: str  # import, export
    limit_kw: float
    actual_kw: float
    excess_kw: float


class DiagnosticReport(BaseModel):
    """Complete diagnostic report for a simulation run."""
    scenario_id: str
    run_id: str
    timestep: int
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    power_flow_converged: bool = True
    total_violations: int = 0
    critical_violations: int = 0
    
    def add_diagnostic(self, diagnostic: Diagnostic):
        self.diagnostics.append(diagnostic)
        if diagnostic.severity == Severity.VIOLATION:
            self.total_violations += 1
        elif diagnostic.severity == Severity.CRITICAL:
            self.critical_violations += 1
            self.total_violations += 1
    
    def get_by_category(self, category: DiagnosticCategory) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.category == category]
    
    def get_by_severity(self, severity: Severity) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == severity]
    
    def has_critical(self) -> bool:
        return self.critical_violations > 0