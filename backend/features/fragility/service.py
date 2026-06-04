from .data import get_holdings, get_prices
from .engine import FragilityEngine
from .settings import get_settings


def get_fragility_analysis() -> dict:
    settings = get_settings()
    holdings = get_holdings()
    prices, weights = get_prices(holdings)
    if prices.empty or not weights:
        return FragilityEngine().run(prices, weights)
    engine = FragilityEngine(long_window=settings.get("long_window", 90))
    return engine.run(prices, weights)


def get_fragility_whatif(ticker: str, new_weight_pct: float) -> dict:
    settings = get_settings()
    holdings = get_holdings()
    prices, weights = get_prices(holdings)
    if prices.empty or not weights:
        return FragilityEngine().run(prices, weights)
    # Override weight for the specified ticker
    weights[ticker] = new_weight_pct / 100.0
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}
    engine = FragilityEngine(long_window=settings.get("long_window", 90))
    return engine.run(prices, weights)
