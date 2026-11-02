"""
File này chỉ để khởi tạo app, nạp cấu hình và đăng ký blueprint, không đụng vào
"""
from __future__ import annotations

import os

from flask import Flask

from .config import config_by_name


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    name = config_name or os.environ.get("FLASK_CONFIG", "development")
    app.config.from_object(config_by_name.get(name, config_by_name["development"]))

    # Import ở đây để tránh vòng lặp import giữa app và các blueprint.
    from .blueprints import blueprints

    for blueprint in blueprints:
        app.register_blueprint(blueprint)

    return app
