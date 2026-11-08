"""Truy vấn dữ liệu thật cho các trang quản trị: danh mục, sản phẩm, đơn hàng, khách hàng."""
from __future__ import annotations

import math
import re

from flask import current_app, request, url_for

from ...common.helpers import as_int
from ...db import unaccent

PER_PAGE = 10

ORDER_STATUS = {  # trạng thái -> (nhãn, class badge)
    "pending": ("Chờ xác nhận", "badge-danger"),
    "preparing": ("Đang xử lý", "badge-warn"),
    "shipping": ("Đang giao", "badge-warn"),
    "delivered": ("Hoàn thành", "badge-ok"),
    "cancelled": ("Đã hủy", "badge-danger"),
}
PAYMENT_STATUS = {"unpaid": "Chưa thu tiền", "paid": "Đã thanh toán", "refunded": "Đã hoàn tiền"}
PRODUCT_STATUS = {"active": ("Đang bán", "badge-ok"), "draft": ("Bản nháp", "badge-warn"), "archived": ("Đã lưu trữ", "badge-danger")}
LOW_STOCK = 10


# ------------------------------------------------------------------ chung
def page_number() -> int:
    return max(as_int(request.args.get("page")) or 1, 1)


def link(endpoint: str, **changes) -> str:
    """URL của trang hiện tại, giữ bộ lọc đang dùng và đổi các tham số trong ``changes``."""
    args = {k: v for k, v in request.args.items() if k != "page"}
    args.update(changes)
    return url_for(endpoint, **{k: v for k, v in args.items() if v not in (None, "", "all")})


def pager(endpoint: str, total: int, page: int) -> dict:
    pages = max(math.ceil(total / PER_PAGE), 1)
    page = min(page, pages)

    def url(n):
        args = {k: v for k, v in request.args.items() if k != "page"}
        if n > 1:
            args["page"] = n
        return url_for(endpoint, **args)

    return {
        "page": page, "pages": pages, "total": total, "show": pages > 1,
        "items": [(n, url(n), n == page) for n in range(1, pages + 1)],
        "next": url(page + 1) if page < pages else None,
    }


def like(text: str) -> str:
    return "%" + unaccent(text.strip()).replace("%", "").replace("_", "") + "%"


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return ((parts[0][0] + parts[-1][0]) if len(parts) > 1 else name[:2]).upper() if parts else "?"


# --------------------------------------------------------------- danh mục
def categories(db) -> dict:
    q = request.args.get("q", "").strip()
    where, params = "", []
    if q:
        where, params = "WHERE unaccent(c.name) LIKE ? OR c.slug LIKE ?", [like(q), like(q)]
    rows = db.execute(
        f"""SELECT c.id, c.name, c.slug, c.position, COUNT(p.id) AS product_count
            FROM categories c LEFT JOIN products p ON p.category_id = c.id
            {where} GROUP BY c.id ORDER BY c.position, c.id""",
        params,
    ).fetchall()
    return {"categories": rows, "q": q}


# ---------------------------------------------------------------- sản phẩm
def products(db) -> dict:
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    stock = request.args.get("stock", "all")
    category = as_int(request.args.get("category"))
    where, params, having = ["1 = 1"], [], []
    if status in PRODUCT_STATUS:
        where.append("p.status = ?"); params.append(status)
    else:
        status = "all"
    if category:
        where.append("p.category_id = ?"); params.append(category)
    if q:
        where.append("(unaccent(p.name) LIKE ? OR p.sku LIKE ?)"); params += [like(q), like(q).upper()]
    having_sql = {"in": "stock > 0", "low": f"stock BETWEEN 1 AND {LOW_STOCK - 1}", "out": "stock = 0"}.get(stock)
    if having_sql is None:
        stock = "all"
    base = f"""
        SELECT p.*, c.name AS category_name, COALESCE(SUM(v.stock), 0) AS stock,
               (SELECT url  FROM product_images i WHERE i.product_id = p.id ORDER BY i.position, i.id LIMIT 1) AS image_url,
               (SELECT tone FROM product_images i WHERE i.product_id = p.id ORDER BY i.position, i.id LIMIT 1) AS image_tone,
               (SELECT group_concat(name, ', ') FROM (SELECT DISTINCT col.name AS name FROM variants v2
                    JOIN colors col ON col.id = v2.color_id WHERE v2.product_id = p.id)) AS colors
        FROM products p JOIN categories c ON c.id = p.category_id LEFT JOIN variants v ON v.product_id = p.id
        WHERE {' AND '.join(where)} GROUP BY p.id {'HAVING ' + having_sql if having_sql else ''}"""
    total = db.execute(f"SELECT COUNT(*) FROM ({base})", params).fetchone()[0]
    pg = pager("admin.products", total, page_number())
    rows = db.execute(base + " ORDER BY p.created_at DESC, p.id DESC LIMIT ? OFFSET ?",
                      [*params, PER_PAGE, (pg["page"] - 1) * PER_PAGE]).fetchall()
    stats = db.execute(
        f"""SELECT COUNT(*) AS total,
                   SUM(status = 'active') AS active, SUM(status = 'draft') AS draft,
                   SUM(status = 'active' AND stock > 0 AND stock < {LOW_STOCK}) AS low
            FROM (SELECT p.status, COALESCE(SUM(v.stock), 0) AS stock FROM products p
                  LEFT JOIN variants v ON v.product_id = p.id GROUP BY p.id)"""
    ).fetchone()
    return {
        "products": rows, "pager": pg, "stats": stats, "q": q, "status": status, "stock": stock, "category": category,
        "category_options": db.execute("SELECT id, name FROM categories ORDER BY position, id").fetchall(),
        "category_count": db.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        "product_status": PRODUCT_STATUS, "low_stock": LOW_STOCK,
    }


# ---------------------------------------------------------------- đơn hàng
def orders(db) -> dict:
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    payment = request.args.get("payment", "all")
    shipping = request.args.get("shipping", "all")
    where, params = ["1 = 1"], []
    if status in ORDER_STATUS:
        where.append("status = ?"); params.append(status)
    else:
        status = "all"
    if payment in PAYMENT_STATUS:
        where.append("payment_status = ?"); params.append(payment)
    else:
        payment = "all"
    if shipping in current_app.config["SHIPPING_METHODS"]:
        where.append("shipping_method = ?"); params.append(shipping)
    else:
        shipping = "all"
    if q:
        where.append("(code LIKE ? OR unaccent(full_name) LIKE ? OR phone LIKE ?)")
        params += ["%" + q.upper().lstrip("#") + "%", like(q), "%" + q + "%"]
    cond = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) FROM orders WHERE {cond}", params).fetchone()[0]
    pg = pager("admin.orders", total, page_number())
    rows = db.execute(
        f"SELECT * FROM orders WHERE {cond} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, PER_PAGE, (pg["page"] - 1) * PER_PAGE],
    ).fetchall()
    counts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status")}
    week = db.execute("SELECT COUNT(*) FROM orders WHERE created_at >= datetime('now', 'localtime', '-7 days')").fetchone()[0]
    return {
        "orders": rows, "pager": pg, "q": q, "status": status, "payment": payment, "shipping": shipping,
        "counts": counts, "all_count": sum(counts.values()), "week": week,
        "order_status": ORDER_STATUS, "payment_status": PAYMENT_STATUS,
        "shipping_methods": current_app.config["SHIPPING_METHODS"],
    }


def order_detail(db, code: str) -> dict | None:
    order = db.execute("SELECT * FROM orders WHERE code = ?", (code.upper().lstrip("#"),)).fetchone()
    if order is None:
        return None
    items = db.execute(
        """SELECT oi.*, (SELECT url FROM product_images i WHERE i.product_id = oi.product_id ORDER BY i.position, i.id LIMIT 1) AS image_url,
                  v.sku AS variant_sku
           FROM order_items oi LEFT JOIN variants v ON v.id = oi.variant_id WHERE oi.order_id = ? ORDER BY oi.id""",
        (order["id"],),
    ).fetchall()
    events = db.execute("SELECT status, created_at FROM order_events WHERE order_id = ? ORDER BY created_at, id", (order["id"],)).fetchall()
    customer, stats = None, None
    if order["user_id"]:
        customer = db.execute("SELECT * FROM users WHERE id = ?", (order["user_id"],)).fetchone()
        stats = db.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN status != 'cancelled' THEN total END), 0) AS spent FROM orders WHERE user_id = ?",
            (order["user_id"],),
        ).fetchone()
    methods = current_app.config["SHIPPING_METHODS"]
    return {
        "order": order, "items": items, "events": events, "customer": customer, "customer_stats": stats,
        "item_count": sum(i["quantity"] for i in items),
        "order_status": ORDER_STATUS, "payment_status": PAYMENT_STATUS,
        "shipping_name": methods.get(order["shipping_method"], {}).get("name", order["shipping_method"]),
        "payment_name": current_app.config["PAYMENT_METHODS"].get(order["payment_method"], order["payment_method"]),
    }


# --------------------------------------------------------------- khách hàng
GROUPS = {  # nhóm -> (nhãn, điều kiện HAVING)
    "new": ("Khách mới", "COUNT(o.id) < 2"),
    "returning": ("Quay lại", "COUNT(o.id) BETWEEN 2 AND 3"),
    "loyal": ("Thân thiết", "COUNT(o.id) >= 4"),
}


def group_of(order_count: int) -> str:
    return GROUPS["loyal" if order_count >= 4 else "returning" if order_count >= 2 else "new"][0]


def customer_code(user_id: int) -> str:
    return f"KH{user_id:05d}"


USERS_SQL = """
    SELECT u.id, u.full_name, u.email, u.phone, u.created_at, COUNT(o.id) AS order_count,
           COALESCE(SUM(CASE WHEN o.status != 'cancelled' THEN o.total END), 0) AS spent, MAX(o.created_at) AS last_order
    FROM users u LEFT JOIN orders o ON o.user_id = u.id
    WHERE u.role = 'customer' {search} GROUP BY u.id {having}"""


def users(db) -> dict:
    q = request.args.get("q", "").strip()
    group = request.args.get("group", "all")
    search, params = "", []
    if q:
        search = "AND (unaccent(u.full_name) LIKE ? OR u.email LIKE ? OR COALESCE(u.phone, '') LIKE ?)"
        params = [like(q), "%" + q.lower() + "%", "%" + q.replace(" ", "") + "%"]
    having = "HAVING " + GROUPS[group][1] if group in GROUPS else ""
    if group not in GROUPS:
        group = "all"
    sql = USERS_SQL.format(search=search, having=having)
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
    pg = pager("admin.users", total, page_number())
    rows = db.execute(sql + " ORDER BY u.created_at DESC, u.id DESC LIMIT ? OFFSET ?", [*params, PER_PAGE, (pg["page"] - 1) * PER_PAGE]).fetchall()
    summary = db.execute(
        f"""SELECT COUNT(*) AS total, SUM(order_count < 2) AS new, SUM(order_count BETWEEN 2 AND 3) AS "returning",
                   SUM(order_count >= 4) AS loyal,
                   SUM(created_at >= datetime('now', 'localtime', '-7 days')) AS week
            FROM ({USERS_SQL.format(search='', having='')})"""
    ).fetchone()
    return {
        "customers": [{**dict(r), "code": customer_code(r["id"]), "group": group_of(r["order_count"]), "initials": initials(r["full_name"])} for r in rows],
        "pager": pg, "q": q, "group": group, "summary": summary, "groups": GROUPS,
    }


def user_detail(db, customer_id: str) -> dict | None:
    match = re.fullmatch(r"(?:KH)?(\d+)", customer_id.upper())
    if not match:
        return None
    user = db.execute("SELECT * FROM users WHERE id = ? AND role = 'customer'", (int(match.group(1)),)).fetchone()
    if user is None:
        return None
    stats = db.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN status != 'cancelled' THEN total END), 0) AS spent,
                  SUM(status IN ('pending', 'preparing', 'shipping')) AS open_orders FROM orders WHERE user_id = ?""",
        (user["id"],),
    ).fetchone()
    recent = db.execute("SELECT code, total, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 5", (user["id"],)).fetchall()
    address = db.execute("SELECT * FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id DESC LIMIT 1", (user["id"],)).fetchone()
    avg_all = db.execute("SELECT COALESCE(AVG(total), 0) FROM orders WHERE status != 'cancelled'").fetchone()[0]
    n_valid = db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status != 'cancelled'", (user["id"],)).fetchone()[0]
    return {
        "user": user, "code": customer_code(user["id"]), "stats": stats, "recent": recent, "address": address,
        "group": group_of(stats["n"]), "avg": stats["spent"] // n_valid if n_valid else 0, "avg_all": int(avg_all),
        "order_status": ORDER_STATUS,
    }
