# SEA Production Operations Guide

## Overview
This document describes operational procedures for the Service-Aware Energy Agents (SEA) platform in staging and production environments.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │     │    Backend      │     │   Postgres      │
│   (nginx)       │────▶│   (FastAPI)     │────▶│   (Postgres 16) │
│   Port 80       │     │   Port 8000     │     │   Port 5432     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │   Loki          │
                        │   (Logs)        │
                        └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │   Prometheus    │
                        │   (Metrics)     │
                        └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │   Grafana       │
                        │   (Dashboards)  │
                        └─────────────────┘
```

## Monitoring Stack

### Prometheus Metrics
- **Port**: 9090
- **Config**: `monitoring/prometheus.yml`
- **Rules**: `monitoring/rules/alerts.yml`
- **Retention**: 15 days

### Grafana Dashboards
- **Port**: 3000
- **Dashboards** (auto-provisioned from `monitoring/grafana/dashboards/`):
  - `sea-overview` - Service Overview
  - `sea-api-metrics` - API Metrics (latency, error rate, throughput)
  - `sea-agent-metrics` - Agent & Simulation Metrics

### Loki Log Aggregation
- **Port**: 3100
- **Config**: `monitoring/loki-config.yml`
- **Promtail**: `monitoring/promtail-config.yml`
- **Retention**: 7 days

### Promtail Log Collection
- Collects from: `/var/log`, backend logs, frontend logs, docker containers

## Alerting Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | 5xx rate > 1% for 2m | critical |
| HighLatency | p95 latency > 2s for 5m | warning |
| BackendDown | up{job="backend"} == 0 for 1m | critical |
| HighMemoryUsage | Memory > 85% for 5m | warning |
| HighCPUUsage | CPU > 85% for 5m | warning |
| DiskSpaceLow | Disk < 10% free for 5m | warning |
| AgentTaskQueueBacklog | Queue depth > 100 for 5m | warning |
| SimulationQueueStalled | No completions in 10m but pending > 0 | critical |
| BuildFailure | CI workflow failed | critical |

## Deployment

### Staging Deployment
- **Trigger**: Push to `main` branch
- **Pipeline**: GitHub Actions (`.github/workflows/ci-cd.yml`)
- **Steps**:
  1. Lint & Type Check (black, ruff, mypy - advisory)
  2. Python Tests (pytest)
  3. Frontend Build & Lint
  4. Seed Reproducibility
  5. Artifact Hygiene
  5. Build Docker Images
  6. Frontend Quality Gates (Lighthouse CI + axe-core)
  6. Docker Compose Smoke Test
  7. Alembic Migration Test
  8. Deploy to Staging (auto on main)
  9. Deploy to Production (manual approval)

### Staging Environment
- **URL**: http://staging.sea.local (or configured domain)
- **API**: http://staging.sea.local/api
- **Grafana**: http://staging.sea.local:3000 (admin/admin)

### Production Environment
- **Trigger**: Manual workflow dispatch
- **Approval**: Manual approval required
- **Rollback**: `scripts/rollback_staging.sh` (works for both staging/prod)

## Rollback Procedures

### Quick Rollback (Staging)
```bash
./scripts/rollback_staging.sh
# or specific tag
./scripts/rollback_staging.sh <tag>
```

### Production Rollback
```bash
# Manual approval required
gh workflow run ci-cd.yml -f environment=production
# Or manual rollback
./scripts/rollback_staging.sh <previous-tag>
```

### Rollback Verification
1. Health checks pass (`/health`, `/ready`)
2. Smoke test passes (`scripts/smoke_deploy.sh`)
3. Grafana dashboards show normal metrics
3. Loki logs show normal operation

## Database Operations

### Backup
```bash
# Manual backup
./scripts/backup_postgres.sh /path/to/backup/dir

# Automated (cron)
0 2 * * * /path/to/scripts/backup_postgres.sh /backups/postgres
```

### Restore
```bash
# From full dump
docker exec -i sea-postgres pg_restore -U sea_user -d sea_staging < /backups/postgres/full.dump

# Schema only
docker exec -i sea-postgres psql -U sea_user -d sea_staging < /backups/postgres/schema.sql

# Data only
docker exec -i sea_staging pg_restore -U sea_user -d sea_staging /backups/postgres/data.dump
```

### Migration
```bash
# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Check current revision
alembic current
```

## Log Management

### Loki Queries
```logql
# All backend logs
{job="sea-backend"}

# Error logs
{job="sea-backend"} |~ "(?i)error|exception|traceback"

# Specific service
{job="sea-backend", service="sea-backend"}

# Frontend logs
{job="sea-frontend"}
```

### Log Retention
- Loki: 7 days (configurable in `loki-config.yml`)
- Promtail: forwards docker logs, system logs, app logs

## Troubleshooting

### Common Issues

| Symptom | Check | Resolution |
|---------|-------|------------|
| Backend 500 errors | `docker logs sea-backend` | Check traceback, restart if needed |
| High latency | Grafana API Latency panel | Check queue depth, scale if needed |
| Queue backlog | Grafana Agent Queue panel | Scale workers, check for stuck tasks |
| DB connection errors | `docker logs sea-postgres` | Check connection pool, restart backend |
| Loki no logs | `docker logs loki` | Check Promtail config, restart Promtail |
| High memory | Grafana Memory panel | Restart container, check for leaks |

### Emergency Contacts
- **On-call**: Check PagerDuty / Slack #oncall
- **Backend**: Backend Engineer A/B
- **Frontend**: Frontend Engineer
- **Infra**: QA/DevOps

## Runbook: Staging Deployment Checklist

### Pre-deployment
- [ ] All CI checks pass
- [ ] Frontend Quality Gates pass (Lighthouse >90, axe 0 violations)
- [ ] Smoke test passes locally
- [ ] Alembic migration test passes

### Deployment
- [ ] Push to main triggers pipeline
- [ ] All CI jobs pass (green)
- [ ] Staging deployment completes
- [ ] Health checks pass (`/health`, `/ready`)

### Post-deployment Validation
- [ ] API endpoints respond correctly
- [ ] Frontend loads without console errors
- [ ] Grafana dashboards show data
- [ ] Loki shows recent logs
- [ ] Smoke test passes in staging
- [ ] Alembic migration applied successfully

### Rollback Trigger
- [ ] Error rate > 5% for 5 minutes
- [ ] p99 latency > 10s
- [ ] Critical functionality broken
- [ ] Data corruption detected

## Runbook: Production Deployment

### Pre-deployment
- [ ] Staging validated for 24h minimum
- [ ] All stakeholders sign off
- [ ] Rollback plan reviewed
- [ ] Database migration reviewed (if applicable)

### Deployment
- [ ] Manual workflow dispatch with `environment=production`
- [ ] Approval from PM + Tech Lead
- [ ] Deploy executes
- [ ] Health checks pass

### Post-deployment
- [ ] Monitor error rate for 30 min
- [ ] Monitor latency for 30 min
- [ ] Verify key user flows
- [ ] Update status page

### Rollback (if needed)
- [ ] Execute rollback workflow
- [ ] Verify health checks
- [ ] Notify stakeholders
- [ ] Post-mortem scheduled

## Maintenance Windows
- **Weekly**: Sunday 02:00-04:00 UTC (automated updates)
- **Monthly**: First Sunday 01:00-05:00 UTC (OS patches, DB maintenance)
- **Quarterly**: Security audit, dependency updates

## Escalation Matrix

| Level | Trigger | Response Time | Contacts |
|-------|---------|---------------|----------|
| P1 | Service down, data loss | 15 min | On-call + PM + Tech Lead |
| P2 | Degraded performance, partial outage | 1 hour | On-call + PM |
| P3 | Minor issues, non-critical bugs | 4 hours | Team |

## Security
- All secrets in GitHub Secrets / OpenBot Vault
- TLS everywhere (internal mTLS where possible)
- Regular dependency scanning (Dependabot)
- Annual penetration test
- SOC2 compliance (in progress)

## CityLearn Dataset Prefetching (CI determinism gate)

The Seed Reproducibility job resolves CityLearn datasets from GitHub on cache
miss; the GitHub API rate-limits that endpoint (HTTP 403), colouring the
pipeline red for environmental (not determinism) reasons.

**Fix: `scripts/prefetch_citylearn.py`** vendors datasets into CityLearn's
cache (`~/.cache/citylearn/<tag>/datasets/`) BEFORE the job runs:

- `citylearn_challenge_2020_climate_zone_1` (4.6 MB) — copied from the
  repo-tracked copy at `experiments/reference/` (zero network; also the
  dataset the smoke/agent path uses, baked into the API image at
  `/app/citylearn_datasets/` by the Dockerfile).
- `citylearn_challenge_2022_phase_all_plus_evs` (13 MB) — downloaded once via
  CityLearn's own machinery with 3 retries + backoff, then cached by
  `actions/cache` (key `citylearn-datasets-v1-*`) so subsequent runs make zero
  GitHub API calls. 13 MB is ~30% over the ~10 MB artifact guideline; the
  full (unpruned) dataset is required because the adapter derives
  `building_ids` from the dataset schema — pruning it would change the
  simulation and break determinism vs the paper's runs.

Determinism gate: the CI job runs prefetch **twice** and asserts identical
`DATASET_SHA256` values — proving the vendored cache is byte-stable whether
sourced from the repo reference or a download. The reproducibility run then
executes with `CITYLEARN_OFFLINE=1`, so any mid-run download attempt fails
loudly instead of 403-flaking.

Local usage:

```bash
python scripts/prefetch_citylearn.py --check          # exit 0 if cached
python scripts/prefetch_citylearn.py                  # vendor the CI set
python scripts/prefetch_citylearn.py --dataset <name> # one dataset
```

Exit codes: 0 = vendored/cached; 1 = vendoring failed after retries; 2 = unused.
(The smoke path needs no prefetch: the api container ships the dataset baked
in, so it never resolves from GitHub regardless of runner state.)

## Appendix: Useful Commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres

# Restart services
docker compose restart backend
docker compose restart frontend

# Scale
docker compose up -d --scale backend=3

# Execute in container
docker compose exec backend bash
docker compose exec frontend sh

# Database shell
docker exec -it sea-postgres psql -U sea_user -d sea_staging

# View metrics
curl http://localhost:9090/api/v1/query?query=up

# Force rebuild
docker compose build --no-cache backend
```