"""API đơn hàng: danh sách (trang 'Đơn hàng của tôi'), chi tiết, hủy đơn, mua lại."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import jsonify, request, session

from ...db import get_db
from . import api_bp
from .service import (CANCELLABLE, ORDER_STATUS_LABELS, PAYMENT_METHODS, PAYMENT_STATUS_LABELS, SHIPPING_METHODS,
                      add_to_cart, delivery_window, find_variant, get_cart, RETURN_DAYS)
from .utils import ApiError, current_user, iso, login_required, now_vn, page_meta, paginate_args, to_int

TABS = {
    "all": None,
    "processing": ("pending", "preparing", "shipping"),
    "delivered": ("delivered",),
    "cancelled": ("cancelled",),
}
RANGES = {"3m": 3, "6m": 6, "12m": 12}  # tháng gần nhất; mặc định (all) = không giới hạn
STEPS = [("pending", "Đã đặt hàng"), ("preparing", "Đang chuẩn bị"), ("shipping", "Đang giao hàng"), ("delivered", "Đã giao hàng")]


def order_dict(order, *, detail: bool = True) -> dict[str, Any]:
    db = get_db()
    items = db.execute(
        """SELECT oi.*, (SELECT url FROM product_images i WHERE i.product_id = oi.product_id ORDER BY i.position LIMIT 1) AS image_url
           FROM order_items oi WHERE oi.order_id = ? ORDER BY oi.id""", (order["id"],)).fetchall()
    lines = [{
        "product": {"id": r["product_id"], "slug": r["product_slug"], "name": r["name"],
                    "image": {"url": r["image_url"], "tone": r["tone"]}},
        "variant_id": r["variant_id"], "color": r["color"], "size": r["size"],
        "unit_price": r["price"], "compare_price": r["compare_price"], "quantity": r["quantity"],
        "line_total": r["price"] * r["quantity"],
    } for r in items]
    placed = datetime.strptime(order["created_at"], "%Y-%m-%d %H:%M:%S")
    eta_from, eta_to = delivery_window(placed, order["shipping_method"])
    ship = SHIPPING_METHODS[order["shipping_method"]]
    pay = PAYMENT_METHODS[order["payment_method"]]
    status = order["status"]
    out: dict[str, Any] = {
        "code": order["code"],
        "status": status,
        "status_label": ORDER_STATUS_LABELS[status],
        "placed_at": iso(order["created_at"]),
        "line_count": len(lines),
        "total_quantity": sum(l["quantity"] for l in lines),
        "total": order["total"],
        "items": lines,
        "shipping": {"method": order["shipping_method"], "label": ship["label"], "fee": order["shipping_fee"],
                     "estimated_from": eta_from, "estimated_to": eta_to},
        "payment": {"method": order["payment_method"], "label": pay["label"], "status": order["payment_status"],
                    "status_label": PAYMENT_STATUS_LABELS[order["payment_status"]],
                    "amount_due": order["total"] if order["payment_status"] == "unpaid" and status != "cancelled" else 0},
        "delivered_at": iso(order["delivered_at"]),
        "can_cancel": status in CANCELLABLE,
        "can_review": status == "delivered",
        "can_reorder": status in ("delivered", "cancelled"),
    }
    if not detail:
        return out
    events = {e["status"]: e["created_at"] for e in db.execute(
        "SELECT status, created_at FROM order_events WHERE order_id = ? ORDER BY id", (order["id"],))}
    if status == "cancelled":
        timeline = [{"key": "pending", "label": "Đã đặt hàng", "at": iso(events.get("pending")), "state": "done"},
                    {"key": "cancelled", "label": "Đã hủy", "at": iso(events.get("cancelled")), "state": "current"}]
    else:
        idx = [k for k, _ in STEPS].index(status)
        timeline = [{"key": k, "label": label, "at": iso(events.get(k)),
                     "state": "done" if i < idx else "current" if i == idx else "upcoming",
                     **({"estimated_from": eta_from, "estimated_to": eta_to} if k == "delivered" and k not in events else {})}
                    for i, (k, label) in enumerate(STEPS)]
    out.update({
        "contact": {"full_name": order["full_name"], "phone": order["phone"], "email": order["email"]},
        "address": {"province": order["province"], "ward": order["ward"], "street": order["street"],
                    "full_address": f"{order['street']}, {order['ward']}, {order['province']}"},
        "note": order["note"],
        "vat_invoice": bool(order["vat_invoice"]),
        "summary": {"subtotal": order["subtotal"], "discount": order["discount"], "coupon_code": order["coupon_code"],
                    "shipping_fee": order["shipping_fee"], "total": order["total"]},
        "timeline": timeline,
        "return_days": RETURN_DAYS,
    })
    return out


def _load_order(code: str):
    """Chủ đơn mới xem được; khách vãng lai xem được đơn vừa đặt trong phiên hiện tại."""
    order = get_db().execute("SELECT * FROM orders WHERE code = ?", (code.upper().lstrip("#"),)).fetchone()
    user = current_user()
    allowed = order is not None and (
        (user is not None and order["user_id"] == user["id"]) or order["code"] in session.get("guest_orders", []))
    if not allowed:
        raise ApiError("Không tìm thấy đơn hàng.", 404, "not_found")
    return order


@api_bp.get("/account/orders")
@login_required
def list_orders():
    user, db = current_user(), get_db()
    tab = request.args.get("tab", "all")
    if tab not in TABS:
        raise ApiError("tab phải là all, processing, delivered hoặc cancelled.", 400, "bad_request")
    where, args = ["o.user_id = ?"], [user["id"]]
    rng = request.args.get("range", "all")
    if rng in RANGES:
        where.append("o.created_at >= datetime('now', 'localtime', ?)")
        args.append(f"-{RANGES[rng]} months")
    q = (request.args.get("q") or "").strip().lstrip("#")
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(o.code LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.id "
                     "AND oi.name LIKE ? ESCAPE '\\'))")
        args += [like, like]
    base = " AND ".join(where)

    counts = {k: 0 for k in TABS}
    for r in db.execute(f"SELECT o.status, COUNT(*) AS n FROM orders o WHERE {base} GROUP BY o.status", args):
        counts["all"] += r["n"]
        for k, statuses in TABS.items():
            if statuses and r["status"] in statuses:
                counts[k] += r["n"]

    tab_sql, tab_args = "", []
    if TABS[tab]:
        tab_sql = f" AND o.status IN ({','.join('?' * len(TABS[tab]))})"
        tab_args = list(TABS[tab])
    page, per_page = paginate_args(default_per_page=3, max_per_page=50)
    rows = db.execute(
        f"SELECT o.* FROM orders o WHERE {base}{tab_sql} ORDER BY o.created_at DESC, o.id DESC LIMIT ? OFFSET ?",
        [*args, *tab_args, per_page, (page - 1) * per_page]).fetchall()
    return jsonify({"items": [order_dict(r, detail=False) for r in rows], "counts": counts, "tab": tab,
                    "pagination": page_meta(page, per_page, counts[tab])})


@api_bp.get("/orders/<code>")
def get_order(code: str):
    return jsonify(order_dict(_load_order(code)))


def restore_stock(order_id: int) -> None:
    db = get_db()
    for it in db.execute("SELECT variant_id, quantity FROM order_items WHERE order_id = ? AND variant_id IS NOT NULL", (order_id,)):
        db.execute("UPDATE variants SET stock = stock + ? WHERE id = ?", (it["quantity"], it["variant_id"]))
        db.execute("UPDATE products SET sold_count = MAX(0, sold_count - ?) WHERE id = "
                   "(SELECT product_id FROM variants WHERE id = ?)", (it["quantity"], it["variant_id"]))


@api_bp.post("/orders/<code>/cancel")
def cancel_order(code: str):
    order = _load_order(code)
    if order["status"] not in CANCELLABLE:
        raise ApiError("Đơn hàng đã được bàn giao cho vận chuyển nên không thể hủy.", 409, "not_cancellable")
    db = get_db()
    restore_stock(order["id"])
    db.execute("UPDATE orders SET status = 'cancelled', payment_status = CASE WHEN payment_status = 'paid' "
               "THEN 'refunded' ELSE payment_status END WHERE id = ?", (order["id"],))
    db.execute("INSERT INTO order_events (order_id, status, created_at) VALUES (?, 'cancelled', ?)", (order["id"], now_vn()))
    db.commit()
    return jsonify(order_dict(_load_order(code)))


@api_bp.post("/orders/<code>/reorder")
@login_required
def reorder(code: str):
    """'Mua lại': thêm các sản phẩm của đơn vào giỏ hàng (bỏ qua món đã hết hàng)."""
    order = _load_order(code)
    cart = get_cart(create=True)
    added, skipped = [], []
    for it in get_db().execute("SELECT variant_id, name, size, quantity FROM order_items WHERE order_id = ?", (order["id"],)):
        variant = find_variant(it["variant_id"]) if it["variant_id"] else None
        try:
            add_to_cart(cart, variant, it["quantity"])
            added.append(it["name"])
        except ApiError:
            skipped.append({"name": it["name"], "size": it["size"]})
    get_db().commit()
    from .service import cart_payload
    return jsonify({"added": added, "skipped": skipped, "cart": cart_payload(cart)})
