"""Khu vực tài khoản (tất cả đều cần đăng nhập).

    GET/PATCH  /api/account/profile                  hồ sơ cá nhân (PATCH: chỉ gửi trường cần đổi)
    POST       /api/account/password                 đổi mật khẩu (đăng xuất các thiết bị khác)
    POST       /api/account/logout-all               đăng xuất mọi thiết bị
    GET/POST   /api/account/addresses                sổ địa chỉ
    PATCH/DELETE /api/account/addresses/<id>         sửa / xóa địa chỉ
    POST       /api/account/addresses/<id>/default   đặt làm mặc định
    GET/POST   /api/account/wishlist                 yêu thích (POST {product_id}, idempotent)
    DELETE     /api/account/wishlist/<product_id>    bỏ yêu thích
    GET        /api/account/orders                   lịch sử đơn (?status=all|processing|delivered|cancelled&q=&page=)
    POST       /api/account/orders/<code>/cancel     hủy đơn (khi pending/preparing)
    POST       /api/account/orders/<code>/reorder    "Mua lại": thêm các món còn hàng vào giỏ
    GET        /api/account/reviews                  đánh giá của tôi (items) + sản phẩm đã nhận nhưng chưa đánh giá (pending)

Chi tiết một đơn: GET /api/orders/<code> (checkout.py).
"""
from __future__ import annotations

import math
import sqlite3

from flask import jsonify, request, g
from flask.views import MethodView
from werkzeug.security import check_password_hash, generate_password_hash

from ...db import get_db, transaction
from . import account_api_bp as api_bp
from ..store.cart_api import respond_cart
from ...common.helpers import ApiError, Fields, arg_int, current_user, json_body, login_required, login_user
from ...common.serializers import (
    PRODUCT_CARD_SELECT,
    address_json,
    order_json,
    orders_json,
    product_cards,
    review_json,
    user_json,
)
from ...common.services import find_cart, make_default_address, placeholders, set_item_quantity

STATUS_GROUPS = {
    "all": None,
    "processing": ("pending", "preparing", "shipping"),
    "delivered": ("delivered",),
    "cancelled": ("cancelled",),
}


# ------------------------------------------------------------------- hồ sơ
class ProfileView(MethodView):
    decorators = [login_required]

    def get(self):
        return jsonify(user=user_json(current_user()))

    def patch(self):
        db = get_db()
        user = current_user()
        data = json_body()
        f = Fields(data)
        changes: dict = {}
        if "full_name" in data:
            changes["full_name"] = f.text("full_name", "Họ và tên", max_len=100)
        if "email" in data:
            changes["email"] = f.email()
        if "phone" in data:
            changes["phone"] = f.phone(required=False)
        if "birthday" in data:
            changes["birthday"] = f.birthday()
        if "gender" in data:
            changes["gender"] = f.choice("gender", "Giới tính", ("nam", "nu", "khac"))
        if "newsletter" in data:
            changes["newsletter"] = int(f.boolean("newsletter"))
        f.done()
        if not changes:
            raise ApiError("Không có thông tin nào để cập nhật.", 400, "empty_update")
        assignments = ", ".join(f"{col} = ?" for col in changes)
        try:
            db.execute(f"UPDATE users SET {assignments} WHERE id = ?", [*changes.values(), user["id"]])
        except sqlite3.IntegrityError:
            raise ApiError("Email này đã được sử dụng.", 409, "email_taken", {"email": "Email này đã được sử dụng."})
        return jsonify(user=user_json(db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()))


@api_bp.post("/account/password")
@login_required
def change_password():
    db = get_db()
    user = current_user()
    data = json_body()
    f = Fields(data)
    current = data.get("current_password")
    if not isinstance(current, str) or not current:
        f.fail("current_password", "Mật khẩu hiện tại là bắt buộc.")
    new = f.password("new_password", "Mật khẩu mới")
    if "confirm_password" in data and data["confirm_password"] != data.get("new_password"):
        f.fail("confirm_password", "Mật khẩu xác nhận không khớp.")
    f.done()
    if not check_password_hash(user["password_hash"], current):
        raise ApiError("Mật khẩu hiện tại không đúng.", 422, "wrong_password", {"current_password": "Mật khẩu hiện tại không đúng."})
    if check_password_hash(user["password_hash"], new):
        raise ApiError("Mật khẩu mới phải khác mật khẩu hiện tại.", 422, "same_password", {"new_password": "Mật khẩu mới phải khác mật khẩu hiện tại."})
    db.execute(
        """UPDATE users SET password_hash = ?, password_updated_at = datetime('now'),
                  session_version = session_version + 1 WHERE id = ?""",
        (generate_password_hash(new), user["id"]),
    )
    # Thiết bị hiện tại vẫn đăng nhập; các thiết bị khác bị đăng xuất do session_version đổi.
    login_user(db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone(), remember=g.jwt_payload["remember"] if g.get("jwt_payload") else False)
    return jsonify(ok=True, message="Đã cập nhật mật khẩu.")


@api_bp.post("/account/logout-all")
@login_required
def logout_all():
    db = get_db()
    user = current_user()
    db.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (user["id"],))
    from ...common.helpers import logout_user
    logout_user()
    return jsonify(ok=True)


# ----------------------------------------------------------------- địa chỉ
def _address_fields(data: dict, partial_from=None) -> dict:
    """Kiểm tra dữ liệu địa chỉ. Với PATCH, trường vắng mặt lấy từ bản ghi cũ."""
    if partial_from is not None:
        data = {**{k: partial_from[k] for k in ("label", "full_name", "phone", "province", "ward", "street")}, **data}
    f = Fields(data)
    out = {
        "label": f.text("label", "Nhãn", required=False, max_len=40),
        "full_name": f.text("full_name", "Họ và tên", max_len=100),
        "phone": f.phone(),
        "province": f.text("province", "Tỉnh / Thành phố", max_len=100),
        "ward": f.text("ward", "Phường / Xã", max_len=100),
        "street": f.text("street", "Địa chỉ cụ thể", max_len=200),
    }
    f.done()
    return out


def _own_address(db, address_id: int):
    row = db.execute(
        "SELECT * FROM addresses WHERE id = ? AND user_id = ?", (address_id, current_user()["id"])
    ).fetchone()
    if row is None:
        raise ApiError("Không tìm thấy địa chỉ.", 404, "address_not_found")
    return row


class AddressesView(MethodView):
    decorators = [login_required]

    def get(self):
        rows = get_db().execute(
            "SELECT * FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id DESC", (current_user()["id"],)
        ).fetchall()
        return jsonify(items=[address_json(r) for r in rows])

    def post(self):
        db = get_db()
        user = current_user()
        data = json_body()
        fields = _address_fields(data)
        first = db.execute("SELECT 1 FROM addresses WHERE user_id = ?", (user["id"],)).fetchone() is None
        make_default = first or bool(data.get("is_default"))
        with transaction(db):
            if make_default:
                db.execute("UPDATE addresses SET is_default = 0 WHERE user_id = ?", (user["id"],))
            cur = db.execute(
                """INSERT INTO addresses (user_id, label, full_name, phone, province, ward, street, is_default)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user["id"], *fields.values(), int(make_default)),
            )
        response = jsonify(address=address_json(db.execute("SELECT * FROM addresses WHERE id = ?", (cur.lastrowid,)).fetchone()))
        response.status_code = 201
        return response


class AddressView(MethodView):
    decorators = [login_required]

    def patch(self, address_id):
        db = get_db()
        row = _own_address(db, address_id)
        fields = _address_fields(json_body(), partial_from=row)
        db.execute(
            "UPDATE addresses SET label = ?, full_name = ?, phone = ?, province = ?, ward = ?, street = ? WHERE id = ?",
            (*fields.values(), row["id"]),
        )
        return jsonify(address=address_json(db.execute("SELECT * FROM addresses WHERE id = ?", (row["id"],)).fetchone()))

    def delete(self, address_id):
        db = get_db()
        row = _own_address(db, address_id)
        with transaction(db):
            db.execute("DELETE FROM addresses WHERE id = ?", (row["id"],))
            if row["is_default"]:  # chuyển mặc định sang địa chỉ mới nhất còn lại
                db.execute(
                    "UPDATE addresses SET is_default = 1 WHERE id = "
                    "(SELECT id FROM addresses WHERE user_id = ? ORDER BY id DESC LIMIT 1)",
                    (row["user_id"],),
                )
        return jsonify(ok=True)


@api_bp.post("/account/addresses/<int:address_id>/default")
@login_required
def set_default_address(address_id):
    db = get_db()
    row = _own_address(db, address_id)
    with transaction(db):
        db.execute("UPDATE addresses SET is_default = 0 WHERE user_id = ?", (row["user_id"],))
        db.execute("UPDATE addresses SET is_default = 1 WHERE id = ?", (row["id"],))
    return jsonify(address=address_json(db.execute("SELECT * FROM addresses WHERE id = ?", (row["id"],)).fetchone()))


# ---------------------------------------------------------------- yêu thích
class WishlistView(MethodView):
    decorators = [login_required]

    def get(self):
        db = get_db()
        rows = db.execute(
            f"{PRODUCT_CARD_SELECT} JOIN wishlist w ON w.product_id = p.id "
            "WHERE w.user_id = ? AND p.status = 'active' ORDER BY w.created_at DESC, p.id DESC",
            (current_user()["id"],),
        ).fetchall()
        return jsonify(items=product_cards(db, rows), total=len(rows))

    def post(self):
        db = get_db()
        f = Fields(json_body())
        product_id = f.integer("product_id", "Sản phẩm", minimum=1, maximum=2**53)
        f.done()
        if db.execute("SELECT 1 FROM products WHERE id = ? AND status = 'active'", (product_id,)).fetchone() is None:
            raise ApiError("Không tìm thấy sản phẩm.", 404, "product_not_found")
        db.execute("INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)", (current_user()["id"], product_id))
        response = jsonify(ok=True, product_id=product_id, in_wishlist=True)
        response.status_code = 201
        return response


@api_bp.delete("/account/wishlist/<int:product_id>")
@login_required
def remove_wishlist(product_id):
    get_db().execute("DELETE FROM wishlist WHERE user_id = ? AND product_id = ?", (current_user()["id"], product_id))
    return jsonify(ok=True, product_id=product_id, in_wishlist=False)


# ------------------------------------------------------------------ đơn hàng
@api_bp.get("/account/orders")
@login_required
def my_orders():
    db = get_db()
    status = request.args.get("status", "all")
    if status not in STATUS_GROUPS:
        raise ApiError(f"status phải là một trong: {', '.join(STATUS_GROUPS)}.", 400, "invalid_param")
    page = arg_int("page", 1)
    per_page = arg_int("per_page", 10, maximum=50)
    where, params = ["user_id = ?"], [current_user()["id"]]
    group = STATUS_GROUPS[status]
    if group:
        where.append(f"status IN ({placeholders(group)})")
        params += group
    q = (request.args.get("q") or "").strip().lstrip("#")
    if q:
        where.append(
            "(code LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = orders.id "
            "AND unaccent(oi.name) LIKE ? ESCAPE '\\'))"
        )
        from ...db import unaccent

        esc = lambda s: s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")  # noqa: E731
        params += [f"%{esc(q.upper())}%", f"%{esc(unaccent(q))}%"]
    clause = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) FROM orders WHERE {clause}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM orders WHERE {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    return jsonify(
        items=orders_json(db, rows), total=total, page=page, per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


def _own_order(db, code: str):
    row = db.execute("SELECT * FROM orders WHERE code = ? AND user_id = ?", (code.upper(), current_user()["id"])).fetchone()
    if row is None:
        raise ApiError("Không tìm thấy đơn hàng.", 404, "order_not_found")
    return row


@api_bp.post("/account/orders/<code>/cancel")
@login_required
def cancel_order(code):
    db = get_db()
    with transaction(db):
        order = _own_order(db, code)
        if order["status"] not in ("pending", "preparing"):
            raise ApiError("Đơn hàng đã được bàn giao vận chuyển hoặc đã đóng, không thể hủy.", 409, "cannot_cancel")
        for item in db.execute("SELECT variant_id, product_id, quantity FROM order_items WHERE order_id = ?", (order["id"],)):
            if item["variant_id"] is not None:
                db.execute("UPDATE variants SET stock = stock + ? WHERE id = ?", (item["quantity"], item["variant_id"]))
            if item["product_id"] is not None:
                db.execute(
                    "UPDATE products SET sold_count = MAX(sold_count - ?, 0) WHERE id = ?",
                    (item["quantity"], item["product_id"]),
                )
        payment_status = "refunded" if order["payment_status"] == "paid" else order["payment_status"]
        db.execute("UPDATE orders SET status = 'cancelled', payment_status = ? WHERE id = ?", (payment_status, order["id"]))
        db.execute("INSERT INTO order_events (order_id, status) VALUES (?, 'cancelled')", (order["id"],))
    return jsonify(order=order_json(db, _own_order(db, code)))


@api_bp.post("/account/orders/<code>/reorder")
@login_required
def reorder(code):
    db = get_db()
    order = _own_order(db, code)
    cart = find_cart(db, create=True)
    skipped = []
    for item in db.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],)).fetchall():
        if item["variant_id"] is None:
            skipped.append({"name": item["name"], "reason": "Sản phẩm không còn được bán."})
            continue
        try:
            set_item_quantity(db, cart["id"], item["variant_id"], item["quantity"], add=True)
        except ApiError as err:
            skipped.append({"name": item["name"], "reason": err.message})
    response = respond_cart(db)
    payload = response.get_json()
    payload["skipped"] = skipped
    return jsonify(payload)


# ------------------------------------------------------------------ đánh giá
@api_bp.get("/account/reviews")
@login_required
def my_reviews():
    db = get_db()
    uid = current_user()["id"]
    written = db.execute(
        """SELECT r.*, p.slug AS product_slug, p.name AS product_name
           FROM reviews r JOIN products p ON p.id = r.product_id
           WHERE r.user_id = ? ORDER BY r.created_at DESC, r.id DESC""",
        (uid,),
    ).fetchall()
    # Sản phẩm đã nhận hàng (đơn delivered) mà chưa đánh giá; mỗi sản phẩm chỉ liệt kê một lần (đơn mới nhất).
    pending = db.execute(
        """SELECT p.id AS product_id, p.slug, p.name, o.code AS order_code, o.delivered_at, MAX(o.id) AS _o
           FROM order_items oi
           JOIN orders o ON o.id = oi.order_id
           JOIN products p ON p.id = oi.product_id
           WHERE o.user_id = ? AND o.status = 'delivered' AND p.status = 'active'
             AND NOT EXISTS (SELECT 1 FROM reviews r WHERE r.user_id = o.user_id AND r.product_id = p.id)
           GROUP BY p.id ORDER BY _o DESC""",
        (uid,),
    ).fetchall()
    return jsonify(
        items=[{**review_json(r), "product": {"slug": r["product_slug"], "name": r["product_name"]}} for r in written],
        pending=[
            {
                "product_id": r["product_id"],
                "slug": r["slug"],
                "name": r["name"],
                "order_code": r["order_code"],
                "delivered_at": r["delivered_at"],
            }
            for r in pending
        ],
    )


api_bp.add_url_rule("/account/profile", view_func=ProfileView.as_view("account_profile"))
api_bp.add_url_rule("/account/addresses", view_func=AddressesView.as_view("account_addresses"))
api_bp.add_url_rule("/account/addresses/<int:address_id>", view_func=AddressView.as_view("account_address"))
api_bp.add_url_rule("/account/wishlist", view_func=WishlistView.as_view("account_wishlist"))
