from flask import Blueprint

account_bp = Blueprint("account", __name__, url_prefix="/account")
# API JSON tài khoản: /api/account/...
account_api_bp = Blueprint("account_api", __name__, url_prefix="/api")

from . import api, routes  # noqa: E402,F401
