# Project Brief: A Spatio-Temporal Virtual Community Simulator for Renewable Energy Communities with Physics-Grounded Code Agents

## 1. Product Vision

Build an open-source **spatio-temporal virtual community simulator** for renewable energy communities containing buildings, rooftop PV, batteries, electric vehicles (EVs), and flexible loads.

The user should be able to:

1. Create or import a virtual community on a map or 3D/2.5D scene.
2. Configure buildings, PV, batteries, EVs, flexible loads, tariffs, weather, and a distribution-grid model.
3. Run a time-stepped simulation over a day, week, or year.
4. Observe how energy flows, asset states, user services, and grid conditions evolve in **both time and space**.
5. Compare what-if scenarios, such as higher PV penetration, more EVs, additional battery capacity, equipment failures, or different control strategies.
6. Use an LLM-based code agent as a **simulation and engineering co-pilot** that can construct scenarios, generate or repair controllers, diagnose failures, and produce auditable reports.

The system is therefore not primarily a dashboard. It is a **virtual community simulator** with an integrated engineering-analysis and agent workspace.

```text
User designs a virtual community
        ↓
System simulates its operation over time
        ↓
User observes spatial and temporal impacts
        ↓
System validates services and grid constraints
        ↓
User compares scenarios and asks follow-up questions
        ↓
Code agent constructs, diagnoses, repairs, and explains simulations
```

## 2. Core Question

The system should answer questions such as:

- How does a renewable energy community operate across a day, week, or year?
- Where and when do PV, batteries, EVs, and flexible loads interact?
- Can the community reduce cost, peak demand, grid import, and emissions?
- Can every EV reach its required state of charge before departure?
- Can building comfort and flexible-load deadlines be maintained?
- Does a proposed PV, battery, or EV configuration remain safe on the distribution grid?
- Which control strategy is more reliable, fair, and robust?
- What happens when an inverter, charger, battery, sensor, or grid constraint fails?

The central research question is:

> Can a spatio-temporal building–grid simulator, assisted by physics-grounded code agents, reliably construct, execute, diagnose, and repair renewable-energy-community scenarios while preserving individual service guarantees and distribution-grid constraints?

## 3. What the System Is

The system combines three layers:

| Layer | Responsibility | Primary engine |
|---|---|---|
| **Community layer** | Buildings, PV, batteries, EVs, flexible loads, comfort, user services | CityLearn v3 |
| **Coordination layer** | Charging, discharging, load shifting, demand response, local sharing, settlement | Controllers and agents |
| **Grid layer** | Power flow, voltages, line/transformer loading, grid feasibility | pandapower |
| **Virtual community layer** | Spatial representation, time playback, scenario editing, visualization | Web frontend |
| **Agent layer** | Natural-language task interpretation, scenario construction, code repair, diagnosis, reporting | LLM code agents |

CityLearn and pandapower are open-source simulation engines. The project’s original contribution is the coupling, spatio-temporal simulation experience, service/grid verification, scenario benchmark, and agentic workflow built on top of them.

## 4. Why This Matters

Traditional building-energy tools often optimize aggregate KPIs such as total cost or grid import. However, an aggregate improvement can hide unacceptable outcomes for individual participants:

- An EV may miss its departure-time charging deadline.
- A building may suffer comfort violations.
- A battery owner’s asset may be disproportionately used.
- A demand-response obligation may be nominally met but unevenly distributed.
- A locally beneficial PV or storage plan may create voltage or loading problems elsewhere on the feeder.

CityLearn v3 supports configurable renewable energy communities with buildings, PV, batteries, EVs, flexible loads, electrical-service limits, local energy sharing and settlement, demand-response requests, changing members/assets, and failures. It distinguishes requested, limited, and applied actions, making it suitable for studying service-aware coordination rather than aggregate optimization alone.

The simulator must therefore evaluate both:

- **System-level performance**: cost, peak demand, grid import/export, renewable utilization, emissions.
- **Participant-level service and fairness**: EV charging completion, comfort violations, battery usage, settlement savings, and unmet demand-response obligations.
- **Grid-level feasibility**: voltage, line and transformer loading, power-flow convergence, and export/import constraints.

## 5. Core User Experience

### 5.1 Virtual Community Canvas

The main screen is a spatial community view, not a chart-first dashboard.

```text
┌────────────────────────────────────────────────────────────┐
│  Virtual Community: Eco-District A                         │
│                                                            │
│   🏢 Building 1        🏢 Building 2        🏢 Building 3   │
│   ☀️ Rooftop PV        ☀️ Rooftop PV                      │
│                                                            │
│              🔋 Community Battery                          │
│                                                            │
│   🚗 EV Hub            🏢 Building 4        🏢 Building 5   │
│                                                            │
│   ─────────────── Feeder A ───────────────                 │
│                  ⚡ Transformer                            │
│                                                            │
│  [00:00 ───────────●────────── 24:00]                      │
│  ▶ Play   ⏸ Pause   ⏭ Step   15-min resolution            │
└────────────────────────────────────────────────────────────┘
```

Users can:

- Click a building to inspect load, PV, indoor comfort, battery, and settlement.
- Click an EV to inspect SOC, charging power, departure deadline, and charging schedule.
- Click a battery to inspect SOC, charge/discharge power, availability, and cycling.
- Click a feeder, transformer, or bus to inspect power flow, loading, and voltage.
- Drag the time slider to inspect any moment in the simulation.
- Press play to watch the community evolve through time.
- Toggle layers for PV, batteries, EVs, flexible loads, grid topology, violations, and energy flows.

### 5.2 Time Simulation

The simulator must support:

- **Playback**: run a 24-hour, one-week, or one-year simulation.
- **Time scrubbing**: move to any timestep and inspect the full system state.
- **Step mode**: advance in 15-minute or hourly increments.
- **Event replay**: jump to the time when a voltage violation, transformer overload, missed EV deadline, or equipment failure occurred.
- **Scenario replay**: compare two or more scenarios at the same timestamp.

At each timestep, the frontend should display:

- Building demand and PV generation.
- Battery SOC and charge/discharge state.
- EV SOC, charging status, and remaining time to deadline.
- Flexible-load status and completion risk.
- Community grid import/export.
- Feeder and transformer loading.
- Bus voltages and constraint violations.
- Energy flows between PV, buildings, batteries, EVs, and the grid.

### 5.3 Spatial Visualization

Each asset should have a meaningful spatial representation.

| Asset | Spatial representation | Visual state |
|---|---|---|
| Building | 2.5D extruded polygon or simplified 3D volume | Color/height by load, comfort risk, or settlement outcome |
| PV | Rooftop surface or panel layer | Installed capacity, generation, curtailment |
| Battery | Community battery or building battery icon | SOC, charge/discharge direction, availability |
| EV | Parking bay, charging hub, or street-level icon | SOC, charging power, departure risk, V2G state |
| Flexible load | Building or device marker | Pending, shifted, completed, delayed, failed |
| Feeder | Line geometry | Loading, power flow direction, congestion |
| Transformer | Substation icon | Loading, capacity margin, overload |
| Bus/node | Map node | Voltage magnitude, violation state |

### 5.4 Energy-Flow Visualization

The simulator should visualize energy flows as dynamic relationships, not only static numbers.

Examples:

```text
12:00
PV 320 kW ──▶ Building load 180 kW
          ──▶ Battery charging 90 kW
          ──▶ Grid export 50 kW
```

```text
18:30
Grid 240 kW ──▶ Building load 150 kW
            ──▶ EV charging 70 kW
Battery 40 kW ──▶ Community load
```

Visual forms:

- Animated arrows or particles for power flows.
- Sankey-style community energy balance.
- Time-series area charts for generation, load, storage, and grid exchange.
- Feeder-level flow animation.
- Heatmaps for voltage and loading across time and network nodes.

### 5.5 Scenario Editor

The user must be able to modify the virtual community and rerun the simulation.

```yaml
community:
  name: eco_district_a
  buildings: 10
  simulation_period: 7_days
  timestep_minutes: 15

assets:
  pv:
    penetration: 0.4
    orientation: rooftop
  batteries:
    community_capacity_kwh: 800
    max_power_kw: 250
  evs:
    number: 35
    charging_power_kw:[7][22][60]
    departure_soc_requirement: 0.8
  flexible_loads:
    share: 0.15

grid:
  model: simbench_lv_grid_1
  transformer_capacity_kva: 630
  voltage_limits_pu: [0.95, 1.05]
  import_limit_kw: 500
  export_limit_kw: 200

control:
  strategy: agent_policy
  objective:
    - minimize_cost
    - minimize_peak
    - maximize_renewable_self_consumption
    - preserve_ev_service
    - preserve_comfort
```

Supported scenario changes:

- Add or remove buildings.
- Change PV capacity or orientation.
- Add community or building-level batteries.
- Change EV fleet size, charging power, arrival/departure schedules, and SOC requirements.
- Change flexible-load share and deadlines.
- Change tariffs, carbon intensity, weather, or demand-response events.
- Apply grid constraints, such as transformer capacity, feeder limits, or voltage bounds.
- Inject failures, such as PV inverter outage, charger failure, battery unavailability, or sensor loss.

## 6. System Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                        Web Frontend                          │
│                                                              │
│  Virtual Community Canvas | Time Player | Scenario Editor    │
│  Grid Explorer | Asset Inspector | Scenario Comparison       │
│  Agent Workspace | Report Viewer                             │
└───────────────────────────────┬──────────────────────────────┘
                                │ REST + WebSocket/SSE
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                        Backend API                           │
│                     FastAPI / Python                         │
└───────────────────────────────┬──────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Scenario Service │  │ Simulation       │  │ Agent Service    │
│                  │  │ Orchestrator     │  │                  │
│ - Community      │  │                  │  │ - Planner        │
│ - Assets         │  │ - CityLearn      │  │ - Coder          │
│ - Grid mapping   │  │ - pandapower     │  │ - Executor       │
│ - Constraints    │  │ - Coupling       │  │ - Verifier       │
│ - KPI settings   │  │ - Verification   │  │ - Repairer       │
└──────────────────┘  └──────────────────┘  │ - Reporter       │
                                            └──────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                     Data and Result Store                    │
│                                                              │
│  PostgreSQL: scenarios, assets, users, runs                  │
│  Parquet/DuckDB: time-series and simulation trajectories     │
│  Object storage: reports, plots, logs, generated code        │
└──────────────────────────────────────────────────────────────┘
```

## 7. Simulation Coupling

At each simulation step:

1. CityLearn produces building-level demand, PV generation, battery/EV/flexible-load actions, and community-level energy flows.
2. The coupling layer maps community or building-level power to selected buses in a pandapower network.
3. pandapower performs power-flow analysis.
4. The verifier checks grid constraints and service constraints.
5. Results are written to a time-series store and streamed to the frontend.
6. If violations occur, the system records a structured diagnostic and may trigger agent repair.

The frontend must never infer grid feasibility by itself. Every voltage, loading, and power-flow result must come from pandapower or another validated solver.

## 8. Agent Layer

The code agent is a **co-pilot for the simulator**, not a chatbot bolted onto a dashboard.

It should support:

- Building a scenario from natural language.
- Generating or modifying controller/scheduler code.
- Running simulations.
- Interpreting simulation and grid diagnostics.
- Explaining why a scenario fails.
- Proposing and applying minimal repairs.
- Re-running and comparing scenarios.
- Producing reproducible reports.

### Agent Workflow

```text
Planner
  ↓
Coder
  ↓
Executor
  ↓
Verifier
  ↓
Repairer, if needed
  ↓
Reporter
```

### Agent Responsibilities

| Role | Responsibility |
|---|---|
| Planner | Parses the user task, identifies assets, constraints, KPIs, and required simulations |
| Coder | Generates Python controllers, configuration, or analysis code |
| Executor | Runs CityLearn and pandapower in a controlled environment |
| Verifier | Checks physical, electrical, service, and reporting validity |
| Repairer | Diagnoses failures and proposes targeted code/configuration patches |
| Reporter | Produces a reproducible Markdown/JSON report with evidence |

### Example Agent Task

Input:

```text
Create a renewable energy community with 10 buildings, rooftop PV,
building batteries, and EV charging. Each EV must reach at least 80% SOC
before 07:00. Limit total community grid import to 200 kW. Compare
rule-based charging with a coordinated agent-based policy.
```

Expected system behavior:

1. Create a valid CityLearn scenario.
2. Map community demand to a pandapower feeder.
3. Run the rule-based baseline.
4. Generate and run a coordinated policy.
5. Detect voltage, loading, or service violations.
6. If needed, repair the policy or configuration.
7. Display both scenarios on the virtual community canvas.
8. Produce a reproducible comparison report.

## 9. Core Research Contributions

### Contribution 1: Spatio-temporal building–grid co-simulation

Develop a reproducible framework that couples community-level building energy simulation with distribution-grid power-flow analysis.

The system must support:

- Time-stepped community simulation.
- Spatial mapping of buildings and assets to grid buses.
- Power-flow validation at selected timesteps or every timestep.
- Voltage, loading, and power-balance diagnostics.
- Scenario replay and comparison.

### Contribution 2: Service-aware coordination

Design controllers and agents that coordinate local energy resources while respecting:

- EV departure-time SOC requirements.
- Building thermal-comfort bounds.
- Battery SOC and degradation constraints.
- Flexible-load completion deadlines.
- Per-phase and total active-power import/export limits.
- Demand-response delivery obligations.
- Local energy-sharing and settlement rules.

The key novelty is not merely minimizing cost. The system must explicitly trade off community benefit against participant-level service reliability and fairness.

### Contribution 3: Physics-grounded code-agent workflow

The code agent must:

- Generate executable Python controllers from structured task specifications.
- Execute them against CityLearn.
- Interpret simulation logs, KPI outputs, and pandapower diagnostics.
- Detect service failures and grid-constraint violations.
- Produce minimal, testable patches.
- Re-run experiments after repair.
- Refuse to report success unless validation passes.

### Contribution 4: Reproducible simulator benchmark

Release:

- Task definitions.
- Scenario configurations.
- Community and grid models.
- Agent prompts.
- Tool schemas.
- Baselines.
- Evaluation scripts.
- Raw simulation logs.
- Metrics.
- Example reports.

The benchmark should allow researchers to compare rule-based control, MPC, reinforcement learning, and LLM/code-agent approaches under identical virtual-community scenarios.

## 10. Experimental Scenarios

### Scenario A: Baseline Renewable Energy Community

- 5–20 buildings.
- Rooftop PV.
- Community or building-level batteries.
- EV charging.
- Flexible loads.
- Time-of-use grid tariff.
- No major failures.

Goal: establish baseline performance and validate the simulator pipeline.

### Scenario B: High EV Penetration

- Increase EV penetration to 30–60%.
- Include morning and evening departure deadlines.
- Evaluate whether coordinated charging reduces peak demand without missing service deadlines.

### Scenario C: PV Export and Grid Constraints

- Increase PV capacity.
- Apply feeder-level or nodal import/export limits.
- Evaluate voltage rise, reverse power flow, and curtailment.
- Test whether local storage and demand shifting reduce grid violations.

### Scenario D: Local Energy Sharing and Settlement

Enable community market or local energy sharing and compare:

- No sharing.
- Uniform price sharing.
- Weighted importer/exporter settlement.
- Carbon-aware or fairness-aware settlement.

Report both community savings and the distribution of savings among members.

### Scenario E: Failures and Robustness

Inject:

- PV inverter failure.
- Battery unavailability.
- EV-charger failure.
- Sensor or observation failure.
- Temporary grid-service limit reduction.

Measure how quickly the system detects the issue, repairs the policy or configuration, and restores service.

## 11. Evaluation Metrics

### Energy and Cost

- Total electricity cost.
- Grid import/export energy.
- Peak demand.
- Load factor.
- PV self-consumption.
- PV curtailment.
- Battery throughput and cycling proxy.
- Carbon emissions or carbon-intensity-weighted emissions.

### Service and Fairness

- EV charging completion rate.
- Average and worst-case EV SOC at departure.
- Comfort violation degree-hours.
- Flexible-load completion rate and delay.
- Demand-response requested versus delivered versus credited response.
- Per-member settlement cost or savings.
- Gini coefficient or another distributional-fairness metric.
- Worst-member outcome, not only mean outcome.

### Grid Feasibility

- Power-flow convergence rate.
- Number and duration of voltage violations.
- Maximum and minimum voltage.
- Line and transformer loading.
- Number of constraint violations after agent repair.
- Requested versus limited versus applied power.

### Simulator and Agent Performance

- Scenario construction success rate.
- Simulation execution success rate.
- First-attempt code validity.
- Repair success rate.
- Number of repair iterations.
- Task completion time.
- Token consumption.
- Constraint-violation rate.
- Report evidence completeness.
- Frontend rendering performance for selected community sizes.

## 12. Baselines

Implement and compare:

1. **Rule-based control**
   - Fixed EV charging schedules.
   - Threshold-based battery control.
   - Simple PV-following load shifting.

2. **Model predictive control**
   - Deterministic or scenario-based MPC.
   - Uses forecasted load, PV, tariff, and weather where available.

3. **Single-agent reinforcement learning**
   - One centralized agent controlling all assets.

4. **Multi-agent reinforcement learning**
   - Independent learners or a standard MARL baseline.

5. **LLM code agent without physics verification**
   - Generates and executes code but does not receive structured verifier feedback.

6. **LLM code agent with physics/service verification**
   - Full proposed system.

The most important comparison is between baselines 5 and 6. This isolates the value of structured physical and service feedback.

## 13. Frontend Design

### Recommended stack

```text
React + TypeScript
+ MapLibre GL JS or Mapbox GL JS
+ deck.gl
+ Plotly or ECharts
+ Zustand or Redux
+ FastAPI backend
+ WebSocket or Server-Sent Events
```

Optional 3D:

```text
Three.js for lightweight community scenes
Cesium for georeferenced city-scale scenes
3D Tiles for large urban models
```

For the first version, use a **2.5D map-based community view** rather than a full 3D city engine. Buildings can be rendered as extruded polygons; PV, batteries, EVs, feeders, and violations can be represented as map layers.

### Main pages

```text
1. Community Canvas
   - Map or 3D community view
   - Time player
   - Asset layers
   - Energy-flow animation

2. Asset Inspector
   - Building details
   - PV details
   - Battery details
   - EV details
   - Flexible-load details

3. Grid Explorer
   - Feeder topology
   - Voltage heatmap
   - Loading heatmap
   - Power-flow results
   - Violation list

4. Scenario Studio
   - Scenario editor
   - Parameter controls
   - Simulation runner
   - Scenario comparison

5. Agent Workspace
   - Natural-language task input
   - Plan / code / execution / verification timeline
   - Code diffs
   - Failure diagnosis
   - Repair evidence

6. Reports
   - Downloadable Markdown/PDF report
   - Assumptions, constraints, evidence, recommendations
```

## 14. Repository Structure

```text
virtual-community-simulator/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── scenarios.py
│   │   │   ├── simulations.py
│   │   │   ├── assets.py
│   │   │   ├── agents.py
│   │   │   └── reports.py
│   │   ├── simulation/
│   │   │   ├── citylearn_adapter.py
│   │   │   ├── pandapower_adapter.py
│   │   │   ├── coupling.py
│   │   │   └── orchestrator.py
│   │   ├── agents/
│   │   │   ├── planner.py
│   │   │   ├── coder.py
│   │   │   ├── executor.py
│   │   │   ├── verifier.py
│   │   │   ├── repairer.py
│   │   │   └── reporter.py
│   │   ├── controllers/
│   │   │   ├── rule_based.py
│   │   │   ├── mpc.py
│   │   │   ├── rl_baseline.py
│   │   │   └── agent_policy.py
│   │   ├── evaluation/
│   │   │   ├── metrics.py
│   │   │   ├── fairness.py
│   │   │   └── reports.py
│   │   └── schemas/
│   │       ├── scenario.py
│   │       ├── asset.py
│   │       ├── action.py
│   │       ├── diagnostics.py
│   │       └── report.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── CommunityCanvas.tsx
│   │   │   ├── GridExplorer.tsx
│   │   │   ├── ScenarioStudio.tsx
│   │   │   ├── AgentWorkspace.tsx
│   │   │   └── Reports.tsx
│   │   ├── components/
│   │   │   ├── TimePlayer.tsx
│   │   │   ├── AssetLayer.tsx
│   │   │   ├── EnergyFlowLayer.tsx
│   │   │   ├── GridLayer.tsx
│   │   │   ├── ViolationLayer.tsx
│   │   │   └── AssetInspector.tsx
│   │   └── api/
│   └── package.json
├── configs/
│   ├── scenario_a.yaml
│   ├── scenario_b.yaml
│   ├── scenario_c.yaml
│   ├── scenario_d.yaml
│   └── scenario_e.yaml
├── experiments/
│   ├── run_experiment.py
│   ├── run_all.sh
│   └── results/
└── docs/
    ├── architecture.md
    ├── data_model.md
    ├── simulation_coupling.md
    └── agent_workflow.md
```

## 15. Implementation Plan

### Phase 1: Simulation core

- Install and validate CityLearn v3.
- Create a minimal renewable-energy-community scenario.
- Implement a deterministic rule-based controller.
- Log requested, limited, and applied actions.
- Compute energy, cost, service, and fairness metrics.
- Add unit tests.

### Phase 2: Building-grid coupling

- Select an IEEE or SimBench distribution-network model.
- Map building/community demand to grid buses.
- Run pandapower power flow at each step or selected intervals.
- Add voltage and loading checks.
- Return structured diagnostics on failure.

### Phase 3: Virtual community frontend

- Build a map-based community canvas.
- Render buildings, PV, batteries, EVs, feeders, and transformers.
- Implement a time player and time scrubber.
- Add asset inspector panels.
- Visualize energy flows, voltages, loading, and violations.
- Enable scenario creation and rerunning.

### Phase 4: Code-agent workflow

- Implement planner, coder, executor, verifier, repairer, and reporter.
- Define strict JSON schemas for task specification, scenario configuration, controller interface, simulation result, constraint diagnostic, repair patch, and final report.
- Add sandboxed code execution.
- Require tests before accepting a generated controller.
- Connect agent outputs to the community canvas and grid explorer.

### Phase 5: Multi-agent coordination

- Implement building, battery, EV, and community-aggregator agents.
- Add negotiation or hierarchical coordination:
  - Local proposal.
  - Aggregator reconciliation.
  - Grid-constraint validation.
  - Final allocation.
- Compare against centralized and rule-based approaches.

### Phase 6: Benchmark and paper experiments

- Run all scenarios with fixed random seeds.
- Run each configuration at least 3–5 times.
- Produce confidence intervals or statistical tests.
- Generate publication-quality plots, tables, and replayable scenarios.
- Write an experiment report and paper draft.

## 16. Engineering Requirements

### Reproducibility

- Pin all dependency versions.
- Store random seeds.
- Save every scenario configuration hash.
- Log model name, prompt version, tool calls, code diffs, and simulation outputs.
- Make every figure, table, and map state regenerable from saved results.

### Safety and Validation

- Never execute unreviewed generated code with network access.
- Use a sandbox or restricted subprocess environment.
- Enforce timeout and memory limits.
- Validate all generated Python with static checks and unit tests.
- Treat simulation output, not LLM self-assessment, as the source of truth.

### Code Quality

- Use type hints.
- Use Pydantic models for all structured data.
- Keep agent prompts in version-controlled files.
- Separate environment logic, agent logic, controller logic, evaluation logic, and reporting logic.
- Add tests for every critical interface.

## 17. First Milestone

Build a minimum viable demonstration:

1. Create a CityLearn v3 community with:
   - 5 buildings.
   - Rooftop PV.
   - Batteries.
   - EVs.
   - Flexible loads.
2. Render the community on a 2.5D map canvas.
3. Run a rule-based baseline for one week.
4. Implement a time player that shows asset states and community energy flows.
5. Map community demand to a small pandapower feeder.
6. Display voltage, loading, and violation states in a grid explorer.
7. Let a code agent generate a coordinated scheduling policy.
8. Detect at least one service or electrical violation.
9. Let the repair agent fix the policy or configuration.
10. Produce a Markdown report comparing baseline and repaired agent policy.

The first milestone is successful if a user can:

- Open the virtual community.
- Play or scrub through time.
- See how buildings, PV, batteries, EVs, and the feeder change.
- Trigger an agent-generated scenario.
- Observe a constraint violation and its repair.
- Download a reproducible report.

## 18. Paper Positioning

### Working title

> **A Spatio-Temporal Virtual Community Simulator for Renewable Energy Communities: Physics-Grounded Code Agents for Building–Grid Co-Simulation, Service Awareness, and Grid-Constraint Compliance**

### Alternative title

> **Virtual Community Digital Twin for Renewable Energy Communities: Coupling Building and Grid Simulation with Physics-Grounded Code Agents**

### Key claim

> A spatio-temporal building–grid simulator with physics-grounded code agents can reliably construct, execute, diagnose, and repair renewable-energy-community scenarios while preserving individual service guarantees and distribution-grid constraints.

### Target venues

- Applied Energy.
- Energy and AI.
- IEEE Transactions on Smart Grid.
- IEEE Transactions on Sustainable Energy.
- ACM e-Energy.
- AAAI / IJCAI workshops on AI for sustainability, agents, or social good.
- NeurIPS Datasets and Benchmarks, if the benchmark contribution is strong.

## 19. Important Design Warnings

### Do not build only a dashboard

A dashboard displays completed results. A simulator lets users:

- Define a community.
- Change assumptions.
- Run time-stepped simulations.
- Observe spatial and temporal dynamics.
- Compare alternatives.
- Investigate failures.

### Do not build only a chatbot

The agent must operate the simulator through tools, code, and validated results. It must not merely discuss energy policy in natural language.

### Do not fake spatial realism

The first version does not need photorealistic 3D. A clear 2.5D map with meaningful asset states is more useful than a beautiful but non-interactive 3D scene.

### Do not hide uncertainty

Every result should expose:

- Simulation assumptions.
- Weather and load uncertainty.
- Grid-model limitations.
- Requested versus applied actions.
- Failed constraints.
- Agent repair history.

## 20. Definition of Success

The project is successful when a user can do the following without manually editing code:

```text
1. Open a virtual community.
2. Inspect buildings, PV, batteries, EVs, and the distribution feeder.
3. Play or scrub through a simulated day.
4. Change PV, EV, battery, tariff, or control assumptions.
5. Run a new simulation.
6. See spatial and temporal impacts on the community and grid.
7. Ask an agent to diagnose a violation or improve a policy.
8. Watch the agent generate, execute, verify, and repair the workflow.
9. Compare baseline and repaired scenarios.
10. Download a reproducible report with evidence.
```

The scientific value comes from this closed loop:

```text
virtual community design
  → time-stepped building–grid simulation
  → spatial and temporal visualization
  → service and grid-constraint verification
  → structured failure diagnosis
  → targeted code/configuration repair
  → reproducible scenario comparison and reporting
```