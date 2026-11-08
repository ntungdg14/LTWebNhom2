"""Kiểm thử đăng ký / đăng nhập / đăng xuất, CSRF, giới hạn đăng nhập sai và phân quyền.

Chạy: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import re
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from app import create_app
from app.common.helpers import safe_next_url
from app.db import connect

try:
    from .support import ADMIN_EMAIL, CUSTOMER_EMAIL, PASSWORD, add_user, csrf_token, login, make_app, remove_db
except ImportError:  # chạy bằng: python -m unittest discover -s tests
    from support import ADMIN_EMAIL, CUSTOMER_EMAIL, PASSWORD, add_user, csrf_token, login, make_app, remove_db

PROTECTED_PAGES = (
    "/cart",
    "/checkout/shipping",
    "/checkout",
    "/order-success",
    "/account",
    "/account/orders",
    "/account/orders/FR261101028",
    "/account/address",
    "/account/wishlist",
)
PUBLIC_PAGES = ("/", "/shop", "/shop?q=ao&sort=price", "/product?sku=FR-BOM-002", "/terms", "/privacy", "/help",
                "/login", "/register", "/forgot-password")
PUBLIC_API = ("/api/home", "/api/products", "/api/categories", "/api/colors", "/api/provinces", "/api/checkout/options")


def login_redirect(location: str) -> tuple[str, str | None]:
    """Tách Location kiểu /login?next=... thành (đường dẫn, giá trị next đã giải mã)."""
    parts = urlsplit(location)
    return parts.path, (parse_qs(parts.query).get("next") or [None])[0]


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app, self.db_path = make_app(with_seed=True)
        add_user(self.db_path, CUSTOMER_EMAIL, name="Khách Hàng")
        add_user(self.db_path, ADMIN_EMAIL, role="admin", name="Quản Trị Viên")
        self.client = self.app.test_client()

    def tearDown(self):
        remove_db(self.db_path)

    # ---- tiện ích
    def db(self):
        return connect(self.db_path)

    def count(self, sql, *params):
        conn = self.db()
        try:
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()

    def register_form(self, client=None, **overrides):
        client = client or self.client
        data = {
            "full_name": "Nguyễn Minh Anh", "email": "minhanh@example.com", "password": PASSWORD,
            "password_confirmation": PASSWORD, "terms": "1", "csrf_token": csrf_token(client, "/register"),
            **overrides,
        }
        return client.post("/register", data={k: v for k, v in data.items() if v is not None})

    def logged_in(self, email=CUSTOMER_EMAIL):
        client = self.app.test_client()
        response = login(client, email)
        self.assertEqual(response.status_code, 302)
        return client


class RegisterTests(AuthTestCase):
    def test_success_redirects_to_login_without_logging_in(self):
        response = self.register_form()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))
        page = self.client.get("/login").get_data(as_text=True)
        self.assertIn("Đăng ký thành công, vui lòng đăng nhập", page)
        self.assertIn("alert-success", page)
        # không tự đăng nhập: vào trang cần đăng nhập vẫn bị chuyển về /login
        self.assertEqual(self.client.get("/account").status_code, 302)
        self.assertIsNone(self.client.get("/api/auth/me").get_json()["user"])

    def test_password_is_hashed_and_email_normalized(self):
        self.register_form(email="  MinhAnh@Example.COM ")
        conn = self.db()
        row = conn.execute("SELECT email, password_hash, role FROM users WHERE full_name = 'Nguyễn Minh Anh'").fetchone()
        conn.close()
        self.assertEqual(row["email"], "minhanh@example.com")
        self.assertNotEqual(row["password_hash"], PASSWORD)
        self.assertNotIn(PASSWORD, row["password_hash"])
        self.assertEqual(row["role"], "customer")

    def test_duplicate_email_is_case_insensitive(self):
        self.register_form(email="Khach@Example.com")
        response = self.register_form(email="  KHACH@example.COM")
        self.assertEqual(response.status_code, 422)
        self.assertIn("Email này đã được đăng ký.", response.get_data(as_text=True))
        self.assertEqual(self.count("SELECT COUNT(*) FROM users WHERE email = ?", CUSTOMER_EMAIL), 1)

    def test_validation_errors_are_shown_per_field_and_input_is_kept(self):
        cases = {
            "weak": ({"password": "yeu", "password_confirmation": "yeu"}, "Mật khẩu cần ít nhất 8 ký tự"),
            "mismatch": ({"password_confirmation": "Khac12345"}, "Mật khẩu xác nhận không khớp."),
            "terms": ({"terms": None}, "Bạn cần đồng ý với Điều khoản sử dụng"),
            "name": ({"full_name": "  "}, "Họ và tên là bắt buộc."),
            "email": ({"email": "khong-hop-le"}, "Email không hợp lệ."),
        }
        for name, (overrides, message) in cases.items():
            with self.subTest(case=name):
                response = self.register_form(**overrides)
                html = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 422)
                self.assertIn(message, html)
                self.assertIn("field-error", html)
                self.assertIn('value="minhanh@example.com"' if name != "email" else 'value="khong-hop-le"', html)
                self.assertNotIn(PASSWORD, html)  # không điền lại mật khẩu
        self.assertEqual(self.count("SELECT COUNT(*) FROM users WHERE email = 'minhanh@example.com'"), 0)

    def test_concurrent_duplicate_is_handled_as_form_error(self):
        """Hai request đồng thời: pre-check không thấy email, INSERT mới báo IntegrityError -> không được 500."""
        from app.db import get_db as real_get_db

        class BlindDb:
            def __init__(self, db):
                self.db = db

            def execute(self, sql, params=()):
                if sql.startswith("SELECT 1 FROM users"):
                    return self.db.execute("SELECT 1 WHERE 0")
                return self.db.execute(sql, params)

        with mock.patch("app.blueprints.auth.routes.get_db", lambda: BlindDb(real_get_db())):
            response = self.register_form(email=CUSTOMER_EMAIL)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Email này đã được đăng ký.", response.get_data(as_text=True))

    def test_api_register_still_logs_in(self):
        response = self.client.post("/api/auth/register", json={"full_name": "A", "email": "a@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["email"], "a@example.com")

    def test_logged_in_user_is_redirected_away(self):
        client = self.logged_in()
        for url in ("/login", "/register"):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/")


class LoginTests(AuthTestCase):
    def post_login(self, email=CUSTOMER_EMAIL, password=PASSWORD, **extra):
        return login(self.client, email, password, **extra)

    def test_success_goes_home_and_sets_session(self):
        response = self.post_login()
        self.assertEqual((response.status_code, response.headers["Location"]), (302, "/"))
        self.assertEqual(self.client.get("/account").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["email"], CUSTOMER_EMAIL)

    def test_email_is_case_insensitive_and_trimmed(self):
        self.assertEqual(self.post_login(email="  KHACH@Example.com ").status_code, 302)

    def test_wrong_credentials_share_one_generic_message(self):
        wrong_password = self.post_login(password="SaiMatKhau1")
        unknown_email = self.post_login(email="ghost@example.com")
        for response in (wrong_password, unknown_email):
            self.assertEqual(response.status_code, 401)
            self.assertIn("Email hoặc mật khẩu không đúng", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/account").status_code, 302)

    def test_dummy_hash_is_checked_for_unknown_email(self):
        with mock.patch("app.blueprints.auth.routes.check_password_hash", return_value=False) as check:
            self.post_login(email="ghost@example.com")
        self.assertEqual(check.call_count, 1)

    def test_valid_next_is_followed(self):
        token = csrf_token(self.client, "/login?next=/account/orders")
        response = self.client.post("/login", data={
            "email": CUSTOMER_EMAIL, "password": PASSWORD, "csrf_token": token, "next": "/account/orders?page=2",
        })
        self.assertEqual(response.headers["Location"], "/account/orders?page=2")

    def test_login_form_carries_next(self):
        html = self.client.get("/login?next=/account/address").get_data(as_text=True)
        self.assertIn('name="next" value="/account/address"', html)

    def test_external_next_is_ignored(self):
        for bad in ("//evil.com", "https://evil.com/x", "/\\evil.com", "javascript:alert(1)", "evil.com"):
            with self.subTest(next=bad):
                client = self.app.test_client()
                response = login(client, CUSTOMER_EMAIL, next=bad)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/")

    def test_safe_next_url_rules(self):
        self.assertEqual(safe_next_url("/cart?x=1"), "/cart?x=1")
        for bad in (None, "", "cart", "//evil.com", "/\\evil.com", "http://evil.com", "/ok\r\nSet-Cookie: a=b", "/a\tb", 5):
            self.assertIsNone(safe_next_url(bad), bad)

    def test_remember_controls_cookie_lifetime(self):
        remembered = self.post_login(remember="1")
        self.assertIn("Expires=", remembered.headers["Set-Cookie"])
        other = self.app.test_client()
        session_only = login(other, CUSTOMER_EMAIL)
        self.assertNotIn("Expires=", session_only.headers["Set-Cookie"])

    def test_missing_fields_show_field_errors(self):
        response = self.post_login(email="", password="")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Email là bắt buộc.", html)
        self.assertIn("Mật khẩu là bắt buộc.", html)

    def test_session_cookie_flags(self):
        cookie = self.post_login().headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)


class LogoutTests(AuthTestCase):
    def test_logout_is_post_only_with_csrf(self):
        client = self.logged_in()
        self.assertEqual(client.get("/logout").status_code, 405)
        self.assertEqual(client.post("/logout").status_code, 400)  # thiếu CSRF
        self.assertEqual(client.get("/account").status_code, 200)  # vẫn đăng nhập

    def test_logout_clears_session_and_flashes(self):
        client = self.logged_in()
        response = client.post("/logout", data={"csrf_token": csrf_token(client, "/")})
        self.assertEqual((response.status_code, response.headers["Location"]), (302, "/"))
        self.assertIn("Bạn đã đăng xuất", client.get("/").get_data(as_text=True))
        for url in ("/cart", "/account"):
            self.assertEqual(client.get(url).status_code, 302, url)
        self.assertEqual(client.get("/api/cart").status_code, 401)


class CsrfTests(AuthTestCase):
    def test_missing_or_wrong_token_is_rejected(self):
        self.client.get("/login")  # tạo token trong session
        forms = (
            ("/login", {"email": CUSTOMER_EMAIL, "password": PASSWORD}),
            ("/register", {"full_name": "A", "email": "a@example.com", "password": PASSWORD,
                           "password_confirmation": PASSWORD, "terms": "1"}),
        )
        for url, data in forms:
            for label, extra in (("thiếu", {}), ("sai", {"csrf_token": "sai-token"}), ("rỗng", {"csrf_token": ""})):
                with self.subTest(url=url, token=label):
                    self.assertEqual(self.client.post(url, data={**data, **extra}).status_code, 400)
        self.assertEqual(self.count("SELECT COUNT(*) FROM users WHERE email = 'a@example.com'"), 0)
        self.assertEqual(self.client.get("/account").status_code, 302)

    def test_token_without_session_is_rejected(self):
        token = csrf_token(self.client, "/login")
        fresh = self.app.test_client()  # không có cookie phiên
        response = fresh.post("/login", data={"email": CUSTOMER_EMAIL, "password": PASSWORD, "csrf_token": token})
        self.assertEqual(response.status_code, 400)

    def test_admin_forms_require_csrf(self):
        admin = self.logged_in(ADMIN_EMAIL)
        self.assertEqual(admin.post("/admin/users/new", data={"name": "x"}).status_code, 400)
        ok = admin.post("/admin/users/new", data={"name": "x", "csrf_token": csrf_token(admin, "/")})
        self.assertEqual(ok.status_code, 302)

    def test_header_forms_render_token(self):
        html = self.logged_in().get("/").get_data(as_text=True)
        self.assertIn('name="csrf_token"', html)

    def test_json_api_is_not_subject_to_form_csrf(self):
        response = self.client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)


class RateLimitTests(AuthTestCase):
    def fail(self, client, times, email=CUSTOMER_EMAIL):
        return [login(client, email, "SaiMatKhau1").status_code for _ in range(times)]

    def test_five_failures_lock_even_correct_password(self):
        self.assertEqual(self.fail(self.client, 5), [401] * 5)
        response = login(self.client, CUSTOMER_EMAIL, PASSWORD)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Thử lại sau", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/account").status_code, 302)
        self.assertEqual(self.count("SELECT COUNT(*) FROM login_attempts"), 5)  # lần bị khóa không ghi thêm

    def test_lock_is_per_email(self):
        self.fail(self.client, 5)
        other = self.app.test_client()
        self.assertEqual(login(other, ADMIN_EMAIL).status_code, 302)

    def test_unknown_email_is_limited_too(self):
        self.assertEqual(self.fail(self.client, 5, "ghost@example.com"), [401] * 5)
        self.assertEqual(login(self.client, "ghost@example.com", PASSWORD).status_code, 429)

    def test_success_clears_counter(self):
        self.fail(self.client, 4)
        self.assertEqual(login(self.client, CUSTOMER_EMAIL, PASSWORD).status_code, 302)
        self.assertEqual(self.count("SELECT COUNT(*) FROM login_attempts"), 0)
        other = self.app.test_client()
        self.assertEqual(self.fail(other, 4), [401] * 4)  # chưa bị khóa vì bộ đếm đã về 0

    def test_lock_expires_after_15_minutes(self):
        self.fail(self.client, 5)
        conn = self.db()
        conn.execute("UPDATE login_attempts SET attempted_at = attempted_at - 14 * 60")
        conn.close()
        self.assertEqual(login(self.client, CUSTOMER_EMAIL, PASSWORD).status_code, 429)  # còn ~1 phút
        conn = self.db()
        conn.execute("UPDATE login_attempts SET attempted_at = attempted_at - 2 * 60")
        conn.close()
        self.assertEqual(login(self.client, CUSTOMER_EMAIL, PASSWORD).status_code, 302)

    def test_old_failures_do_not_count(self):
        self.fail(self.client, 4)
        conn = self.db()
        conn.execute("UPDATE login_attempts SET attempted_at = attempted_at - 16 * 60")
        conn.close()
        self.assertEqual(self.fail(self.client, 4), [401] * 4)

    def test_api_login_shares_the_limit(self):
        for _ in range(5):
            r = self.client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": "SaiMatKhau1"})
            self.assertEqual(r.status_code, 401)
        r = self.client.post("/api/auth/login", json={"email": CUSTOMER_EMAIL, "password": PASSWORD})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.get_json()["error"]["code"], "too_many_attempts")


class AuthorizationTests(AuthTestCase):
    def test_guest_can_view_public_pages(self):
        for url in PUBLIC_PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_guest_can_use_public_api(self):
        for url in PUBLIC_API:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_protected_pages_redirect_to_login_with_next(self):
        for url in PROTECTED_PAGES + ("/cart?coupon=A&x=1", "/account/orders?status=shipping"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(login_redirect(response.headers["Location"]), ("/login", url))

    def test_redirect_flashes_message_and_login_returns_to_page(self):
        response = self.client.get("/cart")
        self.assertIn("Vui lòng đăng nhập để tiếp tục", self.client.get(response.headers["Location"]).get_data(as_text=True))
        token = csrf_token(self.client, "/login")
        done = self.client.post("/login", data={"email": CUSTOMER_EMAIL, "password": PASSWORD, "csrf_token": token, "next": "/cart"})
        self.assertEqual(done.headers["Location"], "/cart")
        self.assertEqual(self.client.get("/cart").status_code, 200)

    def test_ajax_on_html_route_gets_json_401(self):
        response = self.client.get("/cart", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"]["code"], "unauthorized")

    def test_cart_api_requires_login_with_json_401(self):
        calls = (
            ("get", "/api/cart"), ("delete", "/api/cart"),
            ("post", "/api/cart/items"), ("patch", "/api/cart/items/1"), ("delete", "/api/cart/items/1"),
            ("post", "/api/cart/coupon"), ("delete", "/api/cart/coupon"),
        )
        for method, url in calls:
            with self.subTest(url=url, method=method):
                response = getattr(self.client, method)(url, json={"variant_id": 1, "quantity": 1})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["Content-Type"], "application/json")
                self.assertEqual(response.get_json()["error"]["code"], "unauthorized")
        self.assertEqual(self.count("SELECT COUNT(*) FROM carts"), 0)  # không còn tạo giỏ khách

    def test_every_protected_api_rule_rejects_guests(self):
        prefixes = ("/api/cart", "/api/orders", "/api/account", "/api/chat", "/api/shop/chat")
        checked = 0
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith(prefixes):
                continue
            url = (rule.rule.replace("<int:", "<").replace("<code>", "FR1").replace("<int:item_id>", "1"))
            url = re.sub(r"<[^>]+>", "1", url)
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                with self.subTest(url=url, method=method):
                    response = self.client.open(url, method=method, json={})
                    self.assertEqual(response.status_code, 401, f"{method} {rule.rule}")
                    checked += 1
        self.assertGreater(checked, 20)

    def test_guest_cannot_create_orders(self):
        self.assertEqual(self.client.post("/api/orders", json={}).status_code, 401)
        self.assertEqual(self.client.get("/api/orders/FR261101001").status_code, 401)

    def test_admin_area(self):
        guest = self.client.get("/admin")
        self.assertEqual(guest.status_code, 302)
        self.assertEqual(login_redirect(guest.headers["Location"]), ("/login", "/admin"))
        nested = self.client.get("/admin/users?q=a")
        self.assertEqual(login_redirect(nested.headers["Location"]), ("/login", "/admin/users?q=a"))
        customer = self.logged_in()
        for url in ("/admin", "/admin/products", "/admin/permissions"):
            with self.subTest(url=url):
                self.assertEqual(customer.get(url).status_code, 403)
        admin = self.logged_in(ADMIN_EMAIL)
        for url in ("/admin", "/admin/products", "/admin/permissions"):
            with self.subTest(url=url):
                self.assertEqual(admin.get(url).status_code, 200)

    def test_admin_api_style_response_is_json(self):
        customer = self.logged_in()
        r = customer.get("/admin", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (403, "forbidden"))
        r = self.client.get("/admin", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(r.status_code, 401)

    def test_role_required_decorator_on_api_and_html(self):
        from flask import jsonify

        from app.common.helpers import role_required

        @self.app.get("/api/_t/admin-only")
        @role_required("admin")
        def api_only():
            return jsonify(ok=True)

        @self.app.get("/_t/admin-page")
        @role_required("admin")
        def page_only():
            return "ok"

        self.assertEqual(self.client.get("/api/_t/admin-only").status_code, 401)
        self.assertEqual(self.client.get("/_t/admin-page").status_code, 302)
        customer = self.logged_in()
        self.assertEqual(customer.get("/api/_t/admin-only").status_code, 403)
        self.assertEqual(customer.get("/_t/admin-page").status_code, 403)
        admin = self.logged_in(ADMIN_EMAIL)
        self.assertEqual(admin.get("/api/_t/admin-only").status_code, 200)
        self.assertEqual(admin.get("/_t/admin-page").status_code, 200)


class AuthUiTests(AuthTestCase):
    def test_guest_header_and_product_buttons(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/login">Đăng nhập</a>', html)
        self.assertIn('href="/register">Đăng ký</a>', html)
        self.assertNotIn("Đăng xuất", html)
        self.assertEqual(html.count('class="nav-action"'), 3)
        product = self.client.get("/product?sku=FR-BOM-002&size=M").get_data(as_text=True)
        links = re.findall(r'href="(/login\?next=[^"]+)"', product.replace("&amp;", "&"))
        self.assertEqual(len(links), 2)  # "Thêm vào giỏ hàng" và "Mua ngay"
        for link in links:
            self.assertEqual(login_redirect(link), ("/login", "/product?sku=FR-BOM-002&size=M"))
        self.assertIn("Thêm vào giỏ hàng", product)
        self.assertIn("Mua ngay", product)

    def test_member_header_shows_name_and_logout_form(self):
        html = self.logged_in().get("/").get_data(as_text=True)
        self.assertIn("Khách Hàng", html)
        self.assertIn('action="/logout" method="post"', html)
        self.assertNotIn('href="/login">Đăng nhập</a>', html)

    def test_long_name_is_truncated_in_header(self):
        add_user(self.db_path, "dai@example.com", name="Nguyễn Thị Rất Rất Rất Dài Họ Tên Đầy Đủ")
        client = self.app.test_client()
        login(client, "dai@example.com")
        html = client.get("/").get_data(as_text=True)
        self.assertIn("…</a>", html)

    def test_admin_link_in_account_sidebar_only_for_admin(self):
        self.assertIn('href="/admin"', self.logged_in(ADMIN_EMAIL).get("/account").get_data(as_text=True).split("account-nav", 1)[1])
        sidebar = self.logged_in().get("/account").get_data(as_text=True).split("account-nav", 1)[1].split("</aside>", 1)[0]
        self.assertNotIn('href="/admin"', sidebar)
        self.assertIn('action="/logout"', sidebar)
        self.assertIn("Khách Hàng", sidebar)

    def test_flash_is_shown_on_store_and_auth_layouts(self):
        client = self.logged_in()
        client.post("/logout", data={"csrf_token": csrf_token(client, "/")})
        self.assertIn("alert-success", client.get("/login").get_data(as_text=True))  # đã nằm trong session -> hiện ở base_auth
        client.post("/logout", data={"csrf_token": csrf_token(client, "/login")})
        self.assertIn("alert-success", client.get("/shop").get_data(as_text=True))  # base_store


class ConfigTests(unittest.TestCase):
    def test_production_requires_secret_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            with self.assertRaises(RuntimeError):
                create_app("production")
        with mock.patch.dict(os.environ, {"SECRET_KEY": "dev-only-change-me"}):
            with self.assertRaises(RuntimeError):
                create_app("production")

    def test_production_uses_env_secret_and_secure_cookie(self):
        with mock.patch.dict(os.environ, {"SECRET_KEY": "x" * 40, "DATABASE": ":memory:"}):
            app = create_app("production")
        self.assertEqual(app.config["SECRET_KEY"], "x" * 40)
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_development_has_default_secret(self):
        self.assertTrue(create_app("development").config["SECRET_KEY"])


if __name__ == "__main__":
    unittest.main()
