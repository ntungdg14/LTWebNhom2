"""Logic nghiệp vụ dùng chung: giá, vận chuyển, mã giảm giá, giỏ hàng, sản phẩm."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from flask import session

from ...db import get_db
from .utils import ApiError, current_user, now_vn

FREE_SHIPPING_THRESHOLD = 499_000
STANDARD_FEE_BELOW_THRESHOLD = 30_000
RETURN_DAYS = 30
MAX_LINE_QUANTITY = 10

SHIPPING_METHODS = {
    "standard": {"label": "Giao hàng tiêu chuẩn", "fee": 0, "days": (3, 5), "note": "3–5 ngày làm việc"},
    "express": {"label": "Giao hàng nhanh nội thành", "fee": 35_000, "days": (1, 2), "note": "1–2 ngày làm việc"},
}
PAYMENT_METHODS = {
    "cod": {"label": "Thanh toán khi nhận hàng (COD)", "short": "COD",
            "description": "Thanh toán bằng tiền mặt cho nhân viên giao hàng.", "online": False},
    "vnpay": {"label": "VNPAY / Thẻ ATM nội địa", "short": "VNPAY",
              "description": "Quét mã QR hoặc thanh toán qua ứng dụng ngân hàng.", "online": True},
    "momo": {"label": "Ví điện tử MoMo", "short": "MoMo",
             "description": "Chuyển đến ứng dụng MoMo để xác nhận thanh toán.", "online": True},
    "card": {"label": "Thẻ quốc tế", "short": "THẺ",
             "description": "Visa, Mastercard, JCB · Xác thực an toàn qua 3D Secure.", "online": True},
}

ORDER_STATUS_LABELS = {
    "pending": "Đã tiếp nhận",
    "preparing": "Đang chuẩn bị hàng",
    "shipping": "Đang giao hàng",
    "delivered": "Đã giao hàng",
    "cancelled": "Đã hủy",
}
PAYMENT_STATUS_LABELS = {"unpaid": "Chưa thanh toán", "paid": "Đã thanh toán", "refunded": "Đã hoàn tiền"}
CANCELLABLE = ("pending", "preparing")


def shipping_fee(method: str, subtotal: int) -> int:
    if method == "express":
        return SHIPPING_METHODS["express"]["fee"]
    return 0 if subtotal >= FREE_SHIPPING_THRESHOLD else STANDARD_FEE_BELOW_THRESHOLD


def delivery_window(placed: datetime, method: str) -> tuple[str, str]:
    lo, hi = SHIPPING_METHODS[method]["days"]
    return (placed + timedelta(days=lo)).date().isoformat(), (placed + timedelta(days=hi)).date().isoformat()


# ---------- mã giảm giá ----------
def evaluate_coupon(code: str | None, subtotal: int) -> dict[str, Any] | None:
    """Trả về {code, percent, discount, valid, message}; None nếu không có mã."""
    if not code:
        return None
    row = get_db().execute("SELECT * FROM coupons WHERE code = ?", (code.strip(),)).fetchone()
    base = {"code": code.strip().upper(), "percent": 0, "discount": 0, "valid": False}
    if row is None or not row["is_active"]:
        return {**base, "message": "Mã giảm giá không tồn tại hoặc đã hết hạn."}
    if row["expires_at"] and row["expires_at"] < now_vn():
        return {**base, "message": "Mã giảm giá đã hết hạn."}
    if subtotal < row["min_order"]:
        return {**base, "code": row["code"], "message": f"Đơn hàng cần tối thiểu {row['min_order']:,}₫ để dùng mã này.".replace(",", ".")}
    discount = subtotal * row["percent"] // 100
    if row["max_discount"]:
        discount = min(discount, row["max_discount"])
    return {"code": row["code"], "percent": row["percent"], "discount": discount, "valid": True,
            "message": f"Đã áp dụng {row['code']} · Giảm {row['percent']}%"}


def totals(subtotal: int, coupon: dict | None, method: str = "standard") -> dict[str, Any]:
    discount = coupon["discount"] if coupon and coupon["valid"] else 0
    fee = shipping_fee(method, subtotal)  # miễn phí tính trên tạm tính, trước giảm giá
    return {
        "subtotal": subtotal,
        "discount": discount,
        "shipping_fee": fee,
        "total": subtotal - discount + fee,
        "free_shipping_threshold": FREE_SHIPPING_THRESHOLD,
        "free_shipping_remaining": max(0, FREE_SHIPPING_THRESHOLD - subtotal),
    }


# ---------- sản phẩm ----------
def first_image_sql(alias: str = "p") -> str:
    return (f"(SELECT url FROM product_images i WHERE i.product_id = {alias}.id ORDER BY i.position LIMIT 1)")


def discount_percent(price: int, compare: int | None) -> int | None:
    return round((compare - price) * 100 / compare) if compare else None


PRODUCT_CARD_SELECT = f"""
    SELECT p.id, p.slug, p.sku, p.name, p.category_id, p.price, p.compare_price, p.tone, p.is_new, p.is_featured,
           p.sold_count, p.created_at, c.slug AS category_slug, c.name AS category_name, p.department,
           {first_image_sql()} AS image_url,
           (SELECT COALESCE(SUM(v.stock), 0) FROM variants v WHERE v.product_id = p.id) AS stock,
           (SELECT ROUND(AVG(r.rating), 1) FROM reviews r WHERE r.product_id = p.id) AS rating_avg,
           (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.id) AS rating_count
    FROM products p JOIN categories c ON c.id = p.category_id
"""


def product_cards(rows) -> list[dict[str, Any]]:
    """Chuyển các hàng PRODUCT_CARD_SELECT thành dict thẻ sản phẩm (kèm danh sách màu)."""
    rows = list(rows)
    if not rows:
        return []
    db = get_db()
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    colors: dict[int, list[dict]] = {}
    for r in db.execute(
        f"""SELECT v.product_id, co.slug, co.name, co.hex
            FROM variants v JOIN colors co ON co.id = v.color_id
            WHERE v.product_id IN ({marks}) GROUP BY v.product_id, co.id ORDER BY MIN(v.id)""", ids):
        colors.setdefault(r["product_id"], []).append({"slug": r["slug"], "name": r["name"], "hex": r["hex"]})
    wished: set[int] = set()
    user = current_user()
    if user:
        wished = {r["product_id"] for r in db.execute(
            f"SELECT product_id FROM wishlist WHERE user_id = ? AND product_id IN ({marks})", [user["id"], *ids])}
    out = []
    for r in rows:
        cols = colors.get(r["id"], [])
        out.append({
            "id": r["id"], "slug": r["slug"], "sku": r["sku"], "name": r["name"],
            "price": r["price"], "compare_price": r["compare_price"],
            "discount_percent": discount_percent(r["price"], r["compare_price"]),
            "color": cols[0]["name"] if cols else None, "colors": cols,
            "category": {"slug": r["category_slug"], "name": r["category_name"]},
            "department": r["department"],
            "image": {"url": r["image_url"], "tone": r["tone"]},
            "is_new": bool(r["is_new"]), "in_stock": r["stock"] > 0,
            "rating": {"average": r["rating_avg"], "count": r["rating_count"]},
            "in_wishlist": r["id"] in wished,
        })
    return out


# ---------- giỏ hàng ----------
def _owner_cart(create: bool):
    db = get_db()
    user = current_user()
    if user:
        row = db.execute("SELECT * FROM carts WHERE user_id = ?", (user["id"],)).fetchone()
        if row is None and create:
            cur = db.execute("INSERT INTO carts (user_id) VALUES (?)", (user["id"],))
            row = db.execute("SELECT * FROM carts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row
    token = session.get("cart_token")
    row = db.execute("SELECT * FROM carts WHERE guest_token = ?", (token,)).fetchone() if token else None
    if row is None and create:
        token = secrets.token_urlsafe(24)
        cur = db.execute("INSERT INTO carts (guest_token) VALUES (?)", (token,))
        session["cart_token"] = token
        row = db.execute("SELECT * FROM carts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row


def get_cart(create: bool = False):
    return _owner_cart(create)


def merge_guest_cart(user_id: int) -> None:
    """Gộp giỏ của khách (theo session) vào giỏ của user sau khi đăng nhập/đăng ký."""
    db = get_db()
    token = session.get("cart_token")
    if not token:
        return
    guest = db.execute("SELECT * FROM carts WHERE guest_token = ?", (token,)).fetchone()
    if guest is None:
        return
    mine = db.execute("SELECT * FROM carts WHERE user_id = ?", (user_id,)).fetchone()
    if mine is None:
        db.execute("UPDATE carts SET user_id = ?, guest_token = NULL WHERE id = ?", (user_id, guest["id"]))
    else:
        for it in db.execute("SELECT variant_id, quantity FROM cart_items WHERE cart_id = ?", (guest["id"],)).fetchall():
            db.execute(
                """INSERT INTO cart_items (cart_id, variant_id, quantity) VALUES (?, ?, ?)
                   ON CONFLICT (cart_id, variant_id) DO UPDATE SET quantity = MIN(quantity + excluded.quantity, ?)""",
                (mine["id"], it["variant_id"], it["quantity"], MAX_LINE_QUANTITY))
        if not mine["coupon_code"] and guest["coupon_code"]:
            db.execute("UPDATE carts SET coupon_code = ? WHERE id = ?", (guest["coupon_code"], mine["id"]))
        db.execute("DELETE FROM carts WHERE id = ?", (guest["id"],))
    db.commit()


def cart_lines(cart_id: int) -> list[dict[str, Any]]:
    rows = get_db().execute(
        f"""SELECT ci.id, ci.quantity, v.id AS variant_id, v.size, v.stock, v.sku,
                   co.name AS color, co.slug AS color_slug, co.hex AS color_hex,
                   p.id AS product_id, p.slug, p.name, p.price, p.compare_price, p.tone, p.status,
                   {first_image_sql()} AS image_url
            FROM cart_items ci
            JOIN variants v ON v.id = ci.variant_id JOIN colors co ON co.id = v.color_id
            JOIN products p ON p.id = v.product_id
            WHERE ci.cart_id = ? ORDER BY ci.id""", (cart_id,)).fetchall()
    return [{
        "id": r["id"], "variant_id": r["variant_id"], "quantity": r["quantity"],
        "product": {"id": r["product_id"], "slug": r["slug"], "name": r["name"],
                    "image": {"url": r["image_url"], "tone": r["tone"]}},
        "color": {"slug": r["color_slug"], "name": r["color"], "hex": r["color_hex"]},
        "size": r["size"], "sku": r["sku"],
        "unit_price": r["price"], "compare_price": r["compare_price"],
        "line_total": r["price"] * r["quantity"],
        "stock": r["stock"],
        "available": r["status"] == "active" and r["stock"] >= r["quantity"],
    } for r in rows]


def cart_payload(cart, shipping_method: str = "standard") -> dict[str, Any]:
    lines = cart_lines(cart["id"]) if cart else []
    subtotal = sum(l["line_total"] for l in lines)
    coupon = evaluate_coupon(cart["coupon_code"], subtotal) if cart and cart["coupon_code"] else None
    summary = totals(subtotal, coupon, shipping_method)
    summary.update({"line_count": len(lines), "total_quantity": sum(l["quantity"] for l in lines)})
    return {"items": lines, "coupon": coupon, "summary": summary}


def find_variant(variant_id: int):
    return get_db().execute(
        """SELECT v.*, p.status AS product_status, p.name AS product_name
           FROM variants v JOIN products p ON p.id = v.product_id WHERE v.id = ?""", (variant_id,)).fetchone()


def add_to_cart(cart, variant, quantity: int) -> int:
    """Thêm vào giỏ, trả về số lượng cuối cùng của dòng (đã giới hạn theo tồn kho)."""
    if variant is None or variant["product_status"] != "active":
        raise ApiError("Sản phẩm không tồn tại hoặc đã ngừng bán.", 404, "not_found")
    if variant["stock"] <= 0:
        raise ApiError(f"{variant['product_name']} (size {variant['size']}) đã hết hàng.", 409, "out_of_stock")
    db = get_db()
    row = db.execute("SELECT quantity FROM cart_items WHERE cart_id = ? AND variant_id = ?",
                     (cart["id"], variant["id"])).fetchone()
    wanted = (row["quantity"] if row else 0) + quantity
    final = min(wanted, variant["stock"], MAX_LINE_QUANTITY)
    db.execute(
        """INSERT INTO cart_items (cart_id, variant_id, quantity) VALUES (?, ?, ?)
           ON CONFLICT (cart_id, variant_id) DO UPDATE SET quantity = excluded.quantity""",
        (cart["id"], variant["id"], final))
    db.execute("UPDATE carts SET updated_at = datetime('now') WHERE id = ?", (cart["id"],))
    return final
