from dash import html


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
