"""Scenario management routes."""
from pathlib import Path
import json
import re
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
import yaml

from src.schemas.scenario import ScenarioConfig
from src.simulation.coupling import SimulationCoupler
from src.api.routes.network import set_pandapower_adapter

router = APIRouter()

# In-memory storage for scenarios
_scenarios: Dict[str, ScenarioConfig] = {}
_couplers: Dict[str, SimulationCoupler] = {}
_CONFIGS_DIR = Path(__file__).resolve().parents[3] / "configs"
_SAVED_SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "results" / "api_runs" / "scenarios"


def _load_config_scenario(scenario_id: str) -> ScenarioConfig:
    """Load a repository scenario by its validated ID."""
    if not scenario_id.replace("_", "").isalnum():
        raise HTTPException(status_code=404, detail="Scenario not found")
    config_path = _CONFIGS_DIR / f"{scenario_id}.yaml"
    try:
        if config_path.is_file():
            with config_path.open("r", encoding="utf-8") as config_file:
                return ScenarioConfig.model_validate(yaml.safe_load(config_file))
        saved_path = _SAVED_SCENARIOS_DIR / f"{scenario_id}.json"
        if saved_path.is_file():
            return ScenarioConfig.model_validate_json(saved_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, ValueError) as error:
        raise HTTPException(status_code=500, detail=f"Invalid scenario config: {error}") from error
    raise HTTPException(status_code=404, detail="Scenario not found")


class ScenarioCreateRequest(BaseModel):
    """Request to create a new scenario."""
    scenario_id: str
    name: str
    description: str = ""
    config: Dict[str, Any]


@router.get("")
async def list_scenarios() -> List[Dict[str, Any]]:
    """List all available scenarios."""
    scenarios = {
        scenario_id: scenario
        for scenario_id, scenario in (
            (path.stem, _load_config_scenario(path.stem))
            for path in _CONFIGS_DIR.glob("scenario_*.yaml")
        )
    }
    if _SAVED_SCENARIOS_DIR.exists():
        for saved_path in _SAVED_SCENARIOS_DIR.glob("*.json"):
            try:
                scenarios[saved_path.stem] = ScenarioConfig.model_validate_json(saved_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    scenarios.update(_scenarios)
    return [
        {"scenario_id": scenario.scenario_id, "name": scenario.name, "description": scenario.description}
        for scenario in scenarios.values()
    ]


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str) -> Dict[str, Any]:
    """Get scenario details."""
    scenario = _scenarios.get(scenario_id) or _load_config_scenario(scenario_id)
    return scenario.model_dump()


@router.post("")
async def create_scenario(request: ScenarioCreateRequest) -> Dict[str, Any]:
    """Create a new scenario."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", request.scenario_id):
        raise HTTPException(status_code=422, detail="Scenario ID may contain only letters, numbers, and underscores")
    config = ScenarioConfig(**request.config)
    config.scenario_id = request.scenario_id
    config.name = request.name
    config.description = request.description
    
    _scenarios[request.scenario_id] = config
    if not (_CONFIGS_DIR / f"{request.scenario_id}.yaml").is_file():
        _SAVED_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
        saved_path = _SAVED_SCENARIOS_DIR / f"{request.scenario_id}.json"
        saved_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return config.model_dump()


@router.post("/{scenario_id}/initialize")
async def initialize_scenario(scenario_id: str) -> Dict[str, Any]:
    """Initialize scenario - create pandapower network and coupler."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    config = _scenarios[scenario_id]
    
    # Create coupler which initializes pandapower adapter
    coupler = SimulationCoupler(config)
    _couplers[scenario_id] = coupler
    
    # Set pandapower adapter for network routes
    set_pandapower_adapter(coupler.pandapower)
    
    # Get network geometry
    geometry = coupler.pandapower.get_network_geometry()
    
    return {
        "status": "initialized",
        "scenario_id": scenario_id,
        "network_bounds": geometry.get("bounds"),
        "num_buses": len(geometry.get("buses", {})),
        "num_lines": len(geometry.get("lines", [])),
        "num_transformers": len(geometry.get("transformers", [])),
    }


@router.get("/{scenario_id}/buildings")
async def get_scenario_buildings(scenario_id: str) -> List[Dict[str, Any]]:
    """Get buildings in scenario with their bus mappings."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    config = _scenarios[scenario_id]
    bus_coords = {}
    if scenario_id in _couplers:
        bus_coords = _couplers[scenario_id].pandapower.get_bus_coordinates()
    
    buildings = []
    for building in config.buildings:
        bus_mapping = next((m for m in config.pandapower.bus_mappings if m.building_id == building.building_id), None)
        bus_name = None
        if bus_mapping:
            bus_name = _couplers[scenario_id].pandapower.net.bus.at[bus_mapping.bus_idx, 'name']
        
        # Get bus coordinates if available
        location = None
        if bus_name and bus_name in bus_coords and _couplers[scenario_id].pandapower.coordinate_system == "geographic":
            bc = bus_coords[bus_name]
            location = {"lat": bc["lat"], "lon": bc["lon"]}
        elif building.location.get("lat") is not None and building.location.get("lon") is not None:
            location = {"lat": building.location["lat"], "lon": building.location["lon"]}
        
        # Safely get optional attributes using model_fields (class attribute)
            pv_capacity = 0
            battery_capacity = 0
            ev_capacity = 0
            
            # Use model_dump to safely get all fields as dict
            building_dict = building.model_dump()
            
            pv_capacity = 0
            battery_capacity = 0
            ev_capacity = 0
            
            # PV capacity
            pv_data = building_dict.get('pv')
            if pv_data and isinstance(pv_data, dict):
                pv_capacity = pv_data.get('capacity_kw', 0)
            
            # Battery capacity
            battery_data = building_dict.get('battery')
            if battery_data and isinstance(battery_data, dict):
                battery_capacity = battery_data.get('capacity_kwh', 0)
            
            # EV capacity (evs is a list)
            evs_data = building_dict.get('evs')
            if evs_data and isinstance(evs_data, list):
                ev_capacity = sum(ev.get('capacity_kwh', 0) for ev in evs_data if isinstance(ev, dict))
            
            buildings.append({
                "building_id": building.building_id,
                "name": building.building_id.replace("_", " ").title(),
                "type": building.building_type.value if hasattr(building.building_type, 'value') else str(building.building_type),
                "location": location,
                "bus_name": bus_name,
                "pv_capacity_kw": pv_capacity,
                "battery_capacity_kwh": battery_capacity,
                "ev_capacity_kwh": ev_capacity,
            })
    
    return buildings