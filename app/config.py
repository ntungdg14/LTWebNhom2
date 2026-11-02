"""Cấu hình ứng dụng theo môi trường.

Chọn cấu hình bằng biến môi trường FLASK_CONFIG: development (mặc định),
production hoặc testing. Khi deploy, đặt SECRET_KEY qua biến môi trường;
giá trị mặc định bên dưới chỉ dành cho môi trường phát triển.
"""
from __future__ import annotations

import os


class Config:
    """Cấu hình dùng chung."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    TEMPLATES_AUTO_RELOAD = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False


class TestingConfig(Config):
    TESTING = True
    TEMPLATES_AUTO_RELOAD = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
