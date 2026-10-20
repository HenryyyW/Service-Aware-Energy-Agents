"""Scenario management routes."""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel

from src.schemas.scenario import ScenarioConfig
from src.simulation.coupling import SimulationCoupler
from src.api.routes.network import set_pandapower_adapter

router = APIRouter()

# In-memory storage for scenarios
_scenarios: Dict[str, ScenarioConfig] = {}
_couplers: Dict[str, SimulationCoupler] = {}


class ScenarioCreateRequest(BaseModel):
    """Request to create a new scenario."""
    scenario_id: str
    name: str
    description: str = ""
    config: Dict[str, Any]


@router.get("")
async def list_scenarios() -> List[Dict[str, Any]]:
    """List all available scenarios."""
    return [
        {
            "scenario_id": s.scenario_id,
            "name": s.name,
            "description": s.description,
        }
        for s in _scenarios.values()
    ]


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str) -> Dict[str, Any]:
    """Get scenario details."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenarios[scenario_id].model_dump()


@router.post("")
async def create_scenario(request: ScenarioCreateRequest) -> Dict[str, Any]:
    """Create a new scenario."""
    config = ScenarioConfig(**request.config)
    config.scenario_id = request.scenario_id
    config.name = request.name
    config.description = request.description
    
    _scenarios[request.scenario_id] = config
    return {"status": "created", "scenario_id": request.scenario_id}


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