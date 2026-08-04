from core.data import get_market_data

from .compute import compute_overview
from .settings import get_settings


def get_overview():
    return compute_overview(get_market_data().get_holdings(), get_settings())
