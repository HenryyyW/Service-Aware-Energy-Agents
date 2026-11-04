# Deployment guide — zero to staging

Owner: Product Design Lead (docs) · Date: 2026-11-04
Scope: bring the stack up locally / in staging, run DB migrations, verify, deploy via CI, roll back,
and where to look at logs/metrics. Source of truth is the code in this repo.

Companion: [`docs/api_surface.md`](api_surface.md) (route list).

---

## 1. Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Docker + Compose v2 (`docker compose`) | 24+ | running the stack |
| Python | 3.11 | local backend / alembic / tests |
| Node.js | 20 or 22 | frontend build |
| `gh` CLI (authenticated) | any recent | `scripts/rollback_staging.sh` (reads ghcr packages) |
| Bash | — | `.sh` scripts (Windows: use Git Bash or WSL) |

## 2. Environment

Copy the template and edit — **never commit real secrets**:

```bash
cp .env.example .env            # root: app/db/redis/celery/LLM vars
cp frontend/.env.example frontend/.env   # optional: VITE_API_BASE_URL / VITE_WS_BASE_URL / VITE_MAPBOX_TOKEN
```

Key root vars (defaults in `.env.example`):

| Var | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | Postgres password (compose `db` service) |
| `SECRET_KEY` | API signing secret — **must** be changed for staging/production |
| `DATABASE_URL`, `REDIS_URL` | compose sets these for the `api`/worker from the service names |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | background task queue |
| `GRAFANA_PASSWORD` | Grafana admin password |
| `AGENT_BACKEND`, `LLM_BASE_URL`, `LLM_API_KEY` | hosted-LLM arm; **key is read at call time** (`src/agents/backend/api.py`) and must not be committed |

## 3. Bring the stack up (local ≈ staging shape)

```bash
docker compose up -d --build
docker compose ps              # wait for api + db + redis to be healthy
```

Services and ports (`docker-compose.yml`):

| Service | Port | Notes |
|---|---|---|
| frontend (nginx) | 3000 | serves the built app |
| api (FastAPI) | 8000 | `/health`, `/api/*`, `/ws*` |
| grafana | 3001 | dashboards |
| prometheus | 9090 | metrics |
| loki | 3100 | logs |
| db (postgres 16) | 5432 | `saea` |
| redis 7 | 6379 | broker/cache |

## 4. Database migration

Alembic config is at the repo root (`alembic.ini`), migrations under `alembic/versions/`
(`001_initial.py`). Apply before first use and after each pull that adds a migration:

```bash
alembic upgrade head
```

(For a containerised run, exec it inside the `api` container once it is up.)

## 5. Smoke verification

```bash
curl -fsS http://localhost:8000/health            # -> {"status":"ok", ...}
curl -fsS http://localhost:8000/openapi.json >/dev/null && echo "openapi ok"
bash scripts/smoke_deploy.sh                        # compose smoke used by CI
```

Then open http://localhost:3000 and confirm a run loads on the Community Canvas, and switch the
visual style (System / GE Vernova / Schneider / Canvas) in the top bar.

## 6. Staging deploy via CI

`.github/workflows/ci-cd.yml` runs on push to `main` (and `workflow_dispatch` for prod):

```
lint → python-tests → frontend-build → frontend-quality (Lighthouse + axe)
     → reproducibility → artifact-hygiene
     → build-backend / build-frontend   (push images to ghcr.io)
     → smoke-test (scripts/smoke_deploy.sh) → alembic-migration (alembic upgrade head)
     → deploy-staging  (environment: staging)
```

- Images: `ghcr.io/henryyyw/service-aware-energy-agents-{backend,frontend}`, tagged by run.
- `deploy-production` and `rollback` are `workflow_dispatch` (manual), gated by the `production`
  environment.

> **Current state (read before trusting a deploy):** the `deploy-staging`, `deploy-production` and
> `rollback` jobs are **simulated** — they `echo` and comment the real command
> ("replace with actual deployment"). Treat the pipeline as build+test+smoke verified, but wire the
> real deploy steps before relying on it for staging.

## 7. Rollback

Ad-hoc, from a workstation (uses `gh` to find the previous ghcr tag):

```bash
bash scripts/rollback_staging.sh              # roll back to the previous image tag
bash scripts/rollback_staging.sh <image-tag>  # roll back to a specific tag
```

CI rollback is the manual `rollback` job (`workflow_dispatch`), also currently simulated. The script
is the working path today.

Before rollback, take a DB backup: `bash scripts/backup_postgres.sh`.

## 8. Observability

| What | Where |
|---|---|
| Grafana | http://localhost:3001 — login `admin` / `GRAFANA_PASSWORD` (default `admin`) |
| Dashboards | `monitoring/grafana/dashboards/`: `sea-overview`, `sea-api-metrics`, `sea-agent-metrics` |
| Prometheus | http://localhost:9090 (config `monitoring/prometheus.yml`, alerts `monitoring/rules/alerts.yml`) |
| Loki | http://localhost:3100 (query from Grafana; datasource `monitoring/grafana/datasources/datasources.yml`) |
| Log shipping | `promtail` tails `/var/log` (`monitoring/promtail-config.yml`) |

## 9. Known blockers (verified 2026-11-04 — updated after fixes)

Resolved since this guide was drafted:
- ~~`httpx2` typo~~ — `httpx2` is a real PyPI package (2.14.0); Docker builds pass.
- ~~Celery worker/scheduler crash-loop~~ — services removed from compose (the real
  queue is RQ; the worker runs inside the `api` container, see `scripts/smoke_deploy.sh`).
- ~~PWA icons / CSP~~ — 192/512 px PNG icons shipped; CSP header in `frontend/nginx.conf`.

Still open:
1. **Deploy/rollback CI jobs are simulated** (§6/§7) — placeholder until real infra
   (a staging host / GHCR-backed deploy target) exists.
2. **Legacy `src/api/` coexists with canonical `backend/app/`** — single FastAPI entry is
   `backend.app.main:app` (Dockerfile CMD); `src/api/` is legacy routes kept for
   reference, slated for removal (structure-cleanup task).

