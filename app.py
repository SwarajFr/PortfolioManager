from dash import Dash, html

from auth.kite_auth import register_routes, ensure_login, trigger_login, kite
from services.kite_service import get_holdings
from domain.portfolio import build_portfolio_dataframe, compute_portfolio_health
from domain.allocation import compute_allocation
from domain.concentration import compute_concentration
from domain.exit_engine import compute_exit_signals
from dashboard.layout import build_dashboard


app = Dash(__name__, suppress_callback_exceptions=True)
register_routes(app)


def serve_layout():

    if ensure_login():
        holdings = get_holdings(kite)

        df = build_portfolio_dataframe(holdings)
        health = compute_portfolio_health(df)
        allocation = compute_allocation(df)
        concentration = compute_concentration(df)
        exit_signals = compute_exit_signals(kite, df)

        return build_dashboard(health, allocation, concentration, exit_signals)

    trigger_login()

    return html.Div(
        className="page",
        children=[
            html.H3("Redirecting to Zerodha login…"),
        ],
    )


app.layout = serve_layout

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)