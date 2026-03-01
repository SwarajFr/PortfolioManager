from dash import html
from dashboard.components.metric_card import metric_card
from dashboard.components.tables import build_exit_table


def build_exit_tab(exit_data):
    return html.Div(
        className="tab-content",
        children=[
            html.Div(className="metric-row", children=_exit_summary_cards(exit_data)),
            html.Div(
                className="allocation-card",
                children=[
                    html.Div("Exit Signal Breakdown", className="allocation-title"),
                    build_exit_table(exit_data),
                ]
            ),
        ]
    )


def _exit_summary_cards(data):
    exit_count = sum(1 for r in data if r["action"] == "Exit")
    trim_count = sum(1 for r in data if r["action"] == "Trim")
    watch_count = sum(1 for r in data if r["action"] == "Watch")
    hold_count = sum(1 for r in data if r["action"] == "Hold")

    return [
        metric_card("EXIT NOW", str(exit_count), negative=exit_count > 0),
        metric_card("TRIM", str(trim_count), negative=trim_count > 0),
        metric_card("WATCH", str(watch_count)),
        metric_card("HOLD", str(hold_count), positive=hold_count > 0),
    ]
