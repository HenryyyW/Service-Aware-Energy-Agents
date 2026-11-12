# Deployment posture: research demo vs production

Owner: Project Partner · Updated: 2026-11-12 · Plan phase 6

The platform is released as a **research demonstration**. This page states
plainly what that means, so no reader mistakes the demo for a production
service.

## What the research demo IS

- A single-machine deployment (Docker Compose) with in-memory run state.
- Real simulation: CityLearn + pandapower coupling, the four control
  strategies, the NL→config pipeline, the diagnostics and fix-proposal
  workflow with its approval gate.
- Real evaluation: the 16-item corpus scored with the repo's own instruments
  (14 of 16 items full-bar on the final code, all 8 domains, 4 of 4
  rejection items - the acceptance line in the paper quotes the same clause).

## What the research demo is NOT (do not deploy as-is)

| Concern | Current state | Required before production |
|---|---|---|
| Access control | none | authentication + authorization on every /api route |
| Persistence | in-memory (`_scenarios`, `_runs`, `_fix_proposals` are process state) | durable store with migrations (alembic is scaffolded) |
| Execution isolation | simulations run in-process | sandboxed workers / queue isolation |
| Monitoring & alerting | none | metrics, structured logs, alerting on failure |
| Secrets | per-agent key stores on one machine | a secret manager, per-tenant keys |
| Multi-user | single user assumed | session model, per-user scenario ownership |

## Preview surfaces (clearly marked in the UI)

- The Experiments page shows sample runs in development mode only; production
  builds show an explicit "not wired yet" state.
- The Network page shows sample grid readings in development mode only.
- The dispatch trace in the strategy comparison shows "no record" until
  per-timestep trajectory data is wired through.

## The honesty rule

Any number on screen traces to a run record; missing data renders as
"no record", never a zero or an estimate. The strategy-modification component
is measured at 5 of 9 vs its pre-registered 7 of 9 and is reported at that
level wherever it is mentioned.
