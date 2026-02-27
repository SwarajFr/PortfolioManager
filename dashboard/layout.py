from dash import html, dcc


# =============================================================
#  Dashboard Shell  (tab bar + content)
# =============================================================

def build_dashboard(health, allocation, concentration, exit_signals):
    """
    Renders a tabbed dashboard.
    Adding a new tab = add a dcc.Tab entry + its builder function.
    """

    return html.Div(
        className="page",
        children=[

            # Page title
            html.Div("Portfolio Manager", className="page-title"),

            # Tab bar
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


# =============================================================
#  TAB 1 — Portfolio Health
# =============================================================

def build_health_tab(health, allocation, concentration):

    return html.Div(
        className="tab-content",
        children=[
            build_health_section(health),
            build_allocation_section(allocation),
            build_concentration_section(concentration),
        ]
    )


# ----- Health Metric Cards -----------------------------------

def build_health_section(health):

    return html.Div(
        className="metric-row",
        children=[

            metric_card("TOTAL VALUE", f"₹{health['total_value']:,.0f}"),

            metric_card(
                "P&L",
                f"₹{health['total_pnl']:,.0f}",
                positive=health["total_pnl"] >= 0
            ),

            metric_card(
                "PORTFOLIO RETURN",
                f"{health['portfolio_return']:.2f}%",
                positive=health["portfolio_return"] >= 0
            ),

            metric_card(
                "CAPITAL AT RISK",
                f"₹{health['capital_at_risk']:,.0f}",
                negative=True
            ),
        ]
    )


def metric_card(title, value, positive=False, negative=False):

    classes = "metric-card"
    value_class = "metric-value"

    if positive:
        classes += " positive"
        value_class += " value-positive"

    if negative:
        classes += " negative"
        value_class += " value-negative"

    return html.Div(
        className=classes,
        children=[
            html.Div(title, className="metric-title"),
            html.Div(value, className=value_class)
        ]
    )


# ----- Allocation Table --------------------------------------

def build_allocation_section(rows):

    return html.Div(
        className="allocation-card",
        children=[
            html.Div("Asset Allocation", className="allocation-title"),
            build_allocation_table(rows)
        ]
    )


def format_category_name(cat):
    return cat.replace("INDIAEQUITYETF", "Indian Equity ETF") \
              .replace("INDIAEQUITY", "Indian Equity") \
              .replace("USEQUITY", "US Equity") \
              .replace("METALS", "Metals")


def build_allocation_table(rows):

    header = html.Tr([
        html.Th("Asset", className="col-text"),
        html.Th("Value (₹)", className="col-num"),
        html.Th("Allocation %", className="col-num"),
        html.Th("P&L (₹)", className="col-num"),
        html.Th("P&L %", className="col-num"),
        html.Th("Target", className="col-center"),
        html.Th("Action", className="col-action"),
    ])

    body = []

    for row in rows:

        pnl_class = "value-positive" if row["pnl"] >= 0 else "value-negative"

        body.append(
            html.Tr([
                html.Td(format_category_name(row["category"]), className="col-text"),
                html.Td(f"₹{row['value']:,.0f}", className="col-num"),
                html.Td(f"{row['allocation_pct']:.1f}%", className="col-num"),
                html.Td(
                    f"₹{row['pnl']:,.0f}",
                    className=f"col-num {pnl_class}"
                ),
                html.Td(
                    f"{row['pnl_pct']:.1f}%",
                    className=f"col-num {pnl_class}"
                ),
                html.Td(row["target"], className="col-center"),
                html.Td(
                    html.Span(row["action"], className=f"badge {row['badge']}"),
                    className="col-action"
                ),
            ])
        )

    return html.Table(
        className="data-table",
        children=[
            html.Thead(header),
            html.Tbody(body)
        ]
    )


# ----- Concentration Table -----------------------------------

def build_concentration_section(data):

    return html.Div(
        className="allocation-card",
        children=[
            html.Div("Concentration Limits", className="allocation-title"),
            html.Table(
                className="data-table",
                children=[

                    html.Thead(
                        html.Tr([
                            html.Th("Metric", className="col-text"),
                            html.Th("Value (₹)", className="col-num"),
                            html.Th("Value %", className="col-num"),
                            html.Th("P&L (₹)", className="col-num"),
                            html.Th("P&L %", className="col-num"),
                            html.Th("Limit", className="col-center"),
                            html.Th("Action", className="col-action"),
                        ])
                    ),

                    html.Tbody([

                        # Top 5
                        html.Tr([
                            html.Td("Top 5 Holdings", className="col-text"),
                            html.Td(f"₹{data['top5_value']:,.0f}", className="col-num"),
                            html.Td(f"{data['top5_pct']:.1f}%", className="col-num"),
                            html.Td(f"₹{data['top5_pnl']:,.0f}", className="col-num value-positive"),
                            html.Td(f"{data['top5_pnl_pct']:.1f}%", className="col-num value-positive"),
                            html.Td("< 35%", className="col-center"),
                            html.Td(
                                html.Span(data["top5_action"], className=f"badge {data['top5_badge']}"),
                                className="col-action"
                            ),
                        ]),

                        # Largest Holding
                        html.Tr([
                            html.Td(f"Largest Holding (Overall) - {data['largest_name']}", className="col-text"),
                            html.Td(f"₹{data['largest_value']:,.0f}", className="col-num"),
                            html.Td(f"{data['largest_pct']:.1f}%", className="col-num"),
                            html.Td(f"₹{data['largest_pnl']:,.0f}", className="col-num value-positive"),
                            html.Td(f"{data['largest_pnl_pct']:.1f}%", className="col-num value-positive"),
                            html.Td("≤ 5%", className="col-center"),
                            html.Td(
                                html.Span(data["largest_action"], className=f"badge {data['largest_badge']}"),
                                className="col-action"
                            ),
                        ]),
                    ])
                ]
            )
        ]
    )


# =============================================================
#  TAB 2 — Exit Signals
# =============================================================

def build_exit_tab(exit_data):

    return html.Div(
        className="tab-content",
        children=[

            # Summary cards row
            html.Div(
                className="metric-row",
                children=_exit_summary_cards(exit_data),
            ),

            # Full table
            html.Div(
                className="allocation-card",
                children=[
                    html.Div("Exit Signal Breakdown", className="allocation-title"),
                    _exit_table(exit_data),
                ]
            ),
        ]
    )


def _exit_summary_cards(data):
    """Top-level KPI cards for exit tab."""

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


def _exit_table(data):
    """Per-stock exit signal table."""

    header = html.Tr([
        html.Th("Stock", className="col-text"),
        html.Th("LTP", className="col-num"),
        html.Th("Return %", className="col-num"),
        html.Th("Loss", className="col-num"),
        html.Th("Risk", className="col-num"),
        html.Th("RAR", className="col-num"),
        html.Th("Trend", className="col-num"),
        html.Th("Conc.", className="col-num"),
        html.Th("Exit Score", className="col-num"),
        html.Th("Action", className="col-action"),
    ])

    body = []

    for row in data:

        ret_class = "value-positive" if row["return_pct"] >= 0 else "value-negative"

        body.append(
            html.Tr([
                html.Td(row["symbol"], className="col-text"),
                html.Td(f"₹{row['ltp']:,.2f}", className="col-num"),
                html.Td(
                    f"{row['return_pct']:.1f}%",
                    className=f"col-num {ret_class}"
                ),
                html.Td(str(row["loss_severity"]), className="col-num"),
                html.Td(str(row["risk_score"]), className="col-num"),
                html.Td(str(row["rar_score"]), className="col-num"),
                html.Td(str(row["trend_score"]), className="col-num"),
                html.Td(str(row["concentration"]), className="col-num"),
                html.Td(
                    html.Div(
                        className="score-cell",
                        children=[
                            html.Div(
                                className="score-bar-track",
                                children=[
                                    html.Div(
                                        className=f"score-bar-fill {row['badge']}",
                                        style={"width": f"{row['exit_score']}%"},
                                    )
                                ]
                            ),
                            html.Span(str(row["exit_score"]), className="score-number"),
                        ]
                    ),
                    className="col-num"
                ),
                html.Td(
                    html.Span(row["action"], className=f"badge {row['badge']}"),
                    className="col-action"
                ),
            ])
        )

    return html.Table(
        className="data-table",
        children=[
            html.Thead(header),
            html.Tbody(body),
        ]
    )