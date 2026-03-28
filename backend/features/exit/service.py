from .data import get_holdings, get_historical_data
from .compute import compute_exit_signals


def get_exit_signals():
    df = get_holdings()
    tokens = df["instrument_token"].unique().tolist()
    history = get_historical_data(tokens)
    return compute_exit_signals(df, history)
