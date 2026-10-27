#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/bvb/bvb-info"
LOCK_FILE="/tmp/bvb-info-daily-update.lock"
LOG_PREFIX="[$(date --iso-8601=seconds)]"

cd "$PROJECT_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$LOG_PREFIX SKIP: o alta rulare este deja activa"
    exit 0
fi

echo "$LOG_PREFIX START bvb-info daily update"
echo "$LOG_PREFIX COMMIT $(git rev-parse HEAD)"

source .venv/bin/activate

echo "$LOG_PREFIX RUN bvb_scraper update-all --no-details"
python -m bvb_scraper.main update-all --no-details

echo "$LOG_PREFIX SUCCESS"
