"""Danh sách blueprint được đăng ký trong create_app()."""
from .account import account_api_bp, account_bp
from .admin import admin_bp
from .auth import auth_api_bp, auth_bp
from .checkout import checkout_api_bp, checkout_bp
from .store import store_api_bp, store_bp

blueprints = (
    store_bp, auth_bp, account_bp, checkout_bp, admin_bp,
    # API JSON (không gồm admin)
    store_api_bp, auth_api_bp, account_api_bp, checkout_api_bp,
)

__all__ = ["blueprints"]
