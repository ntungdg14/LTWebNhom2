"""Luồng đặt hàng 4 bước: giỏ hàng -> giao hàng -> thanh toán -> xác nhận."""
from flask import render_template, redirect, request, url_for
from ...common.helpers import current_user

from . import checkout_bp


@checkout_bp.route("/checkout/shipping")
def shipping():
    return render_template("checkout/shipping.html")


@checkout_bp.route("/checkout")
def checkout():
    return render_template("checkout/checkout.html")


@checkout_bp.route("/order-success")
def order_success():
    return render_template("checkout/order_success.html")


@checkout_bp.before_request
def require_page_login():
    if current_user() is None:
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
