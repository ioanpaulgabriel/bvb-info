"""Build BVB portfolio notification payloads and publish them to MQTT."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from bvb_scraper.mqtt_client import publish_json

OUTPUT_DIR = Path("/home/bvb/bvb-info/output")
SIGNALS_FILE = OUTPUT_DIR / "new_signals.json"
METRICS_FILE = OUTPUT_DIR / "portfolio_metrics_history_stop8.json"


def load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_action(raw: dict) -> dict:
    action = str(raw.get("action", raw.get("signal", ""))).upper()
    symbol = raw.get("symbol", raw.get("ticker", ""))
    price = raw.get("price", raw.get("entry_price", raw.get("exit_price")))
    quantity = raw.get("quantity", raw.get("shares"))

    result = {
        "action": action,
        "symbol": symbol,
        "price": price,
        "quantity": quantity,
    }

    for key in (
        "allocation_weight",
        "position_size",
        "position_value",
        "risk_amount",
        "stop_loss_price",
        "reason",
    ):
        if key in raw:
            result[key] = raw[key]

    return result


def build_actions_payload() -> dict | None:
    signals = load_json(SIGNALS_FILE)
    if not signals:
        return None

    actions = [normalize_action(item) for item in signals]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "actions": actions,
    }


def pct(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current / previous - 1) * 100


def build_performance_payload(metrics: dict) -> dict:
    curve = metrics.get("atr_dynamic_equity_curve") or metrics.get("daily_equity_curve") or []
    if not curve:
        raise SystemExit("No equity curve found in metrics file")

    latest = curve[-1]
    latest_date = date.fromisoformat(latest["date"])
    latest_equity = float(latest["equity"])

    def equity_days_ago(days: int) -> float | None:
        target = latest_date - timedelta(days=days)
        candidates = [row for row in curve if date.fromisoformat(row["date"]) <= target]
        return float(candidates[-1]["equity"]) if candidates else None

    weekly_equity = equity_days_ago(7)
    monthly_equity = equity_days_ago(30)

    return {
        "date": latest_date.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "daily": {
            "return_pct": float(latest.get("portfolio_return", 0)) * 100,
            "equity": latest_equity,
        },
        "weekly": {
            "return_pct": pct(latest_equity, weekly_equity) if weekly_equity else None,
            "equity": latest_equity,
        },
        "monthly": {
            "return_pct": pct(latest_equity, monthly_equity) if monthly_equity else None,
            "equity": latest_equity,
        },
        "active_positions": latest.get("active_trades", 0),
        "drawdown_pct": float(latest.get("drawdown", 0)) * 100,
        "daily_risk_used_pct": float(latest.get("daily_risk_used", 0)) * 100,
        "daily_risk_remaining_pct": float(latest.get("daily_risk_remaining", 0)) * 100,
    }


def main() -> None:
    metrics = load_json(METRICS_FILE)

    actions_payload = build_actions_payload()
    if actions_payload:
        if not publish_json("portfolio/actions", actions_payload):
            raise SystemExit("MQTT publication failed for portfolio actions")
        print("Published portfolio actions")

    performance_payload = build_performance_payload(metrics)
    if not publish_json("portfolio/performance", performance_payload):
        raise SystemExit("MQTT publication failed for portfolio performance")
    print("Published portfolio performance")


if __name__ == "__main__":
    main()
