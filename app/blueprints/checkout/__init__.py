from flask import Blueprint

checkout_bp = Blueprint("checkout", __name__)

from . import routes  # noqa: E402,F401  (đăng ký route khi package được import)
