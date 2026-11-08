"""Kiểm thử API JSON (/api/...) trên SQLite tạm + dữ liệu mẫu.

Chạy: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import tempfile
import unittest

from app import create_app
from app.db import connect, init_db
from app.seed import seed

PASSWORD = "Matkhau123"


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app("testing")
        self.app.config["DATABASE"] = self.db_path
        with self.app.app_context():
            init_db()
        conn = connect(self.db_path)
        seed(conn)
        conn.close()
        self.client = self.app.test_client()

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except FileNotFoundError:
                pass

    # ---- tiện ích
    def call(self, method, url, body=None, client=None, expect=None):
        client = client or self.client
        kwargs = {"json": body} if body is not None else {}
        csrf = client.get_cookie("csrf_token")
        if csrf and method.lower() not in ("get", "head"):
            kwargs["headers"] = {"X-CSRF-Token": csrf.value}
        response = getattr(client, method)(url, **kwargs)
        if expect is not None:
            self.assertEqual(response.status_code, expect, response.get_data(as_text=True))
        return response.get_json()

    def register(self, email="minhanh@example.com", client=None):
        return self.call(
            "post", "/api/auth/register",
            {"full_name": "Nguyễn Minh Anh", "email": email, "phone": "090 123 4567", "password": PASSWORD},
            client=client, expect=201,
        )

    def variant_id(self, slug="ao-thun-cotton-essential", size="M", color=None):
        product = self.call("get", f"/api/products/{slug}", expect=200)["product"]
        for c in product["colors"]:
            if color and c["slug"] != color:
                continue
            for s in c["sizes"]:
                if s["size"] == size:
                    return s["variant_id"]
        raise AssertionError("không có biến thể")

    def add_to_cart(self, variant_id, quantity=1, client=None):
        return self.call("post", "/api/cart/items", {"variant_id": variant_id, "quantity": quantity}, client=client, expect=201)

    SHIPPING = {
        "full_name": "Nguyễn Minh Anh", "phone": "0901234567", "email": "minhanh@example.com",
        "province": "TP. Hồ Chí Minh", "ward": "Phường Sài Gòn", "street": "28 Nguyễn Thị Minh Khai",
        "shipping_method": "standard", "payment_method": "cod",
    }


class AuthTests(ApiTestCase):
    def test_register_login_logout_me(self):
        self.assertIsNone(self.call("get", "/api/auth/me")["user"])
        user = self.register()["user"]
        self.assertNotIn("password_hash", user)
        self.assertEqual(self.call("get", "/api/auth/me")["user"]["email"], "minhanh@example.com")
        self.call("post", "/api/auth/logout", {}, expect=200)
        self.assertIsNone(self.call("get", "/api/auth/me")["user"])
        self.call("post", "/api/auth/login", {"email": "MINHANH@example.com", "password": PASSWORD}, expect=200)
        self.assertIsNotNone(self.call("get", "/api/auth/me")["user"])

    def test_register_validation_and_duplicates(self):
        body = self.call("post", "/api/auth/register", {"full_name": "", "email": "x", "password": "123"}, expect=422)
        self.assertEqual(set(body["error"]["fields"]), {"full_name", "email", "password"})
        self.register()
        self.call("post", "/api/auth/register",
                  {"full_name": "A", "email": "MinhAnh@Example.com", "password": PASSWORD}, expect=409)

    def test_wrong_password_and_non_json(self):
        self.register()
        self.call("post", "/api/auth/logout", {})
        self.call("post", "/api/auth/login", {"email": "minhanh@example.com", "password": "sai"}, expect=401)
        self.call("post", "/api/auth/login", {"email": "none@example.com", "password": PASSWORD}, expect=401)
        response = self.client.post("/api/auth/login", data={"email": "a@b.co", "password": "x"})
        self.assertEqual(response.status_code, 400)

    def test_forgot_and_reset_password(self):
        self.register()
        self.call("post", "/api/auth/logout", {})
        unknown = self.call("post", "/api/auth/forgot-password", {"email": "ghost@example.com"}, expect=200)
        self.assertNotIn("reset_token", unknown)
        token = self.call("post", "/api/auth/forgot-password", {"email": "minhanh@example.com"}, expect=200)["reset_token"]
        self.call("post", "/api/auth/reset-password", {"token": "sai", "password": "Matkhau456"}, expect=400)
        self.call("post", "/api/auth/reset-password", {"token": token, "password": "Matkhau456"}, expect=200)
        self.call("post", "/api/auth/reset-password", {"token": token, "password": "Matkhau789"}, expect=400)  # dùng 1 lần
        self.call("post", "/api/auth/login", {"email": "minhanh@example.com", "password": PASSWORD}, expect=401)
        self.call("post", "/api/auth/login", {"email": "minhanh@example.com", "password": "Matkhau456"}, expect=200)

    def test_unknown_api_path_returns_json_404(self):
        response = self.client.get("/api/khong-co")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "not_found")
        self.assertEqual(self.client.get("/khong-co").status_code, 404)


class CatalogTests(ApiTestCase):
    def test_home_categories_colors(self):
        home = self.call("get", "/api/home", expect=200)
        self.assertEqual(len(home["categories"]), 6)
        self.assertTrue(home["featured"] and home["testimonials"])
        cats = self.call("get", "/api/categories")["items"]
        self.assertEqual(sum(c["product_count"] for c in cats), 9)
        families = self.call("get", "/api/colors")["items"]
        self.assertEqual(len(families), 8)
        self.assertTrue(any(f["colors"] for f in families))

    def test_product_filters_sort_pagination(self):
        res = self.call("get", "/api/products", expect=200)
        self.assertEqual(res["total"], 9)
        nam = self.call("get", "/api/products?department=nam")
        self.assertEqual([p["slug"] for p in nam["items"]], ["ao-khoac-bomber-uniform"])
        self.assertEqual(nam["items"][0]["discount_percent"], 25)
        mid = self.call("get", "/api/products?price_min=500000&price_max=1000000&sort=price_asc")
        prices = [p["price"] for p in mid["items"]]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(all(500_000 <= p <= 1_000_000 for p in prices))
        self.assertEqual(self.call("get", "/api/products?category=ao-thun")["total"], 2)
        self.assertEqual(self.call("get", "/api/products?color=hong")["total"], 1)
        self.assertEqual(self.call("get", "/api/products?size=XXL")["total"], 1)
        self.assertEqual(self.call("get", "/api/products?sale=1")["total"], 1)
        page2 = self.call("get", "/api/products?per_page=4&page=3")
        self.assertEqual((page2["pages"], len(page2["items"])), (3, 1))

    def test_facets_ignore_own_category_filter(self):
        res = self.call("get", "/api/products?category=ao-thun")
        counts = {c["slug"]: c["count"] for c in res["facets"]["categories"]}
        self.assertEqual(counts["ao-thun"], 2)
        self.assertEqual(counts["quan-jean"], 2)

    def test_search_without_accents(self):
        res = self.call("get", "/api/products?q=ao khoac")
        self.assertEqual([p["slug"] for p in res["items"]], ["ao-khoac-bomber-uniform"])
        self.assertEqual(self.call("get", "/api/products?q=quần jean")["total"], 2)
        self.assertEqual(self.call("get", "/api/products?q=100%25")["total"], 0)  # % không bị coi là wildcard

    def test_invalid_params(self):
        self.call("get", "/api/products?sort=xyz", expect=400)
        self.call("get", "/api/products?page=abc", expect=400)
        self.call("get", "/api/products?department=khac", expect=400)

    def test_product_detail_and_related(self):
        p = self.call("get", "/api/products/ao-khoac-bomber-uniform", expect=200)["product"]
        self.assertEqual(p["sizes"], ["S", "M", "L", "XL", "XXL"])
        self.assertEqual(len(p["colors"]), 4)
        self.assertEqual(len(p["images"]), 6)
        self.call("get", "/api/products/khong-co", expect=404)
        related = self.call("get", "/api/products/ao-khoac-bomber-uniform/related")["items"]
        self.assertEqual(len(related), 4)
        self.assertNotIn("ao-khoac-bomber-uniform", [r["slug"] for r in related])

    def test_draft_products_are_hidden(self):
        conn = connect(self.db_path)
        conn.execute("UPDATE products SET status = 'draft' WHERE slug = 'ao-thun-cotton-essential'")
        conn.close()
        self.call("get", "/api/products/ao-thun-cotton-essential", expect=404)
        self.assertEqual(self.call("get", "/api/products")["total"], 8)

    def test_reviews(self):
        slug = "ao-thun-cotton-essential"
        self.call("post", f"/api/products/{slug}/reviews", {"rating": 5, "body": "Tốt"}, expect=401)
        self.register()
        self.call("post", f"/api/products/{slug}/reviews", {"rating": 9, "body": "x"}, expect=422)
        res = self.call("post", f"/api/products/{slug}/reviews",
                        {"rating": 4, "fit": 3, "title": "Ổn", "body": "Vải dày dặn", "body_info": "Cao 1m65 · 55kg · Mua size M"},
                        expect=201)
        self.assertFalse(res["review"]["verified"])
        self.assertEqual(res["summary"]["count"], 1)
        self.call("post", f"/api/products/{slug}/reviews", {"rating": 5, "body": "Lần 2"}, expect=409)
        listing = self.call("get", f"/api/products/{slug}/reviews?rating=4")
        self.assertEqual((listing["total"], listing["summary"]["average"]), (1, 4.0))


class CartTests(ApiTestCase):
    def test_guest_cart_flow(self):
        vid = self.variant_id()
        empty = self.call("get", "/api/cart", expect=200)["cart"]
        self.assertEqual((empty["item_count"], empty["total"]), (0, 0))
        cart = self.add_to_cart(vid, 2)["cart"]
        self.assertEqual((cart["item_count"], cart["subtotal"]), (2, 498_000))
        self.assertEqual(cart["shipping_fee"], 30_000)  # < 499.000 -> mất phí
        cart = self.add_to_cart(vid, 1)["cart"]  # cộng dồn
        self.assertEqual(cart["items"][0]["quantity"], 3)
        item_id = cart["items"][0]["id"]
        cart = self.call("patch", f"/api/cart/items/{item_id}", {"quantity": 1}, expect=200)["cart"]
        self.assertEqual(cart["subtotal"], 249_000)
        cart = self.call("delete", f"/api/cart/items/{item_id}", expect=200)["cart"]
        self.assertEqual(cart["line_count"], 0)

    def test_stock_limits(self):
        vid = self.variant_id()
        self.call("post", "/api/cart/items", {"variant_id": vid, "quantity": 26}, expect=409)
        self.call("post", "/api/cart/items", {"variant_id": 99999, "quantity": 1}, expect=404)
        self.call("post", "/api/cart/items", {"variant_id": vid, "quantity": 0}, expect=422)

    def test_coupon_and_shipping_rules(self):
        self.add_to_cart(self.variant_id(), 2)
        self.call("post", "/api/cart/coupon", {"code": "KHONGCO"}, expect=422)
        low = self.call("post", "/api/cart/coupon", {"code": "FREESION20"}, expect=422)  # 498.000 < tối thiểu 1.000.000
        self.assertIn("1.000.000", low["error"]["message"])
        self.add_to_cart(self.variant_id("ao-khoac-bomber-uniform", "L", "nau-dua"), 1)
        cart = self.call("post", "/api/cart/coupon", {"code": "tudo10"}, expect=200)["cart"]
        self.assertEqual(cart["subtotal"], 1_397_000)
        self.assertEqual(cart["discount"], 139_700)
        self.assertEqual(cart["shipping_fee"], 0)
        self.assertEqual(cart["total"], 1_257_300)  # khớp số liệu trong thiết kế
        express = self.call("get", "/api/cart?shipping_method=express")["cart"]
        self.assertEqual(express["total"], 1_257_300 + 35_000)
        self.call("get", "/api/cart?shipping_method=drone", expect=400)
        cart = self.call("delete", "/api/cart/coupon", expect=200)["cart"]
        self.assertEqual(cart["discount"], 0)

    def test_cart_is_private_per_session(self):
        self.add_to_cart(self.variant_id())
        other = self.app.test_client()
        self.assertEqual(self.call("get", "/api/cart", client=other)["cart"]["item_count"], 0)
        item_id = self.call("get", "/api/cart")["cart"]["items"][0]["id"]
        self.call("delete", f"/api/cart/items/{item_id}", client=other, expect=404)

    def test_guest_cart_merges_on_login(self):
        self.register()
        self.add_to_cart(self.variant_id(), 1)
        self.call("post", "/api/auth/logout", {})
        self.add_to_cart(self.variant_id(), 2)
        self.add_to_cart(self.variant_id("ao-thun-cotton-essential", "L"), 1)
        self.call("post", "/api/auth/login", {"email": "minhanh@example.com", "password": PASSWORD}, expect=200)
        cart = self.call("get", "/api/cart")["cart"]
        self.assertEqual(cart["item_count"], 4)
        self.assertEqual(cart["line_count"], 2)


class CheckoutTests(ApiTestCase):
    def test_options(self):
        self.add_to_cart(self.variant_id(), 1)
        res = self.call("get", "/api/checkout/options", expect=200)
        fees = {m["id"]: m["fee"] for m in res["shipping_methods"]}
        self.assertEqual(fees, {"standard": 30_000, "express": 35_000})
        self.assertEqual({p["id"] for p in res["payment_methods"]}, {"cod", "vnpay", "momo", "card"})

    def test_guest_order_end_to_end(self):
        vid = self.variant_id()
        self.add_to_cart(vid, 2)
        self.add_to_cart(self.variant_id("ao-khoac-bomber-uniform", "L", "nau-dua"), 1)
        self.call("post", "/api/cart/coupon", {"code": "TUDO10"}, expect=200)
        res = self.call("post", "/api/orders", self.SHIPPING, expect=201)
        order = res["order"]
        self.assertRegex(order["code"], r"^FR\d{6}001$")
        self.assertEqual((order["subtotal"], order["discount"], order["shipping_fee"], order["total"]),
                         (1_397_000, 139_700, 0, 1_257_300))
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["events"][0]["status"], "pending")
        self.assertEqual(order["item_count"], 3)
        self.assertFalse(res["requires_online_payment"])
        # giỏ đã trống, kho đã trừ, khách xem lại được đơn vừa đặt
        self.assertEqual(self.call("get", "/api/cart")["cart"]["line_count"], 0)
        stock = {s["size"]: s["stock"] for c in self.call("get", "/api/products/ao-thun-cotton-essential")["product"]["colors"]
                 for s in c["sizes"] if c["slug"] == "trang"}  # variant_id() lấy màu đầu tiên: Trắng
        self.assertEqual(stock["M"], 23)
        self.call("get", f"/api/orders/{order['code']}", expect=200)
        self.call("get", f"/api/orders/{order['code']}", client=self.app.test_client(), expect=404)
        second = self.call("post", "/api/orders", self.SHIPPING, expect=409)  # giỏ trống
        self.assertEqual(second["error"]["code"], "cart_empty")

    def test_validation_and_online_payment_flag(self):
        self.add_to_cart(self.variant_id(), 1)
        bad = self.call("post", "/api/orders", {"payment_method": "bitcoin"}, expect=422)
        self.assertIn("full_name", bad["error"]["fields"])
        self.assertIn("payment_method", bad["error"]["fields"])
        res = self.call("post", "/api/orders", {**self.SHIPPING, "payment_method": "momo", "shipping_method": "express"}, expect=201)
        self.assertTrue(res["requires_online_payment"])
        self.assertEqual(res["order"]["shipping_fee"], 35_000)
        self.assertEqual(res["order"]["payment_status"], "unpaid")

    def test_stock_changes_between_cart_and_order(self):
        vid = self.variant_id()
        self.add_to_cart(vid, 5)
        conn = connect(self.db_path)
        conn.execute("UPDATE variants SET stock = 2 WHERE id = ?", (vid,))
        conn.close()
        err = self.call("post", "/api/orders", self.SHIPPING, expect=409)["error"]
        self.assertEqual(err["code"], "stock_issue")
        conn = connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)
        conn.close()

    def test_order_codes_increment_per_day(self):
        codes = []
        for _ in range(2):
            self.add_to_cart(self.variant_id(), 1)
            codes.append(self.call("post", "/api/orders", self.SHIPPING, expect=201)["order"]["code"])
        self.assertEqual([c[-3:] for c in codes], ["001", "002"])


class AccountTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.register()

    def test_requires_login(self):
        anon = self.app.test_client()
        for method, url in (("get", "/api/account/profile"), ("get", "/api/account/addresses"),
                            ("get", "/api/account/wishlist"), ("get", "/api/account/orders")):
            with self.subTest(url=url):
                self.call(method, url, client=anon, expect=401)

    def test_profile_update(self):
        res = self.call("patch", "/api/account/profile",
                        {"full_name": "Minh Anh", "birthday": "1998-08-18", "gender": "nu", "newsletter": True}, expect=200)
        self.assertEqual((res["user"]["gender"], res["user"]["newsletter"]), ("nu", True))
        self.call("patch", "/api/account/profile", {"gender": "robot"}, expect=422)
        self.call("patch", "/api/account/profile", {}, expect=400)
        self.call("post", "/api/auth/logout", {})
        self.register("khac@example.com")
        self.call("patch", "/api/account/profile", {"email": "minhanh@example.com"}, expect=409)

    def test_change_password_logs_out_other_devices(self):
        other = self.app.test_client()
        self.call("post", "/api/auth/login", {"email": "minhanh@example.com", "password": PASSWORD}, client=other, expect=200)
        self.call("post", "/api/account/password",
                  {"current_password": "sai", "new_password": "Matkhau456", "confirm_password": "Matkhau456"}, expect=422)
        self.call("post", "/api/account/password",
                  {"current_password": PASSWORD, "new_password": "yeu", "confirm_password": "yeu"}, expect=422)
        self.call("post", "/api/account/password",
                  {"current_password": PASSWORD, "new_password": "Matkhau456", "confirm_password": "Matkhau456"}, expect=200)
        self.assertIsNotNone(self.call("get", "/api/auth/me")["user"])  # thiết bị hiện tại vẫn đăng nhập
        self.assertIsNone(self.call("get", "/api/auth/me", client=other)["user"])

    def test_logout_all(self):
        other = self.app.test_client()
        self.call("post", "/api/auth/login", {"email": "minhanh@example.com", "password": PASSWORD}, client=other, expect=200)
        self.call("post", "/api/account/logout-all", {}, expect=200)
        self.assertIsNone(self.call("get", "/api/auth/me", client=other)["user"])

    def test_addresses_default_rules(self):
        a = {"label": "Nhà riêng", "full_name": "Minh Anh", "phone": "0901234567", "province": "TP. Hồ Chí Minh",
             "ward": "Phường Bến Nghé", "street": "24 Nguyễn Huệ"}
        first = self.call("post", "/api/account/addresses", a, expect=201)["address"]
        self.assertTrue(first["is_default"])  # địa chỉ đầu tiên tự là mặc định
        second = self.call("post", "/api/account/addresses", {**a, "street": "118 Lê Lợi"}, expect=201)["address"]
        self.assertFalse(second["is_default"])
        self.call("post", f"/api/account/addresses/{second['id']}/default", {}, expect=200)
        items = self.call("get", "/api/account/addresses")["items"]
        self.assertEqual([i["id"] for i in items if i["is_default"]], [second["id"]])
        self.call("patch", f"/api/account/addresses/{second['id']}", {"street": "120 Lê Lợi"}, expect=200)
        self.call("patch", f"/api/account/addresses/{second['id']}", {"phone": "123"}, expect=422)
        self.call("delete", f"/api/account/addresses/{second['id']}", expect=200)
        left = self.call("get", "/api/account/addresses")["items"]
        self.assertEqual((len(left), left[0]["is_default"]), (1, True))  # mặc định chuyển sang địa chỉ còn lại
        stranger = self.app.test_client()
        self.register("la@example.com", client=stranger)
        self.call("delete", f"/api/account/addresses/{first['id']}", client=stranger, expect=404)

    def test_wishlist(self):
        pid = self.call("get", "/api/products/ao-thun-cotton-essential")["product"]["id"]
        self.call("post", "/api/account/wishlist", {"product_id": pid}, expect=201)
        self.call("post", "/api/account/wishlist", {"product_id": pid}, expect=201)  # idempotent
        self.call("post", "/api/account/wishlist", {"product_id": 99999}, expect=404)
        items = self.call("get", "/api/account/wishlist")["items"]
        self.assertEqual([i["id"] for i in items], [pid])
        listing = self.call("get", "/api/products?q=essential")["items"]
        self.assertTrue(listing[0]["in_wishlist"])
        self.call("delete", f"/api/account/wishlist/{pid}", expect=200)
        self.assertEqual(self.call("get", "/api/account/wishlist")["total"], 0)

    def _place_order(self, qty=2):
        self.add_to_cart(self.variant_id(), qty)
        return self.call("post", "/api/orders", {**self.SHIPPING, "save_as_default": True}, expect=201)["order"]

    def test_orders_list_cancel_reorder(self):
        order = self._place_order()
        saved = self.call("get", "/api/account/addresses")["items"]
        self.assertEqual((len(saved), saved[0]["street"]), (1, "28 Nguyễn Thị Minh Khai"))  # lưu từ checkout
        listing = self.call("get", "/api/account/orders?status=processing")
        self.assertEqual([o["code"] for o in listing["items"]], [order["code"]])
        self.assertEqual(self.call("get", "/api/account/orders?status=delivered")["total"], 0)
        self.assertEqual(self.call("get", f"/api/account/orders?q={order['code'][-6:]}")["total"], 1)
        self.assertEqual(self.call("get", "/api/account/orders?q=thun")["total"], 1)
        self.call("get", "/api/account/orders?status=khac", expect=400)

        cancelled = self.call("post", f"/api/account/orders/{order['code']}/cancel", {}, expect=200)["order"]
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual([e["status"] for e in cancelled["events"]], ["pending", "cancelled"])
        self.call("post", f"/api/account/orders/{order['code']}/cancel", {}, expect=409)
        stock = next(s["stock"] for c in self.call("get", "/api/products/ao-thun-cotton-essential")["product"]["colors"]
                     for s in c["sizes"] if s["size"] == "M" and c["slug"] == "trang")
        self.assertEqual(stock, 25)  # kho được hoàn lại

        cart = self.call("post", f"/api/account/orders/{order['code']}/reorder", {}, expect=200)
        self.assertEqual(cart["cart"]["item_count"], 2)
        self.assertEqual(cart["skipped"], [])

    def test_cannot_touch_other_users_orders(self):
        order = self._place_order(1)
        other = self.app.test_client()
        self.register("la@example.com", client=other)
        self.call("post", f"/api/account/orders/{order['code']}/cancel", {}, client=other, expect=404)
        self.call("get", f"/api/orders/{order['code']}", client=other, expect=404)
        self.call("get", f"/api/orders/{order['code']}", expect=200)

    def test_delivered_order_marks_review_verified(self):
        order = self._place_order(1)
        conn = connect(self.db_path)
        conn.execute("UPDATE orders SET status = 'delivered' WHERE code = ?", (order["code"],))
        conn.close()
        self.call("post", f"/api/account/orders/{order['code']}/cancel", {}, expect=409)
        res = self.call("post", "/api/products/ao-thun-cotton-essential/reviews", {"rating": 5, "body": "Rất đẹp"}, expect=201)
        self.assertTrue(res["review"]["verified"])


def make_admin(case, email="shop@example.com"):
    """Tạo client đã đăng nhập bằng tài khoản admin (admin không có API đăng ký, nên sửa role trực tiếp trong DB)."""
    client = case.app.test_client()
    case.register(email, client=client)
    conn = connect(case.db_path)
    conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
    conn.close()
    return client


class TrackingTests(ApiTestCase):
    def _order(self):
        self.register()
        self.add_to_cart(self.variant_id(), 1)
        return self.call("post", "/api/orders", self.SHIPPING, expect=201)["order"]

    def test_tracking_follows_status_column(self):
        order = self._order()
        code = order["code"]
        t = self.call("get", f"/api/orders/{code}/tracking", expect=200)["tracking"]
        self.assertEqual((t["status"], t["current_step"]), ("pending", 0))
        self.assertEqual([s["state"] for s in t["steps"]], ["current", "upcoming", "upcoming", "upcoming"])
        self.assertIsNone(t["tracking_number"])
        self.assertIn("estimated_delivery", t)

        # Đổi cột status trong DB -> tracking hiện đúng trạng thái tương ứng.
        conn = connect(self.db_path)
        conn.execute("UPDATE orders SET status = 'shipping' WHERE code = ?", (code,))
        conn.close()
        t = self.call("get", f"/api/orders/{code}/tracking")["tracking"]
        self.assertEqual([s["state"] for s in t["steps"]], ["done", "done", "current", "upcoming"])
        self.assertEqual(t["status_label"], "Đang giao hàng")
        self.assertTrue(t["tracking_number"].startswith("FX"))

    def test_tracking_is_private(self):
        code = self._order()["code"]
        self.call("get", f"/api/orders/{code}/tracking", client=self.app.test_client(), expect=404)
        self.call("get", "/api/orders/FR000000000/tracking", expect=404)

    def test_simulate_advance_to_delivered(self):
        code = self._order()["code"]
        res = self.call("post", f"/api/orders/{code}/simulate", {}, expect=200)
        self.assertEqual(res["order"]["status"], "preparing")
        res = self.call("post", f"/api/orders/{code}/simulate", {"to": "delivered"}, expect=200)
        order, t = res["order"], res["tracking"]
        self.assertEqual([e["status"] for e in order["events"]], ["pending", "preparing", "shipping", "delivered"])
        self.assertTrue(t["is_delivered"])
        self.assertEqual([s["state"] for s in t["steps"]], ["done"] * 4)
        self.assertEqual((order["payment_status"], bool(order["delivered_at"])), ("paid", True))  # COD thu khi giao
        self.call("post", f"/api/orders/{code}/simulate", {}, expect=409)  # đã giao xong
        self.call("post", f"/api/orders/{code}/simulate", {"to": "pending"}, expect=409)

    def test_simulate_rejects_bad_target_and_cancelled(self):
        code = self._order()["code"]
        bad = self.call("post", f"/api/orders/{code}/simulate", {"to": "pending"}, expect=422)
        self.assertEqual(bad["error"]["code"], "invalid_status")
        self.call("post", f"/api/account/orders/{code}/cancel", {}, expect=200)
        t = self.call("get", f"/api/orders/{code}/tracking")["tracking"]
        self.assertTrue(t["is_cancelled"])
        self.assertEqual([s["state"] for s in t["steps"]], ["done", "cancelled"])
        self.call("post", f"/api/orders/{code}/simulate", {}, expect=409)

    def test_simulation_can_be_disabled(self):
        code = self._order()["code"]
        self.app.config["ORDER_SIMULATION"] = False
        self.call("post", f"/api/orders/{code}/simulate", {}, expect=403)
        # admin vẫn được phép dù mô phỏng đang tắt, và xem được đơn của khách
        shop = make_admin(self)
        res = self.call("post", f"/api/orders/{code}/simulate", {}, client=shop, expect=200)
        self.assertEqual(res["order"]["status"], "preparing")
        self.assertEqual(self.call("get", f"/api/orders/{code}/tracking")["tracking"]["status"], "preparing")


class ChatTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.shop = make_admin(self)
        self.register()  # self.client = khách

    def test_requires_login_and_admin(self):
        anon = self.app.test_client()
        self.call("get", "/api/chat/messages", client=anon, expect=401)
        self.call("post", "/api/chat/messages", {"body": "hi"}, client=anon, expect=401)
        self.call("get", "/api/shop/chat/conversations", client=anon, expect=401)
        self.call("get", "/api/shop/chat/conversations", expect=403)  # khách thường không vào được phía shop
        self.call("post", "/api/shop/chat/conversations/1/messages", {"body": "x"}, expect=403)

    def test_customer_to_shop_and_back(self):
        self.assertIsNone(self.call("get", "/api/chat/conversation", expect=200)["conversation"])
        self.assertEqual(self.call("get", "/api/chat/messages")["items"], [])
        self.call("post", "/api/chat/messages", {"body": "   "}, expect=422)
        sent = self.call("post", "/api/chat/messages", {"body": "Shop ơi còn size M không?"}, expect=201)
        conv_id = sent["conversation_id"]
        self.assertTrue(sent["message"]["is_mine"])
        self.call("post", "/api/chat/messages", {"body": "Mình cần gấp ạ"}, expect=201)

        # Shop thấy hội thoại với 2 tin chưa đọc
        inbox = self.call("get", "/api/shop/chat/conversations", client=self.shop, expect=200)
        self.assertEqual((inbox["total"], inbox["items"][0]["unread"]), (1, 2))
        self.assertEqual(inbox["items"][0]["customer"]["email"], "minhanh@example.com")
        self.assertEqual(self.call("get", "/api/shop/chat/unread", client=self.shop)["unread"], 2)
        self.assertEqual(self.call("get", "/api/shop/chat/conversations?unread=1", client=self.shop)["total"], 1)
        self.assertEqual(self.call("get", "/api/shop/chat/conversations?q=minh+anh", client=self.shop)["total"], 1)
        self.assertEqual(self.call("get", "/api/shop/chat/conversations?q=khongco", client=self.shop)["total"], 0)

        msgs = self.call("get", f"/api/shop/chat/conversations/{conv_id}/messages", client=self.shop)
        self.assertEqual([m["body"] for m in msgs["items"]], ["Shop ơi còn size M không?", "Mình cần gấp ạ"])
        self.assertFalse(msgs["items"][0]["is_mine"])
        self.assertEqual(msgs["unread"], 0)  # đọc xong là hết chưa đọc
        self.assertEqual(self.call("get", "/api/shop/chat/unread", client=self.shop)["unread"], 0)

        self.call("post", f"/api/shop/chat/conversations/{conv_id}/messages", {"body": "Còn nhé bạn!"}, client=self.shop, expect=201)
        self.call("post", "/api/shop/chat/conversations/999/messages", {"body": "x"}, client=self.shop, expect=404)

        # Khách thấy 1 tin chưa đọc, đọc xong thì shop thấy tin của mình đã được đọc
        self.assertEqual(self.call("get", "/api/chat/unread")["unread"], 1)
        self.assertEqual(self.call("get", "/api/chat/conversation")["conversation"]["unread"], 1)
        mine = self.call("get", "/api/chat/messages")
        self.assertEqual([m["sender"] for m in mine["items"]], ["customer", "customer", "shop"])
        self.assertEqual(mine["unread"], 0)
        again = self.call("get", f"/api/shop/chat/conversations/{conv_id}/messages", client=self.shop)
        self.assertTrue(again["items"][-1]["is_mine"])
        self.assertTrue(again["items"][0]["read"] is True)  # tin khách gửi: shop đã đọc

    def test_polling_and_paging(self):
        for i in range(5):
            self.call("post", "/api/chat/messages", {"body": f"tin {i}"}, expect=201)
        newest = self.call("get", "/api/chat/messages?limit=2")
        self.assertEqual([m["body"] for m in newest["items"]], ["tin 3", "tin 4"])
        self.assertTrue(newest["has_more"])
        older = self.call("get", f"/api/chat/messages?limit=2&before_id={newest['items'][0]['id']}")
        self.assertEqual([m["body"] for m in older["items"]], ["tin 1", "tin 2"])
        last_id = newest["items"][-1]["id"]
        self.assertEqual(self.call("get", f"/api/chat/messages?after_id={last_id}")["items"], [])
        self.call("post", "/api/chat/messages", {"body": "tin 5"}, expect=201)
        fresh = self.call("get", f"/api/chat/messages?after_id={last_id}")
        self.assertEqual([m["body"] for m in fresh["items"]], ["tin 5"])
        self.call("get", "/api/chat/messages?after_id=1&before_id=3", expect=400)

    def test_attach_order_and_product(self):
        self.add_to_cart(self.variant_id(), 1)
        code = self.call("post", "/api/orders", self.SHIPPING, expect=201)["order"]["code"]
        res = self.call(
            "post", "/api/chat/messages",
            {"body": "Đơn này bao giờ giao?", "order_code": code.lower(), "product_slug": "ao-thun-cotton-essential"},
            expect=201,
        )["message"]
        self.assertEqual(res["order_code"], code)
        self.assertEqual(res["product"]["slug"], "ao-thun-cotton-essential")
        self.call("post", "/api/chat/messages", {"body": "x", "order_code": "FR000000000"}, expect=404)
        self.call("post", "/api/chat/messages", {"body": "x", "product_slug": "khong-co"}, expect=404)
        # đơn của người khác không gắn được
        other = self.app.test_client()
        self.register("la@example.com", client=other)
        self.call("post", "/api/chat/messages", {"body": "x", "order_code": code}, client=other, expect=404)

    def test_each_customer_has_own_conversation(self):
        self.call("post", "/api/chat/messages", {"body": "của khách 1"}, expect=201)
        other = self.app.test_client()
        self.register("la@example.com", client=other)
        self.assertEqual(self.call("get", "/api/chat/messages", client=other)["items"], [])
        self.call("post", "/api/chat/messages", {"body": "của khách 2"}, client=other, expect=201)
        inbox = self.call("get", "/api/shop/chat/conversations", client=self.shop)
        self.assertEqual(inbox["total"], 2)
        self.assertEqual(inbox["items"][0]["last_message"]["body"], "của khách 2")  # mới nhất lên đầu


class ReviewManagementTests(ApiTestCase):
    SLUG = "ao-thun-cotton-essential"

    def setUp(self):
        super().setUp()
        self.register()

    def _delivered_order(self):
        self.add_to_cart(self.variant_id(), 1)
        code = self.call("post", "/api/orders", self.SHIPPING, expect=201)["order"]["code"]
        self.call("post", f"/api/orders/{code}/simulate", {"to": "delivered"}, expect=200)
        return code

    def test_pending_and_can_review_flow(self):
        code = self._delivered_order()
        order = self.call("get", f"/api/orders/{code}")["order"]
        self.assertEqual([(i["can_review"], i["reviewed"]) for i in order["items"]], [(True, False)])
        mine = self.call("get", "/api/account/reviews", expect=200)
        self.assertEqual(mine["items"], [])
        self.assertEqual([(p["slug"], p["order_code"]) for p in mine["pending"]], [(self.SLUG, code)])

        self.call("post", f"/api/products/{self.SLUG}/reviews", {"rating": 5, "body": "Rất đẹp"}, expect=201)
        order = self.call("get", f"/api/orders/{code}")["order"]
        self.assertEqual([(i["can_review"], i["reviewed"]) for i in order["items"]], [(False, True)])
        mine = self.call("get", "/api/account/reviews")
        self.assertEqual((len(mine["items"]), mine["pending"]), (1, []))
        self.assertEqual(mine["items"][0]["product"]["slug"], self.SLUG)
        self.assertTrue(mine["items"][0]["verified"])

    def test_undelivered_order_cannot_be_reviewed_from_order(self):
        self.add_to_cart(self.variant_id(), 1)
        code = self.call("post", "/api/orders", self.SHIPPING, expect=201)["order"]["code"]
        order = self.call("get", f"/api/orders/{code}")["order"]
        self.assertFalse(order["items"][0]["can_review"])
        self.assertEqual(self.call("get", "/api/account/reviews")["pending"], [])

    def test_update_and_delete_own_review(self):
        res = self.call("post", f"/api/products/{self.SLUG}/reviews", {"rating": 3, "fit": 2, "title": "Tạm", "body": "Hơi chật"}, expect=201)
        rid = res["review"]["id"]
        self.assertTrue(res["review"]["is_mine"])
        self.call("patch", f"/api/reviews/{rid}", {}, expect=400)
        self.call("patch", f"/api/reviews/{rid}", {"rating": 7}, expect=422)
        edited = self.call("patch", f"/api/reviews/{rid}", {"rating": 5, "body": "Giặt xong form đẹp", "title": None}, expect=200)
        self.assertEqual((edited["review"]["rating"], edited["review"]["fit"], edited["review"]["title"]), (5, 2, None))
        self.assertEqual(edited["summary"]["average"], 5.0)

        # người khác và khách vãng lai không sửa/xóa được; người khác xem thì is_mine = False
        other = self.app.test_client()
        self.register("la@example.com", client=other)
        self.call("patch", f"/api/reviews/{rid}", {"rating": 1}, client=other, expect=404)
        self.call("delete", f"/api/reviews/{rid}", client=other, expect=404)
        self.assertFalse(self.call("get", f"/api/products/{self.SLUG}/reviews", client=other)["items"][0]["is_mine"])
        self.call("delete", f"/api/reviews/{rid}", client=self.app.test_client(), expect=401)

        gone = self.call("delete", f"/api/reviews/{rid}", expect=200)
        self.assertEqual(gone["summary"]["count"], 0)
        self.call("delete", f"/api/reviews/{rid}", expect=404)
        # xóa xong được đánh giá lại
        self.call("post", f"/api/products/{self.SLUG}/reviews", {"rating": 4, "body": "Đánh giá lại"}, expect=201)


class LocationTests(ApiTestCase):
    def test_provinces_and_wards(self):
        provinces = self.call("get", "/api/provinces", expect=200)["items"]
        self.assertEqual(len(provinces), 3)
        code = next(p["code"] for p in provinces if p["name"] == "Hà Nội")
        self.assertGreater(len(self.call("get", f"/api/provinces/{code}/wards")["items"]), 0)
        self.call("get", "/api/provinces/000/wards", expect=404)


if __name__ == "__main__":
    unittest.main()
