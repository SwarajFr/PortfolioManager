from datetime import date, timedelta

import pandas as pd
import numpy as np


def fetch_historical_data(kite, instrument_token, days=365):
    """
    Fetch daily OHLC candles for a single instrument.
    Returns a DataFrame with columns: date, open, high, low, close, volume.
    """
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    try:
        records = kite.historical_data(
            instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval="day",
        )
    except Exception:
        return pd.DataFrame()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.rename(columns={"date": "date"}, inplace=True)
    return df


def compute_moving_averages(hist_df):
    """
    Add MA50 and MA200 columns.
    Returns the latest MA50 and MA200 as scalars.
    """
    if hist_df.empty or len(hist_df) < 50:
        return None, None

    hist_df["MA50"] = hist_df["close"].rolling(50).mean()
    hist_df["MA200"] = hist_df["close"].rolling(200).mean()

    ma50 = hist_df["MA50"].iloc[-1]
    ma200 = hist_df["MA200"].iloc[-1] if len(hist_df) >= 200 else None

    return ma50, ma200


def compute_annualized_volatility(hist_df):
    """
    Annualized volatility = std(daily returns) * sqrt(252)
    """
    if hist_df.empty or len(hist_df) < 20:
        return 0.0

    daily_returns = hist_df["close"].pct_change().dropna()
    return float(daily_returns.std() * np.sqrt(252))
