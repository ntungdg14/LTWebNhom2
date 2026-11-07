"""Địa giới hành chính cho form địa chỉ.

    GET /api/provinces                    danh sách tỉnh / thành phố
    GET /api/provinces/<code>/wards       phường / xã thuộc tỉnh
"""
from flask import jsonify

from ...db import get_db
from . import checkout_api_bp as api_bp
from ...common.helpers import ApiError


@api_bp.get("/provinces")
def provinces():
    rows = get_db().execute("SELECT code, name FROM provinces ORDER BY name").fetchall()
    return jsonify(items=[dict(r) for r in rows])


@api_bp.get("/provinces/<code>/wards")
def wards(code):
    db = get_db()
    if db.execute("SELECT 1 FROM provinces WHERE code = ?", (code,)).fetchone() is None:
        raise ApiError("Không tìm thấy tỉnh/thành phố.", 404, "province_not_found")
    rows = db.execute("SELECT id, name FROM wards WHERE province_code = ? ORDER BY name", (code,)).fetchall()
    return jsonify(items=[dict(r) for r in rows])
