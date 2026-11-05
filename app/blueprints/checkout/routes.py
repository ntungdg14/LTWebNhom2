"""Luồng đặt hàng 4 bước: giỏ hàng -> giao hàng -> thanh toán -> xác nhận.

Cả 3 trang đều nhận cùng một view-model `order` (order_items + orders),
nên "Tóm tắt đơn hàng" là một component duy nhất, không copy markup.
"""
from flask import render_template

from app import commerce

from . import checkout_bp


@checkout_bp.route("/checkout/shipping")
def shipping():
    return render_template("checkout/shipping.html", order=commerce.get_order())


@checkout_bp.route("/checkout")
def checkout():
    return render_template("checkout/checkout.html", order=commerce.get_order())


@checkout_bp.route("/order-success")
def order_success():
    return render_template("checkout/order_success.html", order=commerce.get_order())
