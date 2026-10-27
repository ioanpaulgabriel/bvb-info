"""Portfolio backtest for v1.1_holding_6_20.

Rules:
- Maximum 20 simultaneous positions.
- 5% of current equity allocated per new position.
- One position per symbol.
- Tradeville-style round-trip costs: 0.76% + 0.60 EUR.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import text

from bvb_scraper.db.base import get_engine
from bvb_scraper.logging_config import get_logger

logger = get_logger(__name__)

STRATEGY_VERSION = "v1.2_low_volume"
START_CAPITAL = 10_000.0
MAX_POSITIONS = 20
MAX_POSITIONS_PER_SECTOR = 3
ALLOCATION = 0.05
ROUND_TRIP_PCT = 0.0076
ROUND_TRIP_FIXED_RON = 3.00
OUTPUT_FILE = Path("output/backtest_v11_equity.csv")


def load_sector_map() -> dict[str, str]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol, sector FROM symbol_sector")).all()
    return {symbol: sector for symbol, sector in rows}


def load_trades() -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT symbol, entry_date, exit_date,
                   (exit_price - entry_price) / NULLIF(entry_price, 0) AS gross_return
            FROM strategy_trades
            WHERE strategy_version = :version
            ORDER BY entry_date, symbol
        """), {"version": STRATEGY_VERSION}).mappings().all()

    trades = []
    for row in rows:
        trades.append({
            "symbol": row["symbol"],
            "entry_date": row["entry_date"],
            "exit_date": row["exit_date"],
            "gross_return": float(row["gross_return"]),
        })
    logger.info("Loaded %d trades for %s", len(trades), STRATEGY_VERSION)
    return trades


def get_trading_days(trades: list[dict]) -> list[date]:
    days = set()
    for trade in trades:
        days.add(trade["entry_date"])
        days.add(trade["exit_date"])
    return sorted(days)


def run_backtest() -> dict:
    trades = load_trades()
    sector_map = load_sector_map()
    trading_days = get_trading_days(trades)

    cash = START_CAPITAL
    open_positions: dict[str, dict] = {}
    sector_counts: dict[str, int] = defaultdict(int)
    closed_trades = 0
    skipped_signals = 0
    rejected_same_symbol = 0
    rejected_no_slot = 0
    rejected_sector_limit = 0
    equity_curve: list[dict] = []

    for day in trading_days:
        # Close positions whose exit date has arrived.
        for symbol in sorted(list(open_positions)):
            position = open_positions[symbol]
            if position["exit_date"] <= day:
                allocated = position["allocated"]
                net_return = (
                    position["gross_return"]
                    - ROUND_TRIP_PCT
                    - (ROUND_TRIP_FIXED_RON / allocated)
                )
                proceeds = allocated * (1 + net_return)
                cash += proceeds
                closed_trades += 1
                sector_counts[sector_map.get(symbol, 'OTHER')] -= 1
                del open_positions[symbol]

        # Process new entries on this day.
        for trade in trades:
            if trade["entry_date"] != day:
                continue

            symbol = trade["symbol"]

            if symbol in open_positions:
                rejected_same_symbol += 1
                continue

            sector = sector_map.get(symbol, 'OTHER')

            if sector_counts[sector] >= MAX_POSITIONS_PER_SECTOR:
                rejected_sector_limit += 1
                continue

            if len(open_positions) >= MAX_POSITIONS:
                rejected_no_slot += 1
                continue

            allocated = cash * ALLOCATION
            if allocated <= 0:
                skipped_signals += 1
                continue

            cash -= allocated
            sector_counts[sector] += 1
            open_positions[symbol] = {
                "entry_date": day,
                "exit_date": trade["exit_date"],
                "allocated": allocated,
                "gross_return": trade["gross_return"],
            }

        # Portfolio value: free cash plus open positions at cost.
        portfolio_value = cash + sum(p["allocated"] for p in open_positions.values())
        equity_curve.append({
            "date": day,
            "cash": round(cash, 2),
            "open_positions": len(open_positions),
            "portfolio_value": round(portfolio_value, 2),
        })

    # Close any remaining positions at the end of the test.
    for position in open_positions.values():
        allocated = position["allocated"]
        net_return = (
            position["gross_return"]
            - ROUND_TRIP_PCT
            - (ROUND_TRIP_FIXED_RON / allocated)
        )
        cash += allocated * (1 + net_return)
        closed_trades += 1

    final_value = cash
    peak = START_CAPITAL
    max_drawdown = 0.0

    for point in equity_curve:
        value = point["portfolio_value"]
        peak = max(peak, value)
        drawdown = value / peak - 1
        max_drawdown = min(max_drawdown, drawdown)

    return {
        "trades_loaded": len(trades),
        "closed_trades": closed_trades,
        "rejected_same_symbol": rejected_same_symbol,
        "rejected_no_slot": rejected_no_slot,
        "rejected_sector_limit": rejected_sector_limit,
        "skipped_signals": skipped_signals,
        "final_value": final_value,
        "total_return_pct": (final_value / START_CAPITAL - 1) * 100,
        "max_drawdown_pct": max_drawdown * 100,
        "equity_curve": equity_curve,
    }


def write_equity_curve(curve: list[dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "cash", "open_positions", "portfolio_value"],
        )
        writer.writeheader()
        writer.writerows(curve)
    logger.info("Equity curve written to %s", OUTPUT_FILE)


def main() -> None:
    result = run_backtest()

    print(f"=== Backtest {STRATEGY_VERSION} ===")
    print(f"Tranzacții încărcate: {result['trades_loaded']}")
    print(f"Poziții închise: {result['closed_trades']}")
    print(f"Refuzate: simbol deja deschis: {result['rejected_same_symbol']}")
    print(f"Refuzate: fără slot disponibil: {result['rejected_no_slot']}")
    print(f"Refuzate: limită sector: {result['rejected_sector_limit']}")
    print(f"Refuzate: cash insuficient: {result['skipped_signals']}")
    print(f"Valoare finală: {result['final_value']:.2f} RON")
    print(f"Randament total: {result['total_return_pct']:.2f}%")
    print(f"Drawdown maxim: {result['max_drawdown_pct']:.2f}%")
    print(f"Curba de capital: {OUTPUT_FILE}")

    write_equity_curve(result["equity_curve"])


if __name__ == "__main__":
    main()
