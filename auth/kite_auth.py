import webbrowser

from kiteconnect import KiteConnect
from flask import request, redirect

from config.settings import API_KEY, API_SECRET

kite = KiteConnect(api_key=API_KEY)


def register_routes(app):
    """
    Register callback route ONCE at startup.
    """

    @app.server.route("/callback")
    def callback():
        request_token = request.args.get("request_token")

        if not request_token:
            return "Login failed."

        data = kite.generate_session(
            request_token=request_token,
            api_secret=API_SECRET
        )

        kite.set_access_token(data["access_token"])

        return redirect("/")


def ensure_login():
    """
    Checks if the current in-memory Kite client has a valid session.
    """
    try:
        kite.holdings()
        return True
    except:
        return False


def trigger_login():
    webbrowser.open(kite.login_url())
