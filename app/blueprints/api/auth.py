"""API xác thực: đăng ký, đăng nhập, đăng xuất, quên/đặt lại mật khẩu."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ...db import get_db
from . import api_bp
from .service import merge_guest_cart
from .utils import (ApiError, check_password_strength, current_user, json_body, login_user, raise_if, text,
                    user_dict, valid_email, valid_phone)

# Chống dò mật khẩu: tối đa 5 lần sai / 15 phút cho mỗi (email, IP). Lưu trong bộ nhớ tiến trình.
_FAILS: dict[tuple[str, str], list[float]] = {}
_LOCK = threading.Lock()
MAX_FAILS, WINDOW = 5, 15 * 60


def reset_throttle() -> None:
    with _LOCK:
        _FAILS.clear()


def _throttle_key(email: str) -> tuple[str, str]:
    return email.lower(), request.remote_addr or ""


def _recent_fails(key) -> list[float]:
    cutoff = time.time() - WINDOW
    with _LOCK:
        _FAILS[key] = [t for t in _FAILS.get(key, []) if t > cutoff]
        return list(_FAILS[key])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@api_bp.post("/auth/register")
def register():
    data, errors = json_body(), {}
    name = text(data, "full_name", "họ và tên", errors, max_len=100)
    email = valid_email(text(data, "email", "email", errors, max_len=150), errors)
    phone = valid_phone(text(data, "phone", "số điện thoại", errors, required=False, max_len=20), errors)
    password = data.get("password")
    check_password_strength(password, errors)
    if "password" not in errors and password != data.get("confirm_password"):
        errors["confirm_password"] = "Mật khẩu xác nhận không khớp."
    if data.get("accept_terms") is not True:
        errors["accept_terms"] = "Bạn cần đồng ý với Điều khoản sử dụng và Chính sách bảo mật."
    raise_if(errors)

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise ApiError("Email này đã được đăng ký.", 409, "email_taken", {"email": "Email này đã được đăng ký."})
    guest_token = session.get("cart_token")
    cur = db.execute(
        "INSERT INTO users (full_name, email, phone, password_hash, password_updated_at) VALUES (?, ?, ?, ?, date('now'))",
        (name, email, phone, generate_password_hash(password)))
    db.commit()
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    login_user(user)
    if guest_token:
        session["cart_token"] = guest_token
        merge_guest_cart(user["id"])
        session.pop("cart_token", None)
    return jsonify({"user": user_dict(user)}), 201


@api_bp.post("/auth/login")
def login():
    data, errors = json_body(), {}
    email = text(data, "email", "email", errors, max_len=150)
    password = data.get("password")
    if not password or not isinstance(password, str):
        errors["password"] = "Vui lòng nhập mật khẩu."
    raise_if(errors)

    key = _throttle_key(email)
    if len(_recent_fails(key)) >= MAX_FAILS:
        raise ApiError("Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.", 429, "too_many_attempts")
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        with _LOCK:
            _FAILS.setdefault(key, []).append(time.time())
        raise ApiError("Email hoặc mật khẩu không đúng.", 401, "invalid_credentials")
    with _LOCK:
        _FAILS.pop(key, None)

    guest_token = session.get("cart_token")
    login_user(user, remember=data.get("remember") is True)
    if guest_token:
        session["cart_token"] = guest_token
        merge_guest_cart(user["id"])
        session.pop("cart_token", None)
    return jsonify({"user": user_dict(user)})


@api_bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@api_bp.get("/auth/me")
def me():
    user = current_user()
    return jsonify({"authenticated": user is not None, "user": user_dict(user) if user else None})


@api_bp.post("/auth/forgot-password")
def forgot_password():
    """Luôn trả 200 (không lộ email nào có tài khoản). Chưa tích hợp gửi mail:
    link đặt lại được ghi vào log; ở chế độ DEBUG/TESTING token được trả kèm để thử nghiệm."""
    errors: dict = {}
    email = valid_email(text(json_body(), "email", "email", errors, max_len=150), errors)
    raise_if(errors)
    db = get_db()
    user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    body: dict = {"message": "Nếu email tồn tại, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu."}
    if user:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO password_resets (token, user_id, expires_at) VALUES (?, ?, ?)",
                   (_hash_token(token), user["id"], expires))
        db.commit()
        current_app.logger.info("Password reset token cho %s: %s", email, token)
        if current_app.debug or current_app.testing:
            body["debug_token"] = token
    return jsonify(body)


@api_bp.post("/auth/reset-password")
def reset_password():
    data, errors = json_body(), {}
    token = text(data, "token", "mã xác nhận", errors, max_len=200)
    password = data.get("password")
    check_password_strength(password, errors)
    if "password" not in errors and password != data.get("confirm_password"):
        errors["confirm_password"] = "Mật khẩu xác nhận không khớp."
    raise_if(errors)
    db = get_db()
    row = db.execute(
        "SELECT * FROM password_resets WHERE token = ? AND used = 0 AND expires_at > datetime('now')",
        (_hash_token(token),)).fetchone()
    if row is None:
        raise ApiError("Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.", 400, "invalid_token")
    db.execute("UPDATE users SET password_hash = ?, password_updated_at = date('now'), session_version = session_version + 1 "
               "WHERE id = ?", (generate_password_hash(password), row["user_id"]))
    db.execute("UPDATE password_resets SET used = 1 WHERE token = ?", (row["token"],))
    db.commit()
    return jsonify({"ok": True})
