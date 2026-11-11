"""Scenario management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from uuid import uuid4
import json
import os
from pathlib import Path

from src.schemas.scenario import (
    ScenarioConfig,
    BuildingConfig,
    PandapowerConfig,
    PVConfig,
    BatteryConfig,
    EnergySharingConfig,
    FailureConfig,
)

router = APIRouter()

# In-memory storage for scenarios (in production, use a database)
_scenarios: dict[str, ScenarioConfig] = {}


def _get_scenario_data_dir() -> Path:
    """Get the scenario data directory, resolving from multiple possible locations."""
    # Try environment variable first
    if "PROJECT_ROOT" in os.environ:
        return Path(os.environ["PROJECT_ROOT"]) / "data" / "schemas"

    # Try to find data/schemas by walking up from this file
    current = Path(__file__).parent
    for _ in range(6):
        candidate = current / "data" / "schemas"
        if candidate.exists():
            return candidate
        current = current.parent

    # Fallback to relative path from project root
    return Path(__file__).parent.parent.parent.parent.parent / "data" / "schemas"


def get_scenario_data_dir() -> Path:
    """Resolve the scenario data dir at call time.

    Import-time resolution breaks in containers where the mounted data dir
    only appears after startup (docker creates the host dir on first mount).
    """
    return _get_scenario_data_dir()


# Kept for backward compatibility; prefer get_scenario_data_dir().
SCENARIO_DATA_DIR = _get_scenario_data_dir()


def _load_scenario_from_disk(scenario_id: str) -> Optional[ScenarioConfig]:
    """Load a scenario from disk."""
    schema_path = get_scenario_data_dir() / scenario_id / "schema.json"
    if schema_path.exists():
        with open(schema_path) as f:
            data = json.load(f)
        # Convert to our ScenarioConfig format
        return _schema_to_scenario_config(data, scenario_id)
    return None


def _schema_to_scenario_config(schema: dict, scenario_id: str) -> ScenarioConfig:
    """Convert CityLearn schema to our ScenarioConfig."""
    buildings = []
    buildings_data = schema.get("buildings", {})
    if isinstance(buildings_data, dict):
        # CityLearn-style schema: building_id -> device config
        building_items = list(buildings_data.items())
    else:
        # Round-tripped config (saved by POST/PATCH /scenarios): list of
        # BuildingConfig-shaped dicts.
        building_items = [
            (
                b.get("building_id", f"building_{index}"),
                b,
            )
            for index, b in enumerate(buildings_data)
        ]
    for bid, bdata in building_items:
        if not bdata.get("include", True):
            continue
        pv = None
        pv_data = bdata.get("pv")
        if isinstance(pv_data, dict):
            pv_attrs = pv_data.get("attributes") or {}
            nominal_power = pv_attrs.get("nominal_power") or pv_data.get("capacity_kw")
            if nominal_power:
                pv = PVConfig(capacity_kw=float(nominal_power))
        battery = None
        storage_data = bdata.get("electrical_storage")
        if isinstance(storage_data, dict):
            storage_attrs = storage_data.get("attributes") or {}
            capacity = storage_attrs.get("capacity") or storage_data.get("capacity_kwh")
            power = storage_attrs.get("nominal_power") or storage_data.get("power_kw")
            if capacity and power:
                battery = BatteryConfig(
                    capacity_kwh=float(capacity),
                    power_kw=float(power),
                    efficiency_charge=float(storage_attrs.get("efficiency", 0.95)),
                    initial_soc=float(storage_attrs.get("initial_soc", 0.5)),
                )
        buildings.append(
            BuildingConfig(
                building_id=bid,
                building_type=bdata.get("building_type", "residential"),
                location=bdata.get("location", {}),
                simulation_start=bdata.get("simulation_start", "2023-01-01"),
                simulation_end=bdata.get("simulation_end", "2023-01-08"),
                pv=pv,
                battery=battery,
            )
        )

    pandapower_config = None
    if "pandapower" in schema:
        pp_data = schema["pandapower"]
        pandapower_config = PandapowerConfig(
            network_type=pp_data.get("network_type", "ieee_34"),
            network_file=pp_data.get("network_file"),
            coordinate_system=pp_data.get("coordinate_system", "schematic"),
            bus_mappings=[],  # Will be populated from mappings
            slack_bus=pp_data.get("slack_bus", 0),
            voltage_limits=pp_data.get("voltage_limits", {"min": 0.95, "max": 1.05}),
            line_loading_limit=pp_data.get("line_loading_limit", 1.0),
            transformer_loading_limit=pp_data.get("transformer_loading_limit", 1.0),
            run_power_flow_every=pp_data.get("run_power_flow_every", 1),
        )

    return ScenarioConfig(
        scenario_id=scenario_id,
        name=schema.get("name", scenario_id),
        description=schema.get("description", ""),
        buildings=buildings,
        pandapower=pandapower_config,
        random_seed=schema.get("random_seed", 42),
        timestep_minutes=schema.get("seconds_per_time_step", 900) // 60,
    )


def _scenario_to_dict(scenario: ScenarioConfig) -> dict:
    """Convert ScenarioConfig to dict for API response."""
    return {
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "description": scenario.description,
        "buildings": [b.model_dump() for b in scenario.buildings],
        "community": {
            "name": scenario.name,
            "buildings": len(scenario.buildings),
            "simulation_period": "1_week",
            "timestep_minutes": scenario.timestep_minutes,
        },
        "assets": {
            "pv": {"penetration": 0.5, "orientation": "south"},
            "batteries": {"community_capacity_kwh": 100, "max_power_kw": 50},
            "evs": {
                "number": 10,
                "charging_power_kw": [11],
                "departure_soc_requirement": 0.8,
            },
            "flexible_loads": {"share": 0.3},
        },
        "grid": {
            "model": (
                scenario.pandapower.network_type if scenario.pandapower else "ieee_34"
            ),
            "transformer_capacity_kva": 630,
            "voltage_limits_pu": [0.95, 1.05],
            "import_limit_kw": scenario.community_import_limit_kw or 500,
            "export_limit_kw": scenario.community_export_limit_kw or 500,
        },
        "control": {
            "strategy": "rule_based",
            "objective": ["cost_minimization", "carbon_reduction"],
        },
        "pandapower": scenario.pandapower.model_dump() if scenario.pandapower else None,
        # Top-level config the GET serializer used to drop entirely - an
        # energy-sharing scenario came back without its market definition.
        "energy_sharing": (
            scenario.energy_sharing.model_dump() if scenario.energy_sharing else None
        ),
        "failures": [f.model_dump() for f in scenario.failures],
        "carbon_intensity_file": scenario.carbon_intensity_file,
        "random_seed": scenario.random_seed,
        "timestep_minutes": scenario.timestep_minutes,
    }


@router.post("/scenarios/generate", response_model=dict)
async def generate_scenario(request: dict):
    """NL -> executable scenario config through the verified pipeline.

    The planner (LLM with the rule-based fallback) + coder + executor +
    verifier run here; the response carries the config for the confirm step
    AND the provenance (plan_source) plus any named rejections, so the UI can
    show a degraded 'preview' mode instead of pretending it is the agent."""
    import time

    nl = (request.get("nl") or request.get("description") or "").strip()
    if not nl:
        raise HTTPException(status_code=422, detail="nl (the natural-language description) is required")

    max_iterations = int(request.get("max_iterations", 2))
    project_root = os.environ.get(
        "PROJECT_ROOT", str(Path(__file__).resolve().parents[3])
    )
    started = time.time()
    try:
        from src.agents.nl_config_pipeline import run_nl_to_config

        result = run_nl_to_config(
            nl,
            scenario_id=f"gen_{uuid4().hex[:8]}",
            max_iterations=max_iterations,
            project_root=project_root,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced, never a silent 500
        raise HTTPException(
            status_code=500, detail=f"NL->config pipeline failed: {exc}"
        ) from exc

    manifest = result.get("manifest") or {}
    iterations = result.get("iterations") or []
    last = iterations[-1] if iterations else {}
    return {
        "config": result.get("final_config"),
        "plan_source": manifest.get("plan_source"),
        "rejected_fields": manifest.get("rejected_fields") or [],
        "success": bool(result.get("success")),
        "iterations": len(iterations),
        "final_verdict": (last.get("verifier_output") or {}).get("recommendation"),
        "elapsed_s": round(time.time() - started, 1),
    }


@router.get("/scenarios", response_model=List[dict])
async def get_scenarios():
    """Get all scenarios."""
    # Load from disk first
    scenario_root = get_scenario_data_dir()
    if scenario_root.exists():
        for scenario_dir in scenario_root.iterdir():
            if scenario_dir.is_dir() and scenario_dir.name not in _scenarios:
                scenario = _load_scenario_from_disk(scenario_dir.name)
                if scenario:
                    _scenarios[scenario.scenario_id] = scenario

    return [_scenario_to_dict(s) for s in _scenarios.values()]


@router.get("/scenarios/{scenario_id}", response_model=dict)
async def get_scenario(scenario_id: str):
    """Get a specific scenario by ID."""
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(
                status_code=404, detail=f"Scenario {scenario_id} not found"
            )

    return _scenario_to_dict(_scenarios[scenario_id])


@router.post("/scenarios", response_model=dict, status_code=201)
async def create_scenario(scenario_data: dict):
    """Create a new scenario."""
    scenario_id = scenario_data.get("scenario_id") or f"scenario_{uuid4().hex[:8]}"

    # Create ScenarioConfig from the input
    scenario = ScenarioConfig(
        scenario_id=scenario_id,
        name=scenario_data.get("name", scenario_id),
        description=scenario_data.get("description", ""),
        buildings=[BuildingConfig(**b) for b in scenario_data.get("buildings", [])],
        pandapower=(
            PandapowerConfig(**scenario_data["pandapower"])
            if scenario_data.get("pandapower")
            else None
        ),
        community_import_limit_kw=scenario_data.get("community_import_limit_kw"),
        community_export_limit_kw=scenario_data.get("community_export_limit_kw"),
        # Top-level fields the API used to drop at the door (c10's C5 failure:
        # an energy-sharing config POSTed then GET-back-less). Buildings already
        # carry pv/battery/evs/flexible_loads/tariff/weather_file through.
        energy_sharing=(
            EnergySharingConfig(**scenario_data["energy_sharing"])
            if scenario_data.get("energy_sharing")
            else None
        ),
        failures=[FailureConfig(**f) for f in scenario_data.get("failures") or []],
        carbon_intensity_file=scenario_data.get("carbon_intensity_file"),
        random_seed=scenario_data.get("random_seed", 42),
        timestep_minutes=scenario_data.get("timestep_minutes", 15),
    )

    _scenarios[scenario_id] = scenario

    # Save to disk
    scenario_dir = get_scenario_data_dir() / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # Save a minimal schema.json
    schema_data = _scenario_to_dict(scenario)
    with open(scenario_dir / "schema.json", "w") as f:
        json.dump(schema_data, f, indent=2)

    return _scenario_to_dict(scenario)


@router.patch("/scenarios/{scenario_id}", response_model=dict)
async def update_scenario(scenario_id: str, updates: dict):
    """Update an existing scenario."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    scenario = _scenarios[scenario_id]

    # Apply updates
    for key, value in updates.items():
        if hasattr(scenario, key):
            setattr(scenario, key, value)

    # Save to disk
    scenario_dir = get_scenario_data_dir() / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    schema_data = _scenario_to_dict(scenario)
    with open(scenario_dir / "schema.json", "w") as f:
        json.dump(_scenario_to_dict(scenario), f, indent=2)

    return _scenario_to_dict(scenario)


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str):
    """Delete a scenario."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    del _scenarios[scenario_id]

    # Also remove from disk
    import shutil

    scenario_dir = get_scenario_data_dir() / scenario_id
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)


@router.get("/scenarios/{scenario_id}/validate")
async def validate_scenario(scenario_id: str):
    """Validate a scenario configuration."""
    if scenario_id not in _scenarios:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    scenario = _scenarios[scenario_id]
    errors = []
    warnings = []

    # Validate buildings
    if not scenario.buildings:
        errors.append("No buildings configured")

    # Validate grid config
    if not scenario.pandapower:
        warnings.append("No pandapower configuration - grid validation will be skipped")

    # Validate timestep
    if scenario.timestep_minutes not in [5, 15, 30, 60]:
        warnings.append(f"Unusual timestep: {scenario.timestep_minutes} minutes")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
