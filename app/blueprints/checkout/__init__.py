from flask import Blueprint

checkout_bp = Blueprint("checkout", __name__)
# API JSON đặt hàng: /api/checkout/options, /api/orders..., /api/provinces...
checkout_api_bp = Blueprint("checkout_api", __name__, url_prefix="/api")

from . import api, locations_api, routes  # noqa: E402,F401
