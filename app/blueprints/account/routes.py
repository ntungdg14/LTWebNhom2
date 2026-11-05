"""Khu vực tài khoản cá nhân (URL bắt đầu bằng /account)."""
from flask import render_template

from app import commerce

from . import account_bp


@account_bp.route("")
def profile():
    return render_template("account/profile.html")


@account_bp.route("/orders")
def order_history():
    return render_template("account/order_history.html", orders=commerce.get_order_history())


@account_bp.route("/orders/<order_id>")
def order_detail(order_id):
    return render_template(
        "account/order_detail.html", order_id=order_id, order=commerce.get_order()
    )


@account_bp.route("/address")
def address():
    return render_template("account/address.html")


@account_bp.route("/wishlist")
def wishlist():
    return render_template("account/wishlist.html")
