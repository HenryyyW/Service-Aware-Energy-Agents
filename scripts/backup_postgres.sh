#!/usr/bin/env bash
# Postgres volume backup script for SEA staging
# Usage: ./scripts/backup_postgres.sh [output-dir]

set -euo pipefail

BACKUP_DIR="${1:-/tmp/sea-backups/$(date -u +%Y%m%d_%H%M%S)}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-sea-postgres}"
DB_NAME="${POSTGRES_DB:-sea_staging}"
DB_USER="${POSTGRES_USER:-sea_user}"

log() { echo "[$(date -u +'%H:%M:%S')] $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"

log "Starting Postgres backup to $BACKUP_DIR"

# Dump schema
log "Dumping schema..."
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" --schema-only > "$BACKUP_DIR/schema.sql"

# Dump data (custom format for faster restore)
log "Dumping data..."
docker exec "$DB_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" --data-only --format=custom > "$BACKUP_DIR/data.dump"

# Full backup (schema + data)
log "Creating full backup..."
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom > "$BACKUP_DIR/full.dump"

# Create manifest
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
SEA Postgres Backup Manifest
Generated: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
Database: $DB_NAME
Container: $CONTAINER_NAME
Files:
  - schema.sql (schema only)
  - data.dump (data only, custom format)
  - full.dump (schema + data, custom format)
EOF

log "Backup complete: $BACKUP_DIR"
log "Files:"
ls -lh "$BACKUP_DIR"