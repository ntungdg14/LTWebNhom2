"""Kiểm thử hồi quy cho cấu trúc Flask, đường dẫn, biểu mẫu và header.

Chạy: python -m unittest discover -s tests -v
(Không cần pytest, chỉ dùng Flask test_client và unittest có sẵn.)
"""
from __future__ import annotations

import atexit
import os
import re
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import connect, init_db
from app.seed import seed

STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"

PAGES = (
    "/",
    "/shop",
    "/product",
    "/cart",
    "/checkout/shipping",
    "/checkout",
    "/order-success",
    "/login",
    "/register",
    "/forgot-password",
    "/terms",
    "/privacy",
    "/help",
    "/account",
    "/account/orders",
    "/account/orders/FR261101028",
    "/account/address",
    "/account/wishlist",
    "/admin",
    "/admin/products",
    "/admin/products/new",
    "/admin/products/FR-BOM-002/edit",
    "/admin/categories",
    "/admin/categories/new",
    "/admin/orders",
    "/admin/orders/FR10285",
    "/admin/users",
    "/admin/users/new",
    "/admin/users/KH00057",
    "/admin/permissions",
    "/admin/inventory",
    "/admin/promotions",
    "/admin/reports",
)

STORE_LAYOUT_PAGES = PAGES[:18]  # các trang dùng base_store.html (trừ 17 trang admin)
ADMIN_PAGES = PAGES[18:]



def logged_in_client():
    """Client đã đăng nhập (dùng DB tạm, không đụng instance/freesion.db): /account bắt buộc đăng nhập."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    def cleanup():
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(db_path + suffix)
            except FileNotFoundError:
                pass

    atexit.register(cleanup)
    app = create_app("testing")
    app.config["DATABASE"] = db_path
    with app.app_context():
        init_db()
    conn = connect(db_path)
    seed(conn)
    conn.close()
    client = app.test_client()
    res = client.post("/api/auth/register", json={
        "full_name": "Nguyễn Minh Anh", "email": "minhanh@example.com",
        "phone": "090 123 4567", "password": "Matkhau123",
    })
    assert res.status_code == 201, res.get_data(as_text=True)
    return client


STYLESHEET_RE = re.compile(r'<link rel="stylesheet" href="([^"]+)"')
INTERNAL_LINK_RE = re.compile(r'(?:href|action)="([^"]*)"')


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = logged_in_client()

    def test_blueprints_registered(self):
        expected = {"store", "auth", "account", "checkout", "admin"}
        self.assertTrue(expected.issubset(set(self.app.blueprints)))

    def test_every_page_renders(self):
        for url in PAGES:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"<!DOCTYPE html>", response.data)

    def test_url_rules_are_unique(self):
        rules = [rule.rule for rule in self.app.url_map.iter_rules()]
        self.assertEqual(len(rules), len(set(rules)), "có route trùng lặp")

    def test_all_internal_links_resolve(self):
        """Rà soát toàn bộ href/action nội bộ trên mọi trang: không link hỏng."""
        links = set()
        for url in PAGES:
            html = self.client.get(url).get_data(as_text=True)
            for href in INTERNAL_LINK_RE.findall(html):
                # /logout chuyển hướng (302) và xóa phiên, đã có test riêng ở AccountGuardTests.
                if href.startswith("/") and not href.startswith("//") and href != "/logout":
                    links.add(href.replace("&amp;", "&"))
        self.assertGreater(len(links), 100)
        for href in sorted(links):
            with self.subTest(href=href):
                response = self.client.get(href)
                status = response.status_code
                response.close()
                self.assertEqual(status, 200, href)

    def test_no_placeholder_or_external_links(self):
        for url in PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                for href in INTERNAL_LINK_RE.findall(html):
                    self.assertNotEqual(href, "#", url)
                    self.assertFalse(href.startswith(("http://", "https://", "//")), url)
                    self.assertNotIn("javascript:", href)

    def test_stylesheets_are_local_and_exist(self):
        for url in PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                links = STYLESHEET_RE.findall(html)
                self.assertTrue(links, "trang không nạp CSS nào")
                for href in links:
                    self.assertTrue(href.startswith("/static/css/"), href)
                    self.assertTrue(
                        (STATIC_DIR / href.removeprefix("/static/")).is_file(),
                        f"thiếu file CSS: {href}",
                    )

    def test_shared_and_page_layers_are_loaded(self):
        for url in PAGES:
            with self.subTest(url=url):
                links = STYLESHEET_RE.findall(self.client.get(url).get_data(as_text=True))
                self.assertIn("/static/css/base.css", links)
                self.assertIn("/static/css/components.css", links)
                self.assertTrue(any("/static/css/pages/" in link for link in links))

    def test_active_menu_uses_blueprint_endpoints(self):
        self.assertIn("is-active", self.client.get("/admin/orders").get_data(as_text=True))
        self.assertIn("is-active", self.client.get("/account/orders").get_data(as_text=True))


class HeaderLayoutTests(unittest.TestCase):
    """Header 2 hàng: logo - ô tìm kiếm - tiện ích, bên dưới là thanh danh mục."""

    def setUp(self):
        self.client = logged_in_client()

    def test_header_has_two_rows_on_every_store_page(self):
        for url in STORE_LAYOUT_PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertIn('class="site-header"', html)
                self.assertIn('class="header-inner"', html)
                self.assertIn('class="header-nav"', html)
                self.assertIn('class="nav-inner"', html)

    def test_search_bar_is_pure_html(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('class="site-search"', html)
        self.assertIn('method="get"', html)
        self.assertIn('name="q"', html)
        self.assertIn('placeholder="Tìm kiếm"', html)
        self.assertIn('action="/shop"', html)

    def test_actions_have_inline_svg_icons_and_labels(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertEqual(html.count('class="nav-action"'), 4)
        self.assertIn("Yêu thích", html)
        self.assertIn("Cửa hàng", html)
        self.assertIn("Tài khoản", html)
        self.assertIn("Giỏ hàng", html)
        self.assertGreaterEqual(html.count("<svg"), 4)

    def test_category_row_order_and_active_item(self):
        html = self.client.get("/").get_data(as_text=True)
        links = re.findall(r'<a class="nav-link[^"]*"[^>]*>([^<]+)</a>', html)
        self.assertEqual(links, ["Nữ", "Nam", "Phụ kiện", "Hàng mới", "Sale"])
        self.assertIn('class="nav-link is-active"', html)
        self.assertIn('nav-link nav-sale', html)

    def test_reference_only_items_are_excluded(self):
        header = self.client.get("/").get_data(as_text=True).split("</header>", 1)[0]
        for label in ("CANIFA S", "Canifa", "LICENSE", "License", "SCHOOL", "School", "ĐỒNG PHỤC"):
            with self.subTest(label=label):
                self.assertNotIn(label, header)
        self.assertNotIn("<img", header)


class NavIndicatorTests(unittest.TestCase):
    """Task 4: thanh ngang đen trượt theo nút navbar đang hover."""

    def setUp(self):
        self.client = logged_in_client()
        self.html = self.client.get("/").get_data(as_text=True)

    def test_indicator_markup_and_assets(self):
        self.assertEqual(self.html.count('class="nav-indicator"'), 1)
        self.assertIn("/static/js/nav-indicator.js", self.html)
        self.assertTrue((STATIC_DIR / "js/nav-indicator.js").is_file())

    def test_slide_is_driven_by_css_transition(self):
        css = (STATIC_DIR / "css/layouts/store.css").read_text(encoding="utf-8")
        self.assertIn(".nav-indicator", css)
        self.assertIn("background: var(--stone-950)", css)
        self.assertIn("transition: transform", css)
        self.assertIn("transition: color 0.2s ease", css)  # giống header actions
        js = (STATIC_DIR / "js/nav-indicator.js").read_text(encoding="utf-8")
        self.assertIn("getBoundingClientRect", js)
        self.assertIn("mouseenter", js)

    def test_no_inline_handlers_or_external_scripts(self):
        for handler in ("onmouseover", "onmouseenter", "onclick", "onfocus"):
            self.assertNotIn(handler, self.html)
        self.assertNotIn("<script src=\"http", self.html)


class MegaMenuTests(unittest.TestCase):
    """Menu thả xuống khi di chuột: thuần CSS, một panel cho mỗi mục."""

    def setUp(self):
        self.client = logged_in_client()
        self.html = self.client.get("/").get_data(as_text=True)

    def test_each_tab_has_one_panel(self):
        self.assertEqual(self.html.count('class="nav-item"'), 5)
        self.assertEqual(self.html.count('class="mega-menu"'), 5)

    def test_panel_has_four_columns_without_images(self):
        self.assertEqual(self.html.count('class="mega-title"'), 15)
        self.assertEqual(self.html.count('class="mega-col mega-quick"'), 5)
        self.assertIn('class="mega-hot">HOT', self.html)
        self.assertNotIn("<img", self.html.split("</header>", 1)[0])

    def test_hover_is_css_only(self):
        css = (STATIC_DIR / "css/layouts/store.css").read_text(encoding="utf-8")
        self.assertIn(".nav-item:hover > .mega-menu", css)
        self.assertIn(".nav-item:focus-within > .mega-menu", css)
        self.assertIn("visibility: hidden", css)

    def test_mega_menu_on_every_store_page(self):
        for url in STORE_LAYOUT_PAGES:
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url).get_data(as_text=True).count('class="mega-menu"'), 5
                )


class AdminFormTests(unittest.TestCase):
    """Task 3: 4 form mới, dùng chung .input/.btn/.field của dự án."""

    FORMS = {
        "/admin/products/new": ("Thêm sản phẩm", "product-name"),
        "/admin/categories/new": ("Thêm danh mục", "category-name"),
        "/admin/users/new": ("Thêm khách hàng", "customer-name"),
        "/admin/permissions": ("Phân quyền tài khoản", "account-search"),
    }

    def setUp(self):
        self.client = logged_in_client()

    def test_forms_render_with_existing_input_and_button_styles(self):
        for url, (title, field_id) in self.FORMS.items():
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertIn(title, html)
                self.assertIn(f'id="{field_id}"', html)
                self.assertIn('class="input', html)
                self.assertIn('class="btn', html)
                self.assertIn('method="get"', html) if url.endswith("permissions") else self.assertIn('method="post"', html)
                self.assertIn("/static/css/pages/admin/forms.css", html)

    def test_permissions_form_requirements(self):
        html = self.client.get("/admin/permissions").get_data(as_text=True)
        self.assertIn('type="search"', html)          # thanh tìm kiếm
        self.assertIn('name="q"', html)
        self.assertIn('name="role"', html)            # bộ lọc theo vai trò
        self.assertIn("Quản trị viên", html)
        self.assertIn("Khách hàng", html)
        self.assertIn("Quyền hiện tại:", html)
        self.assertGreaterEqual(html.count('class="account-row"'), 5)
        search_pos = html.index('id="account-search"')
        self.assertLess(search_pos, html.index('name="role"'))  # bộ lọc nằm dưới thanh tìm kiếm

    def test_permissions_filter_and_search_work(self):
        admins = self.client.get("/admin/permissions?role=admin").get_data(as_text=True)
        self.assertIn("minhanh@freesion.vn", admins)
        self.assertNotIn("minhanh.nguyen@gmail.com", admins)
        found = self.client.get("/admin/permissions?q=Hoang").get_data(as_text=True)
        self.assertIn("Trần Hoàng Nam", found)
        self.assertNotIn("Lê Thu Hà", found)
        empty = self.client.get("/admin/permissions?q=khong-co-ai").get_data(as_text=True)
        self.assertIn("Không tìm thấy tài khoản nào", empty)

    def test_form_post_redirects_to_list(self):
        for url, target in (
            ("/admin/products/new", "/admin/products?created=product"),
            ("/admin/categories/new", "/admin/categories?created=category"),
            ("/admin/users/new", "/admin/users?created=user"),
        ):
            with self.subTest(url=url):
                response = self.client.post(url, data={"name": "Mẫu thử"})
                self.assertEqual(response.status_code, 302)
                self.assertIn(response.headers["Location"], target)

    def test_permissions_post_preserves_filters(self):
        response = self.client.post(
            "/admin/permissions", data={"q": "Minh Anh", "role": "admin"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("q=Minh+Anh", response.headers["Location"])
        self.assertIn("role=admin", response.headers["Location"])


class CheckoutFlowTests(unittest.TestCase):
    """Luồng 4 bước: giỏ hàng -> giao hàng -> thanh toán -> xác nhận."""

    STEPS = ("/cart", "/checkout/shipping", "/checkout", "/order-success")

    def setUp(self):
        self.client = logged_in_client()

    def test_step_bar_on_checkout_pages(self):
        for step, url in enumerate(("/checkout/shipping", "/checkout", "/order-success"), start=2):
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertIn('class="checkout-steps"', html)
                self.assertIn('class="checkout-step is-active"', html)
                self.assertIn("Shopping Cart", html)
                self.assertIn("Confirmation", html)
                self.assertIn('href="/checkout/shipping"', html)


class FooterLayoutTests(unittest.TestCase):
    """Footer tách riêng khỏi store.css, luôn được nạp trên các trang cửa hàng."""

    CSS_DIR = STATIC_DIR / "css"

    def setUp(self):
        self.client = logged_in_client()

    def test_footer_stylesheet_is_loaded(self):
        for url in STORE_LAYOUT_PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertIn("/static/css/layouts/footer.css", html)
                self.assertIn('class="site-footer"', html)
                self.assertIn('class="footer-grid"', html)
                self.assertIn('class="footer-copy"', html)

    def test_admin_pages_do_not_load_store_layout_assets(self):
        for url in ADMIN_PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertNotIn("/static/css/layouts/store.css", html)
                self.assertNotIn("/static/css/layouts/footer.css", html)

    def test_header_and_footer_css_are_separated(self):
        store_css = (self.CSS_DIR / "layouts/store.css").read_text(encoding="utf-8")
        footer_css = (self.CSS_DIR / "layouts/footer.css").read_text(encoding="utf-8")
        self.assertNotIn(".site-footer", store_css)
        self.assertIn(".site-footer", footer_css)
        self.assertIn("@media (min-width: 768px)", footer_css)
        for name, text in (("store.css", store_css), ("footer.css", footer_css)):
            with self.subTest(file=name):
                self.assertEqual(text.count("{"), text.count("}"), name)


if __name__ == "__main__":
    unittest.main()


class AccountGuardTests(unittest.TestCase):
    """Chưa đăng nhập mà vào /account thì được chuyển tới trang đăng nhập."""

    def test_anonymous_is_redirected_to_login(self):
        client = create_app("testing").test_client()
        for url in ("/account", "/account/orders", "/account/address", "/account/wishlist"):
            with self.subTest(url=url):
                res = client.get(url)
                self.assertEqual(res.status_code, 302)
                self.assertTrue(res.headers["Location"].startswith("/login?next="), res.headers["Location"])

    def test_logged_in_user_can_open_account(self):
        self.assertEqual(logged_in_client().get("/account").status_code, 200)

    def test_logout_link_really_logs_out(self):
        client = logged_in_client()
        self.assertEqual(client.get("/account").status_code, 200)
        self.assertIn('href="/logout"', client.get("/account").get_data(as_text=True))
        res = client.get("/logout")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers["Location"], "/login")
        self.assertEqual(client.get("/account").status_code, 302)  # đã đăng xuất nên bị chuyển về /login
