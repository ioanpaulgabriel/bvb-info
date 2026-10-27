#!/usr/bin/env python3
"""Publishes a defensive MQTT failure alert for bvb_daily.sh."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from bvb_scraper.mqtt_client import publish_json


def main() -> int:
    exit_code = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    payload = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "status": "error",
        "error_details": {
            "failing_command": "bvb_daily.sh",
            "exit_code": exit_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    published = publish_json("update/status", payload)
    return 0 if published else 1


if __name__ == "__main__":
    raise SystemExit(main())
