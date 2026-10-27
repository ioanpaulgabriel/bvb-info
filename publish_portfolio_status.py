"""Publish v1.1 portfolio status to Home Assistant via MQTT."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from backtest import run_backtest
from bvb_scraper.logging_config import get_logger

logger = get_logger(__name__)

MQTT_HOST = os.getenv("BVB_MQTT_HOST", "192.168.1.186")
MQTT_PORT = int(os.getenv("BVB_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("BVB_MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("BVB_MQTT_PASSWORD")
TOPIC_PREFIX = os.getenv("BVB_MQTT_TOPIC_PREFIX", "homelab/bvb-info")

STATE_TOPIC = f"{TOPIC_PREFIX}/portfolio/v11/status"
CONFIG_TOPIC = "homeassistant/sensor/bvb_portfolio_v11/config"


def build_state() -> dict:
    result = run_backtest()
    curve = result["equity_curve"]
    latest = curve[-1]

    peak = max(point["portfolio_value"] for point in curve)
    current_drawdown = (latest["portfolio_value"] / peak - 1) * 100

    return {
        "portfolio_value": round(latest["portfolio_value"], 2),
        "cash": round(latest["cash"], 2),
        "open_positions": latest["open_positions"],
        "current_drawdown_pct": round(current_drawdown, 2),
        "max_drawdown_pct": round(result["max_drawdown_pct"], 2),
        "total_return_pct": round(result["total_return_pct"], 2),
        "closed_trades": result["closed_trades"],
        "strategy_version": "v1.2_low_volume",
        "last_update": datetime.now(timezone.utc).isoformat(),
    }


def publish() -> None:
    state = build_state()

    client = mqtt.Client(client_id="bvb-portfolio-v11", protocol=mqtt.MQTTv311)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    discovery = {
        "name": "BVB Portfolio v1.1 Value",
        "unique_id": "bvb_portfolio_v11_value",
        "state_topic": STATE_TOPIC,
        "json_attributes_topic": STATE_TOPIC,
        "value_template": "{{ value_json.portfolio_value }}",
        "unit_of_measurement": "RON",
        "currency": "RON",
        "state_class": "measurement",
        "device": {
            "identifiers": ["bvb_info_homelab"],
            "name": "BVB Info Homelab",
            "manufacturer": "bvb-info",
        },
    }

    client.publish(CONFIG_TOPIC, json.dumps(discovery), retain=True)
    client.publish(STATE_TOPIC, json.dumps(state), retain=True)

    client.loop_stop()
    client.disconnect()

    logger.info("Published portfolio status: %s", state)


if __name__ == "__main__":
    publish()
