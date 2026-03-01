from dash import html, dcc
from dashboard.pages.health import build_health_tab
from dashboard.pages.exit_signals import build_exit_tab


def build_dashboard(health, allocation, concentration, exit_signals):
    return html.Div(
        className="page",
        children=[
            html.Div("Portfolio Manager", className="page-title"),

            dcc.Tabs(
                id="tabs",
                value="tab-health",
                className="tab-bar",
                children=[
                    dcc.Tab(
                        label="Portfolio Health",
                        value="tab-health",
                        className="tab-item",
                        selected_className="tab-item--active",
                        children=[build_health_tab(health, allocation, concentration)],
                    ),
                    dcc.Tab(
                        label="Exit Signals",
                        value="tab-exit",
                        className="tab-item",
                        selected_className="tab-item--active",
                        children=[build_exit_tab(exit_signals)],
                    ),
                ],
            ),
        ]
    )
