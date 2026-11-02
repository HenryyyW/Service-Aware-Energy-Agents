# Service-Aware Energy Agents

**English** | [蝞雿葉?(README.zh-CN.md)

A research prototype for simulating renewable-energy communities and investigating whether code-generating agents can coordinate buildings, PV, batteries, EVs, and flexible loads while respecting participant service requirements and distribution-grid constraints.

> **Project status:** A working research prototype — Python simulation + experiment tooling, a FastAPI service (`backend/`), and a React map frontend (`frontend/`) with a switchable visual style. Implemented and covered by tests: pricing regimes (pool-TOU / LMP), P2P matching, configured failure injection (scenario E), and a plan → code → execute → verify → repair agent workflow. It is still **not** a production VPP: the API is a local/dev service, the LMP arm is fallback-dominated on congested cases, and P2P runs are not scheduled. See [Current limitations](#current-limitations) before citing any numbers.

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

The current co-simulation sequence is: obtain CityLearn observations, request and apply controller actions, pass resulting building powers to pandapower, then record grid diagnostics alongside the simulation step. The grid loop now closes the loop: violations detected (pandapower diagnostics) → controller update_grid_diagnostics → re-dispatch → power flow re-check, running continuously inside SimulationCoupler.step. Metrics track violations resolved vs attempted per run; re-dispatch actions recorded in result.json.

## Repository layout

```text
.
  configs/                 # Scenario A YAML configurations
  data/schemas/            # CityLearn schemas and scenario data
  experiments/
    run_experiment.py      # Run one scenario/controller experiment
    run_benchmark.py       # Run scenario/controller/seed combinations
    ...                    # Saved experiment outputs and summaries
  frontend/                # React + TypeScript + Vite application
  src/
    api/                 # FastAPI production service (single entry point)
    agents/              # Planner, coder, executor, verifier, repair and reporter
    controllers/         # Rule-based, centralized heuristic and multi-agent controllers
    coordination/       # Building/resource agents and community aggregator
    evaluation/          # Energy, service, grid, fairness metrics and plots
    schemas/             # Pydantic scenario, action, diagnostic and report models
    simulation/          # CityLearn adapter, pandapower adapter and co-simulation
    tests/                   # Python automated tests
  backend/                 # Canonical FastAPI app (entry: backend.app.main:app)
    app/                # Routers: agent, scenarios, simulations, network, reports, compare
  project brief.md         # Full product/research brief and target milestone
  notes.md                 # Research and publication planning notes

```

Key top-level directories: `backend/` (FastAPI service: `/api/*`, `/ws`), `frontend/` (React + Vite app), `src/` (simulation, controllers, coordination, agents, evaluation), `experiments/` (runners, matrices, paper figures), `configs/`, `data/`, `docs/`, `arxiv_submission/`, `scripts/`, `tests/`.

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

> **Pre-fix benchmark numbers are invalid.** Benchmark results generated before the seed-reproducibility fix (PR #1) did not seed every RNG source, so they cannot be reproduced and must not be cited. Re-run any benchmark with the current code before using its numbers; see [`docs/reproducibility.md`](docs/reproducibility.md) for the reproducibility gate.

## Install and run

### Quickstart (about 10 minutes)

Shortest path to a running UI with one real run:

```bash
# 1. Python environment + package
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -e .

# 2. One quick experiment (writes results/<scenario>/<run>/)
python experiments/run_experiment.py \
  --config configs/scenario_a.yaml --controller rule_based --seed 42 --max-steps 96

# 3. Backend API  (serves /api/* and /ws, default port 8001, matches the Vite proxy)
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8001

# 4. Frontend  (separate terminal)
npm --prefix frontend install
npm --prefix frontend run dev                     # http://127.0.0.1:3000
```

Open the Vite URL and pick the run you just produced on the Community Canvas. Switch the visual
style (GE Vernova / Schneider / dark) from the style control in the top bar. If the API is hosted
elsewhere, set `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` (see `frontend/.env.example`).

### Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `VITE_API_BASE_URL`, `VITE_WS_BASE_URL` | `frontend/.env` | Point the frontend at a separate API/WebSocket service |
| `VITE_MAPBOX_TOKEN` | `frontend/.env` | Optional; Carto basemaps are used by default |
| `AGENT_BACKEND` | shell / `.env` | Hosted LLM backend, e.g. `api:poolside/laguna-xs-2.1` |
| `LLM_BASE_URL`, `LLM_API_KEY` | shell / `.env` | Hosted-LLM endpoint and key (key is never committed) |

See `frontend/.env.example` and the root `.env.example` for the full list.

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

Train the tabular Q-learning baseline before running the `rl` controller. Training writes to `experiments/rl_policy/` (gitignored); curated policies for the benchmark matrix are checked in under `experiments/reference/rl_policy/`.

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
- **Switchable visual style** — `GE Vernova` (default, light enterprise), `Schneider` (light, green), and `dark` canvas. Switched from the style control in the top bar; implemented with `<html data-theme>` and `frontend/src/config/theme.ts`. Design notes: `docs/frontend_visual_direction.md`.
- **Colour scheme** — IEEE-blue accent for chrome and focus (`#00C0EF`) with the neutral locational-price ramp on the map; red is reserved for violations. The Agent Workspace uses a horizontal `Plan → Code → Execute → Verify → Repair → Report` rail (design: `docs/phase4_agent_workspace_design.md`).

The current map positions and feeder geometry are schematic. Run data is real when loaded from saved results, but several visual and workflow elements are incomplete: actual grid topology is not mapped, some equipment state is inferred from observations/actions, and scenario/agent/report actions require backend routes that are not yet provided.

## Tests and current validation

Run tests from the repository root:

```powershell
pytest -q tests
```
The suite covers controller coordination, CityLearn adapter behavior, pandapower adapter behavior, metrics, the benchmark supervisor, and agent repair scaffolding. **The full suite passes**, including regression tests for the CityLearn adapter time-step convention and for the controller action interface (kW request to normalized CityLearn action, including asset-id aliases and EV observation sourcing).

## Current limitations

- **Not a production VPP.** The FastAPI service (`backend/`) is a local/dev API (no auth, localhost CORS), and the Vite `results/` middleware is a development convenience only.
- **LMP arm is fallback-dominated on congested cases.** On the M1 `lmp` runs the OPF falls back (`power_flow_not_converged`) and the per-run price metrics are unusable (zero/negative measured spread), so no valid locational-price dispersal result (figure F8) can be produced from them yet.
- **P2P is not scheduled.** The matching engine and schemas exist and are tested, but no `p2p` runs are executed and there is no P2P WebSocket endpoint.
- **Grid feedback loop is partial.** Violations are recorded and re-dispatch exists; a fully verified closed loop across all cases is not yet demonstrated.
- **Illustrative geometry.** Map positions and feeder geometry are schematic, not the actual pandapower network; frontend time labels assume 15-minute steps.
- **Benchmark coverage.** The matrix covers the main controllers and pricing regimes; paper-grade MPC/RL and unverified-vs-verified agent comparisons are still being extended.

## Roadmap

1. **DONE** — Restored a clean test baseline and unified the timestep/data-unit contract.
2. **DONE** — Pricing regimes (pool-TOU / LMP), P2P matching + schemas, configured failure injection (scenario E), the plan → code → execute → verify → repair agent workflow, and a FastAPI service with a switchable-style React frontend.
3. Close the co-simulation loop so grid diagnostics can constrain or trigger a verified re-dispatch.
4. Make the LMP arm produce valid locational prices on congested cases (fix the OPF fallback) so price-spread results are claim-grade.
5. Schedule and validate `p2p` runs; add the P2P WebSocket endpoint.
6. Run the full benchmark matrix with reproducible seeds, appropriate baselines and statistical analysis.

See [`project brief.md`](project%20brief.md) for the full product specification, first-milestone acceptance criteria and paper framing.

## License

The project metadata declares MIT. Confirm the repository's license file and third-party asset terms before redistribution.
