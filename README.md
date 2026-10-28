# Service-Aware Energy Agents

**English** | [简体中文](README.zh-CN.md)

A research prototype for simulating renewable-energy communities and investigating whether code-generating agents can coordinate buildings, PV, batteries, EVs, and flexible loads while respecting participant service requirements and distribution-grid constraints.

> **Project status:** This repository contains a working Python simulation prototype, experiment tooling, and a React map-based results frontend. It is not yet a complete end-to-end virtual power plant (VPP) product. In particular, the production backend, market settlement, configured failure injection, and behavior-changing agent repair are incomplete. See [Current limitations](#current-limitations) before interpreting results.

## Contents

- [Research question](#research-question)
- [System architecture](#system-architecture)
- [Repository layout](#repository-layout)
- [Scenarios](#scenarios)
- [Metrics and experiment design](#metrics-and-experiment-design)
- [Install and run](#install-and-run)
- [React frontend](#react-frontend)
- [Tests and current validation](#tests-and-current-validation)
- [Current limitations](#current-limitations)
- [Roadmap](#roadmap)

## Research question

The project asks:

> Can a physics-grounded code-agent workflow construct, execute, diagnose, and repair renewable-energy-community simulations while preserving individual service guarantees and distribution-grid constraints?

The system is intended to assess more than aggregate cost or grid import. It also tracks whether individual EVs meet departure SOC targets, whether buildings remain within comfort bounds, how energy resources are used, and whether the coupled distribution network remains feasible.

## System architecture

| Layer | Responsibility | Main implementation |
|---|---|---|
| Community simulation | Building demand, PV, storage, EVs, flexible loads, observations and actions | CityLearn v3 adapter |
| Coordination | Rule-based and hierarchical multi-agent control; community import/export limiting | `src/controllers/`, `src/coordination/` |
| Grid simulation | Map building power to a distribution network and evaluate power flow, voltage and loading | pandapower adapter |
| Evaluation | Energy, service, grid, agent and per-member metrics; plots and reports | `src/evaluation/` |
| Agent workflow | Plan, generate code, execute in a sandbox, verify, repair and report | `src/agents/` |
| Results interface | Browse saved runs, spatial layers, assets and simulation time steps | React, TypeScript, MapLibre, deck.gl and Plotly under `frontend/` |

The current co-simulation sequence is: obtain CityLearn observations, request and apply controller actions, pass resulting building powers to pandapower, then record grid diagnostics alongside the simulation step. Grid diagnostics are currently primarily validation outputs; the implementation does not yet provide a generally verified closed-loop process that feeds every grid violation back into a controller and confirms its repair.

## Repository layout

```text
.
├── configs/                 # Scenario A–E YAML configurations
├── data/schemas/            # CityLearn schemas and scenario data
├── experiments/
│   ├── run_experiment.py    # Run one scenario/controller experiment
│   ├── run_benchmark.py    # Run scenario/controller/seed combinations
│   └── ...                  # Saved experiment outputs and summaries
├── frontend/                # React + TypeScript + Vite application
├── src/
│   ├── agents/              # Planner, coder, executor, verifier, repair and reporter
│   ├── controllers/         # Rule-based, centralized heuristic and multi-agent controllers
│   ├── coordination/       # Building/resource agents and community aggregator
│   ├── evaluation/          # Energy, service, grid, fairness metrics and plots
│   ├── schemas/             # Pydantic scenario, action, diagnostic and report models
│   └── simulation/          # CityLearn adapter, pandapower adapter and co-simulation
├── tests/                   # Python automated tests
├── project brief.md         # Full product/research brief and target milestone
└── notes.md                 # Research and publication planning notes
```

Generated runs are written under the selected output directory. Avoid committing large generated trajectories or plots unless they are intentionally part of a reproducibility artifact.

## Scenarios

All scenarios currently describe five-building communities and are configured in `configs/`.

| File | Intended study | Configuration status |
|---|---|---|
| `scenario_a.yaml` | Baseline community with PV, batteries, EVs, flexible loads and time-of-use tariff | Baseline experiment configuration |
| `scenario_b.yaml` | Higher EV penetration and morning/evening charging deadlines | Scenario configuration; runtime results need validation |
| `scenario_c.yaml` | Higher PV penetration, export and grid constraints | Scenario configuration; runtime results need validation |
| `scenario_d.yaml` | Local energy sharing and settlement | Sharing settings are declared; market execution and settlement are not yet implemented end to end |
| `scenario_e.yaml` | PV, battery, charger, sensor and grid-limit failures | Failure cases are declared; runtime injection and recovery are not yet implemented end to end |

## Metrics and experiment design

The evaluation code defines metrics in these groups:

- **Energy and cost:** total cost, grid import/export, peak demand, load factor, PV generation/self-consumption/curtailment, battery throughput/cycles and carbon emissions.
- **Participant service:** EV completion and departure SOC, comfort violation degree-hours, flexible-load completion/delay, demand-response delivery and per-member outcomes.
- **Grid feasibility:** power-flow convergence, voltage bounds and violations, line/transformer loading, and community import/export limits.
- **Agent execution:** task and simulation success, first-attempt validity, repair iterations, runtime and report completeness.

`experiments/run_benchmark.py` supports the `rule_based`, `multi_agent`, `centralized`, `mpc`, and `rl` controller labels. `mpc` is a deterministic receding-horizon linear program; `rl` is a tabular Q-learning policy loaded from `experiments/rl_policy/<scenario>.json`. The `centralized` implementation remains a heuristic controller, not an optimizer. Controllers request power in kW under the published asset ids (`{building}_battery`, `{building}_ev_{i}`, `{building}_flex_{i}`); the CityLearn adapter converts those to the simulator's normalized device actions using live device ratings. The benchmark script runs each configuration in its own process, supports parallel workers, and reports mean, sample standard deviation, and Student-t 95% confidence intervals. See `experiments/BENCHMARK_MATRIX.md` for the planned matrix, seeds, runtime budget, and known measurement caveats. A small smoke run is not sufficient evidence for a paper claim.

## Install and run

### Python simulation

Use Python 3.10 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

Run one experiment:

```powershell
python experiments/run_experiment.py `
  --config configs/scenario_a.yaml `
  --controller rule_based `
  --seed 42
```

Supported controller arguments are `rule_based`, `multi_agent`, `centralized`, `mpc`, and `rl`. Optional arguments include `--max-steps`, `--output-dir`, `--seed`, `--run-id`, and `--rl-policy` (required for `rl`).

Train the tabular Q-learning baseline before running the `rl` controller:

```powershell
python -m experiments.train_rl `
  --config configs/scenario_a.yaml `
  --out experiments/rl_policy/scenario_a.json `
  --episodes 60
```

Run a small benchmark, for example:

```powershell
python experiments/run_benchmark.py `
  --scenarios configs/scenario_a.yaml `
  --controllers rule_based multi_agent `
  --seeds 42 123 `
  --output experiments/benchmark_test
```

The benchmark command defaults to scenarios A-E, five controller labels, and five seeds (42, 123, 456, 789, 999). Use `--workers N` to run configurations in parallel and `--rl-policy-dir` to point at per-scenario RL policies. Full runs take hours, not minutes: budget from the measured per-run time in `experiments/BENCHMARK_MATRIX.md`. `experiments/run_all.sh` is a Bash script; use Git Bash, WSL, or another Bash environment on Windows.

### React frontend

Node.js and npm are required. From the repository root:

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

Open the Vite URL, normally `http://127.0.0.1:3000/`. A VS Code task named **Run Virtual Community Frontend** is also configured.

Build and type-check the frontend:

```powershell
npm.cmd --prefix frontend run build
```

### Local results API

The Vite development server includes a read-only local middleware that scans the repository's `results/` directory for `result.json` files and serves run summaries and sibling `trajectories.jsonl` files. This is a development convenience, **not a production backend**. The frontend API client also defines scenario, simulation, agent, report, comparison and WebSocket endpoints; a matching FastAPI service is not currently included in this repository. Set `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` when connecting to a separate service.

## React frontend

The default route is the community canvas. It includes:

- Run selection backed by saved experiment results.
- A MapLibre basemap with deck.gl layers for buildings, PV, batteries, EVs, feeder, transformer, violations, heatmaps and energy flows.
- A time slider with play/pause, step, reset and speed controls.
- A context-sensitive asset/grid inspector.
- Routes for Scenario Studio, Agent Workspace, reports and run comparison.

The current map positions and feeder geometry are schematic. Run data is real when loaded from saved results, but several visual and workflow elements are incomplete: actual grid topology is not mapped, some equipment state is inferred from observations/actions, and scenario/agent/report actions require backend routes that are not yet provided.

## Tests and current validation

Run tests from the repository root:

```powershell
pytest -q tests
```
The suite covers controller coordination, CityLearn adapter behavior, pandapower adapter behavior, metrics, the benchmark supervisor, and agent repair scaffolding. **The full suite passes**, including regression tests for the CityLearn adapter time-step convention and for the controller action interface (kW request to normalized CityLearn action, including asset-id aliases and EV observation sourcing).

## Current limitations

- The Vite local-results middleware is not a production API/backend.
- CityLearn adapter time step convention is now unified and protected by regression tests (integer schema fields, CSV length matching episode steps, float/int seconds_per_time_step handling).
- Grid violations are recorded, but a complete grid-feedback/re-dispatch control loop is not yet demonstrated.
- `energy_sharing` and settlement options exist in scenario schemas/configurations, but there is no end-to-end market clearing or settlement path; per-member settlement savings are placeholders.
- Scenario E declares failures, but configured failure injection and recovery are not implemented end to end.
- The repair path is not yet trustworthy as a code-repair result: parts of patch application are placeholders, and a passing quick sandbox run is not equivalent to demonstrating that the targeted service/grid violation was repaired.
- The React map uses illustrative coordinates and does not yet display the actual pandapower network geometry.
- Time labels in the frontend assume 15-minute steps; this must be reconciled with runs that use a different dataset-native interval.
- The benchmark currently lacks MPC, RL, unverified-agent and verified-agent comparisons required by the research brief.

## Roadmap

1. ✅ **DONE** — Restored clean test baseline; unified timestep/data-unit contract with integer-only schema fields, CSV/episode step alignment, and parametrized 3600/3600.0 regression coverage.
2. Close the co-simulation loop so grid diagnostics can constrain or trigger a verified re-dispatch.
3. Make agent patches behavior-changing and verify repairs against full-run service/grid metrics.
4. Implement energy sharing, settlement and configured failure injection as executable simulation behavior.
5. Connect the React Scenario Studio, Agent Workspace and reports to a real API; load actual asset/grid metadata and run timestep metadata.
6. Run the full benchmark matrix with reproducible seeds, appropriate baselines and statistical analysis.

See [`project brief.md`](project%20brief.md) for the full product specification, first-milestone acceptance criteria and paper framing.

## License

The project metadata declares MIT. Confirm the repository's license file and third-party asset terms before redistribution.
