#!/usr/bin/env bash
# Docker compose end-to-end smoke test
# Validates Phase 1 deployment: up -> health -> agent task -> terminal -> repairs -> down

set -euo pipefail

COMPOSE_FILE="${1:-docker-compose.yml}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-300}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"

log() { echo "[$(date -u +'%H:%M:%S')] $*"; }
fail() { log "FAIL: $*"; exit 1; }

# Cleanup on exit
cleanup() {
    log "Cleaning up..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

log "Starting docker compose..."
# Use pre-built tagged images (CI pulls sea-backend:latest / sea-frontend:latest
# before calling this script). --build would rebuild in-job and blow the timeout.
docker compose -f "$COMPOSE_FILE" up -d --no-build --pull never

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

log "Creating agent task..."
TASK_RESPONSE=$(curl -sf -X POST "$BACKEND_URL/api/agent/tasks" \
    -H "Content-Type: application/json" \
    -d '{"description": "Smoke test: optimize battery dispatch for scenario A", "scenario_id": "scenario_a", "run_id": "smoke_test"}' || fail "Failed to create task")

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

log "Smoke test PASSED"
exit 0