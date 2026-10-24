"""Network geometry routes for pandapower network visualization."""
import yaml
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional

from src.simulation.pandapower_adapter import PandapowerAdapter
from src.schemas.scenario import ScenarioConfig

router = APIRouter()

# Global reference to pandapower adapter (set during scenario initialization)
_pandapower_adapter: Optional[PandapowerAdapter] = None


def set_pandapower_adapter(adapter: PandapowerAdapter):
    """Set the global pandapower adapter instance."""
    global _pandapower_adapter
    _pandapower_adapter = adapter


def get_pandapower_adapter() -> PandapowerAdapter:
    """Get the global pandapower adapter instance."""
    if _pandapower_adapter is None:
        scenario_path = Path(__file__).resolve().parents[3] / "configs" / "scenario_a.yaml"
        try:
            with scenario_path.open("r", encoding="utf-8") as scenario_file:
                scenario = ScenarioConfig.model_validate(yaml.safe_load(scenario_file))
            if scenario.pandapower is None:
                raise ValueError("Scenario has no pandapower configuration")
            set_pandapower_adapter(PandapowerAdapter(scenario.pandapower))
        except (OSError, yaml.YAMLError, ValueError) as error:
            raise HTTPException(status_code=503, detail=f"Default network could not be loaded: {error}") from error
    return _pandapower_adapter


@router.get("/geometry")
async def get_network_geometry() -> Dict[str, Any]:
    """Get complete network geometry for frontend visualization.
    
    Returns buses, lines, transformers, and bounds for map fitting.
    """
    adapter = get_pandapower_adapter()
    return adapter.get_network_geometry()


@router.get("/buses")
async def get_bus_coordinates() -> Dict[str, Dict[str, Any]]:
    """Get raw x/y bus coordinates and lat/lon only for geographic networks.
    
    Returns dict mapping bus name -> {lat, lon, vn_kv, name, bus_idx}
    """
    adapter = get_pandapower_adapter()
    return adapter.get_bus_coordinates()


@router.get("/lines")
async def get_line_geometries() -> list:
    """Get line geometries as LineString coordinates.
    
    Returns list of line geometries with coordinates, from_bus, to_bus, etc.
    """
    adapter = get_pandapower_adapter()
    return adapter.get_line_geometries()


@router.get("/transformers")
async def get_transformer_geometries() -> list:
    """Get transformer geometries in the network's declared coordinate system.
    
    Returns list of transformer locations with lat/lon and metadata.
    """
    adapter = get_pandapower_adapter()
    return adapter.get_transformer_geometries()


@router.get("/bounds")
async def get_network_bounds() -> Dict[str, Any]:
    """Get bounds in the network's declared coordinate system.
    
    Returns min/max lat/lon for all network elements.
    """
    adapter = get_pandapower_adapter()
    geometry = adapter.get_network_geometry()
    return geometry["bounds"] or {}