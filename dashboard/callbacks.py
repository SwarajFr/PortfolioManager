from dash import Input, Output, dcc
from services.kite_service import get_holdings
from domain.portfolio import portfolio_summary
from auth.kite_auth import kite
from dashboard.layout import metric_card
import dash_bootstrap_components as dbc


def register_callbacks(app):

    @app.callback(
        Output("portfolio-container", "children"),
        Input("refresh-interval", "n_intervals")
    )
    def refresh_dashboard(n):
        holdings = get_holdings(kite)
        summary = portfolio_summary(holdings)

        return [
            dbc.Row([
                dbc.Col(metric_card("Investment", f"₹{summary['investment']:,.0f}", "dark")),
                dbc.Col(metric_card("Value", f"₹{summary['value']:,.0f}", "dark")),
                dbc.Col(metric_card("P&L", f"₹{summary['pnl']:,.0f}", "success")),
                dbc.Col(metric_card("Return %", f"{summary['return_pct']:.2f}%", "success")),
            ])
        ]