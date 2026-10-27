"""Backtest engine for a single-symbol OHLCV series."""
from .rules import StrategyConfig, STRATEGY_VERSION, entry_signal, exit_signal


def find_trades(df, cfg: StrategyConfig = StrategyConfig()):
    trades = []
    position_open_until = -1

    for i in range(len(df)):
        if i <= position_open_until:
            continue

        row = df.iloc[i]

        if i < cfg.min_history:
            continue

        if not entry_signal(row, cfg):
            continue

        entry_date = row["date"]
        entry_price = row["close"]
        exit_date = None
        exit_price = None
        exit_type = None

        for j in range(i + 1, len(df)):
            candidate = df.iloc[j]
            should_exit, reason = exit_signal(entry_price, candidate, cfg)

            if should_exit:
                exit_date = candidate["date"]
                exit_price = candidate["close"]
                exit_type = reason
                position_open_until = j
                break

        if exit_date is None:
            continue

        trades.append({
            "symbol": df.iloc[i]["symbol"] if "symbol" in df else None,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "volume_ratio": row["volume_ratio"],
            "signal_type": "overextended_mean_reversion",
            "exit_type": exit_type,
            "strategy_version": STRATEGY_VERSION,
        })

    return trades
