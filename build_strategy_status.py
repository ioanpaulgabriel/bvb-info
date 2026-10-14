"""Build strategy_status.json from bvb-data-worker metrics and daily signals."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

METRICS_FILE = Path("/home/bvb/bvb-info/output/portfolio_metrics_history_stop8.json")
SIGNALS_FILE = Path("/home/bvb/bvb-info/output/new_signals.json")
OUTPUT_FILE = Path("/home/bvb/bvb-info/strategy_status.json")

STRATEGY_NAME = "bvb_overextended_mean_reversion"
STRATEGY_VERSION = "v1.0_stop8"


def main() -> None:
    if not METRICS_FILE.exists():
        raise SystemExit(f"Metrics file not found: {METRICS_FILE}")

    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    new_signals = 0
    if SIGNALS_FILE.exists():
        signals = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
        new_signals = len(signals) if isinstance(signals, list) else 0

    payload = {
        "strategy": STRATEGY_NAME,
        "version": STRATEGY_VERSION,
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "total_trades": metrics.get("total_trades", 0),
        "new_signals": new_signals,
        "win_rate": metrics.get("win_rate", 0),
        "average_net_return": metrics.get("average_net_return", 0),
        "net_profit_factor": metrics.get("net_profit_factor", 0),
        "max_drawdown": metrics.get("max_drawdown", 0),
        "stop_loss": metrics.get("configuration", {}).get("stop_loss", 0.08),
        "stopped_out_trades": metrics.get("stopped_out_trades", 0),
        "final_equity": metrics.get("final_equity", 0),
        "cost_rate": metrics.get("cost_rate", 0),
        "risk_status": metrics.get(
            "risk_status",
            {
                "date": None,
                "status": "UNKNOWN",
                "daily_risk_used": 0,
                "daily_risk_remaining": 0,
            },
        ),
    }

    OUTPUT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Strategy status written to {OUTPUT_FILE}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
