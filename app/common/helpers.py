"""Tiện ích dùng chung cho API: lỗi JSON, đăng nhập theo session, kiểm tra dữ liệu.

Quy ước phản hồi lỗi::

    {"error": {"code": "validation_error", "message": "...", "fields": {"email": "..."}}}
"""
from __future__ import annotations

import re
from functools import wraps

from flask import g, jsonify, request, session

from ..db import get_db


# --------------------------------------------------------------------- lỗi
class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request", fields: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.fields = fields


def error_response(message, status=400, code="bad_request", fields=None):
    body = {"code": code, "message": message}
    if fields:
        body["fields"] = fields
    response = jsonify(error=body)
    response.status_code = status
    return response


# ---------------------------------------------------------------- đầu vào
def json_body() -> dict:
    """Đọc body JSON (bắt buộc Content-Type: application/json, cũng là lớp chống CSRF)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Body phải là JSON object (Content-Type: application/json).", 400, "invalid_json")
    return data


def optional_json_body() -> dict:
    return request.get_json(silent=True) if isinstance(request.get_json(silent=True), dict) else {}


def as_int(value):
    """Chuyển về int; trả None nếu không hợp lệ (bool bị loại)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return None


def arg_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    value = as_int(raw)
    if value is None:
        raise ApiError(f"Tham số '{name}' phải là số nguyên.", 400, "invalid_param")
    value = max(value, minimum)
    return min(value, maximum) if maximum is not None else value


def arg_list(name: str) -> list[str]:
    """?color=den,trang hoặc ?color=den&color=trang -> ['den', 'trang']."""
    out: list[str] = []
    for raw in request.args.getlist(name):
        out.extend(part.strip() for part in raw.split(",") if part.strip())
    return out


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^(0|\+84)\d{9}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_phone(raw: str) -> str:
    return re.sub(r"[\s.\-()]", "", raw or "")


def password_problem(password: str) -> str | None:
    if len(password) < 8 or not (
        re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password)
    ):
        return "Mật khẩu cần ít nhất 8 ký tự, gồm chữ hoa, chữ thường và số."
    return None


class Fields:
    """Gom lỗi theo từng trường rồi ném một ApiError 422."""

    def __init__(self, data: dict):
        self.data = data
        self.errors: dict[str, str] = {}

    def fail(self, key: str, message: str) -> None:
        self.errors.setdefault(key, message)

    def text(self, key, label, *, required=True, max_len=255, default=None):
        value = self.data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                self.fail(key, f"{label} là bắt buộc.")
            return default
        if not isinstance(value, str):
            self.fail(key, f"{label} không hợp lệ.")
            return default
        value = value.strip()
        if len(value) > max_len:
            self.fail(key, f"{label} tối đa {max_len} ký tự.")
        return value

    def email(self, key="email", label="Email", *, required=True):
        value = self.text(key, label, required=required, max_len=254)
        if value is None:
            return None
        if not EMAIL_RE.match(value):
            self.fail(key, "Email không hợp lệ.")
        return value.lower()

    def phone(self, key="phone", label="Số điện thoại", *, required=True):
        value = self.text(key, label, required=required, max_len=20)
        if value is None:
            return None
        value = normalize_phone(value)
        if not PHONE_RE.match(value):
            self.fail(key, "Số điện thoại không hợp lệ.")
        return value

    def password(self, key="password", label="Mật khẩu"):
        value = self.data.get(key)
        if not isinstance(value, str) or not value:
            self.fail(key, f"{label} là bắt buộc.")
            return None
        problem = password_problem(value)
        if problem:
            self.fail(key, problem)
        return value

    def birthday(self, key="birthday"):
        from datetime import date

        value = self.text(key, "Ngày sinh", required=False, max_len=10)
        if value is None:
            return None
        try:
            if not DATE_RE.match(value) or date.fromisoformat(value) > date.today():
                raise ValueError
        except ValueError:
            self.fail(key, "Ngày sinh không hợp lệ (định dạng YYYY-MM-DD).")
        return value

    def choice(self, key, label, options, *, required=False, default=None):
        value = self.data.get(key)
        if value in (None, ""):
            if required:
                self.fail(key, f"{label} là bắt buộc.")
            return default
        if value not in options:
            self.fail(key, f"{label} không hợp lệ.")
            return default
        return value

    def boolean(self, key, default=False):
        value = self.data.get(key, default)
        return bool(value) if isinstance(value, (bool, int)) else default

    def integer(self, key, label, *, minimum, maximum, required=True):
        value = self.data.get(key)
        if value is None:
            if required:
                self.fail(key, f"{label} là bắt buộc.")
            return None
        number = as_int(value)
        if number is None or not (minimum <= number <= maximum):
            self.fail(key, f"{label} phải từ {minimum} đến {maximum}.")
            return None
        return number

    def done(self) -> None:
        if self.errors:
            raise ApiError("Dữ liệu không hợp lệ.", 422, "validation_error", self.errors)


# ------------------------------------------------------------ đăng nhập
def login_user(user, remember: bool = False) -> None:
    session["uid"] = user["id"]
    session["sv"] = user["session_version"]
    session.permanent = bool(remember)
    g.user = user


def logout_user() -> None:
    session.clear()
    g.user = None


def current_user():
    """Trả về hàng users của người đang đăng nhập (hoặc None)."""
    if "user" in g:
        return g.user
    user = None
    uid = session.get("uid")
    if uid is not None:
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if row is not None and row["session_version"] == session.get("sv"):
            user = row
        else:  # tài khoản bị xóa hoặc đã "đăng xuất mọi thiết bị"
            session.pop("uid", None)
            session.pop("sv", None)
    g.user = user
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            raise ApiError("Bạn cần đăng nhập để thực hiện thao tác này.", 401, "unauthorized")
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    """Chỉ tài khoản role = 'admin' (phía shop). 401 nếu chưa đăng nhập, 403 nếu không phải admin."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            raise ApiError("Bạn cần đăng nhập để thực hiện thao tác này.", 401, "unauthorized")
        if user["role"] != "admin":
            raise ApiError("Chỉ shop (quản trị viên) mới dùng được chức năng này.", 403, "forbidden")
        return view(*args, **kwargs)

    return wrapper
