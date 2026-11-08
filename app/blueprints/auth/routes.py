"""Các trang xác thực: đăng nhập, đăng ký, quên mật khẩu."""
from flask import redirect, render_template, url_for

from ...common.helpers import logout_user
from . import auth_bp


@auth_bp.route("/login")
def login():
    return render_template("auth/login.html")


@auth_bp.route("/register")
def register():
    return render_template("auth/register.html")


@auth_bp.route("/forgot-password")
def forgot_password():
    return render_template("auth/forgot_password.html")


@auth_bp.route("/logout")
def logout():
    """Xóa phiên đăng nhập rồi về trang đăng nhập (liên kết "Đăng xuất" trỏ vào đây)."""
    logout_user()
    return redirect(url_for("auth.login"))
