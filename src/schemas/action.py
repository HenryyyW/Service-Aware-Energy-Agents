"""Action schemas for CityLearn requested/limited/applied actions."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ActionType(str, Enum):
    BATTERY_CHARGE = "battery_charge"
    BATTERY_DISCHARGE = "battery_discharge"
    EV_CHARGE = "ev_charge"
    FLEXIBLE_LOAD = "flexible_load"
    GRID_IMPORT = "grid_import"
    GRID_EXPORT = "grid_export"
    ENERGY_SHARE_IMPORT = "energy_share_import"
    ENERGY_SHARE_EXPORT = "energy_share_export"


class Action(BaseModel):
    """Single action for an asset."""
    asset_id: str
    action_type: ActionType
    value_kw: float  # positive for charge/import, negative for discharge/export
    timestep: int


class ActionSet(BaseModel):
    """Complete set of actions for a timestep."""
    timestep: int
    actions: List[Action] = Field(default_factory=list)
    
    def get_action(self, asset_id: str, action_type: ActionType) -> Optional[Action]:
        for a in self.actions:
            if a.asset_id == asset_id and a.action_type == action_type:
                return a
        return None
    
    def get_total_grid_import(self) -> float:
        return sum(a.value_kw for a in self.actions 
                   if a.action_type == ActionType.GRID_IMPORT and a.value_kw > 0)
    
    def get_total_grid_export(self) -> float:
        return sum(-a.value_kw for a in self.actions 
                   if a.action_type == ActionType.GRID_EXPORT and a.value_kw < 0)


class RequestedActions(ActionSet):
    """Actions requested by the controller/agent."""
    pass


class LimitedActions(ActionSet):
    """Actions after applying electrical service limits."""
    limit_reasons: Dict[str, str] = Field(default_factory=dict)  # asset_id -> reason


class AppliedActions(ActionSet):
    """Actions actually applied in simulation (after all constraints)."""
    pass


class ActionComparison(BaseModel):
    """Comparison between requested, limited, and applied actions."""
    timestep: int
    asset_id: str
    requested_kw: float
    limited_kw: float
    applied_kw: float
    limit_reason: Optional[str] = None
    deviation_pct: float = 0.0  # (applied - requested) / requested * 100


class ControllerOutput(BaseModel):
    """Output from a controller for one timestep."""
    timestep: int
    requested_actions: RequestedActions
    observations: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SimulationStepResult(BaseModel):
    """Result of one simulation step."""
    timestep: int
    requested_actions: RequestedActions
    limited_actions: LimitedActions
    applied_actions: AppliedActions
    observations: Dict[str, Any] = Field(default_factory=dict)
    rewards: Dict[str, float] = Field(default_factory=dict)
    costs: Dict[str, float] = Field(default_factory=dict)
    grid_diagnostics: Optional[Dict[str, Any]] = None
    constraint_violations: List[str] = Field(default_factory=list)
    terminated: bool = False
    truncated: bool = False