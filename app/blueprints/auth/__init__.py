from flask import Blueprint

auth_bp = Blueprint("auth", __name__)
# API JSON xác thực: /api/auth/...
auth_api_bp = Blueprint("auth_api", __name__, url_prefix="/api")

from . import api, routes  # noqa: E402,F401
