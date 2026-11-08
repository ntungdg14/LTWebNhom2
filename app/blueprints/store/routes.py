"""Các trang cửa hàng: trang chủ, danh sách, chi tiết sản phẩm, giỏ hàng.

Ngoài ra có 3 trang thông tin tĩnh dùng cho các liên kết chân trang / biểu mẫu.
"""
from flask import render_template, redirect, request, url_for
from ...common.helpers import current_user

from . import store_bp

INFO_PAGES = {
    "terms": (
        "Điều khoản sử dụng",
        "Khi sử dụng Freesion, bạn đồng ý cung cấp thông tin chính xác và tôn trọng "
        "quy định đặt hàng, thanh toán, đổi trả trong vòng 30 ngày.",
    ),
    "privacy": (
        "Chính sách bảo mật",
        "Freesion chỉ dùng thông tin cá nhân để xác nhận đơn hàng, giao hàng và hỗ trợ "
        "khách hàng. Chúng tôi không chia sẻ dữ liệu cho bên thứ ba.",
    ),
    "help": (
        "Hỗ trợ kỹ thuật",
        "Cần hỗ trợ? Liên hệ 1900 636 028 hoặc hello@freesion.vn, 8:30–21:00 mỗi ngày.",
    ),
}


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
    if current_user() is None:
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
    return render_template("store/cart.html")


def _render_info(key):
    title, content = INFO_PAGES[key]
    return render_template("store/info.html", title=title, content=content)


@store_bp.route("/terms")
def terms():
    return _render_info("terms")


@store_bp.route("/privacy")
def privacy():
    return _render_info("privacy")


@store_bp.route("/help")
def help_page():
    return _render_info("help")
