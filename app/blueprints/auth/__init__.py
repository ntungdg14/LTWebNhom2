from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from . import routes  # noqa: E402,F401  (đăng ký route khi package được import)
