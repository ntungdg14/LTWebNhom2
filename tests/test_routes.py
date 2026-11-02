"""Kiểm thử hồi quy cho cấu trúc Flask và việc tách CSS.

Chạy: python -m unittest discover -s tests -v
(Không cần pytest, chỉ dùng Flask test_client và unittest có sẵn.)
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from app import create_app

STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"

PAGES = (
    "/",
    "/shop",
    "/product",
    "/cart",
    "/checkout",
    "/order-success",
    "/login",
    "/register",
    "/forgot-password",
    "/account",
    "/account/orders",
    "/account/address",
    "/account/wishlist",
    "/admin",
    "/admin/products",
    "/admin/orders",
    "/admin/users",
)

STYLESHEET_RE = re.compile(r'<link rel="stylesheet" href="([^"]+)"')


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_blueprints_registered(self):
        expected = {"store", "auth", "account", "checkout", "admin"}
        self.assertTrue(expected.issubset(set(self.app.blueprints)))

    def test_every_page_renders(self):
        for url in PAGES:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"<!DOCTYPE html>", response.data)

    def test_stylesheets_are_local_and_exist(self):
        for url in PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                links = STYLESHEET_RE.findall(html)
                self.assertTrue(links, "trang không nạp CSS nào")
                for href in links:
                    self.assertFalse(href.startswith(("http://", "https://", "//")), href)
                    self.assertTrue(href.startswith("/static/css/"), href)
                    self.assertTrue(
                        (STATIC_DIR / href.removeprefix("/static/")).is_file(),
                        f"thiếu file CSS: {href}",
                    )

    def test_shared_and_page_layers_are_loaded(self):
        for url in PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                links = STYLESHEET_RE.findall(html)
                self.assertIn("/static/css/base.css", links)
                self.assertIn("/static/css/components.css", links)
                self.assertTrue(
                    any("/static/css/pages/" in link for link in links),
                    "trang thiếu stylesheet riêng",
                )

    def test_active_menu_uses_blueprint_endpoints(self):
        self.assertIn("is-active", self.client.get("/admin/orders").get_data(as_text=True))
        self.assertIn("is-active", self.client.get("/account/wishlist").get_data(as_text=True))


class HeaderLayoutTests(unittest.TestCase):
    """Header 2 hàng: logo - ô tìm kiếm - tiện ích, bên dưới là thanh danh mục."""

    STORE_PAGES = PAGES[:13]  # các trang dùng base_store.html (trừ 4 trang admin)

    def setUp(self):
        self.client = create_app("testing").test_client()

    def test_header_has_two_rows_on_every_store_page(self):
        for url in self.STORE_PAGES:
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
        self.assertEqual(html.count('class="nav-action"'), 3)
        self.assertIn("Cửa hàng", html)
        self.assertIn("Tài khoản", html)
        self.assertIn("Giỏ hàng", html)
        self.assertGreaterEqual(html.count("<svg"), 4)  # tìm kiếm + 3 tiện ích
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)

    def test_category_row_order_and_active_item(self):
        html = self.client.get("/").get_data(as_text=True)
        row = html.split('class="nav-inner"', 1)[1].split("</div>", 1)[0]
        self.assertIn('class="is-active">Nữ', row)
        self.assertIn('class="nav-sale">Sale', row)
        self.assertLess(row.index(">Nữ<"), row.index(">Nam<"))


class FooterLayoutTests(unittest.TestCase):
    """Footer tách riêng khỏi store.css, luôn được nạp trên các trang cửa hàng."""

    STORE_PAGES = PAGES[:13]
    ADMIN_PAGES = PAGES[13:]
    CSS_DIR = STATIC_DIR / "css"

    def setUp(self):
        self.client = create_app("testing").test_client()

    def test_footer_stylesheet_is_loaded(self):
        for url in self.STORE_PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertIn("/static/css/layouts/footer.css", html)
                self.assertIn('class="site-footer"', html)
                self.assertIn('class="footer-grid"', html)
                self.assertIn('class="footer-copy"', html)

    def test_admin_pages_do_not_load_store_layout_assets(self):
        for url in self.ADMIN_PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                self.assertNotIn("/static/css/layouts/store.css", html)
                self.assertNotIn("/static/css/layouts/footer.css", html)

    def test_header_and_footer_css_are_separated(self):
        store_css = (self.CSS_DIR / "layouts/store.css").read_text(encoding="utf-8")
        footer_css = (self.CSS_DIR / "layouts/footer.css").read_text(encoding="utf-8")
        self.assertNotIn(".site-footer", store_css)
        self.assertNotIn(".footer-grid", store_css)
        self.assertIn(".site-footer", footer_css)
        self.assertIn(".footer-grid", footer_css)
        self.assertIn("@media (min-width: 768px)", footer_css)
        for name, text in (("store.css", store_css), ("footer.css", footer_css)):
            with self.subTest(file=name):
                self.assertEqual(text.count("{"), text.count("}"), name)


if __name__ == "__main__":
    unittest.main()
