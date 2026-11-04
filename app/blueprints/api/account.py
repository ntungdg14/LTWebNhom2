"""API tài khoản: hồ sơ, đổi mật khẩu, sổ địa chỉ, yêu thích."""
from __future__ import annotations

from datetime import date

from flask import jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from ...db import get_db
from . import api_bp
from .service import PRODUCT_CARD_SELECT, product_cards
from .utils import (ApiError, check_password_strength, current_user, json_body, login_required, raise_if, text,
                    user_dict, valid_email, valid_phone)


def address_dict(r) -> dict:
    return {"id": r["id"], "label": r["label"], "full_name": r["full_name"], "phone": r["phone"],
            "province": r["province"], "ward": r["ward"], "street": r["street"],
            "full_address": f"{r['street']}, {r['ward']}, {r['province']}", "is_default": bool(r["is_default"])}


def default_address(user_id: int):
    r = get_db().execute("SELECT * FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id DESC LIMIT 1",
                         (user_id,)).fetchone()
    return address_dict(r) if r else None


# ---------- hồ sơ ----------
@api_bp.get("/account/profile")
@login_required
def get_profile():
    user = current_user()
    return jsonify({**user_dict(user), "default_address": default_address(user["id"])})


@api_bp.patch("/account/profile")
@login_required
def update_profile():
    user, data, errors, db = current_user(), json_body(), {}, get_db()
    fields: dict = {}
    if "full_name" in data:
        fields["full_name"] = text(data, "full_name", "họ và tên", errors, max_len=100)
    if "email" in data:
        email = valid_email(text(data, "email", "email", errors, max_len=150), errors)
        if email and "email" not in errors and db.execute(
                "SELECT 1 FROM users WHERE email = ? AND id != ?", (email, user["id"])).fetchone():
            errors["email"] = "Email này đã được sử dụng."
        fields["email"] = email
    if "phone" in data:
        fields["phone"] = valid_phone(text(data, "phone", "số điện thoại", errors, max_len=20), errors)
    if "birthday" in data:
        b = data["birthday"]
        if b in (None, ""):
            fields["birthday"] = None
        else:
            try:
                d = date.fromisoformat(b)
                if d > date.today():
                    raise ValueError
                fields["birthday"] = d.isoformat()
            except (TypeError, ValueError):
                errors["birthday"] = "Ngày sinh không hợp lệ (định dạng YYYY-MM-DD)."
    if "gender" in data:
        if data["gender"] not in (None, "nam", "nu", "khac"):
            errors["gender"] = "Giới tính phải là nam, nu hoặc khac."
        fields["gender"] = data["gender"]
    if "newsletter" in data:
        if not isinstance(data["newsletter"], bool):
            errors["newsletter"] = "Giá trị phải là true/false."
        fields["newsletter"] = int(bool(data["newsletter"]))
    raise_if(errors)
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        db.execute(f"UPDATE users SET {sets} WHERE id = ?", [*fields.values(), user["id"]])
        db.commit()
    fresh = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify({**user_dict(fresh), "default_address": default_address(user["id"])})


@api_bp.post("/account/password")
@login_required
def change_password():
    user, data, errors = current_user(), json_body(), {}
    current = data.get("current_password")
    if not current or not check_password_hash(user["password_hash"], current):
        errors["current_password"] = "Mật khẩu hiện tại không đúng."
    check_password_strength(data.get("new_password"), errors, "new_password")
    if "new_password" not in errors and data["new_password"] != data.get("confirm_password"):
        errors["confirm_password"] = "Mật khẩu xác nhận không khớp."
    if "new_password" not in errors and data.get("new_password") == current:
        errors["new_password"] = "Mật khẩu mới phải khác mật khẩu hiện tại."
    raise_if(errors)
    db = get_db()
    # Tăng session_version để đăng xuất các thiết bị khác, giữ phiên hiện tại.
    db.execute("UPDATE users SET password_hash = ?, password_updated_at = date('now'), "
               "session_version = session_version + 1 WHERE id = ?",
               (generate_password_hash(data["new_password"]), user["id"]))
    db.commit()
    session["sv"] = user["session_version"] + 1
    return jsonify({"ok": True, "password_updated_at": date.today().isoformat()})


@api_bp.post("/account/logout-others")
@login_required
def logout_others():
    user, db = current_user(), get_db()
    db.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (user["id"],))
    db.commit()
    session["sv"] = user["session_version"] + 1
    return jsonify({"ok": True})


# ---------- sổ địa chỉ ----------
def _address_input(data: dict) -> dict:
    errors: dict = {}
    out = {
        "label": text(data, "label", "tên gọi địa chỉ", errors, required=False, max_len=40),
        "full_name": text(data, "full_name", "họ và tên", errors, max_len=100),
        "phone": valid_phone(text(data, "phone", "số điện thoại", errors, max_len=20), errors),
        "province": text(data, "province", "tỉnh/thành phố", errors, max_len=80),
        "ward": text(data, "ward", "phường/xã", errors, max_len=80),
        "street": text(data, "street", "địa chỉ cụ thể", errors, max_len=200),
    }
    raise_if(errors)
    return out


def _own_address(address_id: int, user_id: int):
    r = get_db().execute("SELECT * FROM addresses WHERE id = ? AND user_id = ?", (address_id, user_id)).fetchone()
    if r is None:
        raise ApiError("Không tìm thấy địa chỉ.", 404, "not_found")
    return r


def set_default_address(user_id: int, address_id: int) -> None:
    db = get_db()
    db.execute("UPDATE addresses SET is_default = (id = ?) WHERE user_id = ?", (address_id, user_id))


@api_bp.get("/account/addresses")
@login_required
def list_addresses():
    rows = get_db().execute("SELECT * FROM addresses WHERE user_id = ? ORDER BY is_default DESC, id", (current_user()["id"],))
    return jsonify({"items": [address_dict(r) for r in rows]})


@api_bp.post("/account/addresses")
@login_required
def create_address():
    user, data, db = current_user(), json_body(), get_db()
    vals = _address_input(data)
    count = db.execute("SELECT COUNT(*) FROM addresses WHERE user_id = ?", (user["id"],)).fetchone()[0]
    if count >= 10:
        raise ApiError("Bạn chỉ có thể lưu tối đa 10 địa chỉ.", 409, "limit_reached")
    cur = db.execute(
        "INSERT INTO addresses (user_id, label, full_name, phone, province, ward, street) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["id"], *vals.values()))
    if count == 0 or data.get("is_default") is True:
        set_default_address(user["id"], cur.lastrowid)
    db.commit()
    return jsonify(address_dict(_own_address(cur.lastrowid, user["id"]))), 201


@api_bp.patch("/account/addresses/<int:address_id>")
@login_required
def update_address(address_id: int):
    user, data, db = current_user(), json_body(), get_db()
    current = _own_address(address_id, user["id"])
    merged = {k: data.get(k, current[k]) for k in ("label", "full_name", "phone", "province", "ward", "street")}
    vals = _address_input(merged)
    db.execute("UPDATE addresses SET label = ?, full_name = ?, phone = ?, province = ?, ward = ?, street = ? WHERE id = ?",
               (*vals.values(), address_id))
    if data.get("is_default") is True:
        set_default_address(user["id"], address_id)
    db.commit()
    return jsonify(address_dict(_own_address(address_id, user["id"])))


@api_bp.post("/account/addresses/<int:address_id>/default")
@login_required
def make_default_address(address_id: int):
    user = current_user()
    _own_address(address_id, user["id"])
    set_default_address(user["id"], address_id)
    get_db().commit()
    return jsonify(address_dict(_own_address(address_id, user["id"])))


@api_bp.delete("/account/addresses/<int:address_id>")
@login_required
def delete_address(address_id: int):
    user, db = current_user(), get_db()
    row = _own_address(address_id, user["id"])
    db.execute("DELETE FROM addresses WHERE id = ?", (address_id,))
    if row["is_default"]:  # chuyển mặc định sang địa chỉ mới nhất còn lại
        nxt = db.execute("SELECT id FROM addresses WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
        if nxt:
            set_default_address(user["id"], nxt["id"])
    db.commit()
    return jsonify({"ok": True})


# ---------- yêu thích ----------
@api_bp.get("/account/wishlist")
@login_required
def list_wishlist():
    rows = get_db().execute(
        f"""{PRODUCT_CARD_SELECT} JOIN wishlist w ON w.product_id = p.id
            WHERE w.user_id = ? AND p.status = 'active' ORDER BY w.created_at DESC, p.id DESC""",
        (current_user()["id"],)).fetchall()
    items = product_cards(rows)
    return jsonify({"items": items, "count": len(items)})


@api_bp.post("/account/wishlist")
@login_required
def add_wishlist():
    data = json_body()
    pid = data.get("product_id")
    slug = data.get("product")
    db = get_db()
    row = (db.execute("SELECT id FROM products WHERE id = ? AND status = 'active'", (pid,)).fetchone() if isinstance(pid, int)
           else db.execute("SELECT id FROM products WHERE slug = ? AND status = 'active'", (slug,)).fetchone() if isinstance(slug, str)
           else None)
    if row is None:
        raise ApiError("Không tìm thấy sản phẩm.", 404, "not_found")
    db.execute("INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)", (current_user()["id"], row["id"]))
    db.commit()
    return jsonify({"product_id": row["id"], "in_wishlist": True}), 201


@api_bp.delete("/account/wishlist/<int:product_id>")
@login_required
def remove_wishlist(product_id: int):
    db = get_db()
    db.execute("DELETE FROM wishlist WHERE user_id = ? AND product_id = ?", (current_user()["id"], product_id))
    db.commit()
    return jsonify({"product_id": product_id, "in_wishlist": False})
