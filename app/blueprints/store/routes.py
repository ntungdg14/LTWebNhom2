"""Các trang cửa hàng: trang chủ, danh sách, chi tiết sản phẩm, giỏ hàng.

Ngoài ra có 3 trang thông tin tĩnh dùng cho các liên kết chân trang / biểu mẫu.

Mô tả sản phẩm, giỏ hàng và tóm tắt đơn hàng không viết cứng trong template:
route lấy view-model từ app.commerce rồi truyền vào, template/macro chỉ lặp.
"""
from flask import render_template, request

from app import commerce

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
    product = commerce.get_product(
        request.args.get("sku"),
        color=request.args.get("color"),
        size=request.args.get("size"),
    )
    return render_template(
        "store/product_detail.html",
        product=product,
        related=commerce.get_related(product["sku"]),
        reviews=commerce.REVIEWS,
        rating_breakdown=commerce.RATING_BREAKDOWN,
    )


@store_bp.route("/cart")
def cart():
    return render_template("store/cart.html", cart=commerce.get_cart())


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
