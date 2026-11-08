"""Luồng đặt hàng 4 bước: giỏ hàng -> giao hàng -> thanh toán -> xác nhận."""
from flask import current_app, flash, redirect, render_template, request, session, url_for

from ...common.helpers import ApiError, EMAIL_RE, PHONE_RE, check_role, current_user, normalize_phone
from ...common.services import compute_totals, estimated_delivery, find_cart, line_issue, load_cart_rows, make_default_address, shipping_fee, shipping_methods
from ...db import get_db
from .api import place_order
from . import checkout_bp

SESSION_KEY = "checkout_shipping"


@checkout_bp.before_request
def require_login():
    """Giao hàng, thanh toán, xác nhận đơn: cần đăng nhập."""
    return check_role()


def _cart_rows(db):
    cart = find_cart(db)
    return load_cart_rows(db, cart["id"]) if cart else []


def _prefill(db, user):
    """Thông tin điền sẵn: phiên checkout đang dở > địa chỉ mặc định > hồ sơ tài khoản."""
    saved = session.get(SESSION_KEY)
    if saved:
        return dict(saved)
    address = db.execute(
        "SELECT * FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id DESC LIMIT 1", (user["id"],)
    ).fetchone()
    return {
        "full_name": (address["full_name"] if address else user["full_name"]) or "",
        "phone": (address["phone"] if address else user["phone"]) or "",
        "email": user["email"],
        "province": address["province"] if address else "",
        "ward": address["ward"] if address else "",
        "street": address["street"] if address else "",
        "method": "standard",
        "note": "",
        "save_default": address is None,
    }


def _render_shipping(db, rows, values, errors=None):
    provinces = db.execute("SELECT code, name FROM provinces ORDER BY name").fetchall()
    province = next((p for p in provinces if p["name"] == values.get("province")), None)
    wards = (
        db.execute("SELECT name FROM wards WHERE province_code = ? ORDER BY name", (province["code"],)).fetchall()
        if province else []
    )
    method = values.get("method") if values.get("method") in shipping_methods() else "standard"
    items = [{**dict(r), "line_total": r["price"] * r["quantity"]} for r in rows]
    subtotal = sum(i["line_total"] for i in items)
    return render_template(
        "checkout/shipping.html",
        v=values,
        errors=errors or {},
        provinces=provinces,
        wards=wards,
        province_code=province["code"] if province else "",
        items=items,
        totals=compute_totals(db, rows, None, method),
        methods=[
            {"id": k, "name": info["name"], "fee": shipping_fee(k, subtotal), "eta": estimated_delivery(k), "days": info["days"]}
            for k, info in shipping_methods().items()
        ],
        method=method,
    )


@checkout_bp.route("/checkout/shipping", methods=["GET", "POST"])
def shipping():
    db = get_db()
    rows = _cart_rows(db)
    if not rows and request.method == "POST":
        flash("Giỏ hàng đang trống.", "error")
        return redirect(url_for("store.cart"))
    if any(line_issue(r) for r in rows):
        flash("Vui lòng xử lý các sản phẩm có cảnh báo trong giỏ hàng.", "error")
        return redirect(url_for("store.cart"))
    user = current_user()
    if request.method == "GET":
        return _render_shipping(db, rows, _prefill(db, user))

    form = request.form
    values = {
        "full_name": form.get("name", "").strip(),
        "phone": normalize_phone(form.get("phone", "")),
        "email": form.get("email", "").strip(),
        "street": form.get("address", "").strip(),
        "method": form.get("shipping", "standard"),
        "note": form.get("note", "").strip()[:500],
        "save_default": bool(form.get("default")),
    }
    province = db.execute("SELECT code, name FROM provinces WHERE code = ?", (form.get("city", ""),)).fetchone()
    ward = db.execute(
        "SELECT name FROM wards WHERE province_code = ? AND name = ?", (province["code"], form.get("ward", ""))
    ).fetchone() if province else None
    values["province"] = province["name"] if province else ""
    values["ward"] = ward["name"] if ward else ""

    errors = {}
    if not values["full_name"] or len(values["full_name"]) > 100:
        errors["name"] = "Vui lòng nhập họ và tên."
    if not PHONE_RE.match(values["phone"]):
        errors["phone"] = "Số điện thoại phải gồm 10 số (bắt đầu bằng 0 hoặc +84)."
    if not EMAIL_RE.match(values["email"]):
        errors["email"] = "Email chưa hợp lệ."
    if province is None:
        errors["city"] = "Vui lòng chọn tỉnh / thành phố."
    if ward is None:
        errors["ward"] = "Vui lòng chọn phường / xã."
    if not values["street"] or len(values["street"]) > 200:
        errors["address"] = "Vui lòng nhập địa chỉ cụ thể."
    if values["method"] not in shipping_methods():
        errors["shipping"] = "Phương thức giao hàng không hợp lệ."
        values["method"] = "standard"
    if errors:
        return _render_shipping(db, rows, values, errors)

    session[SESSION_KEY] = values
    if values["save_default"]:
        make_default_address(db, user["id"], {
            "full_name": values["full_name"], "phone": values["phone"], "province": values["province"],
            "ward": values["ward"], "street": values["street"],
        })
    return redirect(url_for("checkout.checkout"))


@checkout_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    db = get_db()
    shipping_info = session.get(SESSION_KEY) or _prefill(db, current_user())
    rows = _cart_rows(db)
    if not rows and request.method == "POST":
        flash("Giỏ hàng đang trống.", "error")
        return redirect(url_for("store.cart"))
    if any(line_issue(r) for r in rows):
        flash("Vui lòng xử lý các sản phẩm có cảnh báo trong giỏ hàng.", "error")
        return redirect(url_for("store.cart"))

    method = shipping_info.get("method") if shipping_info.get("method") in shipping_methods() else "standard"
    payments = current_app.config["PAYMENT_METHODS"]

    if request.method == "POST":
        payment = request.form.get("payment", "")
        if payment not in payments:
            flash("Vui lòng chọn phương thức thanh toán.", "error")
        elif not request.form.get("terms"):
            flash("Bạn cần đồng ý với Điều khoản mua hàng và Chính sách bảo mật.", "error")
        else:
            try:
                order, _ = place_order({
                    "full_name": shipping_info["full_name"], "phone": shipping_info["phone"],
                    "email": shipping_info["email"], "province": shipping_info["province"],
                    "ward": shipping_info["ward"], "street": shipping_info["street"],
                    "note": shipping_info.get("note") or None, "shipping_method": method,
                    "payment_method": payment, "vat_invoice": bool(request.form.get("vat")),
                })
            except ApiError as exc:
                flash("Vui lòng hoàn tất thông tin giao hàng." if exc.fields else exc.message, "error")
                return redirect(url_for("store.cart") if exc.code in ("stock_issue", "out_of_stock", "cart_empty") else url_for("checkout.shipping"))
            session.pop(SESSION_KEY, None)
            return redirect(url_for("checkout.order_success", code=order["code"]))

    items = [{**dict(r), "line_total": r["price"] * r["quantity"]} for r in rows]
    return render_template(
        "checkout/checkout.html",
        s=shipping_info,
        method_name=shipping_methods()[method]["name"],
        eta=estimated_delivery(method),
        items=items,
        totals=compute_totals(db, rows, None, method),
        payments=payments,
        selected_payment=request.form.get("payment", "cod"),
    )


@checkout_bp.route("/order-success")
def order_success():
    return render_template("checkout/order_success.html")
