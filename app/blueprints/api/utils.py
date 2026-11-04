"""Tiện ích dùng chung cho API: lỗi JSON, xác thực, kiểm tra dữ liệu, phân trang."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

from flask import g, jsonify, request, session

from ...db import get_db
from . import api_bp

VN_TZ = timezone(timedelta(hours=7))
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^(0|\+?84)\d{9}$")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request",
                 fields: dict[str, str] | None = None):
        super().__init__(message)
        self.message, self.status, self.code, self.fields = message, status, code, fields or {}


def error_response(message: str, status: int, code: str, fields: dict[str, str] | None = None):
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return jsonify(body), status


@api_bp.errorhandler(ApiError)
def _handle_api_error(err: ApiError):
    return error_response(err.message, err.status, err.code, err.fields)


def register_json_errors(app) -> None:
    """404/405/413/500 trong /api/* cũng trả JSON thay vì HTML."""
    for status, code, msg in (
        (404, "not_found", "Không tìm thấy tài nguyên."),
        (405, "method_not_allowed", "Phương thức không được hỗ trợ."),
        (413, "payload_too_large", "Dữ liệu gửi lên quá lớn."),
        (500, "server_error", "Lỗi máy chủ, vui lòng thử lại sau."),
    ):
        def handler(_err, _s=status, _c=code, _m=msg):
            if request.path.startswith("/api/") or request.path == "/api":
                return error_response(_m, _s, _c)
            return _err
        app.register_error_handler(status, handler)


@api_bp.before_request
def _guard_mutations():
    """Chống CSRF: request ghi dữ liệu phải là JSON hoặc có header X-Requested-With.

    Form HTML từ trang khác không thể đặt Content-Type JSON/header tùy chỉnh
    nếu không qua CORS preflight, nên cookie phiên không bị lợi dụng.
    """
    if request.method in MUTATING and not (request.is_json or request.headers.get("X-Requested-With")):
        raise ApiError("Yêu cầu phải dùng Content-Type: application/json.", 415, "unsupported_media_type")


# ---------- thời gian ----------
def now_vn() -> str:
    return datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def iso(ts: str | None) -> str | None:
    return ts.replace(" ", "T") if ts else None


# ---------- body & kiểm tra dữ liệu ----------
def json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None and not request.get_data():
        return {}
    if not isinstance(data, dict):
        raise ApiError("Nội dung JSON không hợp lệ.", 400, "invalid_json")
    return data


def text(data: dict, key: str, label: str, errors: dict, *, required: bool = True,
         max_len: int = 255, default: str | None = None) -> str | None:
    val = data.get(key)
    if val is None or (isinstance(val, str) and not val.strip()):
        if required:
            errors[key] = f"Vui lòng nhập {label}."
        return default
    if not isinstance(val, str):
        errors[key] = f"{label.capitalize()} không hợp lệ."
        return default
    val = val.strip()
    if len(val) > max_len:
        errors[key] = f"{label.capitalize()} tối đa {max_len} ký tự."
    return val


def valid_email(value: str | None, errors: dict, key: str = "email") -> str | None:
    if value and not EMAIL_RE.match(value):
        errors[key] = "Email không hợp lệ."
    return value.lower() if value else value


def valid_phone(value: str | None, errors: dict, key: str = "phone") -> str | None:
    if not value:
        return value
    cleaned = re.sub(r"[\s.\-]", "", value)
    if not PHONE_RE.match(cleaned):
        errors[key] = "Số điện thoại không hợp lệ."
    return cleaned


def check_password_strength(password: str | None, errors: dict, key: str = "password") -> None:
    if not password:
        errors[key] = "Vui lòng nhập mật khẩu."
    elif len(password) < 8 or not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password)
                                   and re.search(r"\d", password)):
        errors[key] = "Mật khẩu cần ít nhất 8 ký tự, gồm chữ hoa, chữ thường và số."


def raise_if(errors: dict) -> None:
    if errors:
        raise ApiError("Dữ liệu không hợp lệ.", 422, "validation_error", errors)


def to_int(value: Any, default: int, lo: int = 1, hi: int | None = None) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    n = max(lo, n)
    return min(n, hi) if hi else n


def paginate_args(default_per_page: int = 12, max_per_page: int = 48) -> tuple[int, int]:
    return (to_int(request.args.get("page"), 1),
            to_int(request.args.get("per_page"), default_per_page, 1, max_per_page))


def page_meta(page: int, per_page: int, total: int) -> dict[str, Any]:
    pages = max(1, -(-total // per_page))
    return {"page": page, "per_page": per_page, "total": total, "pages": pages, "has_more": page < pages}


# ---------- xác thực ----------
def current_user():
    """Trả về hàng users của người đang đăng nhập (hoặc None)."""
    if "user" not in g:
        g.user = None
        uid = session.get("user_id")
        if uid:
            row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
            if row and row["session_version"] == session.get("sv", 0):
                g.user = row
            else:
                session.pop("user_id", None)
    return g.user


def login_user(user, remember: bool = False) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["sv"] = user["session_version"]
    session.permanent = bool(remember)
    g.user = user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            raise ApiError("Vui lòng đăng nhập để tiếp tục.", 401, "unauthorized")
        return view(*args, **kwargs)
    return wrapper


def user_dict(user) -> dict[str, Any]:
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "phone": user["phone"],
        "birthday": user["birthday"],
        "gender": user["gender"],
        "newsletter": bool(user["newsletter"]),
        "role": user["role"],
        "member_since": user["created_at"][:7] if user["created_at"] else None,  # YYYY-MM
        "password_updated_at": user["password_updated_at"],
    }
