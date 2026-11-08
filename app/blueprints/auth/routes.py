"""Các trang xác thực: đăng nhập, đăng ký, quên mật khẩu."""
from flask import render_template, redirect, request, url_for
from ...common.helpers import current_user

from . import auth_bp


@auth_bp.route("/login")
def login():
    if current_user() is not None:
        return redirect(_safe_next())
    return render_template("auth/login.html")


@auth_bp.route("/register")
def register():
    if current_user() is not None:
        return redirect(_safe_next())
    return render_template("auth/register.html")


@auth_bp.route("/forgot-password")
def forgot_password():
    return render_template("auth/forgot_password.html")


def _safe_next():
    target = request.args.get("next", "")
    if not target.startswith("/") or target.startswith("//") or "\\" in target or target.startswith(("/login", "/register", "/api/")):
        return url_for("store.home")
    return target
