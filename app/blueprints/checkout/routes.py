"""Luồng đặt hàng: thông tin thanh toán và trang xác nhận."""
from flask import render_template

from . import checkout_bp


@checkout_bp.route("/checkout")
def checkout():
    return render_template("checkout/checkout.html")


@checkout_bp.route("/order-success")
def order_success():
    return render_template("checkout/order_success.html")
