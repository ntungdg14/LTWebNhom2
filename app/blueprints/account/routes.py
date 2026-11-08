"""Khu vực tài khoản cá nhân (URL bắt đầu bằng /account)."""
from flask import render_template

from ...common.helpers import check_role
from . import account_bp


@account_bp.before_request
def require_login():
    """Mọi trang /account cần đăng nhập."""
    return check_role()


@account_bp.route("")
def profile():
    return render_template("account/profile.html")


@account_bp.route("/orders")
def order_history():
    return render_template("account/order_history.html")


@account_bp.route("/orders/<order_id>")
def order_detail(order_id):
    return render_template("account/order_detail.html", order_id=order_id)


@account_bp.route("/address")
def address():
    return render_template("account/address.html")


@account_bp.route("/wishlist")
def wishlist():
    return render_template("account/wishlist.html")
