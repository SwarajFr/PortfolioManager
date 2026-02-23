from dash import Dash, html
import dash_bootstrap_components as dbc

from auth.kite_auth import (
    register_routes,
    ensure_login,
    trigger_login,
    kite,
)

from services.kite_service import get_holdings
from domain.portfolio import portfolio_summary
from dashboard.layout import main_layout
from dashboard.callbacks import register_callbacks



# Create Dash App
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)


# Register Flask routes ONCE
# (Important: must happen before first request)
register_routes(app)


# Layout Factory
def serve_layout():

    # Check if valid session exists
    if ensure_login():
        holdings = get_holdings(kite)
        summary = portfolio_summary(holdings)
        return main_layout()

    # If not logged in → trigger login
    trigger_login()

    return html.Div(
        [
            html.H3("Redirecting to Zerodha login…"),
            dbc.Spinner(size="lg"),
        ],
        style={"textAlign": "center", "marginTop": "100px"},
    )

# Assign layout as function
app.layout = serve_layout

# Register Dash callbacks
register_callbacks(app)

# Run Server
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)