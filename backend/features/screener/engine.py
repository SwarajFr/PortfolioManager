"""Strategy ABC, self-registering strategy classes, and the two run paths that
read the cached signals table. Adding a strategy = one new @register class."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from . import compute

REGISTRY: dict[str, type["Strategy"]] = {}


def register(cls: type["Strategy"]) -> type["Strategy"]:
    REGISTRY[cls.name] = cls
    return cls


class Strategy(ABC):
    name: str = ""

    def __init__(self, params: dict):
        self.params = params

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series: ...

    @abstractmethod
    def passes(self, df: pd.DataFrame) -> pd.Series: ...


@register
class MACrossover(Strategy):
    name = "ma_crossover"

    def compute(self, df):
        return compute.ma_crossover_score(df, self.params["fast"], self.params["slow"])

    def passes(self, df):
        return compute.ma_crossover_pass(df, self.params["fast"], self.params["slow"])


@register
class Momentum121(Strategy):
    name = "momentum_12_1"

    def compute(self, df):
        return compute.momentum_score(df, self.params["lookback"], self.params["skip"])

    def passes(self, df):
        return compute.momentum_pass(df, self.params["lookback"], self.params["skip"])


@register
class Breakout(Strategy):
    name = "breakout"

    def compute(self, df):
        return compute.breakout_score(df, self.params["n_high"])

    def passes(self, df):
        return compute.breakout_pass(df, self.params["n_high"])


@register
class RSIReversion(Strategy):
    name = "rsi_reversion"

    def compute(self, df):
        return compute.rsi_reversion_score(df, self.params["rsi_period"])

    def passes(self, df):
        return compute.rsi_reversion_pass(
            df, self.params["rsi_period"], self.params["oversold"]
        )


@register
class High52Week(Strategy):
    name = "high_52w"

    def compute(self, df):
        return compute.high_52w_score(df, self.params["window"])

    def passes(self, df):
        return compute.high_52w_pass(df, self.params["window"], self.params["proximity"])


def build_strategies(settings: dict, names: list[str] | None = None) -> list[Strategy]:
    sconf = settings["strategies"]
    names = names if names is not None else list(REGISTRY)
    return [REGISTRY[n](sconf[n]) for n in names]


def strategy_metadata(settings: dict) -> list[dict]:
    sconf = settings["strategies"]
    return [{"name": n, "params": sconf[n]} for n in REGISTRY]


def run_individual(name: str, scores: pd.DataFrame, passes: pd.DataFrame) -> list[dict]:
    mask = passes[name].astype(bool)
    ranked = scores.loc[mask, name].sort_values(ascending=False)
    return [{"symbol": sym, "score": round(float(v), 4)} for sym, v in ranked.items()]


def run_combined(
    selected: list[str],
    weights: dict,
    k,
    fallback_n: int,
    scores: pd.DataFrame,
    passes: pd.DataFrame,
) -> dict:
    weights = weights or {s: 1.0 for s in selected}
    weights = {s: float(weights.get(s, 1.0)) for s in selected}
    norm = pd.DataFrame(
        {s: compute.percentile_normalize(scores[s]) for s in selected}
    )
    agg = compute.aggregate(norm, weights)
    matched = compute.k_of_n_match(passes[selected], k)
    ranked, is_fallback = compute.rank_and_fallback(agg, matched, fallback_n)
    results = [
        {
            "symbol": sym,
            "aggregate": round(float(agg[sym]), 4),
            "passes": int(passes.loc[sym, selected].astype(bool).sum()),
        }
        for sym in ranked
    ]
    return {
        "results": results,
        "is_fallback": is_fallback,
        "selected": list(selected),
        "k": k,
    }
