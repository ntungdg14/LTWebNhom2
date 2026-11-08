"""
File này chỉ để khởi tạo app, nạp cấu hình và đăng ký blueprint, không đụng vào
"""
from __future__ import annotations

import os

from flask import Flask, request

from .config import DEV_SECRET_KEY, config_by_name


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    name = config_name or os.environ.get("FLASK_CONFIG", "development")
    app.config.from_object(config_by_name.get(name, config_by_name["development"]))

    if name == "production":
        secret = os.environ.get("SECRET_KEY")
        if not secret or secret == DEV_SECRET_KEY:
            raise RuntimeError("Thiếu biến môi trường SECRET_KEY: bắt buộc khi chạy FLASK_CONFIG=production.")
        app.config["SECRET_KEY"] = secret

    from . import db

    db.init_app(app)

    from .common.errors import register_error_handlers

    register_error_handlers(app)

    from .common.helpers import csrf_token, current_user, validate_csrf

    @app.before_request
    def csrf_protect():
        """CSRF cho mọi form HTML POST/PUT/PATCH/DELETE. /api/* dùng JSON (Content-Type) nên bỏ qua."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.path.startswith("/api/"):
            validate_csrf()

    @app.context_processor
    def inject_auth():
        return {"current_user": current_user(), "csrf_token": csrf_token}

    # Import ở đây để tránh vòng lặp import giữa app và các blueprint.
    from .blueprints import blueprints

    for blueprint in blueprints:
        app.register_blueprint(blueprint)

    return app
