"""API giỏ hàng (khách dùng session, người dùng đăng nhập dùng giỏ lưu trong DB)."""
from __future__ import annotations

from flask import jsonify, request

from ...db import get_db
from . import api_bp
from .service import (MAX_LINE_QUANTITY, PRODUCT_CARD_SELECT, add_to_cart, cart_payload, evaluate_coupon,
                      find_variant, get_cart, product_cards)
from .utils import ApiError, json_body, raise_if, text, to_int


def _quantity(data: dict, key: str = "quantity", default: int = 1) -> int:
    val = data.get(key, default)
    if not isinstance(val, int) or isinstance(val, bool) or val < 1:
        raise ApiError("Số lượng phải là số nguyên từ 1 trở lên.", 422, "validation_error", {key: "Số lượng không hợp lệ."})
    return min(val, MAX_LINE_QUANTITY)


@api_bp.get("/cart")
def view_cart():
    return jsonify(cart_payload(get_cart()))


@api_bp.get("/cart/count")
def cart_count():
    """Số hiển thị ở header: Giỏ hàng (n) — n là tổng số lượng."""
    cart = get_cart()
    n = 0
    if cart:
        n = get_db().execute("SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE cart_id = ?", (cart["id"],)).fetchone()[0]
    return jsonify({"count": n})


@api_bp.post("/cart/items")
def add_item():
    """Body: {"variant_id": 12, "quantity": 1} hoặc {"product": "slug", "color": "nau-dua", "size": "M", "quantity": 1}"""
    data, db = json_body(), get_db()
    quantity = _quantity(data)
    if data.get("variant_id") is not None:
        variant = find_variant(to_int(data["variant_id"], 0))
    else:
        errors: dict = {}
        slug = text(data, "product", "sản phẩm", errors)
        color = text(data, "color", "màu sắc", errors)
        size = text(data, "size", "kích cỡ", errors)
        raise_if(errors)
        row = db.execute(
            """SELECT v.id FROM variants v JOIN products p ON p.id = v.product_id JOIN colors co ON co.id = v.color_id
               WHERE p.slug = ? AND co.slug = ? AND v.size = ?""", (slug, color, size.upper())).fetchone()
        variant = find_variant(row["id"]) if row else None
    cart = get_cart(create=True)
    final = add_to_cart(cart, variant, quantity)
    db.commit()
    payload = cart_payload(cart)
    payload["added"] = {"variant_id": variant["id"], "quantity": final}
    return jsonify(payload), 201


def _own_item(item_id: int):
    cart = get_cart()
    row = get_db().execute(
        """SELECT ci.id, ci.quantity, v.stock FROM cart_items ci JOIN variants v ON v.id = ci.variant_id
           WHERE ci.id = ? AND ci.cart_id = ?""", (item_id, cart["id"] if cart else -1)).fetchone()
    if row is None:
        raise ApiError("Không tìm thấy sản phẩm trong giỏ hàng.", 404, "not_found")
    return cart, row


@api_bp.patch("/cart/items/<int:item_id>")
def update_item(item_id: int):
    cart, row = _own_item(item_id)
    quantity = _quantity(json_body())
    if quantity > row["stock"]:
        raise ApiError(f"Chỉ còn {row['stock']} sản phẩm trong kho.", 409, "out_of_stock")
    db = get_db()
    db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (quantity, item_id))
    db.commit()
    return jsonify(cart_payload(cart))


@api_bp.delete("/cart/items/<int:item_id>")
def remove_item(item_id: int):
    cart, _ = _own_item(item_id)
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE id = ?", (item_id,))
    db.commit()
    return jsonify(cart_payload(cart))


@api_bp.delete("/cart")
def clear_cart():
    cart = get_cart()
    if cart:
        db = get_db()
        db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart["id"],))
        db.execute("UPDATE carts SET coupon_code = NULL WHERE id = ?", (cart["id"],))
        db.commit()
    return jsonify(cart_payload(cart))


@api_bp.post("/cart/coupon")
def apply_coupon():
    errors: dict = {}
    code = text(json_body(), "code", "mã giảm giá", errors, max_len=40)
    raise_if(errors)
    cart = get_cart()
    payload = cart_payload(cart)
    result = evaluate_coupon(code, payload["summary"]["subtotal"])
    if not result["valid"]:
        raise ApiError(result["message"], 422, "invalid_coupon", {"code": result["message"]})
    db = get_db()
    db.execute("UPDATE carts SET coupon_code = ? WHERE id = ?", (result["code"], cart["id"]))
    db.commit()
    return jsonify(cart_payload(get_cart()))


@api_bp.delete("/cart/coupon")
def remove_coupon():
    cart = get_cart()
    if cart:
        db = get_db()
        db.execute("UPDATE carts SET coupon_code = NULL WHERE id = ?", (cart["id"],))
        db.commit()
    return jsonify(cart_payload(get_cart()))


@api_bp.get("/cart/recommendations")
def cart_recommendations():
    """'Hoàn thiện set đồ của bạn': sản phẩm khác danh mục với những món trong giỏ."""
    cart = get_cart()
    in_cart = []
    cats = []
    if cart:
        for r in get_db().execute(
                """SELECT DISTINCT p.id, p.category_id FROM cart_items ci JOIN variants v ON v.id = ci.variant_id
                   JOIN products p ON p.id = v.product_id WHERE ci.cart_id = ?""", (cart["id"],)):
            in_cart.append(r["id"])
            cats.append(r["category_id"])
    limit = to_int(request.args.get("limit"), 4, 1, 12)
    ex_ids = ",".join("?" * len(in_cart)) or "NULL"
    ex_cats = ",".join("?" * len(cats)) or "NULL"
    rows = get_db().execute(
        f"""{PRODUCT_CARD_SELECT} WHERE p.status = 'active' AND p.id NOT IN ({ex_ids})
            ORDER BY (p.category_id IN ({ex_cats})) ASC, p.sold_count DESC, p.id LIMIT ?""",
        [*in_cart, *cats, limit]).fetchall()
    return jsonify({"items": product_cards(rows)})
