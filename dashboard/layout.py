from dash import html, dcc
import dash_bootstrap_components as dbc


def metric_card(title, value, color):
    return dbc.Card(
        dbc.CardBody([
            html.Small(title),
            html.H4(value, className=f"text-{color}")
        ])
    )


def main_layout():
    return dbc.Container([
        html.H2("Portfolio Dashboard", className="mb-4"),

        dcc.Interval(
            id="refresh-interval",
            interval=30 * 1000,  
            n_intervals=0
        ),

        html.Div(id="portfolio-container")
    ], fluid=True)