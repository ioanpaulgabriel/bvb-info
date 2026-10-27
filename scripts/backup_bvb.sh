#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="/home/bvb/bvb-backups"
DB_DIR="$BACKUP_ROOT/db"
LOG_FILE="$BACKUP_ROOT/logs/backup.log"
RETENTION_DAYS=7
STAMP="$(date +%F_%H%M%S)"
DB_FILE="$DB_DIR/bvb_data_${STAMP}.sql.gz"

mkdir -p "$DB_DIR" "$(dirname "$LOG_FILE")"

log() {
  printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG_FILE"
}

cd /home/bvb/bvb-info

# Citim BVB_DATABASE_URL din .env fără a-l afișa în log.
set -a
source .env
set +a

DB_URL="${BVB_DATABASE_URL//postgresql+psycopg2:\/\//postgresql://}"

pg_dump "$DB_URL" --no-owner --no-privileges | gzip -9 > "$DB_FILE"

find "$DB_DIR" -type f -name 'bvb_data_*.sql.gz' -mtime +"$RETENTION_DAYS" -delete

log "DB backup creat: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"
log "Retenție DB: păstrate maxim ultimele $RETENTION_DAYS zile"
