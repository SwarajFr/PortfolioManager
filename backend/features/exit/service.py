"""Orchestration for exit signals: holdings + one year of prices → scoring."""
from __future__ import annotations

import pandas as pd

from core.data import InstrumentRef, get_market_data

from .compute import compute_exit_signals

LOOKBACK_DAYS = 365


def _refs(holdings: pd.DataFrame) -> list[InstrumentRef]:
    """Holdings already carry an instrument token, so history needs no lookup."""
    return [
        InstrumentRef(symbol=str(row.tradingsymbol), token=int(row.instrument_token))
        for row in holdings.itertuples()
    ]


def get_exit_signals():
    market_data = get_market_data()
    holdings = market_data.get_holdings()
    refs = _refs(holdings)

    by_symbol = market_data.get_history_batch(refs, lookback_days=LOOKBACK_DAYS)

    # The scoring layer indexes history by instrument token.
    history = {
        ref.token: by_symbol[ref.symbol] for ref in refs if ref.symbol in by_symbol
    }
    return compute_exit_signals(holdings, history)
