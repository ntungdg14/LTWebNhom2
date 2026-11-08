"""Tiện ích dùng chung cho API: lỗi JSON, đăng nhập theo session, kiểm tra dữ liệu.

Quy ước phản hồi lỗi::

    {"error": {"code": "validation_error", "message": "...", "fields": {"email": "..."}}}
"""
from __future__ import annotations

import re
import secrets
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, flash, g, jsonify, redirect, request, session, url_for

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
    session.pop("csrf_token", None)  # đổi CSRF token sau khi đăng nhập
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


# ------------------------------------------------------------------ CSRF
def csrf_token() -> str:
    """Token CSRF của phiên hiện tại (tạo mới nếu chưa có). Dùng trong template: {{ csrf_token() }}."""
    token = session.get("csrf_token")
    if not token:
        token = session["csrf_token"] = secrets.token_urlsafe(32)
    return token


def validate_csrf() -> None:
    """So sánh token gửi lên (field `csrf_token` hoặc header X-CSRF-Token) với token trong session."""
    expected = session.get("csrf_token")
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not expected or not sent or not secrets.compare_digest(sent.encode(), expected.encode()):
        abort(400, description="CSRF token thiếu hoặc không hợp lệ. Hãy tải lại trang rồi thử lại.")


# ------------------------------------------------------- điều hướng / next
def safe_next_url(target) -> str | None:
    """Chỉ chấp nhận đường dẫn nội bộ: bắt đầu bằng '/', không '//', không '\\', không scheme/host."""
    if not isinstance(target, str) or not target.startswith("/") or target.startswith("//"):
        return None
    if "\\" in target or any(ord(ch) < 32 or ord(ch) == 127 for ch in target):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


def wants_json() -> bool:
    """True với /api/*, fetch/AJAX (X-Requested-With), body JSON hoặc client ưu tiên JSON."""
    if request.path == "/api" or request.path.startswith("/api/"):
        return True
    if request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest" or request.is_json:
        return True
    best = request.accept_mimetypes.best_match(["text/html", "application/json"])
    return best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]


def _current_path_with_query() -> str:
    path = request.full_path if request.query_string else request.path
    return path.rstrip("?")


def redirect_to_login():
    flash("Vui lòng đăng nhập để tiếp tục", "error")
    return redirect(url_for("auth.login", next=_current_path_with_query()))


def check_role(*roles: str):
    """Kiểm tra đăng nhập (+ vai trò nếu có). Trả về response nếu bị chặn, None nếu hợp lệ.

    - Chưa đăng nhập: JSON 401 (API/AJAX) hoặc redirect tới auth.login?next=...
    - Sai vai trò: 403 (JSON hoặc trang lỗi).
    """
    user = current_user()
    if user is None:
        if wants_json():
            raise ApiError("Bạn cần đăng nhập để thực hiện thao tác này.", 401, "unauthorized")
        return redirect_to_login()
    if roles and user["role"] not in roles:
        if wants_json():
            raise ApiError("Bạn không có quyền thực hiện thao tác này.", 403, "forbidden")
        abort(403)
    return None


def login_required_page(view):
    """Decorator cho trang HTML: chưa đăng nhập thì chuyển tới đăng nhập (kèm next)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        blocked = check_role()
        return blocked if blocked is not None else view(*args, **kwargs)

    return wrapper


def role_required(*roles: str):
    """Decorator dùng được cho cả HTML lẫn API: @role_required('admin')."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            blocked = check_role(*roles)
            return blocked if blocked is not None else view(*args, **kwargs)

        return wrapper

    return decorator
