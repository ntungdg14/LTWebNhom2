from flask import Blueprint

# API JSON nhắn tin: /api/chat/... (khách) và /api/shop/chat/... (shop = tài khoản admin)
chat_api_bp = Blueprint("chat_api", __name__, url_prefix="/api")

from . import api  # noqa: E402,F401
