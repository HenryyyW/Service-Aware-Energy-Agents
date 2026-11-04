#!/usr/bin/env bash
# Staging rollback script for SEA
# Usage: ./scripts/rollback_staging.sh [previous|<image-tag>]

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
BACKEND_IMAGE="${BACKEND_IMAGE:-ghcr.io/henryyyw/service-aware-energy-agents-backend}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-ghcr.io/henryyyw/service-aware-energy-agents-frontend}"

log() { echo "[$(date -u +'%H:%M:%S')] $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

# Get previous image tag from GitHub Container Registry
get_previous_tag() {
    local image_name="$1"
    # Get all tags, exclude 'latest', sort by creation date, get second one (first is current)
    gh api "/users/henryyyw/packages/container/${image_name}/versions" --jq '.[].metadata.container.tags[]' 2>/dev/null | grep -v '^latest$' | head -2 | tail -1
}

# Rollback to specific tag or previous
rollback_image() {
    local image_name="$1"
    local tag="${2:-}"
    
    if [[ -z "$tag" ]]; then
        tag=$(get_previous_tag "$image_name")
        if [[ -z "$tag" ]]; then
            fail "Could not determine previous tag for $image_name"
        fi
        log "Auto-detected previous tag: $tag"
    fi
    
    log "Rolling back $image_name to tag: $tag"
    
    # Pull the previous image
    docker pull "ghcr.io/henryyyw/${image_name}:${tag}"
    
    # Tag it as latest for docker-compose
    docker tag "ghcr.io/henryyyw/${image_name}:${tag}" "${image_name}:latest"
}

# Main rollback function
main() {
    local target="${1:-previous}"
    
    log "Starting staging rollback..."
    log "Target: $target"
    
    # Determine tags
    local backend_tag="${BACKEND_TAG:-}"
    local frontend_tag="${FRONTEND_TAG:-}"
    
    if [[ "$target" != "previous" ]]; then
        backend_tag="$target"
        frontend_tag="$target"
    fi
    
    # Rollback backend
    rollback_image "service-aware-energy-agents-backend" "$backend_tag"
    
    # Rollback frontend
    rollback_image "service-aware-energy-agents-frontend" "$frontend_tag"
    
    # Restart with docker-compose
    log "Restarting services with rolled back images..."
    docker compose -f docker-compose.yml down
    docker compose -f docker-compose.yml up -d
    
    # Wait for health checks
    log "Waiting for health checks..."
    local timeout=120
    local start=$(date +%s)
    
    while true; do
        if curl -sf http://localhost:8000/health >/dev/null 2>&1 && \
           curl -sf http://localhost/ >/dev/null 2>&1; then
            log "Health checks passed - rollback complete!"
            break
        fi
        if (( $(date +%s) - start > timeout )); then
            fail "Health checks timeout after ${timeout}s"
        fi
        sleep 5
    done
    
    log "Rollback completed successfully!"
}

# Allow sourcing for testing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi