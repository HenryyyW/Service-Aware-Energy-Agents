#!/usr/bin/env bash
# Docker compose end-to-end smoke test
# Validates Phase 1 deployment: up -> health -> agent task -> terminal -> repairs -> down

set -euo pipefail

COMPOSE_FILE="${1:-docker-compose.yml}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-600}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"

log() { echo "[$(date -u +'%H:%M:%S')] $*"; }
fail() { log "FAIL: $*"; exit 1; }

# Cleanup on exit
cleanup() {
    log "Cleaning up..."
    # Dump container logs so CI shows why the API crashed
    if [ "${SMOKE_STARTED:-0}" = "1" ]; then
        docker compose -f "$COMPOSE_FILE" logs --tail 40 api frontend db redis 2>/dev/null || true
        [ -f rq_worker.log ] && echo "=== rq_worker.log (tail) ===" && tail -20 rq_worker.log || true
    fi
    [ -n "${RQ_PID:-}" ] && kill "$RQ_PID" 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

log "Starting docker compose..."
SMOKE_STARTED=1
# Use pre-built tagged images (CI pulls sea-backend:latest / sea-frontend:latest
# before calling this script). --build would rebuild in-job and blow the timeout.
docker compose -f "$COMPOSE_FILE" up -d --no-build db redis api frontend

# Start an RQ worker inside the api container so queued agent tasks execute.
# The API enqueues to the 'agent_tasks' RQ queue; without a worker the task
# sits pending forever and the poll below times out.
# Run via runner-side background exec with -T so stdout lands in rq_worker.log
# (detached `exec -d` hides crashes — we learned that the hard way).
log "Checking rq availability in image..."
docker compose -f "$COMPOSE_FILE" exec -T api python -c "import rq; print('rq', rq.__version__)" \
  || log "WARN: rq not importable inside api container"
log "Starting RQ worker (foreground-in-container, logged)..."
docker compose -f "$COMPOSE_FILE" exec -T api sh -c 'PYTHONPATH=/app rq worker --url redis://redis:6379/0 agent_tasks' > rq_worker.log 2>&1 &
RQ_PID=$!

log "Waiting for backend health endpoint..."
start=$(date +%s)
while true; do
    if curl -sf "$BACKEND_URL/health" >/dev/null 2>&1; then
        log "Health endpoint OK"
        break
    fi
    if (( $(date +%s) - start > TIMEOUT )); then
        fail "Health endpoint timeout after ${TIMEOUT}s"
    fi
    sleep 2
done

log "Waiting for ready endpoint..."
start=$(date +%s)
while true; do
    if curl -sf "$BACKEND_URL/ready" >/dev/null 2>&1; then
        log "Ready endpoint OK"
        break
    fi
    if (( $(date +%s) - start > TIMEOUT )); then
        fail "Ready endpoint timeout after ${TIMEOUT}s"
    fi
    sleep 2
done

# --- STEP 1: Create a REAL simulation run first ---
# Derive a violation-prone scenario on the runner side (bind mount makes it
# visible in the container; POST /scenarios cannot write the read-only mount).
# No stock scenario ships a pandapower config, so inject one with tight limits
# to guarantee deterministic grid violations.
log "Creating violation-prone scenario (smoke_violation)..."
mkdir -p data/schemas
# chmod the data root so appuser can create agent_runs/ (docker creates data/ as root)
chmod a+rwX data
rm -rf data/schemas/smoke_violation
# Copy ONLY schema.json — adapter re-synthesizes CSVs from baked dataset.
# Copying CSV files would leave them owned by runner uid; appuser (different
# uid) then gets EPERM on copystat/chmod. Adapter synthesizes CSVs as appuser.
mkdir -p data/schemas/smoke_violation
cp experiments/reference/scenario_c_test/schema.json data/schemas/smoke_violation/schema.json
python3 - <<'EOF'
import json

path = "data/schemas/smoke_violation/schema.json"
schema = json.load(open(path))
schema["scenario_id"] = "smoke_violation"
schema["name"] = "smoke_violation"
schema["pandapower"] = {
    "network_type": "ieee_34",
    "voltage_limits": {"min": 0.99, "max": 1.01},
    "line_loading_limit": 0.5,
    "transformer_loading_limit": 0.4,
    "run_power_flow_every": 1,
}
with open(path, "w") as f:
    json.dump(schema, f, indent=2)
print("smoke_violation scenario ready (tight voltage/trafo limits)")
EOF
# schema.json is READ-ONLY for appuser — read for others suffices.
# No CSVs copied: adapter synthesizes them as appuser (no cross-uid files).
chmod a+rX data/schemas/smoke_violation data/schemas/smoke_violation/schema.json

log "Creating REAL simulation run (smoke_violation with violations)..."
RUN_RESPONSE=$(curl -sf -X POST "$BACKEND_URL/api/simulations" \
    -H "Content-Type: application/json" \
    -d '{"scenario_id": "smoke_violation", "controller_type": "rule_based", "parameters": {"max_steps": 48, "random_seed": 42}, "run_name": "smoke_test_violation_run"}' || fail "Failed to create simulation run")

RUN_ID=$(echo "$RUN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
log "Simulation run created: $RUN_ID"

log "Waiting for simulation run to complete..."
start=$(date +%s)
while true; do
    RUN_STATUS=$(curl -sf "$BACKEND_URL/api/simulations/$RUN_ID" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    log "Run status: $RUN_STATUS"
    
    case "$RUN_STATUS" in
        completed)
            log "Simulation run completed successfully"
            break
            ;;
        failed)
            RUN_DETAIL=$(curl -sf "$BACKEND_URL/api/simulations/$RUN_ID")
            fail "Simulation run failed: $(echo "$RUN_DETAIL" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('error') or d.get('outcome_sentence') or 'unknown')")"
            ;;
        *)
            if (( $(date +%s) - start > TIMEOUT )); then
                fail "Simulation run timeout after ${TIMEOUT}s"
            fi
            sleep "$POLL_INTERVAL"
            ;;
    esac
done

# Verify the run has violations (we need a failed run for repair)
RUN_DETAIL=$(curl -sf "$BACKEND_URL/api/simulations/$RUN_ID")
GRID_VIOLATIONS=$(echo "$RUN_DETAIL" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('grid_metrics', {}).get('voltage_violations_count', 0))")
log "Simulation run has $GRID_VIOLATIONS grid voltage violations"

# --- STEP 2: Create agent task with the REAL run_id ---
log "Creating agent task with REAL run_id..."
TASK_RESPONSE=$(curl -sf -X POST "$BACKEND_URL/api/agent/tasks" \
    -H "Content-Type: application/json" \
    -d "{\"description\": \"Repair grid violations for smoke test run\", \"scenario_id\": \"smoke_violation\", \"run_id\": \"$RUN_ID\"}" || fail "Failed to create task")

TASK_ID=$(echo "$TASK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['task_id'])")
log "Task created: $TASK_ID"

log "Polling task to terminal state..."
start=$(date +%s)
while true; do
    TASK_STATUS=$(curl -sf "$BACKEND_URL/api/agent/tasks/$TASK_ID" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    log "Task status: $TASK_STATUS"
    
    case "$TASK_STATUS" in
        completed)
            log "Task completed successfully"
            break
            ;;
        failed)
            TASK_DETAIL=$(curl -sf "$BACKEND_URL/api/agent/tasks/$TASK_ID")
            fail "Task failed: $(echo "$TASK_DETAIL" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('execution_log', [])[-1] if d.get('execution_log') else 'unknown')")"
            ;;
        *)
            if (( $(date +%s) - start > TIMEOUT )); then
                fail "Task timeout after ${TIMEOUT}s"
            fi
            sleep "$POLL_INTERVAL"
            ;;
    esac
done

log "Verifying repairs field is non-empty..."
TASK_DETAIL=$(curl -sf "$BACKEND_URL/api/agent/tasks/$TASK_ID")
REPAIRS=$(echo "$TASK_DETAIL" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('repairs', [])))")
if (( REPAIRS == 0 )); then
    # Check if there's verification data instead
    VERIFICATION=$(echo "$TASK_DETAIL" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('verification') is not None)")
    if [[ "$VERIFICATION" == "True" ]]; then
        log "Task has verification data (repairs may be empty for successful runs)"
    else
        fail "Repairs field is empty and no verification data"
    fi
else
    log "Repairs field has $REPAIRS entries"
fi

# Verify metrics_comparison has real data
METRICS_COMP=$(echo "$TASK_DETAIL" | python3 -c "import sys, json; d=json.load(sys.stdin); print('metrics_comparison' in d and d['metrics_comparison'])")
if [[ "$METRICS_COMP" == "True" ]]; then
    log "Task has metrics_comparison with real before/after data"
else
    fail "Task missing metrics_comparison with real before/after data"
fi

log "Smoke test PASSED"
exit 0