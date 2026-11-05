"""Kiểm thử cấu trúc component thương mại.

Mục tiêu: mỗi đơn vị thông tin (mô tả sản phẩm, 1 sản phẩm trong giỏ,
1 sản phẩm trong tóm tắt đơn hàng) phải nằm trong ĐÚNG MỘT khung chứa,
và khung tóm tắt phải bao danh sách sản phẩm + các dòng tiền.
Dữ liệu phải đến từ app.commerce, không viết cứng trong template.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from app import commerce, create_app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
STATIC = ROOT / "app" / "static"

# Bắt cả thẻ mở để kiểm tra được thuộc tính data-* của chính khung chứa.
CART_CARD = re.compile(r'(<article class="cart-card"[^>]*>.*?</article>)', re.S)
ORDER_ITEM = re.compile(r'(<article class="order-item-card"[^>]*>.*?</article>)', re.S)
SUMMARY = re.compile(r'<section class="order-summary-card[^"]*"[^>]*>(.*?)</section>', re.S)
DESCRIPTION = re.compile(
    r'<article class="info-card product-description-card"[^>]*>(.*?)</article>', re.S
)
INLINE_POSITIONING = re.compile(
    r'style="[^"]*(?:margin|position|flex|align-items|font-size|text-align|padding|background|gap)[^"]*"'
)

SUMMARY_PAGES = (
    "/cart",
    "/checkout/shipping",
    "/checkout",
    "/order-success",
    "/account/orders/FR261101028",
)

REFACTORED_TEMPLATES = (
    "store/cart.html",
    "store/product_detail.html",
    "checkout/shipping.html",
    "checkout/checkout.html",
    "checkout/order_success.html",
    "account/order_detail.html",
    "account/order_history.html",
)


class ViewModelTests(unittest.TestCase):
    """Hợp đồng dữ liệu bám db/schema.sql; backend có thể thay mock bằng SQL."""

    def test_vnd_filter(self):
        self.assertEqual(commerce.format_vnd(249000), "249.000₫")
        self.assertEqual(commerce.format_vnd(-139700), "-139.700₫")
        self.assertEqual(commerce.format_vnd(0), "0₫")
        self.assertEqual(create_app("testing").jinja_env.filters["vnd"](1257300), "1.257.300₫")

    def test_cart_items_have_schema_fields_and_computed_totals(self):
        cart = commerce.get_cart()
        self.assertEqual(len(cart["items"]), 2)
        for item in cart["items"]:
            for key in ("id", "variant_id", "sku", "product_sku", "product_slug",
                        "name", "color", "size", "tone", "price", "compare_price",
                        "quantity", "image", "line_total"):
                self.assertIn(key, item, key)
            self.assertEqual(item["line_total"], item["price"] * item["quantity"])
            self.assertIn("tone", item["image"])

    def test_order_totals_are_derived_not_hardcoded(self):
        order = commerce.get_order()
        subtotal = sum(i["price"] * i["quantity"] for i in order["items"])
        self.assertEqual(order["subtotal"], subtotal)
        self.assertEqual(order["discount"], subtotal * commerce.COUPON["percent"] // 100)
        self.assertEqual(order["total"], subtotal - order["discount"] + order["shipping_fee"])
        self.assertEqual(order["quantity_total"], 3)
        self.assertEqual([row["label"] for row in order["rows"]][-1], "Phí vận chuyển")

    def test_product_and_history_view_models(self):
        product = commerce.get_product("FR-BOM-002")
        self.assertEqual(len(product["specs"]), 3)
        self.assertEqual(len(product["images"]), 6)
        self.assertEqual(product["selected_color_name"], "Nâu dừa")
        self.assertEqual(commerce.get_product("FR-OXF-001")["name"], "Áo sơ mi Oxford dáng rộng")
        self.assertEqual(len(commerce.get_related("FR-BOM-002")), 4)
        orders = commerce.get_order_history()
        self.assertEqual(len(orders), 3)
        for order in orders:
            self.assertTrue(order["items"])
            self.assertIn("image", order["items"][0])


class CartCardStructureTests(unittest.TestCase):
    def setUp(self):
        self.html = create_app("testing").test_client().get("/cart").get_data(as_text=True)

    def test_each_cart_product_is_one_complete_card(self):
        cards = CART_CARD.findall(self.html)
        self.assertEqual(len(cards), 2)
        for card, name in zip(cards, ("Áo thun cotton Essential", "Áo khoác bomber Uniform")):
            with self.subTest(name=name):
                # Ảnh + tên + giá + số lượng + nút xóa + thành tiền CÙNG trong 1 article
                for needle in ("media-thumb", "<h2>", name, 'class="price',
                               'class="qty', ">Xóa<", "cart-card__total", "data-sku"):
                    self.assertIn(needle, card)
        self.assertIn("498.000₫", cards[0])
        self.assertIn("899.000₫", cards[1])

    def test_cards_live_in_a_real_list_container(self):
        self.assertIn('class="cart-list"', self.html)
        self.assertIn('class="split-main cart-shell"', self.html)
        self.assertIn('class="cart-head"', self.html)
        self.assertNotIn('class="cart-item"', self.html)  # layout rời rạc cũ

    def test_cart_css_uses_grid_not_positioning(self):
        css = (STATIC / "css/pages/store/cart.css").read_text(encoding="utf-8")
        self.assertIn(".cart-list {", css)
        self.assertIn("display: grid", css)
        self.assertNotIn("position:", css)


class OrderSummaryStructureTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app("testing").test_client()

    def test_outer_frame_contains_item_cards_then_totals(self):
        for url in SUMMARY_PAGES:
            with self.subTest(url=url):
                html = self.client.get(url).get_data(as_text=True)
                summaries = SUMMARY.findall(html)
                self.assertEqual(len(summaries), 1, url)
                block = summaries[0]
                items = ORDER_ITEM.findall(block)
                self.assertEqual(len(items), 2, url)
                for item in items:
                    for needle in ("media-sm", "<h3>", "×", "order-item-card__amount", "data-sku"):
                        self.assertIn(needle, item)
                self.assertIn("Tạm tính", block)
                self.assertIn("Phí vận chuyển", block)
                self.assertIn("Tổng cộng", block)
                self.assertIn("1.257.300₫", block)
                # Thứ tự: danh sách sản phẩm đứng trước các dòng tiền
                self.assertLess(block.index("order-item-card"), block.index("summary-total"))

    def test_summary_css_is_flex_grid_container(self):
        css = (STATIC / "css/components/commerce.css").read_text(encoding="utf-8")
        for selector in (".order-summary-card {", ".order-summary-card__items {",
                         ".order-summary-card__totals", ".order-item-card {"):
            self.assertIn(selector, css)
        self.assertIn("display: grid", css)
        self.assertIn("display: flex", css)
        self.assertNotIn("position:", css)


class ProductDescriptionStructureTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app("testing").test_client()

    def test_description_is_one_card_with_all_specs(self):
        html = self.client.get("/product").get_data(as_text=True)
        blocks = DESCRIPTION.findall(html)
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertIn("Mô tả sản phẩm", block)
        self.assertIn("Áo khoác bomber dáng suông", block)
        self.assertIn("<dl", block)
        self.assertEqual(block.count("<dt>"), 3)
        self.assertIn("65% polyester tái chế, 35% cotton", block)
        self.assertIn("Cao 1m78, mặc size M", block)

    def test_product_info_groups_and_loops(self):
        html = self.client.get("/product").get_data(as_text=True)
        self.assertGreaterEqual(html.count('class="info-card'), 5)
        self.assertEqual(html.count('class="product-card"'), 4)  # related, từ dữ liệu
        self.assertEqual(html.count('class="review-card"'), 2)

    def test_every_catalog_sku_renders(self):
        for sku, product in commerce.PRODUCTS.items():
            with self.subTest(sku=sku):
                response = self.client.get(f"/product?sku={sku}")
                self.assertEqual(response.status_code, 200)
                self.assertIn(product["name"], response.get_data(as_text=True))


class DataDrivenTemplateTests(unittest.TestCase):
    def test_no_hardcoded_product_data_in_refactored_templates(self):
        for name in REFACTORED_TEMPLATES:
            with self.subTest(template=name):
                source = (TEMPLATES / name).read_text(encoding="utf-8")
                self.assertNotIn("Áo thun cotton Essential", source)
                self.assertNotIn("Áo khoác bomber Uniform", source)
                self.assertNotIn("1.257.300₫", source)
                # Trang ủy việc lặp cho component dùng chung (import macro).
                self.assertIn('{% import "layouts/macros/_commerce.html" as commerce %}', source)

    def test_loops_live_in_macros_and_list_pages(self):
        macro = (TEMPLATES / "layouts/macros/_commerce.html").read_text(encoding="utf-8")
        self.assertIn("{% for", macro)
        for name in ("store/cart.html", "store/product_detail.html",
                     "account/order_history.html"):
            with self.subTest(template=name):
                self.assertIn("{% for", (TEMPLATES / name).read_text(encoding="utf-8"))

    def test_no_discrete_inline_positioning_styles(self):
        for name in REFACTORED_TEMPLATES:
            with self.subTest(template=name):
                source = (TEMPLATES / name).read_text(encoding="utf-8")
                self.assertIsNone(INLINE_POSITIONING.search(source))

    def test_shared_component_assets_exist_on_every_page(self):
        client = create_app("testing").test_client()
        for url in ("/", "/product", "/cart", "/checkout", "/account/orders/FR261101028", "/admin"):
            with self.subTest(url=url):
                html = client.get(url).get_data(as_text=True)
                self.assertIn("/static/css/components/commerce.css", html)
        self.assertTrue((STATIC / "css/components/commerce.css").is_file())
        self.assertTrue((TEMPLATES / "layouts/macros/_commerce.html").is_file())
