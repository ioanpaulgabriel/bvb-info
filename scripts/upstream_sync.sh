#!/usr/bin/env bash
set -uo pipefail

cd /home/bvb/bvb-info || exit 1

LOG="/home/bvb/bvb-info/logs/upstream_sync.log"
mkdir -p "$(dirname "$LOG")"

{
    echo "=== upstream sync started: $(date -Is) ==="

    if git fetch upstream &&
       git merge --ff-only upstream/master &&
       git push origin master; then
        echo "upstream sync OK: $(date -Is)"
        echo "=== upstream sync finished: $(date -Is) ==="
        exit 0
    fi

    echo "upstream sync FAILED: $(date -Is)"
    echo "=== upstream sync finished: $(date -Is) ==="

    /home/bvb/bvb-info/.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from bvb_scraper.mqtt_client import publish_json

publish_json(
    "upstream_sync/status",
    {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "status": "error",
        "error_details": {
            "failing_command": "scripts/upstream_sync.sh",
            "message": "Upstream Git synchronization failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    },
)
PY

    exit 1
} >> "$LOG" 2>&1
