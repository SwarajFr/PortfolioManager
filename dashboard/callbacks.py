from dash import Input, Output, html


def register_callbacks(app):
    """
    Tab-switching callback:
    Reads the selected tab value from dcc.Tabs and renders
    the matching content from the dcc.Store data.
    """

    @app.callback(
        Output("tab-content", "children"),
        Input("tabs", "value"),
    )
    def switch_tab(tab_id):
        # Content is pre-rendered inside each dcc.Tab,
        # so this callback is a placeholder for any future
        # dynamic tab behaviour.
        return html.Div()