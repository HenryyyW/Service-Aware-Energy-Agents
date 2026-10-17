import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"


def load_experiment_results(results_dir: Path) -> list[dict]:
    runs = []
    for result_file in results_dir.rglob("result.json"):
        try:
            with result_file.open(encoding="utf-8") as file:
                result = json.load(file)
            runs.append({
                "run_id": result.get("run_id", result_file.parent.name),
                "scenario_id": result.get("scenario_id", ""),
                "controller_type": str(result.get("controller_type", "")),
                "status": result.get("status", ""),
                "start_time": result.get("start_time", ""),
                "result": result,
                "path": result_file.parent,
            })
        except (OSError, json.JSONDecodeError) as error:
            st.warning(f"Could not load {result_file}: {error}")
    return runs


def load_trajectories(run_path: Path) -> list[dict] | None:
    trajectory_file = run_path / "trajectories.jsonl"
    if not trajectory_file.exists():
        return None

    rows = []
    try:
        with trajectory_file.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as error:
        st.error(f"Could not read trajectories: {error}")
        return None
    return rows


def load_scenario_config(scenario_id: str) -> dict | None:
    scenario_file = CONFIGS_DIR / f"{scenario_id}.yaml"
    if scenario_file.exists():
        with scenario_file.open(encoding="utf-8") as file:
            return yaml.safe_load(file)
    return None


def get_building_ids(scenario_config: dict | None, trajectory: dict) -> list[str]:
    if scenario_config and scenario_config.get("buildings"):
        return [building["building_id"] for building in scenario_config["buildings"]]

    observations = trajectory.get("observations", {})
    if isinstance(observations, dict):
        return sorted({key.split("_", 1)[0] for key in observations if key.startswith("building_")})
    return []


def expand_trajectories(steps: list[dict], building_ids: list[str]) -> pd.DataFrame:
    """Turn timestep records with flattened observations into one row per building."""
    rows = []
    for step in steps:
        observations = step.get("observations", {})
        costs = step.get("costs", {})
        actions_by_building: dict[str, dict[str, float]] = {
            building_id: {
                "battery_power_kw": 0.0,
                "ev_charge_kw": 0.0,
                "flexible_load_kw": 0.0,
            }
            for building_id in building_ids
        }

        for action in step.get("applied_actions", []):
            asset_id = action.get("asset_id", "")
            building_id = next(
                (candidate for candidate in building_ids if asset_id.startswith(candidate + "_")),
                None,
            )
            if building_id is None:
                continue
            action_type = action.get("action_type")
            if action_type in ("battery_charge", "battery_discharge"):
                column = "battery_power_kw"
            elif action_type == "ev_charge":
                column = "ev_charge_kw"
            elif action_type == "flexible_load":
                column = "flexible_load_kw"
            else:
                continue
            actions_by_building[building_id][column] += float(action.get("value_kw", 0.0))

        for building_id in building_ids:
            prefix = f"{building_id}_"
            row = {
                "timestep": int(step.get("timestep", 0)),
                "building_id": building_id,
                "cost": float(costs.get(building_id, 0.0)),
            }
            row.update({
                key[len(prefix):]: value
                for key, value in observations.items()
                if key.startswith(prefix)
            })
            row.update(actions_by_building[building_id])
            rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="Energy Community", layout="wide")
    st.title("Service-Aware Energy Agents")

    if not RESULTS_DIR.exists():
        st.error(f"Results directory not found: {RESULTS_DIR}")
        st.stop()

    runs = load_experiment_results(RESULTS_DIR)
    if not runs:
        st.error("No experiment runs found in results/.")
        st.stop()

    runs.sort(key=lambda run: run.get("start_time", ""), reverse=True)
    run_options = {
        f"{run['run_id']} · {run['scenario_id']} · {run['controller_type']}": run
        for run in runs
    }
    selected_run = st.selectbox("Experiment run", options=list(run_options), index=0)
    run = run_options[selected_run]
    result = run["result"]

    overview = st.columns(5)
    overview[0].metric("Run", run["run_id"])
    overview[1].metric("Status", run["status"])
    overview[2].metric("Total cost", f"${result.get('energy', {}).get('total_cost', 0):,.2f}")
    overview[3].metric("Grid import", f"{result.get('energy', {}).get('grid_import_kwh', 0):,.1f} kWh")
    overview[4].metric("Peak demand", f"{result.get('energy', {}).get('peak_demand_kw', 0):,.2f} kW")

    raw_steps = load_trajectories(run["path"])
    if not raw_steps:
        st.error("No trajectory records found for this run.")
        st.stop()

    scenario_config = load_scenario_config(run["scenario_id"])
    building_ids = get_building_ids(scenario_config, raw_steps[0])
    trajectory = expand_trajectories(raw_steps, building_ids)
    if trajectory.empty:
        st.error("Could not extract building observations from trajectory records.")
        st.stop()

    timestep = st.slider(
        "Timestep",
        min_value=int(trajectory["timestep"].min()),
        max_value=int(trajectory["timestep"].max()),
        value=int(trajectory["timestep"].min()),
    )
    timestep_rows = trajectory[trajectory["timestep"] == timestep]
    selected_building = st.selectbox("Building", options=building_ids)
    building_row = timestep_rows[timestep_rows["building_id"] == selected_building]

    spatial_tab, temporal_tab, diagnostics_tab = st.tabs(["Spatial", "Temporal", "Grid diagnostics"])
    with spatial_tab:
        map_col, detail_col = st.columns([1.35, 1])
        with map_col:
            st.subheader("Community locations")
            locations = []
            for building in (scenario_config or {}).get("buildings", []):
                location = building.get("location") or {}
                if location.get("lat") is not None and location.get("lon") is not None:
                    locations.append({
                        "building_id": building["building_id"],
                        "lat": float(location["lat"]),
                        "lon": float(location["lon"]),
                    })
            if locations:
                st.map(pd.DataFrame(locations), latitude="lat", longitude="lon", size=80)
                st.dataframe(pd.DataFrame(locations), hide_index=True, use_container_width=True)
            else:
                st.info("This scenario has no building coordinates to map.")

        with detail_col:
            st.subheader(f"{selected_building} · timestep {timestep}")
            if not building_row.empty:
                st.dataframe(
                    building_row.drop(columns=["timestep", "building_id"]).T.rename(columns={building_row.index[0]: "value"}),
                    use_container_width=True,
                )
            else:
                st.info("No observations for this building at the selected timestep.")

    with temporal_tab:
        st.subheader("Building time series")
        preferred_metrics = [
            "net_electricity_consumption",
            "solar_generation",
            "electrical_storage_soc",
            "connected_electric_vehicle_at_charger_soc",
            "indoor_dry_bulb_temperature",
            "battery_power_kw",
            "ev_charge_kw",
            "cost",
        ]
        numeric_columns = [
            column for column in trajectory.columns
            if column not in {"timestep", "building_id"}
            and pd.api.types.is_numeric_dtype(trajectory[column])
        ]
        metric_options = [column for column in preferred_metrics if column in numeric_columns]
        metric_options.extend(column for column in numeric_columns if column not in metric_options)
        metric = st.selectbox("Metric", options=metric_options)
        chart_data = trajectory.pivot(index="timestep", columns="building_id", values=metric)
        if selected_building in chart_data.columns:
            st.line_chart(chart_data[[selected_building]])
        else:
            st.line_chart(chart_data)

    with diagnostics_tab:
        st.subheader(f"Grid diagnostics · timestep {timestep}")
        selected_step = next((step for step in raw_steps if step.get("timestep") == timestep), {})
        diagnostics = selected_step.get("grid_diagnostics") or {}
        st.json(diagnostics if diagnostics else {"diagnostics": "No grid diagnostics recorded for this timestep."})

    st.caption(
        f"Scenario {run['scenario_id']} · {len(raw_steps)} recorded steps · "
        f"seed {result.get('random_seed', 'unknown')}"
    )


main()
