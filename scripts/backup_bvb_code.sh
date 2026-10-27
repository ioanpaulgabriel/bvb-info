#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="/home/bvb/bvb-backups"
CODE_DIR="$BACKUP_ROOT/code"
LOG_FILE="$BACKUP_ROOT/logs/backup.log"
RETENTION_DAYS=14
STAMP="$(date +%F_%H%M%S)"
ARCHIVE="$CODE_DIR/bvb_code_${STAMP}.tar.gz"

mkdir -p "$CODE_DIR" "$(dirname "$LOG_FILE")"

log() {
  printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG_FILE"
}

cd /home/bvb

tar -czf "$ARCHIVE" \
  --exclude='bvb-info/.venv' \
  --exclude='bvb-info/logs' \
  --exclude='bvb-info/output' \
  --exclude='bvb-info/data/raw' \
  --exclude='bvb-info/backups' \
  --exclude='bvb-info/__pycache__' \
  --exclude='bvb-data-worker/.venv' \
  --exclude='bvb-data-worker/logs' \
  --exclude='bvb-data-worker/output' \
  --exclude='bvb-data-worker/data/raw' \
  --exclude='bvb-data-worker/backups' \
  --exclude='bvb-data-worker/__pycache__' \
  --exclude='*.bak' \
  --exclude='*.bak.*' \
  --exclude='*.bak-*' \
  bvb-info/bvb_daily.sh \
  bvb-info/*.py \
  bvb-info/db \
  bvb-info/scripts \
  bvb-info/.env \
  bvb-data-worker/src \
  bvb-data-worker/scripts \
  bvb-data-worker/tests \
  bvb-data-worker/migrations \
  bvb-data-worker/config \
  bvb-data-worker/.env \
  2>/dev/null || true

chmod 600 "$ARCHIVE"

find "$CODE_DIR" -type f -name 'bvb_code_*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

log "Code backup creat: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
log "Retenție cod: păstrate maxim ultimele $RETENTION_DAYS zile"
