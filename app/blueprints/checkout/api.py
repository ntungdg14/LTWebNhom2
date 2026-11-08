"""Đặt hàng (khách vãng lai hoặc đã đăng nhập).

    GET  /api/checkout/options      phương thức giao hàng (kèm phí/ngày dự kiến theo giỏ hiện tại) + thanh toán
    POST /api/orders                tạo đơn từ giỏ hàng hiện tại
    GET  /api/orders/<code>         xem đơn (chủ đơn, hoặc khách vừa đặt trong cùng phiên)
    GET  /api/orders/<code>/tracking    theo dõi đơn (mô phỏng: dựng timeline từ cột orders.status)
    POST /api/orders/<code>/simulate    "đẩy" đơn sang bước kế tiếp để demo (cần ORDER_SIMULATION hoặc admin)

Tạo đơn chạy trong một transaction: kiểm tồn kho -> trừ kho -> ghi đơn/dòng hàng/mốc thời gian -> xóa giỏ.
Giá, giảm giá, phí ship và tổng tiền luôn do server tính lại, không tin số liệu từ client.
Thanh toán online (VNPAY/MoMo/thẻ) chưa tích hợp cổng: đơn được tạo ở trạng thái 'unpaid'.
"""
from __future__ import annotations

from datetime import datetime

from flask import current_app, jsonify

from ...db import get_db, transaction
from . import checkout_api_bp as api_bp
from ...common.helpers import ApiError, Fields, current_user, json_body, login_required, optional_json_body
from ...common.serializers import order_json
from ...common.tracking import advance_order, tracking_json
from ...common.services import (
    compute_totals,
    estimated_delivery,
    find_cart,
    line_issue,
    load_cart_rows,
    make_default_address,
    shipping_fee,
    shipping_methods,
)


@api_bp.get("/checkout/options")
def checkout_options():
    db = get_db()
    cart = find_cart(db) if current_user() is not None else None  # endpoint công khai: khách thấy phí chưa có giỏ
    rows = load_cart_rows(db, cart["id"]) if cart else []
    subtotal = sum(r["price"] * r["quantity"] for r in rows)
    return jsonify(
        shipping_methods=[
            {
                "id": key,
                "name": info["name"],
                "fee": shipping_fee(key, subtotal),
                "days": list(info["days"]),
                "estimated_delivery": estimated_delivery(key),
            }
            for key, info in shipping_methods().items()
        ],
        payment_methods=[{"id": k, "name": v} for k, v in current_app.config["PAYMENT_METHODS"].items()],
        free_shipping_threshold=current_app.config["FREE_SHIPPING_THRESHOLD"],
    )


def _new_order_code(db) -> str:
    """FR + yymmdd + số thứ tự trong ngày (3 chữ số), vd. FR261101028."""
    prefix = "FR" + datetime.now().strftime("%y%m%d")
    n = db.execute("SELECT COUNT(*) FROM orders WHERE code LIKE ?", (prefix + "%",)).fetchone()[0] + 1
    while db.execute("SELECT 1 FROM orders WHERE code = ?", (f"{prefix}{n:03d}",)).fetchone():
        n += 1
    return f"{prefix}{n:03d}"


def can_view_order(order) -> bool:
    user = current_user()
    return user is not None and (order["user_id"] == user["id"] or user["role"] == "admin")  # chủ đơn hoặc admin


@api_bp.post("/orders")
@login_required
def create_order():
    order, payment = place_order(json_body())
    response = jsonify(order=order_json(get_db(), order), requires_online_payment=payment != "cod")
    response.status_code = 201
    return response


def place_order(data: dict):
    """Tạo đơn từ giỏ hiện tại. Trả về (dòng orders, phương thức thanh toán); ném ApiError nếu không hợp lệ."""
    db = get_db()
    user = current_user()

    # Dùng địa chỉ trong sổ địa chỉ nếu gửi address_id; các trường gửi kèm sẽ ghi đè.
    if data.get("address_id") is not None:
        saved = db.execute(
            "SELECT * FROM addresses WHERE id = ? AND user_id = ?", (data["address_id"], user["id"])
        ).fetchone()
        if saved is None:
            raise ApiError("Không tìm thấy địa chỉ.", 404, "address_not_found")
        data = {
            "full_name": saved["full_name"],
            "phone": saved["phone"],
            "province": saved["province"],
            "ward": saved["ward"],
            "street": saved["street"],
            **data,
        }
    if user is not None and not data.get("email"):
        data = {**data, "email": user["email"]}

    f = Fields(data)
    full_name = f.text("full_name", "Họ và tên", max_len=100)
    phone = f.phone()
    email = f.email()
    province = f.text("province", "Tỉnh / Thành phố", max_len=100)
    ward = f.text("ward", "Phường / Xã", max_len=100)
    street = f.text("street", "Địa chỉ cụ thể", max_len=200)
    note = f.text("note", "Ghi chú", required=False, max_len=500)
    method = f.choice("shipping_method", "Phương thức giao hàng", tuple(shipping_methods()), default="standard")
    payment = f.choice("payment_method", "Phương thức thanh toán", tuple(current_app.config["PAYMENT_METHODS"]), required=True)
    vat = f.boolean("vat_invoice")
    save_default = f.boolean("save_as_default") and user is not None
    if data.get("accept_terms") is False:
        f.fail("accept_terms", "Bạn cần đồng ý với Điều khoản mua hàng và Chính sách bảo mật.")
    f.done()

    with transaction(db):
        cart = find_cart(db)
        rows = load_cart_rows(db, cart["id"]) if cart else []
        if not rows:
            raise ApiError("Giỏ hàng đang trống.", 409, "cart_empty")
        problems = [
            {"item_id": r["item_id"], "name": r["name"], "message": issue}
            for r in rows
            if (issue := line_issue(r))
        ]
        if problems:
            raise ApiError(
                "Một số sản phẩm trong giỏ không còn đủ hàng.", 409, "stock_issue", {"items": problems}  # type: ignore[arg-type]
            )
        totals = compute_totals(db, rows, cart["coupon_code"], method)
        if cart["coupon_code"] and totals["coupon_error"]:
            raise ApiError(totals["coupon_error"], 409, "invalid_coupon")

        code = _new_order_code(db)
        cur = db.execute(
            """INSERT INTO orders (code, user_id, full_name, phone, email, province, ward, street, note,
                                   shipping_method, shipping_fee, payment_method, subtotal, discount,
                                   coupon_code, total, vat_invoice)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code, user["id"] if user else None, full_name, phone, email, province, ward, street, note,
                method, totals["shipping_fee"], payment, totals["subtotal"], totals["discount"],
                totals["coupon"]["code"] if totals["coupon"] else None, totals["total"], int(vat),
            ),
        )
        order_id = cur.lastrowid
        for r in rows:
            moved = db.execute(
                "UPDATE variants SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (r["quantity"], r["variant_id"], r["quantity"]),
            )
            if moved.rowcount == 0:
                raise ApiError(f"'{r['name']}' vừa hết hàng.", 409, "out_of_stock")
            db.execute("UPDATE products SET sold_count = sold_count + ? WHERE id = ?", (r["quantity"], r["product_id"]))
            db.execute(
                """INSERT INTO order_items (order_id, variant_id, product_id, product_slug, name, color, size, tone,
                                            price, compare_price, quantity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, r["variant_id"], r["product_id"], r["slug"], r["name"], r["color_name"], r["size"],
                    r["image_tone"] or r["tone"], r["price"], r["compare_price"], r["quantity"],
                ),
            )
        db.execute("INSERT INTO order_events (order_id, status) VALUES (?, 'pending')", (order_id,))
        db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart["id"],))
        db.execute("UPDATE carts SET coupon_code = NULL, updated_at = datetime('now') WHERE id = ?", (cart["id"],))
        if save_default:
            make_default_address(
                db, user["id"], {"full_name": full_name, "phone": phone, "province": province, "ward": ward, "street": street}
            )

    return db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone(), payment


@api_bp.get("/orders/<code>")
@login_required
def get_order(code):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE code = ?", (code.upper(),)).fetchone()
    # Không phân biệt "không tồn tại" và "không phải của bạn" để tránh dò mã đơn.
    if order is None or not can_view_order(order):
        raise ApiError("Không tìm thấy đơn hàng.", 404, "order_not_found")
    return jsonify(order=order_json(db, order))


def _viewable_order(db, code: str):
    order = db.execute("SELECT * FROM orders WHERE code = ?", (code.upper(),)).fetchone()
    if order is None or not can_view_order(order):
        raise ApiError("Không tìm thấy đơn hàng.", 404, "order_not_found")
    return order


@api_bp.get("/orders/<code>/tracking")
@login_required
def track_order(code):
    db = get_db()
    return jsonify(tracking=tracking_json(db, _viewable_order(db, code)))


@api_bp.post("/orders/<code>/simulate")
@login_required
def simulate_order(code):
    """Demo: chuyển đơn sang bước tiếp theo (body tùy chọn: {"to": "shipping"} để nhảy tới bước đó)."""
    db = get_db()
    user = current_user()
    if not current_app.config.get("ORDER_SIMULATION") and not (user is not None and user["role"] == "admin"):
        raise ApiError("Chức năng mô phỏng vận chuyển đang tắt.", 403, "simulation_disabled")
    order = _viewable_order(db, code)
    to = optional_json_body().get("to")
    with transaction(db):
        order = db.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
        order = advance_order(db, order, to)
    return jsonify(order=order_json(db, order), tracking=tracking_json(db, order))
