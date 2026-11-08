"""Logic nghiệp vụ dùng chung: giỏ hàng, mã giảm giá, phí vận chuyển, ngày giao dự kiến."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from flask import current_app

from .helpers import ApiError, current_user

SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL"]


def size_key(size: str):
    if size.upper() in SIZE_ORDER:
        return (0, SIZE_ORDER.index(size.upper()), size)
    if size.isdigit():
        return (1, int(size), size)
    return (2, 0, size)


def vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + "₫"


def placeholders(values) -> str:
    return ",".join("?" for _ in values)


# --------------------------------------------------------------- vận chuyển
def add_business_days(start: date, days: int) -> date:
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def shipping_methods() -> dict:
    return current_app.config["SHIPPING_METHODS"]


def shipping_fee(method: str, subtotal: int) -> int:
    info = shipping_methods()[method]
    free_from = info.get("free_from")
    if free_from is not None and subtotal >= free_from:
        return 0
    return info["fee"]


def estimated_delivery(method: str) -> dict:
    low, high = shipping_methods()[method]["days"]
    today = date.today()
    return {
        "from": add_business_days(today, low).isoformat(),
        "to": add_business_days(today, high).isoformat(),
    }


# ------------------------------------------------------------- mã giảm giá
def evaluate_coupon(db, code: str, subtotal: int):
    """Trả về (coupon_dict | None, thông_báo_lỗi | None)."""
    row = db.execute("SELECT * FROM coupons WHERE code = ?", (code.strip(),)).fetchone()
    if row is None or not row["is_active"]:
        return None, "Mã giảm giá không tồn tại hoặc đã ngừng áp dụng."
    expires = row["expires_at"]
    if expires:
        now = datetime.now(timezone.utc)
        if len(expires) <= 10:  # chỉ có ngày -> hết hạn cuối ngày đó
            expired = expires < now.strftime("%Y-%m-%d")
        else:
            expired = expires < now.strftime("%Y-%m-%d %H:%M:%S")
        if expired:
            return None, "Mã giảm giá đã hết hạn."
    if subtotal < row["min_order"]:
        return None, f"Đơn hàng tối thiểu {vnd(row['min_order'])} để dùng mã này."
    discount = subtotal * row["percent"] // 100
    if row["max_discount"] is not None:
        discount = min(discount, row["max_discount"])
    return {
        "code": row["code"],
        "percent": row["percent"],
        "min_order": row["min_order"],
        "max_discount": row["max_discount"],
        "discount": discount,
    }, None


# ------------------------------------------------------------------ giỏ hàng
def find_cart(db, create: bool = False):
    """Giỏ hàng của người dùng đang đăng nhập (luôn thuộc user_id; không còn giỏ khách)."""
    user = current_user()
    if user is None:
        raise ApiError("Bạn cần đăng nhập để thực hiện thao tác này.", 401, "unauthorized")
    row = db.execute("SELECT * FROM carts WHERE user_id = ?", (user["id"],)).fetchone()
    if row is not None or not create:
        return row
    cur = db.execute("INSERT INTO carts (user_id) VALUES (?)", (user["id"],))
    return db.execute("SELECT * FROM carts WHERE id = ?", (cur.lastrowid,)).fetchone()


def touch_cart(db, cart_id: int) -> None:
    db.execute("UPDATE carts SET updated_at = datetime('now') WHERE id = ?", (cart_id,))


CART_ITEM_SQL = """
SELECT ci.id AS item_id, ci.quantity,
       v.id AS variant_id, v.size, v.sku AS variant_sku, v.stock,
       p.id AS product_id, p.slug, p.name, p.price, p.compare_price, p.tone, p.status,
       c.name AS color_name, c.slug AS color_slug, c.hex AS color_hex,
       (SELECT url  FROM product_images i WHERE i.product_id = p.id ORDER BY i.position, i.id LIMIT 1) AS image_url,
       (SELECT tone FROM product_images i WHERE i.product_id = p.id ORDER BY i.position, i.id LIMIT 1) AS image_tone
FROM cart_items ci
JOIN variants v ON v.id = ci.variant_id
JOIN products p ON p.id = v.product_id
JOIN colors   c ON c.id = v.color_id
WHERE ci.cart_id = ?
ORDER BY ci.id
"""


def load_cart_rows(db, cart_id: int):
    return db.execute(CART_ITEM_SQL, (cart_id,)).fetchall()


def line_issue(row) -> str | None:
    if row["status"] != "active":
        return "Sản phẩm không còn được bán."
    if row["stock"] <= 0:
        return "Sản phẩm đã hết hàng."
    if row["quantity"] > row["stock"]:
        return f"Chỉ còn {row['stock']} sản phẩm."
    return None


def compute_totals(db, rows, coupon_code: str | None, method: str = "standard") -> dict:
    subtotal = sum(r["price"] * r["quantity"] for r in rows)
    coupon = None
    coupon_error = None
    discount = 0
    if coupon_code:
        coupon, coupon_error = evaluate_coupon(db, coupon_code, subtotal)
        if coupon:
            discount = coupon["discount"]
    fee = shipping_fee(method, subtotal) if rows else 0
    threshold = current_app.config["FREE_SHIPPING_THRESHOLD"]
    return {
        "item_count": sum(r["quantity"] for r in rows),
        "line_count": len(rows),
        "subtotal": subtotal,
        "discount": discount,
        "coupon": coupon,
        "coupon_error": coupon_error if coupon_code else None,
        "shipping_method": method,
        "shipping_fee": fee,
        "total": subtotal - discount + fee,
        "free_shipping_threshold": threshold,
        "free_shipping_remaining": max(threshold - subtotal, 0) if rows else threshold,
    }


def set_item_quantity(db, cart_id: int, variant_id: int, quantity: int, *, add: bool = False) -> None:
    """Thêm/đổi số lượng một biến thể, kiểm tra tồn kho. Ném ApiError nếu không hợp lệ."""
    variant = db.execute(
        "SELECT v.id, v.stock, p.status FROM variants v JOIN products p ON p.id = v.product_id WHERE v.id = ?",
        (variant_id,),
    ).fetchone()
    if variant is None or variant["status"] != "active":
        raise ApiError("Sản phẩm không tồn tại hoặc không còn được bán.", 404, "variant_not_found")
    existing = db.execute(
        "SELECT id, quantity FROM cart_items WHERE cart_id = ? AND variant_id = ?", (cart_id, variant_id)
    ).fetchone()
    target = quantity + (existing["quantity"] if (existing and add) else 0)
    if target > variant["stock"]:
        message = "Sản phẩm đã hết hàng." if variant["stock"] == 0 else f"Chỉ còn {variant['stock']} sản phẩm trong kho."
        raise ApiError(message, 409, "out_of_stock")
    if existing:
        db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (target, existing["id"]))
    else:
        db.execute(
            "INSERT INTO cart_items (cart_id, variant_id, quantity) VALUES (?, ?, ?)", (cart_id, variant_id, target)
        )
    touch_cart(db, cart_id)


# --------------------------------------------------------------- địa chỉ
def make_default_address(db, user_id: int, fields: dict) -> int:
    """Đặt một địa chỉ làm mặc định; tái sử dụng bản ghi trùng nội dung nếu đã có. Trả về id."""
    keys = ("full_name", "phone", "province", "ward", "street")
    existing = db.execute(
        "SELECT id FROM addresses WHERE user_id = ? AND full_name = ? AND phone = ? AND province = ? "
        "AND ward = ? AND street = ?",
        (user_id, *[fields[k] for k in keys]),
    ).fetchone()
    db.execute("UPDATE addresses SET is_default = 0 WHERE user_id = ?", (user_id,))
    if existing:
        db.execute("UPDATE addresses SET is_default = 1 WHERE id = ?", (existing["id"],))
        return existing["id"]
    cur = db.execute(
        "INSERT INTO addresses (user_id, label, full_name, phone, province, ward, street, is_default) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (user_id, fields.get("label"), *[fields[k] for k in keys]),
    )
    return cur.lastrowid
