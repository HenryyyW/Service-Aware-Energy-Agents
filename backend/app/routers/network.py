"""Network geometry API endpoints for MapLibre/deck.gl visualization."""
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.simulation.pandapower_adapter import create_grid_from_scenario
from src.schemas.scenario import ScenarioConfig
from app.routers.scenarios import _scenarios, _load_scenario_from_disk

router = APIRouter()


class NetworkGeometryResponse(BaseModel):
    coordinate_system: str
    buses: Dict[str, Dict[str, Any]]
    lines: List[Dict[str, Any]]
    transformers: List[Dict[str, Any]]
    bounds: Optional[Dict[str, float]] = None


@router.get("/network/geometry", response_model=NetworkGeometryResponse)
async def get_network_geometry(scenario_id: str = Query(..., description="Scenario ID")):
    """Get network geometry for MapLibre/deck.gl visualization."""
    # Load scenario
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    
    scenario = _scenarios[scenario_id]
    
    # Create pandapower adapter to get geometry
    adapter = create_grid_from_scenario(scenario)
    
    # Get bus coordinates
    bus_coords = adapter.get_bus_coordinates()
    
    # Get line geometries
    line_geoms = adapter.get_line_geometries()
    
    # Get transformer geometries
    trafo_geoms = adapter.get_transformer_geometries()
    
    # Build response matching frontend NetworkGeometry type
    buses = {}
    for bus_name, coord in bus_coords.items():
        buses[bus_name] = {
            "name": coord["name"],
            "x": coord["x"],
            "y": coord["y"],
            "lat": coord.get("lat"),
            "lon": coord.get("lon"),
            "vn_kv": coord["vn_kv"],
            "bus_idx": coord["bus_idx"],
        }
    
    lines = []
    for line in line_geoms:
        lines.append({
            "line_id": line["line_id"],
            "name": line["name"],
            "coordinates": line["coordinates"],
            "from_bus": line["from_bus"],
            "to_bus": line["to_bus"],
            "from_bus_idx": line["from_bus_idx"],
            "to_bus_idx": line["to_bus_idx"],
            "length_km": line["length_km"],
            "std_type": line["std_type"],
        })
    
    transformers = []
    for trafo in trafo_geoms:
        transformers.append({
            "transformer_id": trafo["transformer_id"],
            "name": trafo["name"],
            "x": trafo["x"],
            "y": trafo["y"],
            "lat": trafo.get("lat"),
            "lon": trafo.get("lon"),
            "hv_bus": trafo["hv_bus"],
            "lv_bus": trafo["lv_bus"],
            "hv_bus_idx": trafo["hv_bus_idx"],
            "lv_bus_idx": trafo["lv_bus_idx"],
            "capacity_mva": trafo["capacity_mva"],
        })
    
    # Calculate bounds
    bounds = None
    if bus_coords:
        all_coords = []
        for coord in bus_coords.values():
            if "lat" in coord and "lon" in coord:
                all_coords.append([coord["lon"], coord["lat"]])
            else:
                all_coords.append([coord["x"], coord["y"]])
        
        for line in line_geoms:
            all_coords.extend(line["coordinates"])
        
        if all_coords:
            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
            bounds = {
                "min_lon": min(lons),
                "max_lon": max(lons),
                "min_lat": min(lats),
                "max_lat": max(lats),
            }
    
    return NetworkGeometryResponse(
        coordinate_system=adapter.coordinate_system,
        buses=buses,
        lines=lines,
        transformers=transformers,
        bounds=bounds,
    )


@router.get("/network/geometry/{scenario_id}/realtime")
async def get_realtime_network_state(
    scenario_id: str,
    run_id: Optional[str] = Query(None, description="Optional run ID for real-time state")
):
    """Get real-time network state (voltages, loading) for visualization."""
    # Load scenario
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    
    scenario = _scenarios[scenario_id]
    adapter = create_grid_from_scenario(scenario)
    
    # If run_id provided, try to get state from running simulation
    if run_id:
        from app.routers.simulations import _couplers
        if run_id in _couplers:
            coupler = _couplers[run_id]
            # Get latest power flow results
            state = {
                "converged": coupler.pandapower.net.converged if coupler.pandapower.net else False,
                "voltage_profile": coupler.pandapower.get_voltage_profile(),
                "loading_profile": coupler.pandapower.get_loading_profile(),
                "losses": coupler.pandapower.calculate_losses(),
                "building_contributions": coupler.pandapower.get_per_building_contributions(),
            }
            return state
    
    # Return static network state
    return {
        "converged": False,
        "voltage_profile": {},
        "loading_profile": {"lines": {}, "trafos": {}},
        "losses": {"total_active_loss_kw": 0, "total_reactive_loss_kvar": 0},
        "building_contributions": {},
    }


@router.get("/network/asset-metadata/{scenario_id}")
async def get_asset_metadata(scenario_id: str):
    """Get asset metadata for map visualization (PV, batteries, EVs, flexible loads)."""
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    
    scenario = _scenarios[scenario_id]
    
    assets = {
        "pv": [],
        "batteries": [],
        "evs": [],
        "flexible_loads": [],
        "buildings": [],
    }
    
    for building in scenario.buildings:
        bid = building.building_id
        location = building.location
        
        # Building location
        assets["buildings"].append({
            "building_id": bid,
            "name": f"Building {bid}",
            "location": location,
            "building_type": building.building_type.value if hasattr(building.building_type, 'value') else building.building_type,
        })
        
        # PV assets
        if building.pv:
            assets["pv"].append({
                "asset_id": f"{bid}_pv",
                "building_id": bid,
                "capacity_kw": building.pv.capacity_kw,
                "orientation": building.pv.azimuth,
                "tilt": building.pv.tilt,
                "location": location,
            })
        
        # Battery assets
        if building.battery:
            assets["batteries"].append({
                "asset_id": f"{bid}_battery",
                "building_id": bid,
                "capacity_kwh": building.battery.capacity_kwh,
                "power_kw": building.battery.power_kw,
                "soc_min": building.battery.soc_min,
                "soc_max": building.battery.soc_max,
                "location": location,
            })
        
        # EV assets
        for i, ev in enumerate(building.evs):
            assets["evs"].append({
                "asset_id": f"{bid}_ev_{i}",
                "building_id": bid,
                "capacity_kwh": ev.capacity_kwh,
                "charger_power_kw": ev.max_charge_kw,
                "arrival_time": ev.arrival_time,
                "departure_time": ev.departure_time,
                "target_soc": ev.target_soc,
                "location": location,
            })
        
        # Flexible load assets
        for i, fl in enumerate(building.flexible_loads):
            assets["flexible_loads"].append({
                "asset_id": f"{bid}_flex_{i}",
                "building_id": bid,
                "power_kw": fl.power_kw,
                "energy_kwh": fl.energy_kwh,
                "earliest_start": fl.earliest_start,
                "latest_end": fl.latest_end,
                "location": location,
            })
    
    return assets


# Add the transformer geometries method to pandapower_adapter if not present
# This is a placeholder - the actual method should be added to pandapower_adapter.py