"""Khu vực tài khoản cá nhân (URL bắt đầu bằng /account)."""
from flask import render_template, redirect, request, url_for
from ...common.helpers import current_user

from . import account_bp


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


@account_bp.before_request
def require_page_login():
    if current_user() is None:
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
