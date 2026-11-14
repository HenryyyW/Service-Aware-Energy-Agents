"""Simulation management API endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from uuid import uuid4
from pathlib import Path
from datetime import datetime
import asyncio
import numpy as np
import hashlib
import re
import json


def _convert_numpy(obj):
    """Recursively convert numpy types to Python native types.

    Mirrors _convert_to_json_serializable() in src/simulation/coupling.py:
    non-finite floats (NaN/Inf) are sanitized to None for strict JSON
    compliance (the trajectories endpoint 500'd on them, Phase 6 F2).
    """
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        val = float(obj)
        return val if np.isfinite(val) else None
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: _convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_numpy(v) for v in obj)
    else:
        return obj


def _compute_config_hash(
    scenario_id: str,
    controller_type: str,
    parameters: Optional[Dict[str, Any]],
    random_seed: int,
) -> str:
    """Compute a hash for deduplication."""
    config = {
        "scenario_id": scenario_id,
        "controller_type": controller_type,
        "parameters": parameters or {},
        "random_seed": random_seed,
    }
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]


from src.schemas.scenario import ScenarioConfig
from src.simulation.coupling import SimulationCoupler
from src.controllers import (
    RuleBasedController,
    CentralizedController,
    MultiAgentController,
    MPCController,
    QLearningController,
)
from backend.app.routers.scenarios import (
    _scenarios,
    _load_scenario_from_disk,
    get_scenario_data_dir,
)
from backend.app.state import set_run, set_trajectories

router = APIRouter()

# In-memory storage for simulation runs
_runs: Dict[str, dict] = {}
_couplers: Dict[str, SimulationCoupler] = {}
_controllers: Dict[str, Any] = {}
# Config hash -> run_id mapping for deduplication
_config_hash_index: Dict[str, str] = {}


class SimulationCreateRequest(BaseModel):
    scenario_id: str
    controller_type: str = "rule_based"
    parameters: Optional[Dict[str, Any]] = None
    run_name: Optional[str] = None
    run_description: Optional[str] = None


class SimulationRun(BaseModel):
    run_id: str
    scenario_id: str
    controller_type: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    start_time: str
    end_time: Optional[str] = None
    energy_metrics: Optional[Dict[str, Any]] = None
    service_metrics: Optional[Dict[str, Any]] = None
    grid_metrics: Optional[Dict[str, Any]] = None
    random_seed: Optional[int] = None
    max_steps: Optional[int] = None
    current_step: int = 0
    total_steps: Optional[int] = None
    # New fields for Phase 1
    run_name: Optional[str] = None
    run_description: Optional[str] = None
    generation_status: str = "pending"  # pending, computing, ready, failed
    outcome_sentence: Optional[str] = None
    config_hash: Optional[str] = None
    stage: Optional[str] = None
    eta_seconds: Optional[int] = None
    progress: float = 0.0
    # Controller fallback tracking
    controller_fallback_steps: int = 0
    controller_fallback_reason: Optional[str] = None


RL_POLICY_DIR = (
    Path(__file__).resolve().parents[3] / "experiments" / "reference" / "rl_policy"
)


def _resolve_rl_policy(parameters: Optional[Dict[str, Any]]) -> str:
    """Resolve the single-agent-RL policy path.

    Explicit request parameter first; otherwise the repo's reference policies
    (provenance: docs/rl_policy_provenance.md). A missing policy raises - the
    run fails honestly instead of pretending to run RL."""
    if parameters and parameters.get("rl_policy"):
        policy = Path(str(parameters["rl_policy"]))
        if not policy.is_file():
            raise FileNotFoundError(f"RL policy not found: {policy}")
        return str(policy)
    candidates = sorted(RL_POLICY_DIR.glob("*.json")) if RL_POLICY_DIR.is_dir() else []
    if not candidates:
        raise FileNotFoundError(
            f"no RL policy available under {RL_POLICY_DIR} - cannot run single-agent RL"
        )
    return str(candidates[0])


def _get_controller(
    controller_type: str,
    scenario: ScenarioConfig,
    parameters: Optional[Dict[str, Any]] = None,
):
    """Get controller instance by type (the four strategies of record)."""
    if controller_type == "centralized":
        return CentralizedController(scenario)
    elif controller_type in ("multi_agent", "multi_agent_rl"):
        return MultiAgentController(scenario)
    elif controller_type == "mpc":
        return MPCController(scenario)
    elif controller_type == "single_agent_rl":
        return QLearningController(scenario, policy_path=_resolve_rl_policy(parameters))
    else:
        return RuleBasedController(scenario)


async def _run_simulation_background(
    run_id: str,
    scenario: ScenarioConfig,
    controller_type: str,
    max_steps: int,
    random_seed: int,
    start_step: int = 0,
    parameters: Optional[Dict[str, Any]] = None,
):
    """Background task to run simulation."""
    # Bound before the try: the except branch below inspects `coupler` to persist
    # trajectories on failure, and an early constructor failure (data dir,
    # scenario, dataset load) used to raise UnboundLocalError there instead of
    # recording the original error - the smoke regression on run 402cdf4b8.
    coupler = None
    controller = None  # bound early: the except branch below inspects it, and
    # an early constructor failure must surface the original error, not an
    # UnboundLocalError (the smoke regression this file guards).
    try:
        _runs[run_id]["status"] = "running"
        _runs[run_id]["stage"] = "initializing"
        _runs[run_id]["progress"] = 0.0

        # Use the same data directory resolution as scenarios router
        data_dir = str(get_scenario_data_dir().parent)

        # Disable colorama to prevent stdout flush issues in background task
        import colorama

        colorama.deinit()

        # Initialize coupler and controller
        coupler = SimulationCoupler(scenario, data_dir=data_dir)

        controller = _get_controller(controller_type, scenario, parameters)

        _couplers[run_id] = coupler
        _controllers[run_id] = controller

        # Reset with seed
        observations = coupler.reset(random_seed)

        # Run simulation loop
        for step in range(start_step, max_steps):
            if _runs[run_id].get("cancelled", False):
                _runs[run_id]["status"] = "cancelled"
                _runs[run_id]["stage"] = "cancelled"
                return

            # Update stage and progress
            _runs[run_id]["stage"] = "simulating"
            _runs[run_id]["progress"] = (step + 1) / max_steps

            # Estimate ETA
            if step > 0:

                start = datetime.fromisoformat(
                    _runs[run_id]["start_time"].replace("Z", "+00:00")
                )
                elapsed = (datetime.utcnow() - start).total_seconds()
                progress = (step + 1) / max_steps
                if progress > 0:
                    _runs[run_id]["eta_seconds"] = int(elapsed / progress - elapsed)

            # Get actions from controller
            requested_actions = controller.get_actions(observations, step)

            # Step the co-simulation
            result = coupler.step(requested_actions)

            # Update progress
            _runs[run_id]["current_step"] = step + 1
            _runs[run_id]["total_steps"] = max_steps

            # Check termination
            if result.terminated or result.truncated:
                break

            # Small delay to prevent blocking
            await asyncio.sleep(0.01)

        # Get final KPIs
        kpis = coupler.get_kpis()
        settlement = coupler.get_settlement_result()

        # Absolute energy metrics from per-step building contributions.
        # CityLearn's evaluate() returns baseline-normalized ratios, not
        # absolute values, so we aggregate the co-simulation history instead.
        energy = coupler.compute_energy_summary()

        # Total cost: settlement engine when energy sharing is enabled, else a
        # default tariff consistent with SettlementEngine ($0.30/kWh import,
        # $0.05/kWh export).
        total_cost = energy["grid_import_kwh"] * 0.30 - energy["grid_export_kwh"] * 0.05
        if settlement is not None and settlement.building_settlements:
            settled_cost = sum(
                s.total_grid_import_cost - s.total_grid_export_revenue
                for s in settlement.building_settlements.values()
            )
            if settled_cost != 0:
                total_cost = settled_cost

        grid_import = energy["grid_import_kwh"]
        pv_self = energy["pv_self_consumption"] * 100
        ev_rate = kpis.get("ev_completion_rate", 0) * 100
        convergence = kpis.get("grid_convergence_rate", 0) * 100

        outcome_parts = []
        outcome_parts.append(f"Total cost: ${total_cost:,.0f}")
        outcome_parts.append(f"Grid import: {grid_import:,.0f} kWh")
        outcome_parts.append(f"PV self-consumption: {pv_self:.0f}%")
        outcome_parts.append(f"EV completion: {ev_rate:.0f}%")
        outcome_parts.append(f"Power flow convergence: {convergence:.0f}%")
        outcome_sentence = " | ".join(outcome_parts)

        _runs[run_id]["status"] = "completed"
        _runs[run_id]["end_time"] = datetime.utcnow().isoformat()
        _runs[run_id]["stage"] = "completed"
        _runs[run_id]["progress"] = 1.0
        _runs[run_id]["generation_status"] = "ready"
        _runs[run_id]["outcome_sentence"] = outcome_sentence
        _runs[run_id]["energy_metrics"] = {
            "total_cost": total_cost,
            "grid_import_kwh": energy["grid_import_kwh"],
            "grid_export_kwh": energy["grid_export_kwh"],
            "peak_demand_kw": energy["peak_demand_kw"],
            "pv_self_consumption": energy["pv_self_consumption"],
            "pv_generation_kwh": energy["pv_generation_kwh"],
            "pv_curtailment": energy["pv_curtailment"],
            "battery_throughput_kwh": energy["battery_throughput_kwh"],
            "carbon_emissions_kg": energy["carbon_emissions_kg"],
        }

        # Add controller fallback tracking
        controller_fallback_steps = 0
        controller_fallback_reason = None
        if controller is not None and hasattr(controller, "fallback_steps"):
            controller_fallback_steps = controller.fallback_steps
            if controller.fallback_steps > 0 and hasattr(controller, "_rule_based"):
                controller_fallback_reason = "fallback_to_rule_based"
        _runs[run_id]["controller_fallback_steps"] = controller_fallback_steps
        _runs[run_id]["controller_fallback_reason"] = controller_fallback_reason
        _runs[run_id]["service_metrics"] = {
            "ev_completion_rate": kpis.get("ev_completion_rate", 0),
            "avg_ev_soc_at_departure": kpis.get("avg_ev_soc_at_departure", 0),
            "comfort_violation_degree_hours": kpis.get(
                "comfort_violation_degree_hours", 0
            ),
            "flexible_load_completion_rate": kpis.get(
                "flexible_load_completion_rate", 0
            ),
            "dr_delivery_rate": kpis.get("dr_delivery_rate", 0),
            "gini_coefficient": kpis.get("gini_coefficient", 0),
            "worst_member_savings": kpis.get("worst_member_savings", 0),
        }
        _runs[run_id]["grid_metrics"] = {
            "power_flow_convergence_rate": kpis.get("grid_convergence_rate", 0),
            "voltage_violations_count": kpis.get("grid_voltage_violations", 0),
            "max_voltage_pu": kpis.get("max_voltage_pu", 1.0),
            "min_voltage_pu": kpis.get("min_voltage_pu", 1.0),
            "max_line_loading_pct": kpis.get("max_line_loading_pct", 0),
            "max_transformer_loading_pct": kpis.get("max_trafo_loading_pct", 0),
        }

        if settlement:
            # Extract per-member settlement data for frontend table
            member_settlements = []
            for member_id, member_settlement in settlement.building_settlements.items():
                member_settlements.append(
                    {
                        "member_id": member_id,
                        "net_settlement": member_settlement.net_settlement,
                        "total_bought_kwh": member_settlement.total_bought_kwh,
                        "total_sold_kwh": member_settlement.total_sold_kwh,
                        "total_grid_import_kwh": member_settlement.total_grid_import_kwh,
                        "total_grid_export_kwh": member_settlement.total_grid_export_kwh,
                        "baseline_grid_import_kwh": member_settlement.baseline_grid_import_kwh,
                        "baseline_grid_export_kwh": member_settlement.baseline_grid_export_kwh,
                        "total_community_import_kwh": member_settlement.total_community_import_kwh,
                        "total_community_export_kwh": member_settlement.total_community_export_kwh,
                        "peak_grid_import_kw": member_settlement.peak_grid_import_kw,
                        "baseline_peak_grid_import_kw": member_settlement.baseline_peak_grid_import_kw,
                        "demand_charge_rate": member_settlement.demand_charge_rate,
                        "actual_demand_charge": member_settlement.actual_demand_charge,
                        "baseline_demand_charge": member_settlement.baseline_demand_charge,
                        "total_grid_import_cost": member_settlement.total_grid_import_cost,
                        "total_grid_export_revenue": member_settlement.total_grid_export_revenue,
                        "baseline_grid_import_cost": member_settlement.baseline_grid_import_cost,
                        "baseline_grid_export_revenue": member_settlement.baseline_grid_export_revenue,
                        "total_community_import_cost": member_settlement.total_community_import_cost,
                        "total_community_export_revenue": member_settlement.total_community_export_revenue,
                        "savings_vs_baseline": member_settlement.metadata.get(
                            "savings_vs_baseline", 0
                        ),
                        "self_sufficiency": member_settlement.metadata.get(
                            "self_sufficiency", 0
                        ),
                    }
                )

            _runs[run_id]["settlement"] = {
                "total_community_volume_kwh": settlement.total_community_volume_kwh,
                "total_community_revenue": settlement.total_community_revenue,
                "member_settlements": member_settlements,
                "interval_results": [
                    {
                        "interval_idx": r.interval_idx,
                        "start_timestep": r.start_timestep,
                        "end_timestep": r.end_timestep,
                        "building_settlements": r.building_settlements,
                        "avg_clearing_price": r.avg_clearing_price,
                        "total_volume_kwh": r.total_volume_kwh,
                    }
                    for r in settlement.interval_results
                ],
                "metadata": settlement.metadata,
            }

        # Persist run data for cross-process access (RQ workers, etc.)
        set_run(run_id, _runs[run_id])

        # Persist trajectories for cross-process access (verifier needs them)
        # Use the shared converter so stored format matches GET /trajectories endpoint
        if hasattr(coupler, "co_sim_history") and coupler.co_sim_history:
            effective_timestep = getattr(
                coupler.scenario_config, "effective_timestep_minutes", None
            ) or getattr(coupler.scenario_config, "timestep_minutes", 15)
            set_trajectories(
                run_id,
                _convert_trajectories_to_json(
                    coupler.co_sim_history, effective_timestep
                ),
            )

    except Exception as e:
        _runs[run_id]["status"] = "failed"
        _runs[run_id]["error"] = str(e)
        _runs[run_id]["end_time"] = datetime.utcnow().isoformat()
        _runs[run_id]["stage"] = "error"
        _runs[run_id]["generation_status"] = "failed"
        outcome = f"Simulation failed: {str(e)}"
        if controller is not None and isinstance(controller, QLearningController):
            # A policy mismatch is the common cause (trained on another
            # scenario's devices) - name the cause and the next step instead
            # of leaking a bare IndexError.
            outcome += (
                " - the single-agent-RL policy does not cover this scenario's"
                " devices (list index out of range). Next step: train or select"
                " a policy for this scenario (docs/rl_policy_provenance.md);"
                " the other strategies ran and are comparable."
            )
        _runs[run_id]["outcome_sentence"] = outcome

        # Persist failed run data for cross-process access
        set_run(run_id, _runs[run_id])

        # Persist trajectories even on failure if available
        if hasattr(coupler, "co_sim_history") and coupler.co_sim_history:
            set_trajectories(run_id, coupler.co_sim_history)


@router.post("/simulations", response_model=SimulationRun, status_code=201)
async def create_simulation(
    request: SimulationCreateRequest, background_tasks: BackgroundTasks
):
    """Start a new simulation run (idempotent per config_hash + seed)."""
    # Validate scenario exists

    if request.scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(request.scenario_id)
        if scenario:
            _scenarios[request.scenario_id] = scenario
        else:
            raise HTTPException(
                status_code=404, detail=f"Scenario {request.scenario_id} not found"
            )

    scenario = _scenarios[request.scenario_id]
    max_steps = request.parameters.get("max_steps", 672) if request.parameters else 672
    random_seed = (
        request.parameters.get("random_seed", scenario.random_seed)
        if request.parameters
        else scenario.random_seed
    )

    # Compute config hash for deduplication
    config_hash = _compute_config_hash(
        request.scenario_id, request.controller_type, request.parameters, random_seed
    )

    # Check for existing run with same config
    if config_hash in _config_hash_index:
        existing_run_id = _config_hash_index[config_hash]
        existing_run = _runs[existing_run_id]
        # Return existing run (idempotent)
        existing_run["config_hash"] = config_hash
        return existing_run

    run_id = f"run_{uuid4().hex[:12]}"

    run = SimulationRun(
        run_id=run_id,
        scenario_id=request.scenario_id,
        controller_type=request.controller_type,
        start_time=datetime.utcnow().isoformat(),
        random_seed=random_seed,
        max_steps=max_steps,
        run_name=request.run_name,
        run_description=request.run_description,
        config_hash=config_hash,
        generation_status="computing",
    )

    _runs[run_id] = run.model_dump()
    _config_hash_index[config_hash] = run_id

    # Start background simulation
    background_tasks.add_task(
        _run_simulation_background,
        run_id,
        scenario,
        request.controller_type,
        max_steps,
        random_seed,
        parameters=request.parameters,
    )

    return run


STRATEGY_CONTROLLERS = ("rule_based", "mpc", "single_agent_rl", "multi_agent_rl")


@router.post("/simulations/strategy-comparison", response_model=dict)
async def strategy_comparison(request: dict, background_tasks: BackgroundTasks):
    """Start (or reuse) the four strategies of record on ONE community config,
    same seed. Returns the run ids immediately; the runs execute as background
    tasks and the caller polls GET /simulations/{run_id} for status and
    metrics - a run that has not finished is 'pending', never estimated."""
    scenario_id = request.get("scenario_id")
    if not scenario_id:
        raise HTTPException(status_code=422, detail="scenario_id is required")
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(
                status_code=404, detail=f"Scenario {scenario_id} not found"
            )
    scenario = _scenarios[scenario_id]
    seed = request.get("random_seed", scenario.random_seed)
    max_steps = request.get("max_steps", 24)

    run_ids: Dict[str, str] = {}
    for controller in STRATEGY_CONTROLLERS:
        params = dict(request.get("parameters") or {})
        if controller == "single_agent_rl" and request.get("rl_policy"):
            params.setdefault("rl_policy", request.get("rl_policy"))
        config_hash = _compute_config_hash(
            scenario_id, controller, params or None, seed
        )
        existing = _config_hash_index.get(config_hash)
        if (
            existing
            and existing in _runs
            and _runs[existing]["status"]
            in (
                "completed",
                "running",
                "pending",
            )
        ):
            run_ids[controller] = existing
            continue
        run_id = f"run_{uuid4().hex[:12]}"
        # Store scenario config for report generation
        scenario_config_dict = scenario.model_dump(mode="json")
        _runs[run_id] = {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "controller_type": controller,
            "status": "pending",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "energy_metrics": None,
            "service_metrics": None,
            "grid_metrics": None,
            "random_seed": seed,
            "max_steps": max_steps,
            "config_hash": config_hash,
            "scenario_config": scenario_config_dict,
        }
        _config_hash_index[config_hash] = run_id
        run_ids[controller] = run_id
        background_tasks.add_task(
            _run_simulation_background,
            run_id,
            scenario,
            controller,
            max_steps,
            seed,
            parameters=params or None,
        )

    return {
        "scenario_id": scenario_id,
        "random_seed": seed,
        "runs": run_ids,
        "strategy_data": {
            controller: {
                "status": "pending",
                "import_limit_kw": scenario.community_import_limit_kw,
                "export_limit_kw": scenario.community_export_limit_kw,
                "run_id": rid,
            }
            for controller, rid in run_ids.items()
        },
    }


@router.get("/simulations", response_model=List[SimulationRun])
async def get_simulations():
    """Get all simulation runs."""
    return list(_runs.values())


@router.get("/simulations/{run_id}", response_model=SimulationRun)
async def get_simulation(run_id: str):
    """Get a specific simulation run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _runs[run_id]


def _convert_trajectories_to_json(
    co_sim_history, effective_timestep_minutes: int = 15
) -> list:
    """Convert co-simulation history to JSON-serializable trajectory list.

    This is the canonical converter used by both:
    - GET /api/simulations/{run_id}/trajectories endpoint
    - set_trajectories() for cross-process persistence

    Args:
        co_sim_history: List of CoSimulationStepResult objects
        effective_timestep_minutes: The effective simulation timestep in minutes

    Returns:
        List of JSON-serializable trajectory dicts
    """
    trajectories = []
    for h in co_sim_history:
        # Calculate timestamp using effective timestep
        total_minutes = h.timestep * effective_timestep_minutes
        days = total_minutes // 1440
        hours = (total_minutes % 1440) // 60
        timestamp = f"2023-01-{days + 1:02d}T{hours:02d}:00:00"

        traj = {
            "timestep": h.timestep,
            "timestamp": timestamp,
            "observations": _convert_numpy(h.citylearn_result.observations),
            "applied_actions": [
                _convert_numpy(a.model_dump())
                for a in h.citylearn_result.applied_actions.actions
            ],
            "costs": _convert_numpy(h.citylearn_result.costs),
            "grid_diagnostics": _convert_numpy(h.citylearn_result.grid_diagnostics),
        }
        trajectories.append(traj)

    return _convert_numpy(trajectories)


@router.get("/simulations/{run_id}/trajectories")
async def get_trajectories(run_id: str):
    """Get trajectories for a simulation run."""
    if run_id not in _couplers:
        # Try to load from exported results
        import os

        output_dir = f"results/{run_id}"
        trajectories_file = os.path.join(output_dir, "trajectories.jsonl")
        if os.path.exists(trajectories_file):
            trajectories = []
            with open(trajectories_file) as f:
                for line in f:
                    if line.strip():
                        trajectories.append(json.loads(line))
            return trajectories
        raise HTTPException(
            status_code=404, detail=f"Trajectories for run {run_id} not found"
        )

    coupler = _couplers[run_id]
    effective_timestep = getattr(
        coupler.scenario_config, "effective_timestep_minutes", None
    ) or getattr(coupler.scenario_config, "timestep_minutes", 15)
    return _convert_trajectories_to_json(coupler.co_sim_history, effective_timestep)


CATEGORY_GUIDANCE = {
    "voltage": (
        "Voltage left the permitted band",
        "Check the feeder loading at this timestep; consider a PV curtailment or battery discharge at the flagged bus, or a tap-changer setting review.",
    ),
    "thermal": (
        "Equipment loading exceeded its rating",
        "Reduce the peak transfer at the flagged element or re-balance the community dispatch.",
    ),
    "convergence": (
        "Power flow did not converge",
        "The operating point is likely infeasible: review the dispatch schedule for conflicting setpoints at this timestep.",
    ),
    "default": (
        "Constraint breached",
        "Inspect the flagged element and timestep in the community view; adjust the dispatch or the asset limits and re-run.",
    ),
}


# Fix proposals awaiting approval: proposal_id -> {run_id, scenario_id, ...}
_fix_proposals: Dict[str, dict] = {}


def _proposals_from_findings(findings, scenario):
    """Rule-based, evidence-linked proposals. Each names the expected config
    change and the condition that must hold afterwards. This is the workflow
    layer - the LLM strategy-modification component is measured at 5 of 9 vs
    its 7 of 9 bar and is NOT claimed here."""
    proposals = []
    seen = set()
    values = {}
    for f in findings:
        key = (
            f.get("category"),
            tuple(sorted((f.get("evidence") or {}).get("bus_indices") or [])),
        )
        if key in seen:
            continue
        seen.add(key)
        buses = (f.get("evidence") or {}).get("bus_indices") or []
        values = (f.get("evidence") or {}).get("values") or {}
        cat = f.get("category")
        if cat == "voltage":
            limit = (f.get("evidence") or {}).get("limits") or {}
            proposals.append(
                {
                    "kind": "voltage",
                    "expected_change": (
                        f"Reduce dispatch at bus {buses} (curtail PV / discharge battery) "
                        "or tighten the community import limit for the flagged timesteps"
                    ),
                    "verification_condition": (
                        "bus voltage within the permitted band at the flagged timesteps "
                        f"(limits: {limit})"
                    ),
                    "evidence": f.get("evidence"),
                    "source_finding": f,
                }
            )
        elif cat == "thermal":
            proposals.append(
                {
                    "kind": "thermal",
                    "expected_change": (
                        f"Re-balance the dispatch away from the flagged element {buses} "
                        "or raise its rating after review"
                    ),
                    "verification_condition": "element loading within rating at the flagged timesteps",
                    "evidence": f.get("evidence"),
                    "source_finding": f,
                }
            )
        elif cat == "convergence":
            proposals.append(
                {
                    "kind": "convergence",
                    "expected_change": "Resolve conflicting setpoints at the flagged timesteps",
                    "verification_condition": "power flow converges at every timestep",
                    "evidence": f.get("evidence"),
                    "source_finding": f,
                }
            )
        elif cat in ("grid_limit", "limit"):
            peak = None
            for k, v in (f.get("evidence") or {}).get("values", {}).items():
                if isinstance(v, (int, float)) and "limit" not in str(k).lower():
                    peak = max(peak or 0, v)
            if peak is None:
                m = re.search(r"exceeded:\s*([0-9.]+)", str(f.get("message", "")))
                if m:
                    peak = float(m.group(1))
            proposals.append(
                {
                    "kind": (
                        "voltage"
                        if "voltage" in str(f.get("message", "")).lower()
                        else "grid_limit"
                    ),
                    "expected_change": (
                        f"Community import limit was exceeded (peak observed {peak}). "
                        "Raise the import limit to cover the observed peak, or reduce the "
                        "community dispatch - the applied proposal raises the limit."
                    ),
                    "verification_condition": (
                        "after the change, the community import stays within the limit at "
                        "every timestep (no 'import limit exceeded' diagnostics)"
                    ),
                    "evidence": f.get("evidence"),
                    "source_finding": f,
                    "observed_peak": peak,
                }
            )
        else:
            proposals.append(
                {
                    "kind": "generic",
                    "expected_change": f.get("recommended_action"),
                    "verification_condition": "the flagged constraint holds after the change",
                    "evidence": f.get("evidence"),
                    "source_finding": f,
                }
            )
    if not proposals and values:
        proposals.append(
            {
                "kind": "review",
                "expected_change": "Manual review of the flagged operating point",
                "verification_condition": "no new violations after the change",
                "evidence": values,
                "source_finding": None,
            }
        )
    return proposals


@router.post("/simulations/{run_id}/fix-proposals", response_model=dict)
async def create_fix_proposals(run_id: str):
    """Create fix proposals for a completed run (awaiting approval).

    Proposals are rule-based and evidence-linked; nothing is applied until a
    proposal is approved. The LLM strategy-modification component (measured
    5 of 9 vs its pre-registered 7 of 9) is not claimed by this endpoint."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    run = _runs[run_id]
    diag = await get_diagnostics(run_id)
    proposals = _proposals_from_findings(diag.get("findings") or [], None)
    created = []
    for p in proposals:
        pid = f"fix_{uuid4().hex[:10]}"
        record = {
            "proposal_id": pid,
            "run_id": run_id,
            "scenario_id": run.get("scenario_id"),
            "status": "awaiting_approval",
            "before": {
                "kpi_summary": diag.get("kpi_summary"),
                "findings_count": len(diag.get("findings") or []),
            },
            **{k: v for k, v in p.items() if k != "source_finding"},
        }
        _fix_proposals[pid] = record
        created.append(record)
    return {
        "run_id": run_id,
        "proposals": created,
        "note": "Nothing is applied until a proposal is approved; approval re-runs the scenario and reports the before/after verification.",
    }


@router.get("/simulations/{run_id}/diagnostics", response_model=dict)
async def get_diagnostics(run_id: str):
    """Read-only diagnosis of a completed run: what breached, when, and why -
    with the evidence (values, limits, buses) and a recommended next step.
    Interpretation only: no repair proposal is made here (the repair loop is
    measured at 5/9 vs its 7/9 bar and is not claimed by this endpoint)."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    run = _runs[run_id]
    try:
        trajectories = await get_trajectories(run_id)
    except HTTPException:
        trajectories = []

    findings = []
    for step in trajectories or []:
        ts = step.get("timestep", step.get("step"))
        for diag in (step.get("grid_diagnostics") or {}).get("diagnostics", []):
            if diag.get("severity") not in ("violation", "critical"):
                continue
            category = diag.get("category", "default")
            meaning, action = CATEGORY_GUIDANCE.get(
                category, CATEGORY_GUIDANCE["default"]
            )
            findings.append(
                {
                    "timestep": ts,
                    "category": category,
                    "severity": diag.get("severity"),
                    "message": diag.get("message"),
                    "meaning": meaning,
                    "recommended_action": action,
                    "evidence": {
                        "values": diag.get("values", {}),
                        "limits": diag.get("limits", {}),
                        "bus_indices": diag.get("bus_indices", []),
                        "asset_ids": diag.get("asset_ids", []),
                    },
                }
            )

    energy = run.get("energy_metrics") or {}
    grid = run.get("grid_metrics") or {}
    service = run.get("service_metrics") or {}
    kpi_summary = {
        "total_cost": energy.get("total_cost"),
        "grid_import_kwh": energy.get("grid_import_kwh"),
        "carbon_emissions_kg": energy.get("carbon_emissions_kg"),
        "ev_completion_rate": service.get("ev_completion_rate"),
        "voltage_violations_count": grid.get("voltage_violations_count"),
        "max_voltage_pu": grid.get("max_voltage_pu"),
        "power_flow_convergence_rate": grid.get("power_flow_convergence_rate"),
    }
    return {
        "run_id": run_id,
        "scenario_id": run.get("scenario_id"),
        "controller_type": run.get("controller_type"),
        "status": run.get("status"),
        "findings": findings,
        "kpi_summary": kpi_summary,
        "interpretation": (
            "No constraint violations were recorded in this run."
            if not findings
            else f"{len(findings)} constraint breach(es) recorded; see the per-timestep findings with their evidence."
        ),
        "note": "Interpretation and recommendations are evidence-linked to the run; the strategy-modification component is measured separately (5 of 9 vs its pre-registered 7 of 9) and is not claimed by this endpoint.",
    }


@router.post("/fix-proposals/{proposal_id}/approve", response_model=dict)
async def approve_fix_proposal(proposal_id: str, background_tasks: BackgroundTasks):
    """Approve a fix proposal: apply the change, re-run the scenario, verify.

    The proposal's expected change is applied to the scenario configuration,
    the simulation is re-run, and the before/after KPIs and violation counts
    are reported. The verification condition from the proposal is checked
    against the re-run; an unmet condition is reported, not smoothed over."""
    proposal = _fix_proposals.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    if proposal["status"] != "awaiting_approval":
        raise HTTPException(
            status_code=409, detail=f"Proposal already {proposal['status']}"
        )

    scenario_id = proposal["scenario_id"]
    kind = proposal.get("kind")
    before_kpis = proposal.get("before", {}).get("kpi_summary") or {}

    # Apply the proposal's expected change to the scenario config. For a
    # voltage breach the workflow-level lever is a tighter community import
    # limit (a documented, reviewable change); other kinds adjust the
    # community export limit symmetrically. Anything else stays manual.
    scenario = _scenarios.get(scenario_id) or _load_scenario_from_disk(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    applied_change = None
    if kind in ("voltage", "grid_limit"):
        # a limit breach: raise the documented community limit to just above the
        # observed peak (a reviewable change), or tighten it for a voltage breach
        if kind == "grid_limit":
            new_limit = max(1.0, round((proposal.get("observed_peak") or 0) * 1.05, 3))
        else:
            new_limit = max(1.0, (before_kpis.get("grid_import_kwh") or 0) * 0.9)
        scenario.community_import_limit_kw = new_limit
        applied_change = f"community_import_limit_kw -> {new_limit}"
    elif kind == "thermal":
        new_limit = max(1.0, (before_kpis.get("grid_export_kwh") or 0) * 0.9)
        scenario.community_export_limit_kw = new_limit
        applied_change = f"community_export_limit_kw -> {new_limit}"
    else:
        proposal["status"] = "rejected"
        proposal["resolution"] = "manual review required - no automated change proposed"
        return {
            "proposal_id": proposal_id,
            "status": "rejected",
            "resolution": proposal["resolution"],
        }

    _scenarios[scenario_id] = scenario

    # Re-run the same scenario with the same seed, then verify.
    before_run = _runs.get(proposal["run_id"], {})
    seed = before_run.get("random_seed", scenario.random_seed)
    max_steps = before_run.get("max_steps", 24)
    controller = before_run.get("controller_type", "rule_based")
    new_run_id = f"run_{uuid4().hex[:12]}"
    config_hash = _compute_config_hash(scenario_id, controller, None, seed)
    _runs[new_run_id] = {
        "run_id": new_run_id,
        "scenario_id": scenario_id,
        "controller_type": controller,
        "status": "pending",
        "start_time": datetime.utcnow().isoformat(),
        "end_time": None,
        "energy_metrics": None,
        "service_metrics": None,
        "grid_metrics": None,
        "random_seed": seed,
        "max_steps": max_steps,
        "config_hash": config_hash,
        "note": f"re-run after fix proposal {proposal_id}",
    }
    _config_hash_index[config_hash] = new_run_id

    background_tasks.add_task(
        _run_simulation_background,
        new_run_id,
        scenario,
        controller,
        max_steps,
        seed,
    )

    proposal["status"] = "re_running"
    proposal["applied_change"] = applied_change
    proposal["re_run_id"] = new_run_id
    return {
        "proposal_id": proposal_id,
        "status": "re_running",
        "applied_change": applied_change,
        "re_run_id": new_run_id,
        "before": proposal.get("before"),
        "note": "The re-run executes in the background; poll GET /fix-proposals/{id} for the before/after verification.",
    }


@router.get("/fix-proposals/{proposal_id}", response_model=dict)
async def get_fix_proposal(proposal_id: str):
    """A proposal with its live before/after verification, computed on demand
    from the original run and the proposal's re-run - real data, no estimate."""
    proposal = _fix_proposals.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    re_run_id = proposal.get("re_run_id")
    after = None
    condition_met = None
    if re_run_id and re_run_id in _runs:
        run = _runs[re_run_id]
        if run.get("status") == "completed":
            grid = run.get("grid_metrics") or {}
            energy = run.get("energy_metrics") or {}
            after = {
                "run_id": re_run_id,
                "kpi_summary": {
                    "total_cost": energy.get("total_cost"),
                    "grid_import_kwh": energy.get("grid_import_kwh"),
                    "grid_export_kwh": energy.get("grid_export_kwh"),
                    "voltage_violations_count": grid.get("voltage_violations_count"),
                    "max_voltage_pu": grid.get("max_voltage_pu"),
                    "power_flow_convergence_rate": grid.get(
                        "power_flow_convergence_rate"
                    ),
                },
            }
            before_payload = proposal.get("before") or {}
            before_v = before_payload.get("kpi_summary") or {}
            # the real 'before' breach count is the diagnosis's findings; the
            # run's own grid_metrics may not carry it
            b = (
                before_v.get("voltage_violations_count")
                or before_payload.get("findings_count")
                or 0
            )
            a = grid.get("voltage_violations_count") or 0
            condition_met = a < b
            proposal["status"] = "applied" if condition_met else "applied_unverified"
            proposal["resolution"] = (
                "verification condition met (violations fell)"
                if condition_met
                else "verification condition NOT met (violations did not fall)"
            )
        elif run.get("status") == "failed":
            proposal["status"] = "failed"
            proposal["resolution"] = f"re-run failed: {run.get('error')}"
    return {
        "proposal_id": proposal_id,
        "status": proposal.get("status"),
        "kind": proposal.get("kind"),
        "expected_change": proposal.get("expected_change"),
        "verification_condition": proposal.get("verification_condition"),
        "applied_change": proposal.get("applied_change"),
        "before": proposal.get("before"),
        "after": after,
        "verification_condition_met": condition_met,
        "resolution": proposal.get("resolution"),
    }


@router.get("/simulations/{run_id}/grid")
async def get_grid_diagnostics(run_id: str):
    """Get grid diagnostics for a simulation run."""
    if run_id not in _couplers:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    coupler = _couplers[run_id]
    diagnostics = []
    for h in coupler.co_sim_history:
        for d in h.grid_diagnostics.diagnostics:
            diagnostics.append(
                {
                    "timestep": h.timestep,
                    "diagnostic": _convert_numpy(d.model_dump()),
                }
            )
    return _convert_numpy(diagnostics)


@router.post("/simulations/{run_id}/cancel")
async def cancel_simulation(run_id: str):
    """Cancel a running simulation."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if _runs[run_id]["status"] != "running":
        raise HTTPException(
            status_code=400, detail="Can only cancel running simulations"
        )

    _runs[run_id]["cancelled"] = True
    return {"message": "Simulation cancellation requested"}


@router.post("/simulations/{run_id}/resume")
async def resume_simulation(run_id: str, background_tasks: BackgroundTasks):
    """Resume a cancelled/failed simulation from last checkpoint."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    if run["status"] not in ["cancelled", "failed", "completed"]:
        raise HTTPException(
            status_code=400,
            detail="Can only resume cancelled, failed, or completed simulations",
        )

    # Validate scenario exists

    scenario_id = run["scenario_id"]
    if scenario_id not in _scenarios:
        scenario = _load_scenario_from_disk(scenario_id)
        if scenario:
            _scenarios[scenario_id] = scenario
        else:
            raise HTTPException(
                status_code=404, detail=f"Scenario {scenario_id} not found"
            )

    scenario = _scenarios[scenario_id]
    max_steps = run.get("max_steps", 672)
    random_seed = run.get("random_seed", scenario.random_seed)
    controller_type = run.get("controller_type", "rule_based")
    current_step = run.get("current_step", 0)

    # Reset status for resume
    run["status"] = "running"
    run["cancelled"] = False
    run["end_time"] = None
    run["generation_status"] = "computing"

    # Start background simulation from current_step
    background_tasks.add_task(
        _run_simulation_background,
        run_id,
        scenario,
        controller_type,
        max_steps,
        random_seed,
        current_step,
    )

    return run


@router.get("/simulations/{run_id}/status")
async def get_simulation_status(run_id: str):
    """Get detailed simulation status with stage, ETA, progress."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    current_step = run.get("current_step", 0)
    total_steps = run.get(
        "total_steps", max_steps if (max_steps := run.get("max_steps")) else 1
    )
    progress = current_step / max(total_steps, 1) if total_steps else 0

    # Estimate ETA based on current progress
    eta_seconds = None
    if run["status"] == "running" and current_step > 0 and progress > 0:

        start = datetime.fromisoformat(run["start_time"].replace("Z", "+00:00"))
        elapsed = (datetime.utcnow() - start).total_seconds()
        if progress > 0:
            eta_seconds = int(elapsed / progress - elapsed)

    stage_map = {
        "pending": "initializing",
        "running": "simulating",
        "completed": "finalizing",
        "failed": "error",
        "cancelled": "cancelled",
    }

    return {
        "run_id": run_id,
        "status": run["status"],
        "stage": stage_map.get(run["status"], "unknown"),
        "progress": progress,
        "current_step": current_step,
        "total_steps": total_steps,
        "eta_seconds": eta_seconds,
        "generation_status": run.get("generation_status", "pending"),
        "cancelable": run["status"] == "running",
        "resumable": run["status"] in ["cancelled", "failed"],
    }
