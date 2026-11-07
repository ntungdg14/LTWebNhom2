from flask import Blueprint

store_bp = Blueprint("store", __name__)
# API JSON của cửa hàng: /api/home, /api/products..., /api/cart...
store_api_bp = Blueprint("store_api", __name__, url_prefix="/api")

from . import api, cart_api, routes  # noqa: E402,F401
