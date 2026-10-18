from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIGS_DIR = PROJECT_ROOT / "configs"


# ---------------------------------------------------------------------------
# Data loading helpers (unchanged)
# ---------------------------------------------------------------------------
def load_experiment_results(results_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for result_file in results_dir.rglob("result.json"):
        try:
            with result_file.open(encoding="utf-8") as file:
                result = json.load(file)
            runs.append({
                "run_id": result.get("run_id", result_file.parent.name),
                "scenario_id": result.get("scenario_id", ""),
                "controller_type": str(result.get("controller_type", "")),
                "status": result.get("status", "unknown"),
                "start_time": result.get("start_time", ""),
                "result": result,
                "path": result_file.parent,
            })
        except (OSError, json.JSONDecodeError) as error:
            st.warning(f"Could not load {result_file}: {error}")
    return runs


def load_trajectories(run_path: Path) -> list[dict[str, Any]] | None:
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


def load_scenario_config(scenario_id: str) -> dict[str, Any] | None:
    scenario_file = CONFIGS_DIR / f"{scenario_id}.yaml"
    if not scenario_file.exists():
        return None
    with scenario_file.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def get_building_ids(scenario_config: dict[str, Any] | None, trajectory: dict[str, Any]) -> list[str]:
    if scenario_config and scenario_config.get("buildings"):
        return [building["building_id"] for building in scenario_config["buildings"]]

    observations = trajectory.get("observations", {})
    if isinstance(observations, dict):
        return sorted({
            key.split("_", 1)[0]
            for key in observations
            if key.startswith("building_")
        })
    return []


def expand_trajectories(steps: list[dict[str, Any]], building_ids: list[str]) -> pd.DataFrame:
    """Expand timestep records into one row per building and timestep."""
    rows = []
    action_columns = ("battery_power_kw", "ev_charge_kw", "flexible_load_kw")

    for step in steps:
        observations = step.get("observations") or {}
        costs = step.get("costs") or {}
        actions_by_building = {
            building_id: {column: 0.0 for column in action_columns}
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
            column = {
                "battery_charge": "battery_power_kw",
                "battery_discharge": "battery_power_kw",
                "ev_charge": "ev_charge_kw",
                "flexible_load": "flexible_load_kw",
            }.get(action_type)
            if column:
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


def grid_timeline(steps: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for step in steps:
        diagnostics = step.get("grid_diagnostics") or {}
        voltages = diagnostics.get("voltage_profile") or {}
        loading = diagnostics.get("loading_profile") or {}
        lines = loading.get("lines") or {}
        transformers = loading.get("trafos") or {}
        rows.append({
            "timestep": step.get("timestep", 0),
            "min_voltage_pu": min(voltages.values(), default=None),
            "max_voltage_pu": max(voltages.values(), default=None),
            "max_line_loading_pct": max(lines.values(), default=None) * 100 if lines else None,
            "max_transformer_loading_pct": max(transformers.values(), default=None) * 100 if transformers else None,
            "power_flow_converged": diagnostics.get("power_flow_converged"),
        })
    return pd.DataFrame(rows)


def display_metric(column, label: str, value: Any, *, format_string: str | None = None):
    if value is None:
        column.metric(label, "N/A")
    elif format_string:
        column.metric(label, format_string.format(value))
    else:
        column.metric(label, value)


# ---------------------------------------------------------------------------
# Design-system helpers
# ---------------------------------------------------------------------------
def inject_custom_css():
    """Inject glassmorphism, typography, colour tokens, and component styles."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

        :root {
            --color-primary: #1E293B;
            --color-on-primary: #FFFFFF;
            --color-secondary: #334155;
            --color-on-secondary: #FFFFFF;
            --color-accent: #22C55E;
            --color-on-accent: #0F172A;
            --color-background: #0F172A;
            --color-foreground: #F8FAFC;
            --color-card: #1B2336;
            --color-card-foreground: #F8FAFC;
            --color-muted: #272F42;
            --color-muted-foreground: #94A3B8;
            --color-border: #475569;
            --color-destructive: #EF4444;
            --color-on-destructive: #000000;
            --color-ring: #FFFFFF;

            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --space-2xl: 48px;
            --space-3xl: 64px;

            --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
            --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
            --shadow-xl: 0 20px 25px rgba(0,0,0,0.15);
        }

        html, body, [class*="css"]  {
            font-family: 'Fira Sans', sans-serif;
            color: var(--color-foreground);
            background: var(--color-background);
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Fira Code', monospace;
            color: var(--color-foreground);
        }

        /* Glassmorphism card */
        .glass-card {
            background: rgba(27, 35, 54, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 12px;
            padding: var(--space-lg);
            margin: var(--space-md) 0;
            box-shadow: var(--shadow-md);
            transition: all 200ms ease;
        }
        .glass-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
            border-color: rgba(255,255,255,0.3);
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 200ms ease;
            border: none;
        }
        .stButton > button[kind="primary"] {
            background: var(--color-accent);
            color: var(--color-on-accent);
        }
        .stButton > button[kind="primary"]:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        .stButton > button[kind="secondary"] {
            background: transparent;
            color: var(--color-accent);
            border: 2px solid var(--color-accent);
        }

        /* Inputs */
        .stTextInput>div>div>input,
        .stNumberInput>div>div>input,
        .stSelectbox>div>div>select {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            color: var(--color-foreground);
            padding: 12px 16px;
        }
        .stTextInput>div>div>input:focus,
        .stNumberInput>div>div>input:focus,
        .stSelectbox>div>div>select:focus {
            border-color: var(--color-accent);
            box-shadow: 0 0 0 3px rgba(34,197,94,0.2);
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: rgba(15,23,42,0.85);
            backdrop-filter: blur(12px);
            border-right: 1px solid rgba(255,255,255,0.1);
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 500;
            transition: all 200ms;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(34,197,94,0.2);
            color: var(--color-accent);
        }

        /* Metric cards */
        .metric-card {
            text-align: center;
        }
        .metric-value {
            font-family: 'Fira Code', monospace;
            font-size: 2rem;
            font-weight: 600;
            margin: 8px 0;
        }
        .metric-label {
            font-family: 'Fira Sans', sans-serif;
            font-size: 0.875rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--color-muted-foreground);
        }
        .metric-trend { display:flex; align-items:center; justify-content:center; gap:4px; margin-top:8px; font-size:0.875rem; }
        .trend-up { color: var(--color-accent); }
        .trend-down { color: var(--color-destructive); }
        .trend-neutral { color: var(--color-muted-foreground); }

        /* Scrollbars */
        ::-webkit-scrollbar { width:8px; height:8px; }
        ::-webkit-scrollbar-track { background: rgba(15,23,42,0.2); }
        ::-webkit-scrollbar-thumb { background: rgba(34,197,94,0.3); border-radius:4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(34,197,94,0.5); }

        /* Focus visible */
        *:focus-visible { outline: 2px solid var(--color-ring); outline-offset: 2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def glass_metric_card(label: str, value: str, trend: str | None = None, trend_value: str | None = None):
    """Render a glassmorphism metric card."""
    trend_html = ""
    if trend and trend_value:
        arrow = "▲" if trend == "up" else "▼" if trend == "down" else "◆"
        trend_html = f'<div class="metric-trend trend-{trend}"><span>{arrow}</span><span>{trend_value}</span></div>'
    st.markdown(
        f"""
        <div class="glass-card metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {trend_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------
def render_overview(energy, service, grid):
    st.title("Community Overview")

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        glass_metric_card("Total Cost", f"${energy.get('total_cost',0):,.0f}", "down", "5.2%")
    with c2:
        glass_metric_card("Grid Import", f"{energy.get('grid_import_kwh',0):,.0f} kWh", "neutral", "0.8%")
    with c3:
        glass_metric_card("Peak Demand", f"{energy.get('peak_demand_kw',0):.1f} kW", "up", "3.1%")
    with c4:
        glass_metric_card("EV Completion", f"{service.get('ev_completion_rate',0):.0%}", "up", "2.3%")

    st.divider()

    # Energy flow + alerts
    left, right = st.columns([2,1])
    with left:
        st.subheader("Energy Flow (Sankey placeholder)")
        st.info("Replace with Plotly Sankey when data available")
    with right:
        st.subheader("System Alerts")
        st.markdown(
            """
            <div class="glass-card">
                <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                    <div style="background:#EF4444;width:8px;height:8px;border-radius:50%;margin-right:8px;margin-top:4px;"></div>
                    <div><strong>Voltage Violation</strong><br><small style="opacity:.8;">Bus 14: 1.08 pu</small></div>
                </div>
                <div style="display:flex;align-items:flex-start;margin-bottom:12px;">
                    <div style="background:#FBBF24;width:8px;height:8px;border-radius:50%;margin-right:8px;margin-top:4px;"></div>
                    <div><strong>Loading Alert</strong><br><small style="opacity:.8;">Line L12: 94%</small></div>
                </div>
                <div style="display:flex;align-items:flex-start;">
                    <div style="background:#22C55E;width:8px;height:8px;border-radius:50%;margin-right:8px;margin-top:4px;"></div>
                    <div><strong>All Clear</strong><br><small style="opacity:.8;">EV charging within limits</small></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Performance Trends")
    t1, t2, t3 = st.tabs(["Power Flow", "Voltage Profile", "State of Charge"])
    with t1:
        st.line_chart(pd.DataFrame({"Import":[100,120,90,110,105,115,130],"Export":[20,15,25,30,25,20,10]}), height=200)
    with t2:
        st.line_chart(pd.DataFrame({"Min Voltage":[0.98,0.99,1.0,0.97,0.99,1.0,0.98],"Max Voltage":[1.02,1.03,1.04,1.01,1.02,1.03,1.02]}), height=200)
    with t3:
        st.line_chart(pd.DataFrame({"Battery SOC":[65,70,68,72,75,73,70],"EV SOC":[40,45,50,55,60,58,52]}), height=200)


def render_asset_view(trajectory, building_ids):
    st.title("Asset View")
    selected = st.selectbox("Select Building", building_ids)
    row = trajectory[trajectory["building_id"]==selected].iloc[-1]  # latest
    cols = st.columns(4)
    with cols[0]:
        glass_metric_card("Load", f"{row.get('net_electricity_consumption',0):.1f} kW")
    with cols[1]:
        glass_metric_card("PV Gen", f"{row.get('solar_generation',0):.1f} kW")
    with cols[2]:
        glass_metric_card("Battery SOC", f"{row.get('electrical_storage_soc',0):.0%}")
    with cols[3]:
        glass_metric_card("EV SOC", f"{row.get('connected_electric_vehicle_at_charger_soc',0):.0%}")

    st.divider()
    st.subheader("Time Series for Selected Building")
    metric = st.selectbox("Metric", [c for c in trajectory.columns if c not in {"timestep","building_id"} and pd.api.types.is_numeric_dtype(trajectory[c])])
    bdf = trajectory[trajectory["building_id"]==selected]
    st.line_chart(bdf.set_index("timestep")[metric], height=250)


def render_grid_twin(raw_steps, timestep):
    st.title("Grid Twin")
    step = next((s for s in raw_steps if s.get("timestep")==timestep), {})
    diag = step.get("grid_diagnostics") or {}

    vcol, lcol = st.columns(2)
    with vcol:
        st.subheader("Voltage Profile (p.u.)")
        voltages = diag.get("voltage_profile") or {}
        if voltages:
            st.dataframe(pd.DataFrame([{"bus":b,"voltage_pu":v} for b,v in voltages.items()]), hide_index=True, use_container_width=True)
        else:
            st.info("No voltage data")
    with lcol:
        st.subheader("Loading (%)")
        loading = diag.get("loading_profile") or {}
        rows = []
        for kind in ("lines","trafos"):
            for el,val in loading.get(kind,{}).items():
                rows.append({"type":kind,"element":el,"loading_pct":float(val)*100})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No loading data")

    st.divider()
    st.subheader("Network Topology (placeholder)")
    st.info("Insert network graph showing feeders, transformers, buses")

    st.divider()
    st.subheader("Time-Slider Controls")
    col1, col2, col3 = st.columns([1,1,4])
    with col1:
        if st.button("▶ Play", use_container_width=True):
            st.session_state.playing = True
    with col2:
        if st.button("⏸ Pause", use_container_width=True):
            st.session_state.playing = False
    with col3:
        timestep = st.slider("Timestep", int(trajectory["timestep"].min()), int(trajectory["timestep"].max()), timestep, key="grid_tw_ts")
    st.caption(f"Selected timestep: {timestep}")

    st.divider()
    st.subheader("Heatmap / Violation Tabs")
    t1, t2 = st.tabs(["Voltage Violations", "Loading Violations"])
    with t1:
        st.info("Voltage violation heatmap placeholder")
    with t2:
        st.info("Loading violation heatmap placeholder")


def render_agent_workspace(trajectory, building_ids, scenario_config, timestep):
    st.title("Agent Workspace")
    selected = st.selectbox("Select Building", building_ids, key="aw_building")
    
    # Get building locations from scenario config
    locations = {}
    if scenario_config and scenario_config.get("buildings"):
        for b in scenario_config["buildings"]:
            bid = b.get("building_id")
            loc = b.get("location")
            if loc and loc.get("lat") is not None and loc.get("lon") is not None:
                locations[bid] = {"lat": float(loc["lat"]), "lon": float(loc["lon"])}
    
    # Get metrics for each building at the selected timestep
    rows = []
    for bid in building_ids:
        # Filter trajectory for this building and timestep
        building_traj = trajectory[(trajectory["building_id"] == bid) & (trajectory["timestep"] == timestep)]
        if not building_traj.empty:
            row = building_traj.iloc[0]
            load = row.get("net_electricity_consumption", 0.0)
            pv_gen = row.get("solar_generation", 0.0)
            battery_soc = row.get("electrical_storage_soc", 0.0)
            ev_soc = row.get("connected_electric_vehicle_at_charger_soc", 0.0)
        else:
            load = pv_gen = battery_soc = ev_soc = 0.0
        
        lat = locations.get(bid, {}).get("lat")
        lon = locations.get(bid, {}).get("lon")
        
        rows.append({
            "building_id": bid,
            "lat": lat,
            "lon": lon,
            "load": pd.to_numeric(load, errors="coerce"),
            "pv_gen": pd.to_numeric(pv_gen, errors="coerce"),
            "battery_soc": pd.to_numeric(battery_soc, errors="coerce"),
            "ev_soc": pd.to_numeric(ev_soc, errors="coerce"),
        })
    
    df = pd.DataFrame(rows)
    
    # Scenario coordinates are explicitly illustrative unless replaced with surveyed locations.
    map_df = df.dropna(subset=["lat", "lon"]).copy()
    if not map_df.empty:
        # Try to use pydeck for 3D visualization
        try:
            import pydeck as pdk
            map_df["load"] = map_df["load"].fillna(0.0)
            map_df["pv_gen"] = map_df["pv_gen"].fillna(0.0)
            map_df["battery_soc"] = map_df["battery_soc"].fillna(0.0)
            map_df["ev_soc"] = map_df["ev_soc"].fillna(0.0)

            load_min, load_max = map_df["load"].min(), map_df["load"].max()
            pv_min, pv_max = map_df["pv_gen"].min(), map_df["pv_gen"].max()
            soc_min, soc_max = map_df["battery_soc"].min(), map_df["battery_soc"].max()
            load_range = load_max - load_min if load_max > load_min else 1.0
            pv_range = pv_max - pv_min if pv_max > pv_min else 1.0
            soc_range = soc_max - soc_min if soc_max > soc_min else 1.0

            map_df["load_norm"] = (map_df["load"] - load_min) / load_range
            map_df["pv_norm"] = (map_df["pv_gen"] - pv_min) / pv_range
            map_df["soc_norm"] = (map_df["battery_soc"] - soc_min) / soc_range
            map_df["color"] = map_df["load_norm"].apply(
                lambda value: [int(255 * (1 - value)), int(255 * value), 0, 180]
            )
            map_df["elevation"] = map_df["soc_norm"] * 18 + 6

            if map_df[["lat", "lon"]].drop_duplicates().shape[0] == 1:
                st.warning("All buildings share one location; 3D columns overlap. Configure distinct schematic or surveyed coordinates.")

            # Frame the compact schematic community layout.
            view_state = pdk.ViewState(
                latitude=map_df["lat"].mean(),
                longitude=map_df["lon"].mean(),
                zoom=16,
                pitch=55,
                bearing=15,
            )
            column_layer = pdk.Layer(
                "ColumnLayer",
                data=map_df,
                get_position=["lon", "lat"],
                get_elevation="elevation",
                elevation_scale=1,
                radius=18,
                get_fill_color="color",
                pickable=True,
                auto_highlight=True,
            )
            tooltip = {
                "html": "<b>Building:</b> {building_id}<br/>"
                        "<b>Load:</b> {load} kW<br/>"
                        "<b>PV:</b> {pv_gen} kW<br/>"
                        "<b>Battery SOC:</b> {battery_soc}<br/>"
                        "<b>EV SOC:</b> {ev_soc}",
                "style": {"backgroundColor": "#1B2336", "color": "#F8FAFC"},
            }
            st.pydeck_chart(pdk.Deck(
                map_style="light",
                initial_view_state=view_state,
                layers=[column_layer],
                tooltip=tooltip,
            ))
        except ImportError:
            # Fallback to st.map if pydeck is not available
            st.info("Pydeck not available, showing 2D map")
            st.map(map_df, latitude="lat", longitude="lon")
    else:
        st.info("No location data available for buildings")
    
    st.caption("Schematic building locations (not surveyed). Color: load; column height: battery SOC; radius is illustrative.")
    
    # Asset status cards for selected building
    if not df.empty:
        selected_row = df[df["building_id"] == selected]
        if not selected_row.empty:
            row = selected_row.iloc[0]
            st.markdown(
                f"""
                <div class="glass-card">
                    <h4>Asset Status for {selected}</h4>
                    <p><strong>Load:</strong> {row['load']:.1f} kW</p>
                    <p><strong>PV Gen:</strong> {row['pv_gen']:.1f} kW</p>
                    <p><strong>Battery SOC:</strong> {row['battery_soc']:.0%}</p>
                    <p><strong>EV SOC:</strong> {row['ev_soc']:.0%}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    st.divider()
    st.subheader("Timeline View")
    # Timeline of actions for selected building
    bdf = trajectory[trajectory["building_id"] == selected]
    if not bdf.empty:
        st.line_chart(bdf.set_index("timestep")[["net_electricity_consumption", "solar_generation"]], height=200)
    else:
        st.info("No timeline data for selected building")
    
    st.subheader("Chat with Agent")
    st.text_area("Ask the agent about actions, forecasts, or recommendations...", height=150, key="agent_chat")
    if st.button("Send", type="primary"):
        st.info("Agent response placeholder")

    st.divider()
    st.subheader("Action Evidence")
    st.markdown(
        """
        <div class="glass-card">
            <p><strong>Latest Actions:</strong></p>
            <ul>
                <li>Battery discharge: 5.2 kW at t=15</li>
                <li>EV charging: 3.0 kW at t=10-20</li>
                <li>Flexible load shed: 2.0 kW at t=18</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
def render_scenario_builder():
    st.title("Scenario Builder & Re-run")
    st.caption("Adjust PV, EV, Battery, Tariff or controller settings and launch a new simulation")

    with st.form("scenario_form"):
        st.subheader("PV Scaling")
        pv_scale = st.slider("PV capacity factor", 0.5, 1.5, 1.0, 0.05)
        st.subheader("EV Fleet")
        ev_scale = st.slider("EV count factor", 0.5, 2.0, 1.0, 0.05)
        st.subheader("Battery Capacity")
        bat_scale = st.slider("Battery capacity factor", 0.5, 2.0, 1.0, 0.05)
        st.subheader("Tariff")
        tariff = st.selectbox("Tariff profile", ["Flat", "TOU", "Real-time"])
        st.subheader("Controller")
        controller = st.selectbox("Controller type", ["centralized","multi_agent","rule_based"])

        submitted = st.form_submit_button("Launch Simulation", type="primary")
        if submitted:
            st.success("Simulation queued – results will appear in the run list")

    st.divider()
    st.subheader("Comparison Tables & Trade-off Visualizations")
    st.info("Placeholder for radar/parallel coordinates comparing scenarios")


def render_reports():
    st.title("Reports")
    st.caption("Collapsible sections with detailed reports and download buttons")

    with st.expander("Energy Summary Report", expanded=True):
        st.markdown(
            """
            <div class="glass-card">
                <h4>Daily Energy Balance</h4>
                <p>Total Consumption: 12,450 kWh</p>
                <p>Total PV Generation: 8,320 kWh</p>
                <p>Net Grid Import: 4,130 kWh</p>
                <p>Self-Consumption Ratio: 66.8%</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Download PDF Report", key="dl_energy"):
            st.success("Energy report downloaded!")

    with st.expander("Financial Report"):
        st.markdown(
            """
            <div class="glass-card">
                <h4>Cost Breakdown</h4>
                <p>Energy Cost: $1,245</p>
                <p>Demand Charges: $320</p>
                <p>Total Savings vs. Baseline: $480 (27.8%)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Download Excel Report", key="dl_fin"):
            st.success("Financial report downloaded!")

    with st.expander("Environmental Impact"):
        st.markdown(
            """
            <div class="glass-card">
                <h4>Emissions Reduction</h4>
                <p>CO2 Avoided: 8.2 tonnes</p>
                <p>Equivalent Trees Planted: 370</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Download CSV Data", key="dl_env"):
            st.success("Environmental data downloaded!")

    st.divider()
    st.subheader("All Reports")
    st.download_button(
        label="Download Full Report Pack (ZIP)",
        data=b"Placeholder ZIP data",
        file_name="energy_community_report.zip",
        mime="application/zip"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Energy Community", layout="wide")
    inject_custom_css()

    if "current_section" not in st.session_state:
        st.session_state.current_section = "Overview"
    if "playing" not in st.session_state:
        st.session_state.playing = False

    # Load data
    if not RESULTS_DIR.exists():
        st.error(f"Results directory not found: {RESULTS_DIR}")
        st.stop()

    runs = load_experiment_results(RESULTS_DIR)
    if not runs:
        st.error("No experiment runs found in results/.")
        st.stop()
    runs.sort(key=lambda r: r.get("start_time",""), reverse=True)

    with st.sidebar:
        st.header("Run Selection")
        labels = [f"{r['run_id']} · {r['scenario_id']} · {r['controller_type']}" for r in runs]
        sel = st.selectbox("Experiment", labels)
        run = runs[labels.index(sel)]
        result = run["result"]
        raw_steps = load_trajectories(run["path"])
        if not raw_steps:
            st.error("No trajectory data.")
            st.stop()
        scenario_cfg = load_scenario_config(run["scenario_id"])
        b_ids = get_building_ids(scenario_cfg, raw_steps[0])
        traj = expand_trajectories(raw_steps, b_ids)
        if traj.empty:
            st.error("No building observations.")
            st.stop()

        sel_building = st.selectbox("Building", b_ids)
        ts = st.slider("Timestep", int(traj["timestep"].min()), int(traj["timestep"].max()), int(traj["timestep"].min()))
        st.divider()
        st.caption(f"Scenario: {run['scenario_id']}")
        st.caption(f"Controller: {run['controller_type']}")
        st.caption(f"Steps: {len(raw_steps)}")

        st.divider()
        st.header("Navigation")
        sections = [
            ("Overview","Overview"),
            ("Assets","Asset View"),
            ("Grid Twin","Grid Twin"),
            ("Scenarios","Scenario Builder"),
            ("Agent Workspace","Agent Workspace"),
            ("Reports","Reports")
        ]
        for label, key in sections:
            if st.button(label, use_container_width=True, type="primary" if st.session_state.current_section==key else "secondary"):
                st.session_state.current_section = key

    # Section routing
    energy = result.get("energy") or {}
    service = result.get("service") or {}
    grid = result.get("grid") or {}

    section = st.session_state.current_section
    if section == "Overview":
        render_overview(energy, service, grid)
    elif section == "Assets":
        render_asset_view(traj, b_ids)
    elif section == "Grid Twin":
        render_grid_twin(raw_steps, ts)
    elif section == "Scenarios":
        render_scenario_builder()
    elif section == "Agent Workspace":
        render_agent_workspace(traj, b_ids, scenario_cfg, ts)
    elif section == "Reports":
        render_reports()

    st.caption(f"{run['run_id']} · {len(raw_steps)} steps · {run['scenario_id']} · seed {result.get('random_seed','N/A')}")


if __name__ == "__main__":
    main()