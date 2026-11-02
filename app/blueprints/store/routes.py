"""Các trang cửa hàng: trang chủ, danh sách, chi tiết sản phẩm, giỏ hàng."""
from flask import render_template

from . import store_bp


@store_bp.route("/")
def home():
    return render_template("store/home.html")


@store_bp.route("/shop")
def shop():
    return render_template("store/shop.html")


@store_bp.route("/product")
def product_detail():
    return render_template("store/product_detail.html")


@store_bp.route("/cart")
def cart():
    return render_template("store/cart.html")
