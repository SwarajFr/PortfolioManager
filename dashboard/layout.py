from dash import html, dcc


# -------------------------------------------------
# Dashboard Root (with live-update interval)
# -------------------------------------------------

def build_dashboard(health, allocation, concentration):

    return html.Div(
        className="page",
        children=[

            # Hidden interval component — fires every 5 seconds
            dcc.Interval(
                id="live-interval",
                interval=5 * 1000,   # 5 000 ms
                n_intervals=0,
            ),

            # Header bar with title + live status
            html.Div(
                className="header-bar",
                children=[
                    html.Div("Portfolio Health", className="page-title"),
                    html.Div(
                        className="live-indicator",
                        children=[
                            html.Span(className="live-dot"),
                            html.Span("LIVE", className="live-label"),
                            html.Span("", id="last-updated", className="last-updated-text"),
                        ]
                    ),
                ]
            ),

            # Dynamic container — everything below refreshes in real-time
            html.Div(
                id="live-dashboard",
                children=[
                    build_health_section(health),
                    build_allocation_section(allocation),
                    build_concentration_section(concentration),
                ]
            ),
        ]
    )


# -------------------------------------------------
# HEALTH SECTION
# -------------------------------------------------

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


# -------------------------------------------------
# ALLOCATION SECTION
# -------------------------------------------------

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


# -------------------------------------------------
# CONCENTRATION SECTION
# -------------------------------------------------

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