"""Xác thực: đăng ký, đăng nhập, đăng xuất, quên / đặt lại mật khẩu.

    POST /api/auth/register         tạo tài khoản và đăng nhập luôn
    POST /api/auth/login            email + mật khẩu (+ remember)
    POST /api/auth/logout
    GET  /api/auth/me               người dùng hiện tại (user = null nếu chưa đăng nhập)
    POST /api/auth/forgot-password  tạo token đặt lại mật khẩu
    POST /api/auth/reset-password   đặt mật khẩu mới bằng token
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3

from flask import current_app, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from ...db import get_db
from . import auth_api_bp as api_bp
from ...common.helpers import ApiError, Fields, current_user, json_body, login_user, logout_user
from ...common.serializers import user_json
from ...common.login_limiter import (
    clear_failures, locked_message, normalize_email, record_failure, seconds_locked,
)

RESET_TOKEN_MINUTES = 60
# Hash giả để thời gian phản hồi khi email không tồn tại gần giống khi sai mật khẩu.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


@api_bp.post("/auth/register")
def register():
    data = json_body()
    f = Fields(data)
    full_name = f.text("full_name", "Họ và tên", max_len=100)
    email = f.email()
    phone = f.phone(required=False)
    password = f.password()
    birthday = f.birthday()
    gender = f.choice("gender", "Giới tính", ("nam", "nu", "khac"))
    newsletter = f.boolean("newsletter")
    if data.get("confirm_password") is not None and data.get("confirm_password") != data.get("password"):
        f.fail("confirm_password", "Mật khẩu xác nhận không khớp.")
    f.done()

    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO users (full_name, email, phone, password_hash, birthday, gender, newsletter, password_updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (full_name, email, phone, generate_password_hash(password), birthday, gender, int(newsletter)),
        )
    except sqlite3.IntegrityError:
        raise ApiError("Email này đã được đăng ký.", 409, "email_taken", {"email": "Email này đã được đăng ký."})
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    login_user(user)
    response = jsonify(user=user_json(user))
    response.status_code = 201
    return response


@api_bp.post("/auth/login")
def login():
    data = json_body()
    f = Fields(data)
    email = f.email()
    password = data.get("password")
    if not isinstance(password, str) or not password:
        f.fail("password", "Mật khẩu là bắt buộc.")
    f.done()

    db = get_db()
    email = normalize_email(email)
    locked = seconds_locked(db, email)
    if locked:
        raise ApiError(locked_message(locked), 429, "too_many_attempts")
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
    if not user or not ok:
        record_failure(db, email)
        raise ApiError("Email hoặc mật khẩu không đúng.", 401, "invalid_credentials")
    clear_failures(db, email)
    login_user(user, remember=f.boolean("remember"))
    return jsonify(user=user_json(user))


@api_bp.post("/auth/logout")
def logout():
    logout_user()
    return jsonify(ok=True)


@api_bp.get("/auth/me")
def me():
    user = current_user()
    return jsonify(user=user_json(user) if user else None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@api_bp.post("/auth/forgot-password")
def forgot_password():
    f = Fields(json_body())
    email = f.email()
    f.done()

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    payload = {"message": "Nếu email tồn tại, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu."}
    if user:
        token = secrets.token_urlsafe(32)
        db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (user["id"],))
        db.execute(
            "INSERT INTO password_resets (token, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
            (_hash_token(token), user["id"], f"+{RESET_TOKEN_MINUTES} minutes"),
        )
        # TODO: gửi email chứa liên kết có token. Chưa có dịch vụ email nên chỉ lộ token khi cấu hình cho phép.
        if current_app.config.get("EXPOSE_RESET_TOKEN"):
            payload["reset_token"] = token
    return jsonify(payload)  # luôn trả cùng một kết quả để không lộ email nào đã đăng ký


@api_bp.post("/auth/reset-password")
def reset_password():
    data = json_body()
    f = Fields(data)
    token = f.text("token", "Mã đặt lại", max_len=200)
    password = f.password("password", "Mật khẩu mới")
    if data.get("confirm_password") is not None and data.get("confirm_password") != data.get("password"):
        f.fail("confirm_password", "Mật khẩu xác nhận không khớp.")
    f.done()

    db = get_db()
    row = db.execute(
        "SELECT user_id FROM password_resets WHERE token = ? AND used = 0 AND expires_at > datetime('now')",
        (_hash_token(token),),
    ).fetchone()
    if row is None:
        raise ApiError("Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.", 400, "invalid_token")
    db.execute(
        """UPDATE users SET password_hash = ?, password_updated_at = datetime('now'),
                  session_version = session_version + 1 WHERE id = ?""",
        (generate_password_hash(password), row["user_id"]),
    )
    db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ?", (row["user_id"],))
    return jsonify(ok=True, message="Đã đặt lại mật khẩu. Vui lòng đăng nhập lại.")
