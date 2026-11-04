# API surface

Owner: Product Design Lead (docs) · Date: 2026-11-04
Source of truth: `backend/app/routers/*.py` and `backend/app/main.py`. Terse on purpose — this
complements, and does not replace, the generated OpenAPI schema at `/openapi.json`.

All HTTP routers are mounted under **`/api`** (`main.py`). Auth is not enforced in the current
local/dev service.

## Scenarios — `backend/app/routers/scenarios.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/scenarios` | list scenario configs |
| GET | `/api/scenarios/{scenario_id}` | read one scenario |
| POST | `/api/scenarios` | create a scenario |
| PATCH | `/api/scenarios/{scenario_id}` | update a scenario |
| DELETE | `/api/scenarios/{scenario_id}` | delete a scenario |
| GET | `/api/scenarios/{scenario_id}/validate` | validate a scenario against the schema |

## Simulations — `backend/app/routers/simulations.py`

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/simulations` | start a simulation run |
| GET | `/api/simulations` | list runs |
| GET | `/api/simulations/{run_id}` | run summary |
| GET | `/api/simulations/{run_id}/trajectories` | per-step trajectories |
| GET | `/api/simulations/{run_id}/grid` | grid diagnostics for the run |
| POST | `/api/simulations/{run_id}/cancel` | cancel a running run |
| POST | `/api/simulations/{run_id}/resume` | resume a cancelled run |
| GET | `/api/simulations/{run_id}/status` | run status (for polling) |

## Agent — `backend/app/routers/agent.py`

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/agent/tasks` | submit an agent task (plan→code→execute→verify→repair) |
| GET | `/api/agent/tasks` | list agent tasks |
| GET | `/api/agent/tasks/{task_id}` | task detail + step evidence |
| DELETE | `/api/agent/tasks/{task_id}` | delete a task |
| POST | `/api/agent/tasks/{task_id}/retry` | retry a task |

## Reports — `backend/app/routers/reports.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/reports/{run_id}` | structured report for a run |
| GET | `/api/reports/{run_id}/download` | download the report artifact |

## Comparison — `backend/app/routers/compare.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/compare` | compare runs (query-driven) |
| GET | `/api/compare/detailed/{run_id_a}/{run_id_b}` | detailed A/B comparison |

## Network — `backend/app/routers/network.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/network/geometry` | network geometry for the map |
| GET | `/api/network/geometry/{scenario_id}/realtime` | realtime geometry deltas |
| GET | `/api/network/asset-metadata/{scenario_id}` | asset metadata (ratings, ids) |

## Meta

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness/health probe |
| GET | `/openapi.json` | OpenAPI schema (for the generated client) |

## WebSocket — `backend/app/main.py`

| Path | Purpose |
|---|---|
| `/ws` | generic echo channel |
| `/ws/simulation/{run_id}` | per-run simulation stream (time step, violations) |
| `/ws/p2p/{run_id}` | P2P orderbook / trade stream |
| `/ws/agent/{task_id}` | agent-task step stream |

> Note: `deploy`/CI proxy `frontend/nginx.conf` currently proxies **`/ws/`** to the API; the P2P and
> agent channels ride the same `/ws/` prefix, so no extra nginx location is required.
