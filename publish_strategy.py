"""Publish BVB strategy results to Home Assistant via MQTT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bvb_scraper.mqtt_client import publish_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish BVB strategy results to MQTT/Home Assistant"
    )
    parser.add_argument(
        "input",
        help="Path to a JSON file containing strategy results"
    )
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    required = {"strategy", "status", "generated_at"}
    missing = required - payload.keys()
    if missing:
        raise SystemExit(f"Missing required fields: {', '.join(sorted(missing))}")

    ok = publish_json("strategy/status", payload)

    if not ok:
        raise SystemExit("MQTT publication failed")

    print(f"Published strategy status to homelab/bvb-info/strategy/status")


if __name__ == "__main__":
    main()
