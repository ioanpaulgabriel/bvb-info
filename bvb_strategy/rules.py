"""Pilot strategy rules: v1.0_pilot."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    rsi_entry: float = 30.0
    rsi_exit: float = 50.0
    stop_loss: float = -0.08
    min_volume_ratio: float = 1.0
    min_history: int = 50


STRATEGY_VERSION = "v1.0_pilot"


def entry_signal(row, cfg: StrategyConfig) -> bool:
    return (
        row["rsi14"] < cfg.rsi_entry
        and row["volume_ratio"] >= cfg.min_volume_ratio
    )


def exit_signal(entry_price, row, cfg: StrategyConfig):
    ret = row["close"] / entry_price - 1

    if ret <= cfg.stop_loss:
        return True, "stop_loss"
    if row["rsi14"] >= cfg.rsi_exit:
        return True, "rsi_exit"
    return False, None
