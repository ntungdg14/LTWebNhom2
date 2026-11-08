"""Nhắn tin giữa khách và shop. Mỗi khách có đúng một cuộc hội thoại với shop.

Phía khách (cần đăng nhập):
    GET  /api/chat/conversation        cuộc hội thoại của tôi (null nếu chưa nhắn lần nào) + số tin chưa đọc
    GET  /api/chat/messages            tin nhắn (?after_id= lấy tin mới để polling, ?before_id= lấy tin cũ, ?limit=)
    POST /api/chat/messages            gửi tin {body, order_code?, product_slug?}; tự tạo hội thoại ở tin đầu tiên
    GET  /api/chat/unread              số tin shop gửi mà tôi chưa đọc

Phía shop (cần role = admin):
    GET  /api/shop/chat/conversations                  danh sách hội thoại (?q=tên/email khách, ?unread=1, ?page=)
    GET  /api/shop/chat/conversations/<id>/messages    tin nhắn của một khách (cùng tham số phân trang như trên)
    POST /api/shop/chat/conversations/<id>/messages    shop trả lời {body}
    GET  /api/shop/chat/unread                         tổng số tin khách gửi mà shop chưa đọc

Lấy tin (GET .../messages) sẽ đánh dấu "đã đọc" các tin của bên kia, trừ khi truyền ?mark_read=0.
Tin trả về luôn theo thứ tự cũ -> mới. Chưa có websocket: client gọi lại với ?after_id=<id tin cuối> để lấy tin mới.
"""
from __future__ import annotations

import math

from flask import jsonify, request

from ...db import get_db, transaction, unaccent
from . import chat_api_bp as api_bp
from ...common.helpers import ApiError, Fields, admin_required, arg_int, current_user, json_body, login_required

MESSAGE_SELECT = """
SELECT m.*, p.slug AS product_slug, p.name AS product_name
FROM messages m LEFT JOIN products p ON p.id = m.product_id
"""


def message_json(m, viewer: str) -> dict:
    """``viewer`` là 'customer' hoặc 'shop' -> ``is_mine`` cho biết tin do chính người xem gửi."""
    return {
        "id": m["id"],
        "conversation_id": m["conversation_id"],
        "sender": m["sender"],
        "is_mine": m["sender"] == viewer,
        "body": m["body"],
        "order_code": m["order_code"],
        "product": {"slug": m["product_slug"], "name": m["product_name"]} if m["product_slug"] else None,
        "read": m["read_at"] is not None,
        "created_at": m["created_at"],
    }


def _other(viewer: str) -> str:
    return "shop" if viewer == "customer" else "customer"


def _unread_for(db, conversation_id: int, viewer: str) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND sender = ? AND read_at IS NULL",
        (conversation_id, _other(viewer)),
    ).fetchone()[0]


def _last_message(db, conversation_id: int):
    return db.execute(
        f"{MESSAGE_SELECT} WHERE m.conversation_id = ? ORDER BY m.id DESC LIMIT 1", (conversation_id,)
    ).fetchone()


def _fetch_messages(db, conversation_id: int, viewer: str):
    """Đọc một trang tin nhắn (after_id / before_id / limit) và đánh dấu đã đọc tin của bên kia."""
    limit = arg_int("limit", 30, maximum=100)
    after_id = arg_int("after_id", 0, minimum=0) if request.args.get("after_id") else None
    before_id = arg_int("before_id", 0, minimum=0) if request.args.get("before_id") else None
    if after_id is not None and before_id is not None:
        raise ApiError("Chỉ dùng một trong after_id hoặc before_id.", 400, "invalid_param")

    if request.args.get("mark_read", "1") != "0":  # đánh dấu trước khi đọc để trạng thái trả về khớp DB
        db.execute(
            "UPDATE messages SET read_at = datetime('now', 'localtime') "
            "WHERE conversation_id = ? AND sender = ? AND read_at IS NULL",
            (conversation_id, _other(viewer)),
        )

    where, params = ["m.conversation_id = ?"], [conversation_id]
    if after_id is not None:
        where.append("m.id > ?")
        params.append(after_id)
        rows = db.execute(
            f"{MESSAGE_SELECT} WHERE {' AND '.join(where)} ORDER BY m.id ASC LIMIT ?", [*params, limit + 1]
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
    else:
        if before_id is not None:
            where.append("m.id < ?")
            params.append(before_id)
        rows = db.execute(
            f"{MESSAGE_SELECT} WHERE {' AND '.join(where)} ORDER BY m.id DESC LIMIT ?", [*params, limit + 1]
        ).fetchall()
        has_more = len(rows) > limit
        rows = list(reversed(rows[:limit]))

    return jsonify(
        items=[message_json(r, viewer) for r in rows],
        has_more=has_more,  # còn tin cũ hơn (before_id/mặc định) hoặc còn tin mới hơn (after_id)
        unread=_unread_for(db, conversation_id, viewer),
    )


def _body_field(data: dict) -> str:
    f = Fields(data)
    body = f.text("body", "Nội dung tin nhắn", max_len=2000)
    f.done()
    return body


def _insert_message(db, conversation_id: int, sender: str, sender_id: int, body: str, order_code=None, product_id=None):
    cur = db.execute(
        "INSERT INTO messages (conversation_id, sender, sender_id, body, order_code, product_id) VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, sender, sender_id, body, order_code, product_id),
    )
    db.execute(
        "UPDATE conversations SET last_message_at = datetime('now', 'localtime') WHERE id = ?", (conversation_id,)
    )
    return db.execute(f"{MESSAGE_SELECT} WHERE m.id = ?", (cur.lastrowid,)).fetchone()


# --------------------------------------------------------------------- khách
def _my_conversation(db):
    return db.execute("SELECT * FROM conversations WHERE user_id = ?", (current_user()["id"],)).fetchone()


def _customer_conversation_json(db, conv) -> dict:
    last = _last_message(db, conv["id"])
    return {
        "id": conv["id"],
        "created_at": conv["created_at"],
        "last_message_at": conv["last_message_at"],
        "last_message": message_json(last, "customer") if last else None,
        "unread": _unread_for(db, conv["id"], "customer"),
    }


@api_bp.get("/chat/conversation")
@login_required
def my_conversation():
    db = get_db()
    conv = _my_conversation(db)
    return jsonify(conversation=_customer_conversation_json(db, conv) if conv else None)


def my_messages():
    db = get_db()
    conv = _my_conversation(db)
    if conv is None:  # chưa nhắn lần nào: danh sách rỗng, không tạo hội thoại khi chỉ đọc
        return jsonify(items=[], has_more=False, unread=0)
    return _fetch_messages(db, conv["id"], "customer")


@api_bp.route("/chat/messages", methods=["GET", "POST"])
@login_required
def chat_messages():
    """Một URL, hai phương thức (test kiểm tra mỗi đường dẫn chỉ đăng ký một lần)."""
    return send_message() if request.method == "POST" else my_messages()


@api_bp.get("/chat/unread")
@login_required
def my_unread():
    db = get_db()
    conv = _my_conversation(db)
    return jsonify(unread=_unread_for(db, conv["id"], "customer") if conv else 0)


def send_message():
    db = get_db()
    user = current_user()
    data = json_body()
    body = _body_field(data)

    order_code = None
    if data.get("order_code"):
        row = db.execute(
            "SELECT code FROM orders WHERE code = ? AND user_id = ?", (str(data["order_code"]).upper(), user["id"])
        ).fetchone()
        if row is None:
            raise ApiError("Không tìm thấy đơn hàng.", 404, "order_not_found")
        order_code = row["code"]
    product_id = None
    if data.get("product_slug"):
        row = db.execute(
            "SELECT id FROM products WHERE slug = ? AND status = 'active'", (str(data["product_slug"]),)
        ).fetchone()
        if row is None:
            raise ApiError("Không tìm thấy sản phẩm.", 404, "product_not_found")
        product_id = row["id"]

    with transaction(db):
        db.execute("INSERT OR IGNORE INTO conversations (user_id) VALUES (?)", (user["id"],))
        conv = _my_conversation(db)
        message = _insert_message(db, conv["id"], "customer", user["id"], body, order_code, product_id)
    response = jsonify(message=message_json(message, "customer"), conversation_id=conv["id"])
    response.status_code = 201
    return response


# ---------------------------------------------------------------------- shop
def _conversation_or_404(db, conversation_id: int):
    conv = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if conv is None:
        raise ApiError("Không tìm thấy cuộc hội thoại.", 404, "conversation_not_found")
    return conv


@api_bp.get("/shop/chat/conversations")
@admin_required
def shop_conversations():
    db = get_db()
    page = arg_int("page", 1)
    per_page = arg_int("per_page", 20, maximum=50)
    where, params = ["1 = 1"], []
    if request.args.get("unread") == "1":
        where.append(
            "EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id AND m.sender = 'customer' AND m.read_at IS NULL)"
        )
    q = (request.args.get("q") or "").strip()
    if q:
        esc = unaccent(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(unaccent(u.full_name) LIKE ? ESCAPE '\\' OR unaccent(u.email) LIKE ? ESCAPE '\\')")
        params += [f"%{esc}%", f"%{esc}%"]
    clause = " AND ".join(where)
    base = f"FROM conversations c JOIN users u ON u.id = c.user_id WHERE {clause}"
    total = db.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT c.*, u.full_name, u.email {base} ORDER BY c.last_message_at DESC, c.id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    items = []
    for c in rows:
        last = _last_message(db, c["id"])
        items.append(
            {
                "id": c["id"],
                "customer": {"id": c["user_id"], "full_name": c["full_name"], "email": c["email"]},
                "last_message_at": c["last_message_at"],
                "last_message": message_json(last, "shop") if last else None,
                "unread": _unread_for(db, c["id"], "shop"),
            }
        )
    return jsonify(items=items, total=total, page=page, per_page=per_page, pages=math.ceil(total / per_page) if total else 0)


def shop_messages(conversation_id):
    db = get_db()
    _conversation_or_404(db, conversation_id)
    return _fetch_messages(db, conversation_id, "shop")


def shop_reply(conversation_id):
    db = get_db()
    body = _body_field(json_body())
    with transaction(db):
        _conversation_or_404(db, conversation_id)
        message = _insert_message(db, conversation_id, "shop", current_user()["id"], body)
    response = jsonify(message=message_json(message, "shop"))
    response.status_code = 201
    return response


@api_bp.route("/shop/chat/conversations/<int:conversation_id>/messages", methods=["GET", "POST"])
@admin_required
def shop_conversation_messages(conversation_id):
    return shop_reply(conversation_id) if request.method == "POST" else shop_messages(conversation_id)


@api_bp.get("/shop/chat/unread")
@admin_required
def shop_unread():
    n = get_db().execute("SELECT COUNT(*) FROM messages WHERE sender = 'customer' AND read_at IS NULL").fetchone()[0]
    return jsonify(unread=n)
