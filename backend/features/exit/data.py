import pandas as pd
from datetime import date, timedelta
from core.kite import get_kite


def get_holdings():
    kite = get_kite()
    return pd.DataFrame(kite.holdings())


def get_historical_data(instrument_tokens: list[int]) -> dict[int, pd.DataFrame]:
    """
    Fetch ~1 year of daily OHLC for each instrument token.
    Returns {instrument_token: DataFrame(date, open, high, low, close, volume)}.
    """
    kite = get_kite()
    to_date = date.today()
    from_date = to_date - timedelta(days=365)

    history = {}
    for token in instrument_tokens:
        try:
            records = kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="day",
            )
            if records:
                df = pd.DataFrame(records)
                df["date"] = pd.to_datetime(df["date"]).dt.date
                history[token] = df
        except Exception:
            # Skip instruments where historical data is unavailable
            pass

    return history
