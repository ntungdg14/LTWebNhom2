"""REST API JSON cho cửa hàng (URL bắt đầu bằng /api). Xem docs/API.md."""
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from . import utils  # noqa: E402,F401  (đăng ký before_request + error handler)
from . import account, auth, cart, catalog, checkout, orders  # noqa: E402,F401
