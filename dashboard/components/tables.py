from dash import html


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
                html.Td(f"₹{row['pnl']:,.0f}", className=f"col-num {pnl_class}"),
                html.Td(f"{row['pnl_pct']:.1f}%", className=f"col-num {pnl_class}"),
                html.Td(row["target"], className="col-center"),
                html.Td(
                    html.Span(row["action"], className=f"badge {row['badge']}"),
                    className="col-action"
                ),
            ])
        )

    return html.Table(
        className="data-table",
        children=[html.Thead(header), html.Tbody(body)]
    )


def build_exit_table(data):
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
                html.Td(f"{row['return_pct']:.1f}%", className=f"col-num {ret_class}"),
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
        children=[html.Thead(header), html.Tbody(body)]
    )
