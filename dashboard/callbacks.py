from dash import Input, Output
from datetime import datetime

from services.kite_service import get_holdings
from domain.portfolio import build_portfolio_dataframe, compute_portfolio_health
from domain.allocation import compute_allocation
from domain.concentration import compute_concentration
from dashboard.layout import (
    build_health_section,
    build_allocation_section,
    build_concentration_section,
)
from auth.kite_auth import kite


def register_callbacks(app):
    """
    Real-time callback: Every 5 seconds the Interval component fires,
    we re-fetch holdings from Kite, recompute everything, and push
    updated HTML into the #live-dashboard container.
    """

    @app.callback(
        Output("live-dashboard", "children"),
        Output("last-updated", "children"),
        Input("live-interval", "n_intervals"),
    )
    def refresh_dashboard(n):

        holdings = get_holdings(kite)
        df = build_portfolio_dataframe(holdings)

        health = compute_portfolio_health(df)
        allocation = compute_allocation(df)
        concentration = compute_concentration(df)

        now = datetime.now().strftime("%H:%M:%S")

        return [
            build_health_section(health),
            build_allocation_section(allocation),
            build_concentration_section(concentration),
        ], f"Last updated {now}"