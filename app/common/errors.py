"""Xử lý lỗi JSON cho mọi URL bắt đầu bằng /api (đăng ký một lần trong create_app)."""
from flask import Flask, request
from werkzeug.exceptions import HTTPException

from .helpers import ApiError, error_response


def _is_api_path() -> bool:
    return request.path == "/api" or request.path.startswith("/api/")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.message, err.status, err.code, err.fields)

    def handle_http_error(err):
        """404/405/500 của /api/... trả JSON; trang HTML giữ nguyên hành vi mặc định."""
        if not _is_api_path():
            return err
        code = getattr(err, "code", 500) or 500
        name = getattr(err, "name", "Internal Server Error")
        return error_response(getattr(err, "description", None) or name, code, name.lower().replace(" ", "_"))

    for status in (400, 401, 404, 405, 413, 500):
        app.register_error_handler(status, handle_http_error)
