"""Khu vực tài khoản cá nhân (URL bắt đầu bằng /account)."""
from flask import render_template

from . import account_bp


@account_bp.route("")
def profile():
    return render_template("account/profile.html")


@account_bp.route("/orders")
def order_history():
    return render_template("account/order_history.html")


@account_bp.route("/address")
def address():
    return render_template("account/address.html")


@account_bp.route("/wishlist")
def wishlist():
    return render_template("account/wishlist.html")
