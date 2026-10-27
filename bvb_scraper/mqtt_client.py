"""Minimal MQTT publisher for Home Assistant notifications."""

from __future__ import annotations

import json
from typing import Any

from bvb_scraper.config import settings
from bvb_scraper.logging_config import get_logger

logger = get_logger(__name__)


def publish_json(topic_suffix: str, payload: dict[str, Any]) -> bool:
    """Publish a JSON payload; failures must never break the ETL run."""
    if not settings.mqtt_enabled:
        logger.debug("MQTT disabled; skipping publication")
        return False

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logger.warning("paho-mqtt is not installed; MQTT publication skipped")
        return False

    topic = f"{settings.mqtt_topic_prefix.rstrip('/')}/{topic_suffix.lstrip('/')}"
    message = json.dumps(payload, default=str, ensure_ascii=False)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    if settings.mqtt_username:
        client.username_pw_set(
            settings.mqtt_username,
            settings.mqtt_password,
        )

    try:
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        client.loop_start()

        info = client.publish(topic, message, qos=1, retain=True)
        info.wait_for_publish(timeout=10)

        client.loop_stop()
        client.disconnect()
    except Exception as exc:
        logger.warning("MQTT publication to %s failed: %s", topic, exc)
        return False

    logger.info("MQTT published: %s", topic)
    return True
