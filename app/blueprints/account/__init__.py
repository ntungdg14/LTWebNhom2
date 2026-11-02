from flask import Blueprint

account_bp = Blueprint("account", __name__, url_prefix="/account")

from . import routes  # noqa: E402,F401  (đăng ký route khi package được import)
