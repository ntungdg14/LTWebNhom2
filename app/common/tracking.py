"""Theo dõi đơn hàng (mô phỏng).

Chưa có đơn vị vận chuyển thật nên mọi thứ suy ra từ cột ``orders.status``:
    pending -> preparing -> shipping -> delivered   (hoặc cancelled)
Mốc thời gian lấy từ bảng ``order_events``. "Đẩy" đơn sang bước kế tiếp bằng ``advance_order``
(chỉ dùng để demo, xem ``ORDER_SIMULATION`` trong config.py).
"""
from __future__ import annotations

from .helpers import ApiError
from .serializers import ORDER_STATUS_LABELS, _estimate_from

FLOW = ("pending", "preparing", "shipping", "delivered")

STEP_DESCRIPTIONS = {
    "pending": "Freesion đã nhận đơn và đang chờ xác nhận.",
    "preparing": "Shop đang đóng gói sản phẩm của bạn.",
    "shipping": "Đơn hàng đã giao cho đơn vị vận chuyển và đang trên đường tới bạn.",
    "delivered": "Đơn hàng đã được giao thành công.",
    "cancelled": "Đơn hàng đã bị hủy.",
}

CARRIER = "Freesion Express (mô phỏng)"


def tracking_number(code: str) -> str:
    """Mã vận đơn giả, cố định theo mã đơn: FR261101028 -> FX261101028."""
    return "FX" + code[2:]


def _event_times(db, order_id: int) -> dict[str, str]:
    times: dict[str, str] = {}
    for e in db.execute("SELECT status, created_at FROM order_events WHERE order_id = ? ORDER BY id", (order_id,)):
        times.setdefault(e["status"], e["created_at"])
    return times


def tracking_json(db, order) -> dict:
    status = order["status"]
    times = _event_times(db, order["id"])
    steps = []
    if status == "cancelled":
        # Chỉ hiện các bước đã đi qua, rồi tới bước "Đã hủy".
        for key in FLOW:
            if key in times:
                steps.append({"key": key, "state": "done", "at": times[key]})
        steps.append({"key": "cancelled", "state": "cancelled", "at": times.get("cancelled")})
        current = len(steps) - 1
    else:
        current = FLOW.index(status) if status in FLOW else 0
        for i, key in enumerate(FLOW):
            if i < current:
                state = "done"
            elif i == current:
                state = "done" if status == "delivered" else "current"
            else:
                state = "upcoming"
            steps.append({"key": key, "state": state, "at": times.get(key) if i <= current else None})
    for step in steps:
        step["label"] = ORDER_STATUS_LABELS.get(step["key"], step["key"])
        step["description"] = STEP_DESCRIPTIONS.get(step["key"], "")

    payload = {
        "code": order["code"],
        "status": status,
        "status_label": ORDER_STATUS_LABELS.get(status, status),
        "is_delivered": status == "delivered",
        "is_cancelled": status == "cancelled",
        "current_step": current,
        "steps": steps,
        "carrier": CARRIER,
        "tracking_number": tracking_number(order["code"]) if status in ("shipping", "delivered") else None,
        "simulated": True,
        "delivered_at": order["delivered_at"],
    }
    if status in ("pending", "preparing", "shipping"):
        payload["estimated_delivery"] = _estimate_from(order["created_at"], order["shipping_method"])
    return payload


def advance_order(db, order, to: str | None = None):
    """Chuyển đơn sang bước kế tiếp (hoặc nhảy tới ``to``). Gọi trong một transaction."""
    status = order["status"]
    if status not in FLOW or status == "delivered":
        raise ApiError("Đơn hàng đã đóng, không thể chuyển tiếp.", 409, "cannot_advance")
    index = FLOW.index(status)
    if to is None:
        target = index + 1
    elif to in FLOW and FLOW.index(to) > index:
        target = FLOW.index(to)
    else:
        raise ApiError(
            f"Chỉ có thể chuyển tiếp tới: {', '.join(FLOW[index + 1:])}.", 422, "invalid_status", {"to": "Trạng thái không hợp lệ."}
        )
    for key in FLOW[index + 1 : target + 1]:
        db.execute("INSERT INTO order_events (order_id, status) VALUES (?, ?)", (order["id"], key))
    new_status = FLOW[target]
    if new_status == "delivered":
        # COD: thu tiền khi giao; các phương thức online giữ nguyên trạng thái thanh toán.
        paid = "paid" if order["payment_method"] == "cod" else order["payment_status"]
        db.execute(
            "UPDATE orders SET status = ?, payment_status = ?, delivered_at = datetime('now', 'localtime') WHERE id = ?",
            (new_status, paid, order["id"]),
        )
    else:
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order["id"]))
    return db.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
