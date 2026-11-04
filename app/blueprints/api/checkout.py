"""API thanh toán: dữ liệu bước giao hàng/thanh toán và tạo đơn hàng."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from flask import jsonify, request, session

from ...db import get_db
from . import api_bp
from .account import address_dict, default_address, set_default_address
from .orders import order_dict
from .service import (PAYMENT_METHODS, SHIPPING_METHODS, cart_payload, delivery_window, evaluate_coupon, get_cart,
                      shipping_fee, totals)
from .utils import (ApiError, current_user, json_body, now_vn, raise_if, text, to_int, user_dict, valid_email,
                    valid_phone)


def _methods(subtotal: int) -> list[dict]:
    today = datetime.now()
    out = []
    for key, m in SHIPPING_METHODS.items():
        lo, hi = delivery_window(today, key)
        out.append({"id": key, "label": m["label"], "note": m["note"], "fee": shipping_fee(key, subtotal),
                    "estimated_from": lo, "estimated_to": hi})
    return out


@api_bp.get("/checkout")
def checkout_data():
    """Mọi thứ trang thanh toán cần: giỏ hàng, người dùng + địa chỉ đã lưu, phương thức giao/thanh toán.

    Query: shipping_method=standard|express để tính tổng tiền theo phương thức đang chọn."""
    method = request.args.get("shipping_method", "standard")
    if method not in SHIPPING_METHODS:
        raise ApiError("shipping_method không hợp lệ.", 400, "bad_request")
    cart = cart_payload(get_cart(), method)
    user = current_user()
    addresses = []
    if user:
        addresses = [address_dict(r) for r in get_db().execute(
            "SELECT * FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id", (user["id"],))]
    return jsonify({
        "cart": cart,
        "user": user_dict(user) if user else None,
        "addresses": addresses,
        "default_address": default_address(user["id"]) if user else None,
        "shipping_methods": _methods(cart["summary"]["subtotal"]),
        "payment_methods": [{"id": k, "label": v["label"], "description": v["description"], "short": v["short"]}
                            for k, v in PAYMENT_METHODS.items()],
    })


def _order_code(db: sqlite3.Connection) -> str:
    prefix = "FR" + datetime.now().strftime("%y%m%d")
    n = db.execute("SELECT COUNT(*) FROM orders WHERE code LIKE ?", (prefix + "%",)).fetchone()[0]
    return f"{prefix}{n + 1:03d}"


@api_bp.post("/checkout")
def place_order():
    """Tạo đơn từ giỏ hàng hiện tại. Khách vãng lai cũng đặt được (theo dõi đơn vừa đặt qua session).

    Body mẫu:
      {"contact": {"full_name", "phone", "email"},
       "address": {"address_id": 3}  hoặc  {"province", "ward", "street"},
       "save_as_default": true, "shipping_method": "standard", "payment_method": "cod",
       "note": "...", "vat_invoice": false, "accept_terms": true, "coupon_code": "TUDO10" (tùy chọn)}
    """
    data, errors, db, user = json_body(), {}, get_db(), current_user()
    contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
    if not contact:
        errors["contact"] = "Vui lòng nhập thông tin liên hệ."
    full_name = text(contact, "full_name", "họ và tên", errors, max_len=100) if contact else None
    phone = valid_phone(text(contact, "phone", "số điện thoại", errors, max_len=20), errors) if contact else None
    email = valid_email(text(contact, "email", "email", errors, max_len=150), errors) if contact else None
    for k in ("full_name", "phone", "email"):  # đưa lỗi lồng vào dạng contact.<field>
        if k in errors:
            errors[f"contact.{k}"] = errors.pop(k)

    addr_in = data.get("address") if isinstance(data.get("address"), dict) else {}
    saved_address_id = None
    if addr_in.get("address_id") is not None:
        if user is None:
            errors["address"] = "Cần đăng nhập để dùng địa chỉ đã lưu."
        else:
            row = db.execute("SELECT * FROM addresses WHERE id = ? AND user_id = ?",
                             (to_int(addr_in["address_id"], 0), user["id"])).fetchone()
            if row is None:
                errors["address"] = "Không tìm thấy địa chỉ đã chọn."
            else:
                province, ward, street, saved_address_id = row["province"], row["ward"], row["street"], row["id"]
    else:
        sub: dict = {}
        province = text(addr_in, "province", "tỉnh/thành phố", sub, max_len=80)
        ward = text(addr_in, "ward", "phường/xã", sub, max_len=80)
        street = text(addr_in, "street", "địa chỉ cụ thể", sub, max_len=200)
        errors.update({f"address.{k}": v for k, v in sub.items()})

    method = data.get("shipping_method", "standard")
    if method not in SHIPPING_METHODS:
        errors["shipping_method"] = "Phương thức giao hàng không hợp lệ."
    payment = data.get("payment_method", "cod")
    if payment not in PAYMENT_METHODS:
        errors["payment_method"] = "Phương thức thanh toán không hợp lệ."
    note = text(data, "note", "ghi chú", errors, required=False, max_len=500)
    if data.get("accept_terms") is not True:
        errors["accept_terms"] = "Bạn cần đồng ý với Điều khoản mua hàng và Chính sách bảo mật."
    raise_if(errors)

    cart = get_cart()
    lines = cart_payload(cart, method)["items"] if cart else []
    if not lines:
        raise ApiError("Giỏ hàng đang trống.", 409, "empty_cart")

    # --- Từ đây ghi dữ liệu: dùng một transaction, khóa ghi để tránh bán vượt tồn kho ---
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")
    try:
        # Đọc lại giá/tồn kho trong transaction (giá lấy từ DB, không tin client).
        subtotal, items = 0, []
        for l in cart_payload(cart, method)["items"]:
            ok = db.execute(
                "UPDATE variants SET stock = stock - ? WHERE id = ? AND stock >= ? "
                "AND product_id IN (SELECT id FROM products WHERE status = 'active')",
                (l["quantity"], l["variant_id"], l["quantity"])).rowcount
            if not ok:
                raise ApiError(f"{l['product']['name']} (size {l['size']}) không đủ hàng. Vui lòng cập nhật giỏ hàng.",
                               409, "out_of_stock")
            subtotal += l["line_total"]
            items.append(l)

        code_in = data.get("coupon_code") or cart["coupon_code"]
        coupon = evaluate_coupon(code_in, subtotal)
        if data.get("coupon_code") and not coupon["valid"]:
            raise ApiError(coupon["message"], 422, "invalid_coupon", {"coupon_code": coupon["message"]})
        t = totals(subtotal, coupon, method)
        placed = now_vn()
        for attempt in range(5):
            try:
                cur = db.execute(
                    """INSERT INTO orders (code, user_id, full_name, phone, email, province, ward, street, note,
                           shipping_method, shipping_fee, payment_method, payment_status, status, subtotal, discount,
                           coupon_code, total, vat_invoice, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid', 'pending', ?, ?, ?, ?, ?, ?)""",
                    (_order_code(db), user["id"] if user else None, full_name, phone, email, province, ward, street,
                     note, method, t["shipping_fee"], payment, subtotal, t["discount"],
                     coupon["code"] if coupon and coupon["valid"] else None, t["total"],
                     int(data.get("vat_invoice") is True), placed))
                break
            except sqlite3.IntegrityError:
                if attempt == 4:
                    raise
        order_id = cur.lastrowid
        for l in items:
            db.execute(
                """INSERT INTO order_items (order_id, variant_id, product_id, product_slug, name, color, size, tone,
                                            price, compare_price, quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, l["variant_id"], l["product"]["id"], l["product"]["slug"], l["product"]["name"],
                 l["color"]["name"], l["size"], l["product"]["image"]["tone"], l["unit_price"], l["compare_price"],
                 l["quantity"]))
            db.execute("UPDATE products SET sold_count = sold_count + ? WHERE id = ?", (l["quantity"], l["product"]["id"]))
        db.execute("INSERT INTO order_events (order_id, status, created_at) VALUES (?, 'pending', ?)", (order_id, placed))

        if user:
            if saved_address_id is None and data.get("save_as_default") is True:
                existing = db.execute(
                    "SELECT id FROM addresses WHERE user_id = ? AND province = ? AND ward = ? AND street = ?",
                    (user["id"], province, ward, street)).fetchone()
                saved_address_id = existing["id"] if existing else db.execute(
                    "INSERT INTO addresses (user_id, label, full_name, phone, province, ward, street) VALUES (?, 'Nhà riêng', ?, ?, ?, ?, ?)",
                    (user["id"], full_name, phone, province, ward, street)).lastrowid
                set_default_address(user["id"], saved_address_id)
            elif saved_address_id is not None and data.get("save_as_default") is True:
                set_default_address(user["id"], saved_address_id)

        db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart["id"],))
        db.execute("UPDATE carts SET coupon_code = NULL WHERE id = ?", (cart["id"],))
        db.commit()
    except BaseException:
        db.rollback()
        raise

    code = db.execute("SELECT code FROM orders WHERE id = ?", (order_id,)).fetchone()["code"]
    if user is None:
        session["guest_orders"] = [*session.get("guest_orders", [])[-9:], code]
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return jsonify({"order": order_dict(order),
                    "message": f"Chúng tôi đã gửi xác nhận đến {email}."}), 201
