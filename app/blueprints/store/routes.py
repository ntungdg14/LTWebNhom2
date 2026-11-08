"""Các trang cửa hàng: trang chủ, danh sách, chi tiết sản phẩm, giỏ hàng.

Ngoài ra có 3 trang thông tin tĩnh dùng cho các liên kết chân trang / biểu mẫu.
"""
import sqlite3

from flask import render_template

from ...common.helpers import login_required_page
from ...db import get_db
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
@login_required_page
def cart():
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


# Mega menu ở header: mỗi mục (Nữ / Nam / Phụ kiện / Hàng mới / Sale) lấy sản phẩm THẬT ngay từ server,
# nên HTML trả về đã đúng nội dung, không còn danh sách mẫu hiện ra rồi mới bị JS thay.
MEGA_MENU_FILTERS = {
    "nu": "p.department = 'nu'",
    "nam": "p.department = 'nam'",
    "phu-kien": "p.department = 'phu-kien'",
    "hang-moi": "p.is_new = 1",
    "sale": "p.compare_price IS NOT NULL",
}


@store_bp.app_context_processor
def inject_mega_menu():
    def mega_products(key: str, limit: int = 8) -> list:
        where = MEGA_MENU_FILTERS.get(key)
        if not where:
            return []
        try:
            return get_db().execute(
                f"""SELECT p.slug, p.name, p.is_featured FROM products p
                    WHERE p.status = 'active' AND {where}
                    ORDER BY p.sold_count DESC, p.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        except sqlite3.Error:
            return []

    return {"mega_products": mega_products}
