"""Data access for the BVB pilot universe."""
import pandas as pd
from sqlalchemy import text


def get_pilot_symbols(conn):
    rows = conn.execute(text(
        "SELECT symbol FROM v_market_universe_pilot ORDER BY symbol"
    )).fetchall()
    return [r[0] for r in rows]


def load_symbol(conn, symbol, start_date):
    query = text("""
        SELECT date, open_adjusted AS open, high_adjusted AS high,
               low_adjusted AS low, close_adjusted AS close, volume
        FROM ohlcv_bvb_adjusted
        WHERE symbol = :symbol
          AND date >= :start_date
          AND volume > 0
        ORDER BY date ASC
    """)
    rows = conn.execute(
        query,
        {"symbol": symbol, "start_date": start_date},
    ).fetchall()

    df = pd.DataFrame(
        rows,
        columns=["date", "open", "high", "low", "close", "volume"],
    )
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    df = df[df["volume"] > 0].reset_index(drop=True)
    return df
