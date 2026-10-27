"""Live signal generator for BVB v1.2_low_volume.

Generates daily entry candidates from the pilot universe and publishes
them to MQTT. It does NOT place orders and does NOT touch any broker.
"""

import json
import os
from datetime import date
from pathlib import Path

import paho.mqtt.client as mqtt
import pandas as pd
from sqlalchemy import text

from bvb_scraper.db.base import get_engine
from bvb_strategy.data import get_pilot_symbols, load_symbol
from bvb_strategy.indicators import add_indicators
from bvb_strategy.rules import StrategyConfig

# --- Configurare ---------------------------------------------------------

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("BVB_MQTT_USERNAME", "")
MQTT_PASS = os.getenv("BVB_MQTT_PASSWORD", "")

MQTT_TOPIC_SIGNALS = "homelab/bvb-info/portfolio/v12/signals"
MQTT_TOPIC_STATUS = "homelab/bvb-info/portfolio/v12/signals/status"

STATE_FILE = Path("/home/bvb/bvb-info/data/live_v12_state.json")
SECTOR_MAP_FILE = Path("/home/bvb/bvb-info/data/sector_map.json")

MAX_OPEN_POSITIONS = 20
MAX_PER_SECTOR = 3
MAX_VOLUME_RATIO = 2.0  # filtrul v1.2_low_volume

START_DATE = date(2021, 1, 1)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"open_positions": []}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_sector_map():
    if SECTOR_MAP_FILE.exists():
        with open(SECTOR_MAP_FILE) as f:
            return json.load(f)
    return {}


def get_raw_signals(engine, cfg: StrategyConfig):
    """Returnează semnalele brute pentru ultima zi disponibilă per simbol."""
    engine_conn = engine.connect()
    symbols = get_pilot_symbols(engine_conn)
    engine_conn.close()

    signals = []

    for symbol in symbols:
        conn = engine.connect()
        df = load_symbol(conn, symbol, START_DATE)
        conn.close()

        if df.empty or len(df) < cfg.min_history:
            continue

        df["symbol"] = symbol
        df = add_indicators(df)

        last = df.iloc[-1]

        if (
            pd.notna(last["rsi14"])
            and pd.notna(last["volume_ratio"])
            and last["rsi14"] < cfg.rsi_entry
            and last["volume_ratio"] >= cfg.min_volume_ratio
        ):
            signals.append({
                "symbol": symbol,
                "signal_date": str(last["date"].date()),
                "close": float(last["close"]),
                "rsi14": float(last["rsi14"]),
                "volume_ratio": float(last["volume_ratio"]),
                "signal_type": "overextended_mean_reversion",
                "strategy_version": "v1.2_low_volume",
            })

    return signals


def apply_v12_filters(signals, state, sector_map):
    """Aplică filtrele v1.2: volum, sloturi, sector, un singur simbol."""
    open_positions = state.get("open_positions", [])

    open_symbols = {p["symbol"] for p in open_positions}
    sector_counts = {}
    for p in open_positions:
        sector = p.get("sector", "UNKNOWN")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    accepted = []
    rejected = []

    for s in sorted(signals, key=lambda x: x["volume_ratio"]):
        symbol = s["symbol"]
        sector = sector_map.get(symbol, "UNKNOWN")
        reasons = []

        if symbol in open_symbols:
            reasons.append("pozitie_deschisa")

        if s["volume_ratio"] >= MAX_VOLUME_RATIO:
            reasons.append("volum_prea_mare")

        if len(open_positions) + len(accepted) >= MAX_OPEN_POSITIONS:
            reasons.append("limita_20_sloturi")

        if sector_counts.get(sector, 0) >= MAX_PER_SECTOR:
            reasons.append("limita_3_pe_sector")

        if reasons:
            rejected.append({**s, "sector": sector, "reject_reasons": reasons})
        else:
            accepted.append({**s, "sector": sector})
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

    return accepted, rejected


def publish(payload):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bvb-live-signal-generator")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    client.publish(
        MQTT_TOPIC_SIGNALS,
        json.dumps(payload, ensure_ascii=False),
        qos=1,
        retain=True,
    )

    client.publish(
        MQTT_TOPIC_STATUS,
        json.dumps({
            "signal_date": payload["signal_date"],
            "raw_signals": payload["raw_count"],
            "accepted": payload["accepted_count"],
            "rejected": payload["rejected_count"],
            "open_positions": payload["open_positions"],
        }, ensure_ascii=False),
        qos=1,
        retain=True,
    )

    client.loop_stop()
    client.disconnect()


def main():
    cfg = StrategyConfig()
    engine = get_engine()

    state = load_state()
    sector_map = load_sector_map()

    raw_signals = get_raw_signals(engine, cfg)
    accepted, rejected = apply_v12_filters(raw_signals, state, sector_map)

    payload = {
        "signal_date": str(date.today()),
        "strategy_version": "v1.2_low_volume",
        "raw_count": len(raw_signals),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "open_positions": len(state.get("open_positions", [])),
        "accepted_signals": accepted,
        "rejected_signals": rejected,
    }

    publish(payload)

    print(f"Semnale brute: {len(raw_signals)}")
    print(f"Acceptate: {len(accepted)}")
    print(f"Respins: {len(rejected)}")
    print(f"Publicat pe: {MQTT_TOPIC_SIGNALS}")


if __name__ == "__main__":
    main()
