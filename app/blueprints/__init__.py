"""Danh sách blueprint được đăng ký trong create_app()."""
from .account import account_bp
from .admin import admin_bp
from .api import api_bp
from .auth import auth_bp
from .checkout import checkout_bp
from .store import store_bp

blueprints = (store_bp, auth_bp, account_bp, checkout_bp, admin_bp, api_bp)

__all__ = ["blueprints"]
