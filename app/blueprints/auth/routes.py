"""Các trang xác thực: đăng nhập, đăng ký, đăng xuất, quên mật khẩu (form HTML, có CSRF)."""
from __future__ import annotations

import sqlite3

from flask import flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ...common.helpers import Fields, current_user, login_user, logout_user, safe_next_url
from ...common.login_limiter import (
    clear_failures, locked_message, normalize_email, record_failure, seconds_locked,
)
from ...db import get_db
from . import auth_bp

# Hash giả để thời gian phản hồi khi email không tồn tại gần giống khi sai mật khẩu.
_DUMMY_HASH = generate_password_hash("not-a-real-password")
INVALID_LOGIN = "Email hoặc mật khẩu không đúng"


def _next_target() -> str | None:
    return safe_next_url(request.values.get("next"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user() is not None:
        return redirect(url_for("store.home"))
    if request.method == "GET":
        return render_template("auth/register.html", values={}, errors={})

    form = request.form.to_dict()
    f = Fields(form)
    full_name = f.text("full_name", "Họ và tên", max_len=100)
    email = f.email()
    password = f.password()
    confirmation = form.get("password_confirmation") or ""
    if not confirmation:
        f.fail("password_confirmation", "Vui lòng nhập lại mật khẩu.")
    elif password is not None and confirmation != password:
        f.fail("password_confirmation", "Mật khẩu xác nhận không khớp.")
    if not form.get("terms"):
        f.fail("terms", "Bạn cần đồng ý với Điều khoản sử dụng và Chính sách bảo mật.")

    db = get_db()
    if email and "email" not in f.errors and db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        f.fail("email", "Email này đã được đăng ký.")

    if not f.errors:
        try:
            db.execute(
                "INSERT INTO users (full_name, email, password_hash, password_updated_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (full_name, email, generate_password_hash(password)),
            )
        except sqlite3.IntegrityError:  # hai request đồng thời cùng email
            f.fail("email", "Email này đã được đăng ký.")
        else:
            flash("Đăng ký thành công, vui lòng đăng nhập", "success")
            return redirect(url_for("auth.login"))

    values = {"full_name": form.get("full_name", ""), "email": form.get("email", ""), "terms": bool(form.get("terms"))}
    return render_template("auth/register.html", values=values, errors=f.errors), 422


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("store.home"))
    next_url = _next_target()
    if request.method == "GET":
        return render_template("auth/login.html", values={}, errors={}, next_url=next_url)

    raw_email = request.form.get("email", "")
    password = request.form.get("password", "")
    email = normalize_email(raw_email)
    errors: dict[str, str] = {}
    if not email:
        errors["email"] = "Email là bắt buộc."
    if not password:
        errors["password"] = "Mật khẩu là bắt buộc."
    if errors:
        return render_template("auth/login.html", values={"email": raw_email}, errors=errors, next_url=next_url), 422

    db = get_db()
    locked = seconds_locked(db, email)
    if locked:
        error = locked_message(locked)
        status = 429
    else:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
        if user and ok:
            clear_failures(db, email)
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(next_url or url_for("store.home"))
        record_failure(db, email)
        error, status = INVALID_LOGIN, 401
    return (
        render_template("auth/login.html", values={"email": raw_email}, errors={}, form_error=error, next_url=next_url),
        status,
    )


@auth_bp.post("/logout")
def logout():
    logout_user()
    flash("Bạn đã đăng xuất", "success")
    return redirect(url_for("store.home"))


@auth_bp.route("/forgot-password")
def forgot_password():
    return render_template("auth/forgot_password.html")
