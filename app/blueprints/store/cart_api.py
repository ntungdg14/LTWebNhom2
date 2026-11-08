"""Giỏ hàng của người dùng đã đăng nhập (chưa đăng nhập: 401 JSON).

    GET    /api/cart                 giỏ + tạm tính + giảm giá + phí ship + tổng (?shipping_method=standard|express)
    DELETE /api/cart                 xóa toàn bộ giỏ
    POST   /api/cart/items           {variant_id, quantity=1} thêm (cộng dồn nếu đã có)
    PATCH  /api/cart/items/<id>      {quantity} đổi số lượng
    DELETE /api/cart/items/<id>      xóa một dòng
    POST   /api/cart/coupon          {code} áp mã giảm giá
    DELETE /api/cart/coupon          bỏ mã giảm giá

Mọi thao tác trả về toàn bộ giỏ hàng mới để giao diện vẽ lại một lần.
"""
from __future__ import annotations

from flask import jsonify, request
from flask.views import MethodView

from ...db import get_db
from . import store_api_bp as api_bp
from ...common.helpers import ApiError, Fields, json_body, login_required
from ...common.serializers import cart_json
from ...common.services import (
    evaluate_coupon,
    find_cart,
    load_cart_rows,
    set_item_quantity,
    shipping_methods,
    touch_cart,
)


def shipping_method_arg() -> str:
    method = request.args.get("shipping_method", "standard")
    if method not in shipping_methods():
        raise ApiError(f"shipping_method phải là một trong: {', '.join(shipping_methods())}.", 400, "invalid_param")
    return method


def respond_cart(db, status: int = 200):
    cart = find_cart(db)
    rows = load_cart_rows(db, cart["id"]) if cart else []
    cart = db.execute("SELECT * FROM carts WHERE id = ?", (cart["id"],)).fetchone() if cart else None
    response = jsonify(cart=cart_json(db, cart, rows, shipping_method_arg()))
    response.status_code = status
    return response


class CartView(MethodView):
    decorators = [login_required]

    def get(self):
        return respond_cart(get_db())

    def delete(self):
        db = get_db()
        cart = find_cart(db)
        if cart:
            db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart["id"],))
            db.execute("UPDATE carts SET coupon_code = NULL WHERE id = ?", (cart["id"],))
            touch_cart(db, cart["id"])
        return respond_cart(db)


class CartItemsView(MethodView):
    decorators = [login_required]

    def post(self):
        db = get_db()
        data = json_body()
        f = Fields(data)
        variant_id = f.integer("variant_id", "Biến thể sản phẩm", minimum=1, maximum=2**53)
        quantity = f.integer("quantity", "Số lượng", minimum=1, maximum=99, required=False) or 1
        f.done()
        cart = find_cart(db, create=True)
        set_item_quantity(db, cart["id"], variant_id, quantity, add=True)
        return respond_cart(db, 201)


class CartItemView(MethodView):
    decorators = [login_required]

    def _item(self, db, item_id):
        cart = find_cart(db)
        item = (
            db.execute("SELECT * FROM cart_items WHERE id = ? AND cart_id = ?", (item_id, cart["id"])).fetchone()
            if cart
            else None
        )
        if item is None:
            raise ApiError("Không tìm thấy sản phẩm trong giỏ hàng.", 404, "cart_item_not_found")
        return cart, item

    def patch(self, item_id):
        db = get_db()
        cart, item = self._item(db, item_id)
        f = Fields(json_body())
        quantity = f.integer("quantity", "Số lượng", minimum=0, maximum=99)
        f.done()
        if quantity == 0:
            db.execute("DELETE FROM cart_items WHERE id = ?", (item["id"],))
            touch_cart(db, cart["id"])
        else:
            set_item_quantity(db, cart["id"], item["variant_id"], quantity)
        return respond_cart(db)

    def delete(self, item_id):
        db = get_db()
        cart, item = self._item(db, item_id)
        db.execute("DELETE FROM cart_items WHERE id = ?", (item["id"],))
        touch_cart(db, cart["id"])
        return respond_cart(db)


class CartCouponView(MethodView):
    decorators = [login_required]

    def post(self):
        db = get_db()
        f = Fields(json_body())
        code = f.text("code", "Mã giảm giá", max_len=40)
        f.done()
        cart = find_cart(db)
        rows = load_cart_rows(db, cart["id"]) if cart else []
        if not rows:
            raise ApiError("Giỏ hàng đang trống.", 409, "cart_empty")
        subtotal = sum(r["price"] * r["quantity"] for r in rows)
        coupon, error = evaluate_coupon(db, code, subtotal)
        if coupon is None:
            raise ApiError(error, 422, "invalid_coupon", {"code": error})
        db.execute("UPDATE carts SET coupon_code = ? WHERE id = ?", (coupon["code"], cart["id"]))
        touch_cart(db, cart["id"])
        return respond_cart(db)

    def delete(self):
        db = get_db()
        cart = find_cart(db)
        if cart:
            db.execute("UPDATE carts SET coupon_code = NULL WHERE id = ?", (cart["id"],))
            touch_cart(db, cart["id"])
        return respond_cart(db)


api_bp.add_url_rule("/cart", view_func=CartView.as_view("cart"))
api_bp.add_url_rule("/cart/items", view_func=CartItemsView.as_view("cart_items"))
api_bp.add_url_rule("/cart/items/<int:item_id>", view_func=CartItemView.as_view("cart_item"))
api_bp.add_url_rule("/cart/coupon", view_func=CartCouponView.as_view("cart_coupon"))
