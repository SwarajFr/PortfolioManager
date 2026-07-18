from __future__ import annotations

import datetime
import pandas as pd
from core.kite import get_kite

FETCH_CHUNK_DAYS = 180
MAX_LOOKBACK_DAYS = 900


def get_holdings() -> pd.DataFrame:
    kite = get_kite()
    return pd.DataFrame(kite.holdings())


def get_prices(holdings: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    Returns (prices_df, weights) where:
      prices_df: DataFrame with ticker columns, date index, close prices
      weights: {ticker: fraction} summing to 1
    """
    kite = get_kite()
    today = datetime.date.today()
    start = today - datetime.timedelta(days=MAX_LOOKBACK_DAYS)

    token_to_symbol: dict[int, str] = {
        int(row["instrument_token"]): str(row["tradingsymbol"])
        for _, row in holdings.iterrows()
    }

    price_series: dict[str, pd.Series] = {}
    for token, symbol in token_to_symbol.items():
        chunks = []
        chunk_start = start
        while chunk_start < today:
            chunk_end = min(chunk_start + datetime.timedelta(days=FETCH_CHUNK_DAYS), today)
            try:
                candles = kite.historical_data(token, chunk_start, chunk_end, "day")
                if candles:
                    df = pd.DataFrame(candles)
                    chunks.append(df.set_index("date")["close"])
            except Exception:
                pass
            chunk_start = chunk_end + datetime.timedelta(days=1)
        if chunks:
            price_series[symbol] = pd.concat(chunks).sort_index()

    if not price_series:
        return pd.DataFrame(), {}

    prices = pd.DataFrame(price_series).sort_index()

    # Build weights from current holdings value
    value_map: dict[str, float] = {}
    for _, row in holdings.iterrows():
        sym = str(row["tradingsymbol"])
        if sym in prices.columns:
            value_map[sym] = float(row.get("last_price", 0)) * float(row.get("quantity", 0))

    total_value = sum(value_map.values())
    if total_value == 0:
        return prices, {}
    weights = {sym: val / total_value for sym, val in value_map.items()}
    return prices, weights
