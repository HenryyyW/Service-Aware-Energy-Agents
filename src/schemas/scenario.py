"""Scenario configuration schemas for CityLearn and pandapower."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class BuildingType(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    MIXED = "mixed"


class PVConfig(BaseModel):
    """PV system configuration."""
    capacity_kw: float
    azimuth: float = 180.0  # degrees, 180 = south
    tilt: float = 30.0  # degrees
    efficiency: float = 0.20
    inverter_efficiency: float = 0.96


class BatteryConfig(BaseModel):
    """Battery storage configuration."""
    capacity_kwh: float
    power_kw: float
    efficiency_charge: float = 0.95
    efficiency_discharge: float = 0.95
    soc_min: float = 0.1
    soc_max: float = 0.9
    initial_soc: float = 0.5
    degradation_model: Optional[str] = None


class EVConfig(BaseModel):
    """Electric vehicle configuration."""
    capacity_kwh: float
    max_charge_kw: float
    efficiency: float = 0.90
    arrival_time: str  # HH:MM format
    departure_time: str  # HH:MM format
    target_soc: float = 0.8
    initial_soc: float = 0.3
    connected_days: List[int] = Field(default_factory=lambda: list(range(7)))  # 0-6 for week


class FlexibleLoadConfig(BaseModel):
    """Flexible load configuration."""
    power_kw: float
    energy_kwh: float
    earliest_start: str  # HH:MM
    latest_end: str  # HH:MM
    duration_hours: float


class TariffConfig(BaseModel):
    """Electricity tariff configuration."""
    type: str = "time_of_use"  # time_of_use, real_time, flat
    import_prices: Dict[str, float] = Field(default_factory=dict)  # period -> price
    export_prices: Dict[str, float] = Field(default_factory=dict)
    demand_charge: float = 0.0  # $/kW


class BuildingConfig(BaseModel):
    """Building configuration."""
    building_id: str
    building_type: BuildingType = BuildingType.RESIDENTIAL
    location: Dict[str, Any] = Field(default_factory=dict)  # lat, lon, timezone
    pv: Optional[PVConfig] = None
    battery: Optional[BatteryConfig] = None
    evs: List[EVConfig] = Field(default_factory=list)
    flexible_loads: List[FlexibleLoadConfig] = Field(default_factory=list)
    tariff: Optional[TariffConfig] = None
    weather_file: Optional[str] = None
    simulation_start: str = "2023-01-01"
    simulation_end: str = "2023-01-08"  # one week default


class GridBusMapping(BaseModel):
    """Mapping from building/community to pandapower bus."""
    building_id: str
    bus_idx: int
    phase: str = "all"  # a, b, c, all
    voltage_level: str = "LV"  # LV, MV


class PandapowerConfig(BaseModel):
    """pandapower network configuration."""
    network_type: str = "ieee_34"  # ieee_13, ieee_34, simbench, custom
    network_file: Optional[str] = None
    bus_mappings: List[GridBusMapping] = Field(default_factory=list)
    slack_bus: int = 0
    voltage_limits: Dict[str, float] = Field(default_factory=lambda: {"min": 0.95, "max": 1.05})
    line_loading_limit: float = 1.0  # per unit
    transformer_loading_limit: float = 1.0
    run_power_flow_every: int = 1  # every N timesteps


class EnergySharingConfig(BaseModel):
    """Local energy sharing and settlement configuration."""
    enabled: bool = False
    market_type: str = "uniform_price"  # uniform_price, weighted, carbon_aware, fairness_aware
    settlement_interval: str = "15min"  # 15min, hourly, daily
    export_limit_kw: Optional[float] = None
    import_limit_kw: Optional[float] = None


class FailureConfig(BaseModel):
    """Failure injection configuration."""
    failure_id: str
    asset_id: str
    failure_type: str  # pv_inverter, battery, ev_charger, sensor, grid_limit
    start_time: str  # HH:MM or timestep
    end_time: Optional[str] = None
    severity: float = 1.0  # 0-1, 1 = complete failure


class ScenarioConfig(BaseModel):
    """Complete scenario configuration."""
    scenario_id: str
    name: str
    description: str
    buildings: List[BuildingConfig] = Field(default_factory=list)
    pandapower: Optional[PandapowerConfig] = None
    energy_sharing: Optional[EnergySharingConfig] = None
    failures: List[FailureConfig] = Field(default_factory=list)
    community_import_limit_kw: Optional[float] = None
    community_export_limit_kw: Optional[float] = None
    carbon_intensity_file: Optional[str] = None
    random_seed: int = 42
    timestep_minutes: int = 15