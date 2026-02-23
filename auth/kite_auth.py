import json
import os
import webbrowser

from kiteconnect import KiteConnect
from flask import request, redirect

from config.settings import API_KEY, API_SECRET, TOKEN_FILE

kite = KiteConnect(api_key=API_KEY)


def _save_token(token):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": token}, f)


def _load_token():
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        with open(TOKEN_FILE) as f:
            data = json.load(f)
            return data.get("access_token")
    except:
        return None


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

        _save_token(data["access_token"])
        kite.set_access_token(data["access_token"])

        return redirect("/")


def ensure_login():
    """
    Only checks token validity.
    Does NOT register routes.
    """

    token = _load_token()
    if token:
        kite.set_access_token(token)
        try:
            kite.holdings()
            return True
        except:
            return False

    return False


def trigger_login():
    webbrowser.open(kite.login_url())