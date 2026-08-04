"""Orchestration for the overview page: fetch holdings, apply the user's config.

Thin by design. All the arithmetic is in `compute.py`, so this layer exists only
to bind the two inputs — live holdings and saved settings — that a pure function
must not fetch for itself.
"""
from core.data import get_market_data

from .compute import compute_overview
from .settings import get_settings


def get_overview():
    return compute_overview(get_market_data().get_holdings(), get_settings())
