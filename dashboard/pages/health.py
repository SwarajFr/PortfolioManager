from dash import html
from dashboard.components.metric_card import metric_card
from dashboard.components.tables import build_allocation_table


def build_health_tab(health, allocation, concentration):
    return html.Div(
        className="tab-content",
        children=[
            build_health_section(health),
            build_allocation_section(allocation),
            build_concentration_section(concentration),
        ]
    )


def build_health_section(health):
    return html.Div(
        className="metric-row",
        children=[
            metric_card("TOTAL VALUE", f"₹{health['total_value']:,.0f}"),
            metric_card("P&L", f"₹{health['total_pnl']:,.0f}", positive=health["total_pnl"] >= 0),
            metric_card("PORTFOLIO RETURN", f"{health['portfolio_return']:.2f}%", positive=health["portfolio_return"] >= 0),
            metric_card("CAPITAL AT RISK", f"₹{health['capital_at_risk']:,.0f}", negative=True),
        ]
    )


def build_allocation_section(rows):
    return html.Div(
        className="allocation-card",
        children=[
            html.Div("Asset Allocation", className="allocation-title"),
            build_allocation_table(rows)
        ]
    )


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
