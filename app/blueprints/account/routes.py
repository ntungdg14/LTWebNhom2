"""Khu vực tài khoản cá nhân (URL bắt đầu bằng /account)."""
import math

from flask import abort, flash, redirect, render_template, request, url_for

from ...common.helpers import ApiError, arg_int, check_role, current_user
from ...common.serializers import order_json, orders_json
from ...common.services import placeholders
from ...common.tracking import tracking_json
from ...db import get_db
from . import account_bp
from .api import STATUS_GROUPS, cancel_order as api_cancel_order, reorder as api_reorder

PER_PAGE = 10
BADGES = {"pending": "badge-warn", "preparing": "badge-warn", "shipping": "badge-warn",
          "delivered": "badge-ok", "cancelled": "badge-danger"}
TAB_LABELS = (("all", "Tất cả"), ("processing", "Đang xử lý"), ("delivered", "Đã giao"), ("cancelled", "Đã hủy"))
PAYMENT_NAMES = {"cod": "Thanh toán khi nhận hàng (COD)", "vnpay": "VNPAY / Thẻ ATM nội địa",
                 "momo": "Ví điện tử MoMo", "card": "Thẻ quốc tế"}


def _images(db, product_ids):
    ids = sorted({i for i in product_ids if i is not None})
    if not ids:
        return {}
    found = {}
    for row in db.execute(
        f"SELECT product_id, url FROM product_images WHERE product_id IN ({placeholders(ids)}) ORDER BY position, id", ids
    ):
        found.setdefault(row["product_id"], row["url"])
    return found


def _own_order(db, code):
    return db.execute(
        "SELECT * FROM orders WHERE code = ? AND user_id = ?", (code.upper(), current_user()["id"])
    ).fetchone()


@account_bp.before_request
def require_login():
    """Mọi trang /account cần đăng nhập."""
    return check_role()


@account_bp.route("")
def profile():
    return render_template("account/profile.html")


@account_bp.route("/orders")
def order_history():
    db = get_db()
    status = request.args.get("status", "all")
    if status not in STATUS_GROUPS:
        status = "all"
    where, params = ["user_id = ?"], [current_user()["id"]]
    if STATUS_GROUPS[status]:
        where.append(f"status IN ({placeholders(STATUS_GROUPS[status])})")
        params += STATUS_GROUPS[status]
    clause = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) FROM orders WHERE {clause}", params).fetchone()[0]
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(arg_int("page", 1), pages)
    rows = db.execute(
        f"SELECT * FROM orders WHERE {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, PER_PAGE, (page - 1) * PER_PAGE],
    ).fetchall()
    orders = orders_json(db, rows)
    images = _images(db, [i["product_id"] for o in orders for i in o["items"]])
    for o in orders:
        for i in o["items"]:
            i["image_url"] = images.get(i["product_id"])
    return render_template(
        "account/order_history.html",
        orders=orders, status=status, tabs=TAB_LABELS, badges=BADGES,
        page=page, pages=pages, total=total,
        page_url=lambda n: url_for("account.order_history", status=status if status != "all" else None, page=n if n > 1 else None),
    )


@account_bp.route("/orders/<order_id>")
def order_detail(order_id):
    db = get_db()
    row = _own_order(db, order_id)
    if row is None:
        abort(404)
    order = order_json(db, row)
    images = _images(db, [i["product_id"] for i in order["items"]])
    for i in order["items"]:
        i["image_url"] = images.get(i["product_id"])
    return render_template(
        "account/order_detail.html",
        order=order, tracking=tracking_json(db, row), badges=BADGES,
        payment_name=PAYMENT_NAMES.get(order["payment_method"], order["payment_method"]),
    )


@account_bp.post("/orders/<order_id>/cancel")
def order_cancel(order_id):
    try:
        api_cancel_order(order_id)
        flash("Đã hủy đơn hàng.", "success")
    except ApiError as exc:
        flash(exc.message, "error")
    return redirect(url_for("account.order_detail", order_id=order_id))


@account_bp.post("/orders/<order_id>/reorder")
def order_reorder(order_id):
    try:
        api_reorder(order_id)
    except ApiError as exc:
        flash(exc.message, "error")
        return redirect(url_for("account.order_detail", order_id=order_id))
    flash("Đã thêm các sản phẩm còn hàng vào giỏ.", "success")
    return redirect(url_for("store.cart"))


@account_bp.route("/address")
def address():
    return render_template("account/address.html")


@account_bp.route("/wishlist")
def wishlist():
    return render_template("account/wishlist.html")
