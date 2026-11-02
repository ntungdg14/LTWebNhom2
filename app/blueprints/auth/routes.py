"""Các trang xác thực: đăng nhập, đăng ký, quên mật khẩu."""
from flask import render_template

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
