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

    # File SQLite: đặt biến môi trường DATABASE, mặc định instance/freesion.db (xem app/db.py).

    # Phiên đăng nhập (cookie ký bởi SECRET_KEY).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 30 * 24 * 3600  # "Ghi nhớ đăng nhập": 30 ngày

    # Quy tắc cửa hàng.
    FREE_SHIPPING_THRESHOLD = 499_000  # VND
    SHIPPING_METHODS = {
        "standard": {
            "name": "Giao hàng tiêu chuẩn",
            "fee": 30_000,
            "free_from": 499_000,  # miễn phí khi tạm tính >= mức này
            "days": (3, 5),  # ngày làm việc
        },
        "express": {
            "name": "Giao hàng nhanh nội thành",
            "fee": 35_000,
            "free_from": None,
            "days": (1, 2),
        },
    }
    PAYMENT_METHODS = {
        "cod": "Thanh toán khi nhận hàng (COD)",
        "vnpay": "VNPAY / Thẻ ATM nội địa",
        "momo": "Ví điện tử MoMo",
        "card": "Thẻ quốc tế",
    }

    # Chưa có dịch vụ gửi email: khi True, API quên mật khẩu trả kèm token để thử.
    EXPOSE_RESET_TOKEN = False


class DevelopmentConfig(Config):
    DEBUG = True
    EXPOSE_RESET_TOKEN = True


class ProductionConfig(Config):
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    TEMPLATES_AUTO_RELOAD = False
    EXPOSE_RESET_TOKEN = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
