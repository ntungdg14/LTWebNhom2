"""Chuyển các hàng SQLite thành JSON trả về cho client."""
from __future__ import annotations

from .helpers import current_user
from .services import compute_totals, estimated_delivery, line_issue, placeholders, shipping_methods, size_key

ORDER_STATUS_LABELS = {
    "pending": "Chờ xác nhận",
    "preparing": "Đang chuẩn bị hàng",
    "shipping": "Đang giao hàng",
    "delivered": "Đã giao hàng",
    "cancelled": "Đã hủy",
}
PAYMENT_STATUS_LABELS = {"unpaid": "Chưa thanh toán", "paid": "Đã thanh toán", "refunded": "Đã hoàn tiền"}


# ------------------------------------------------------------------- user
def user_json(user) -> dict:
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "phone": user["phone"],
        "birthday": user["birthday"],
        "gender": user["gender"],
        "newsletter": bool(user["newsletter"]),
        "role": user["role"],
        "created_at": user["created_at"],
    }


# ---------------------------------------------------------------- sản phẩm
def discount_percent(price: int, compare_price) -> int:
    if not compare_price or compare_price <= price:
        return 0
    return round((compare_price - price) * 100 / compare_price)


def product_cards(db, rows) -> list[dict]:
    """Danh sách thẻ sản phẩm (trang chủ, shop, yêu thích, gợi ý). Gộp truy vấn để tránh N+1."""
    rows = list(rows)
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = placeholders(ids)

    images: dict[int, dict] = {}
    for r in db.execute(
        f"SELECT product_id, url, tone, label FROM product_images WHERE product_id IN ({marks}) "
        "ORDER BY product_id, position, id",
        ids,
    ):
        images.setdefault(r["product_id"], {"url": r["url"], "tone": r["tone"], "label": r["label"]})

    colors: dict[int, list] = {}
    stock: dict[int, int] = {}
    for r in db.execute(
        f"""SELECT v.product_id, c.slug, c.name, c.hex, c.family, SUM(v.stock) AS stock
            FROM variants v JOIN colors c ON c.id = v.color_id
            WHERE v.product_id IN ({marks}) GROUP BY v.product_id, c.id ORDER BY c.id""",
        ids,
    ):
        colors.setdefault(r["product_id"], []).append(
            {"slug": r["slug"], "name": r["name"], "hex": r["hex"], "family": r["family"]}
        )
        stock[r["product_id"]] = stock.get(r["product_id"], 0) + r["stock"]

    ratings = {
        r["product_id"]: (r["avg"], r["n"])
        for r in db.execute(
            f"SELECT product_id, AVG(rating) AS avg, COUNT(*) AS n FROM reviews WHERE product_id IN ({marks}) "
            "GROUP BY product_id",
            ids,
        )
    }

    wished: set[int] = set()
    user = current_user()
    if user is not None:
        wished = {
            r["product_id"]
            for r in db.execute(
                f"SELECT product_id FROM wishlist WHERE user_id = ? AND product_id IN ({marks})", [user["id"], *ids]
            )
        }

    cards = []
    for r in rows:
        avg, count = ratings.get(r["id"], (None, 0))
        cards.append(
            {
                "id": r["id"],
                "slug": r["slug"],
                "sku": r["sku"],
                "name": r["name"],
                "price": r["price"],
                "compare_price": r["compare_price"],
                "discount_percent": discount_percent(r["price"], r["compare_price"]),
                "department": r["department"],
                "category": {"slug": r["category_slug"], "name": r["category_name"]},
                "tone": r["tone"],
                "image": images.get(r["id"], {"url": None, "tone": r["tone"], "label": None}),
                "colors": colors.get(r["id"], []),
                "is_new": bool(r["is_new"]),
                "in_stock": stock.get(r["id"], 0) > 0,
                "rating_avg": round(avg, 1) if avg else None,
                "rating_count": count,
                "in_wishlist": r["id"] in wished,
            }
        )
    return cards


PRODUCT_CARD_SELECT = """
SELECT p.*, c.slug AS category_slug, c.name AS category_name
FROM products p JOIN categories c ON c.id = p.category_id
"""


def review_summary(db, product_id: int) -> dict:
    distribution = {str(star): 0 for star in range(5, 0, -1)}
    total = 0
    weighted = 0
    for r in db.execute("SELECT rating, COUNT(*) AS n FROM reviews WHERE product_id = ? GROUP BY rating", (product_id,)):
        distribution[str(r["rating"])] = r["n"]
        total += r["n"]
        weighted += r["rating"] * r["n"]
    fit = db.execute("SELECT AVG(fit) AS f FROM reviews WHERE product_id = ? AND fit IS NOT NULL", (product_id,)).fetchone()
    return {
        "average": round(weighted / total, 1) if total else None,
        "count": total,
        "distribution": distribution,
        "fit_average": round(fit["f"], 1) if fit["f"] is not None else None,  # 1 chật ... 5 rộng
    }


def review_json(r) -> dict:
    user = current_user()
    return {
        "id": r["id"],
        "is_mine": user is not None and r["user_id"] is not None and r["user_id"] == user["id"],
        "author_name": r["author_name"],
        "city": r["city"],
        "rating": r["rating"],
        "fit": r["fit"],
        "title": r["title"],
        "body": r["body"],
        "body_info": r["body_info"],
        "verified": bool(r["verified"]),
        "created_at": r["created_at"],
    }


def product_detail(db, row) -> dict:
    pid = row["id"]
    images = [
        {"id": i["id"], "url": i["url"], "tone": i["tone"], "label": i["label"], "position": i["position"]}
        for i in db.execute(
            "SELECT id, url, tone, label, position FROM product_images WHERE product_id = ? ORDER BY position, id",
            (pid,),
        )
    ]
    colors: dict[int, dict] = {}
    for v in db.execute(
        """SELECT v.id AS variant_id, v.size, v.sku, v.stock, c.id AS color_id, c.slug, c.name, c.hex, c.family
           FROM variants v JOIN colors c ON c.id = v.color_id WHERE v.product_id = ? ORDER BY c.id""",
        (pid,),
    ):
        color = colors.setdefault(
            v["color_id"],
            {"id": v["color_id"], "slug": v["slug"], "name": v["name"], "hex": v["hex"], "family": v["family"], "sizes": []},
        )
        color["sizes"].append({"variant_id": v["variant_id"], "size": v["size"], "sku": v["sku"], "stock": v["stock"]})
    color_list = list(colors.values())
    all_sizes: set[str] = set()
    for color in color_list:
        color["sizes"].sort(key=lambda s: size_key(s["size"]))
        color["in_stock"] = any(s["stock"] > 0 for s in color["sizes"])
        all_sizes.update(s["size"] for s in color["sizes"])

    return {
        "id": pid,
        "slug": row["slug"],
        "sku": row["sku"],
        "name": row["name"],
        "description": row["description"],
        "price": row["price"],
        "compare_price": row["compare_price"],
        "discount_percent": discount_percent(row["price"], row["compare_price"]),
        "department": row["department"],
        "category": {"slug": row["category_slug"], "name": row["category_name"]},
        "tone": row["tone"],
        "material": row["material"],
        "model_info": row["model_info"],
        "care": row["care"],
        "is_new": bool(row["is_new"]),
        "images": images,
        "colors": color_list,
        "sizes": sorted(all_sizes, key=size_key),
        "in_stock": any(c["in_stock"] for c in color_list),
        "rating": review_summary(db, pid),
    }


# ------------------------------------------------------------------ giỏ hàng
def cart_json(db, cart, rows, method: str = "standard") -> dict:
    items = []
    for r in rows:
        issue = line_issue(r)
        items.append(
            {
                "id": r["item_id"],
                "variant_id": r["variant_id"],
                "quantity": r["quantity"],
                "size": r["size"],
                "sku": r["variant_sku"],
                "stock": r["stock"],
                "price": r["price"],
                "compare_price": r["compare_price"],
                "line_total": r["price"] * r["quantity"],
                "available": issue is None,
                "issue": issue,
                "color": {"slug": r["color_slug"], "name": r["color_name"], "hex": r["color_hex"]},
                "product": {
                    "id": r["product_id"],
                    "slug": r["slug"],
                    "name": r["name"],
                    "image": {"url": r["image_url"], "tone": r["image_tone"] or r["tone"]},
                },
            }
        )
    totals = compute_totals(db, rows, cart["coupon_code"] if cart else None, method)
    return {"items": items, **totals, "has_issues": any(not i["available"] for i in items)}


# ------------------------------------------------------------------- đơn hàng
def order_json(db, order, items=None, *, with_events: bool = True) -> dict:
    if items is None:
        items = db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order["id"],)).fetchall()
    method = order["shipping_method"]
    method_info = shipping_methods().get(method)
    # Đơn đã giao: sản phẩm nào chủ đơn đã đánh giá rồi thì không cho đánh giá nữa.
    reviewed: set[int] = set()
    if order["status"] == "delivered" and order["user_id"] is not None:
        reviewed = {
            r["product_id"]
            for r in db.execute("SELECT product_id FROM reviews WHERE user_id = ?", (order["user_id"],))
        }
    payload = {
        "id": order["id"],
        "code": order["code"],
        "status": order["status"],
        "status_label": ORDER_STATUS_LABELS.get(order["status"], order["status"]),
        "payment_method": order["payment_method"],
        "payment_status": order["payment_status"],
        "payment_status_label": PAYMENT_STATUS_LABELS.get(order["payment_status"]),
        "shipping_method": method,
        "shipping_method_name": method_info["name"] if method_info else method,
        "contact": {"full_name": order["full_name"], "phone": order["phone"], "email": order["email"]},
        "address": {
            "province": order["province"],
            "ward": order["ward"],
            "street": order["street"],
            "full": f"{order['street']}, {order['ward']}, {order['province']}",
        },
        "note": order["note"],
        "subtotal": order["subtotal"],
        "discount": order["discount"],
        "coupon_code": order["coupon_code"],
        "shipping_fee": order["shipping_fee"],
        "total": order["total"],
        "vat_invoice": bool(order["vat_invoice"]),
        "item_count": sum(i["quantity"] for i in items),
        "line_count": len(items),
        "can_cancel": order["status"] in ("pending", "preparing"),
        "created_at": order["created_at"],
        "delivered_at": order["delivered_at"],
        "items": [
            {
                "id": i["id"],
                "product_id": i["product_id"],
                "product_slug": i["product_slug"],
                "variant_id": i["variant_id"],
                "name": i["name"],
                "color": i["color"],
                "size": i["size"],
                "tone": i["tone"],
                "price": i["price"],
                "compare_price": i["compare_price"],
                "quantity": i["quantity"],
                "line_total": i["price"] * i["quantity"],
                "reviewed": i["product_id"] in reviewed,
                "can_review": (
                    order["status"] == "delivered"
                    and order["user_id"] is not None
                    and i["product_id"] is not None
                    and i["product_id"] not in reviewed
                ),
            }
            for i in items
        ],
    }
    if method_info and order["status"] in ("pending", "preparing", "shipping"):
        payload["estimated_delivery"] = _estimate_from(order["created_at"], method)
    if with_events:
        payload["events"] = [
            {
                "status": e["status"],
                "label": ORDER_STATUS_LABELS.get(e["status"], e["status"]),
                "created_at": e["created_at"],
            }
            for e in db.execute("SELECT * FROM order_events WHERE order_id = ? ORDER BY id", (order["id"],))
        ]
    return payload


def _estimate_from(created_at: str, method: str) -> dict:
    """Ngày giao dự kiến tính từ ngày đặt hàng (không phải từ hôm nay)."""
    from datetime import date

    from .services import add_business_days

    low, high = shipping_methods()[method]["days"]
    try:
        start = date.fromisoformat(created_at[:10])
    except ValueError:
        return estimated_delivery(method)
    return {"from": add_business_days(start, low).isoformat(), "to": add_business_days(start, high).isoformat()}


def orders_json(db, orders) -> list[dict]:
    """Nhiều đơn cùng lúc (danh sách lịch sử): nạp dòng sản phẩm bằng một truy vấn."""
    orders = list(orders)
    if not orders:
        return []
    ids = [o["id"] for o in orders]
    by_order: dict[int, list] = {}
    for i in db.execute(f"SELECT * FROM order_items WHERE order_id IN ({placeholders(ids)}) ORDER BY id", ids):
        by_order.setdefault(i["order_id"], []).append(i)
    return [order_json(db, o, by_order.get(o["id"], []), with_events=False) for o in orders]


def address_json(a) -> dict:
    return {
        "id": a["id"],
        "label": a["label"],
        "full_name": a["full_name"],
        "phone": a["phone"],
        "province": a["province"],
        "ward": a["ward"],
        "street": a["street"],
        "is_default": bool(a["is_default"]),
    }
