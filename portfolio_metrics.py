#!/usr/bin/env python3
"""
Etapa 6 - Metrici de portofoliu pentru strategia BVB.

Calculeaza, dintr-un fisier de tranzactii:
- randament net per tranzactie
- Profit Factor net
- win rate
- Maximum Drawdown
- distributia pierderilor pentru histograma
- impactul unui stop-loss optional

Input CSV minim:
symbol,entry_date,exit_date,entry_price,exit_price

Optional:
volume_ratio
"""

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

COST_RATE = 0.005  # 0.5% cost total per tranzactie


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def read_trades(path):
    trades = []

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entry_price = float(row["entry_price"])
            exit_price = float(row["exit_price"])

            gross_return = (exit_price / entry_price) - 1
            net_return = gross_return - COST_RATE

            trades.append(
                {
                    "symbol": row["symbol"],
                    "entry_date": parse_date(row["entry_date"]),
                    "exit_date": parse_date(row["exit_date"]),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "volume_ratio": float(row["volume_ratio"])
                    if row.get("volume_ratio")
                    else None,
                    "gross_return": gross_return,
                    "net_return": net_return,
                }
            )

    return trades


def apply_stop_loss(trades, stop_loss=None):
    """
    stop_loss = 0.08 inseamna iesire la -8% net.
    Nu modifica tranzactiile originale; returneaza o copie.
    """
    if stop_loss is None:
        return [dict(t) for t in trades]

    result = []

    for trade in trades:
        item = dict(trade)

        if item["net_return"] <= -stop_loss:
            item["net_return"] = -stop_loss
            item["stopped_out"] = True
        else:
            item["stopped_out"] = False

        result.append(item)

    return result


def calculate_metrics(trades):
    if not trades:
        raise ValueError("Nu exista tranzactii de analizat.")

    returns = [t["net_return"] for t in trades]
    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r <= 0]

    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))

    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float("inf")
    )

    equity = 1.0
    equity_curve = [equity]
    peak = equity
    max_drawdown = 0.0

    for value in returns:
        equity *= 1 + value
        equity_curve.append(equity)

        if equity > peak:
            peak = equity

        drawdown = (equity / peak) - 1
        max_drawdown = min(max_drawdown, drawdown)

    stopped = sum(1 for t in trades if t.get("stopped_out"))

    return {
        "total_trades": len(trades),
        "win_rate": len(winners) / len(trades),
        "average_net_return": sum(returns) / len(trades),
        "net_profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "final_equity": equity_curve[-1],
        "stopped_out_trades": stopped,
        "stopped_out_pct": stopped / len(trades),
        "cost_rate": COST_RATE,
        "net_returns": returns,
    }


def save_report(metrics, output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Calculeaza metrici de portofoliu pentru strategia BVB."
    )
    parser.add_argument("trades_csv", help="Fisierul CSV cu tranzactiile")
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=None,
        help="Stop-loss net, ex: 0.08 pentru -8%%",
    )
    parser.add_argument(
        "--output",
        default="output/portfolio_metrics.json",
        help="Fisierul JSON de iesire",
    )

    args = parser.parse_args()

    trades = read_trades(args.trades_csv)
    trades = apply_stop_loss(trades, args.stop_loss)
    metrics = calculate_metrics(trades)

    metrics["configuration"] = {
        "input_file": str(args.trades_csv),
        "stop_loss": args.stop_loss,
    }

    save_report(metrics, args.output)

    print(f"Tranzactii: {metrics['total_trades']}")
    print(f"Win rate: {metrics['win_rate']:.2%}")
    print(f"Randament mediu net: {metrics['average_net_return']:.2%}")
    print(f"Net Profit Factor: {metrics['net_profit_factor']:.4f}")
    print(f"Maximum Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"Tranzactii oprite de stop: {metrics['stopped_out_trades']}")
    print(f"Raport salvat: {args.output}")


if __name__ == "__main__":
    main()
