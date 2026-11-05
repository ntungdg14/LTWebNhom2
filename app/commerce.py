"""View-model cho các khối thông tin thương mại (sản phẩm, giỏ hàng, đơn hàng).

Mục đích: template chỉ nhận **dữ liệu có cấu trúc**, không chứa tên sản phẩm,
giá hay số lượng viết cứng. Tên trường bám sát ``db/schema.sql`` để khi nối
SQLite backend chỉ cần thay phần lấy dữ liệu, còn template/macro giữ nguyên:

    products + product_images + variants + colors   -> get_product(), get_related()
    cart_items + variants + products + colors       -> get_cart()["items"]
    order_items + orders + coupons                   -> get_order()

Mọi số tiền là ``int`` VND (đúng kiểu cột trong schema); template định dạng
qua Jinja filter ``vnd``. Các giá trị suy diễn (line_total, subtotal, total,
rows) được tính ở đây, không tính trong HTML.
"""
from __future__ import annotations

from typing import Any

DEFAULT_SKU = "FR-BOM-002"
DEFAULT_ORDER_CODE = "FR261101028"
COUPON = {"code": "TUDO10", "percent": 10}


def format_vnd(amount: int | None) -> str:
    """249000 -> '249.000₫'. Dùng làm Jinja filter `vnd`."""
    if amount is None:
        return ""
    return f"{amount:,}".replace(",", ".") + "₫"


def _image(tone: str, label: str = "Ảnh sản phẩm") -> dict[str, Any]:
    """product_images.url = NULL -> placeholder theo tone (xem schema.sql)."""
    return {"url": None, "tone": tone, "label": label}


# products: mỗi dict là một hàng (rút gọn), ảnh màu/size là bảng con.
PRODUCTS: dict[str, dict[str, Any]] = {
    "FR-BOM-002": {
        "id": 2, "sku": "FR-BOM-002", "slug": "ao-khoac-bomber-uniform",
        "name": "Áo khoác bomber Uniform",
        "description": "Áo khoác bomber dáng suông, cổ bo gọn với khóa kéo kim loại. "
                       "Lớp lót mỏng giữ ấm vừa đủ cho những ngày se lạnh, "
                       "dễ mặc ngoài áo thun hay sơ mi.",
        "price": 899000, "compare_price": 1199000,
        "category": "Áo khoác", "department": "Nam", "tone": "beige",
        "material": "65% polyester tái chế, 35% cotton",
        "model_info": "Cao 1m78, mặc size M",
        "care": "Giặt máy nhẹ nhàng, không dùng chất tẩy",
        "rating": 4.9, "review_count": 128,
        "images": [
            _image("beige", "Ảnh 1 · Mặt trước"), _image("taupe", "Ảnh 2 · Mặt sau"),
            _image("cream", "Ảnh 3 · Cổ gập"), _image("taupe", "Ảnh 4 · Ống tay"),
            _image("beige", "Ảnh 5 · Người mẫu"), _image("cream", "Ảnh 6 · Chi tiết"),
        ],
        "colors": [
            {"name": "Nâu dừa", "slug": "nau-dua", "tone": "beige"},
            {"name": "Đen", "slug": "den", "tone": "stone"},
            {"name": "Xanh rêu", "slug": "xanh-reu", "tone": "olive"},
            {"name": "Be", "slug": "be", "tone": "cream"},
        ],
        "sizes": ["S", "M", "L", "XL", "XXL"],
    },
    "FR-TEE-004": {
        "id": 4, "sku": "FR-TEE-004", "slug": "ao-thun-cotton-essential",
        "name": "Áo thun cotton Essential",
        "description": "Áo thun cotton dáng suông, bo cổ chắc, dễ mặc mỗi ngày.",
        "price": 249000, "compare_price": None,
        "category": "Áo thun", "department": "Nam", "tone": "taupe",
        "color": "Den vintage", "material": "100% cotton",
        "model_info": "Cao 1m78, mặc size M", "care": "Giặt máy nhẹ nhàng",
        "rating": 4.8, "review_count": 96,
    },
    "FR-OXF-001": {
        "id": 1, "sku": "FR-OXF-001", "slug": "ao-so-mi-oxford-dang-rong",
        "name": "Áo sơ mi Oxford dáng rộng",
        "description": "Sơ mi Oxford dáng rộng, vải dày vừa, form phối dễ.",
        "price": 459000, "compare_price": None,
        "category": "Áo sơ mi", "department": "Nữ", "tone": "beige",
        "color": "Trắng kem", "material": "100% cotton",
        "model_info": "Cao 1m65, mặc size M", "care": "Giặt máy nhẹ nhàng",
        "rating": 4.9, "review_count": 128,
    },
    "FR-JEA-003": {
        "id": 3, "sku": "FR-JEA-003", "slug": "quan-jean-ong-suong-indigo",
        "name": "Quần jean ống suông Indigo",
        "description": "Jean ống suông, denim Indigo đậm, đứng form.",
        "price": 649000, "compare_price": None,
        "category": "Quần jean", "department": "Nam", "tone": "cream",
        "color": "Xanh đậm", "material": "100% cotton denim",
        "model_info": "Cao 1m78, mặc size 30", "care": "Giặt riêng lần đầu",
        "rating": 4.7, "review_count": 74,
    },
    "FR-KNT-005": {
        "id": 5, "sku": "FR-KNT-005", "slug": "ao-len-det-waffle-co-tron",
        "name": "Áo len dệt waffle cổ tròn",
        "description": "Áo len dệt waffle, cổ tròn, ấm nhẹ cho ngày se lạnh.",
        "price": 589000, "compare_price": None,
        "category": "Áo len", "department": "Nữ", "tone": "rose",
        "color": "Hồng đất", "material": "60% cotton, 40% acrylic",
        "model_info": "Cao 1m65, mặc size M", "care": "Giặt tay, phơi ngang",
        "rating": 4.8, "review_count": 52,
    },
    "FR-OVS-006": {
        "id": 6, "sku": "FR-OVS-006", "slug": "ao-khoac-corduroy",
        "name": "Áo khoác Corduroy", "description": "Áo khoác nhung tăm, form rộng.",
        "price": 899000, "compare_price": None, "category": "Áo khoác",
        "department": "Nam", "tone": "olive", "color": "Xanh rêu",
        "material": "100% cotton", "model_info": "Cao 1m78, mặc size M",
        "care": "Giặt khô", "rating": 4.8, "review_count": 31,
    },
    "FR-BOX-008": {
        "id": 8, "sku": "FR-BOX-008", "slug": "ao-so-mi-box",
        "name": "Áo sơ mi boxy", "description": "Sơ mi form boxy ngắn tay.",
        "price": 529000, "compare_price": None, "category": "Áo sơ mi",
        "department": "Nữ", "tone": "cream", "color": "Be tự nhiên",
        "material": "Linen", "model_info": "Cao 1m65, mặc size M",
        "care": "Giặt máy nhẹ nhàng", "rating": 4.7, "review_count": 18,
    },
    "FR-CHI-007": {
        "id": 7, "sku": "FR-CHI-007", "slug": "chan-vay-chiffon",
        "name": "Chân váy chiffon", "description": "Chân váy chiffon bay nhẹ.",
        "price": 549000, "compare_price": None, "category": "Chân váy",
        "department": "Nữ", "tone": "rose", "color": "Hồng phấn",
        "material": "Chiffon", "model_info": "Cao 1m65, mặc size M",
        "care": "Giặt tay", "rating": 4.6, "review_count": 22,
    },
    "FR-SKI-009": {
        "id": 9, "sku": "FR-SKI-009", "slug": "ao-len-cao-co",
        "name": "Áo len cổ cao", "description": "Áo len cổ cao, dệt mịn.",
        "price": 619000, "compare_price": None, "category": "Áo len",
        "department": "Nam", "tone": "denim", "color": "Xanh khói",
        "material": "Wool blend", "model_info": "Cao 1m78, mặc size M",
        "care": "Giặt tay", "rating": 4.7, "review_count": 27,
    },
}

REVIEWS = [
    {
        "stars": 5, "date": "14 ngày trước", "title": "Ấm vừa đủ, dễ phối",
        "body": "Mặc đi làm lẫn đi chơi đều được, form vừa phối, mặc thêm lớp áo "
                "cũng vẫn gọn. Chắc sẽ mua thêm màu khác.",
        "author": "Minh Anh", "city": "TP. Hồ Chí Minh", "size": "M", "verified": True,
    },
    {
        "stars": 5, "date": "21 ngày trước", "title": "Đúng với mô tả",
        "body": "Chất dày dặn, đường may chắc chắn. Giao nhanh, đóng gói cẩn thận.",
        "author": "Quốc Huy", "city": "Hà Nội", "size": "L", "verified": True,
    },
]

RATING_BREAKDOWN = [
    {"label": "5 sao", "percent": 82, "count": 104},
    {"label": "4 sao", "percent": 14, "count": 17},
    {"label": "3 sao", "percent": 7, "count": 5},
    {"label": "2 sao", "percent": 2, "count": 1},
    {"label": "1 sao", "percent": 1, "count": 1},
]

# cart_items / order_items: khóa ngoài + cột snapshot lưu tại thời điểm đặt.
LINES: list[dict[str, Any]] = [
    {
        "id": 1, "variant_id": 21, "sku": "FR-TEE-004-M-DV",
        "product_sku": "FR-TEE-004", "product_slug": "ao-thun-cotton-essential",
        "name": "Áo thun cotton Essential", "color": "Den vintage", "size": "M",
        "tone": "taupe", "price": 249000, "compare_price": None, "quantity": 2,
    },
    {
        "id": 2, "variant_id": 22, "sku": "FR-BOM-002-L-ND",
        "product_sku": "FR-BOM-002", "product_slug": "ao-khoac-bomber-uniform",
        "name": "Áo khoác bomber Uniform", "color": "Nâu dừa", "size": "L",
        "tone": "beige", "price": 899000, "compare_price": 1199000, "quantity": 1,
    },
]


def _decorate_line(line: dict[str, Any]) -> dict[str, Any]:
    """Thêm các trường suy diễn cho một dòng sản phẩm (không sửa dict gốc)."""
    item = dict(line)
    item["line_total"] = item["price"] * item["quantity"]
    item["image"] = _image(item["tone"])
    return item


def _lines() -> list[dict[str, Any]]:
    return [_decorate_line(line) for line in LINES]


def build_order_summary(
    items: list[dict[str, Any]],
    *,
    code: str = DEFAULT_ORDER_CODE,
    coupon: dict[str, Any] = COUPON,
    shipping_fee: int = 0,
    subtotal_unit: str = "quantity",
    row_order: tuple[str, ...] = ("subtotal", "discount", "shipping"),
    discount_label: str | None = None,
) -> dict[str, Any]:
    """orders + order_items -> dict duy nhất cho component `order_summary_card`."""
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    discount = subtotal * coupon["percent"] // 100
    quantity_total = sum(item["quantity"] for item in items)
    count = len(items) if subtotal_unit == "lines" else quantity_total
    label = discount_label or f"Giảm giá · {coupon['code']} ({coupon['percent']}%)"
    rows = {
        "subtotal": {"label": f"Tạm tính ({count} sản phẩm)", "value": format_vnd(subtotal)},
        "discount": {"label": label, "value": f"-{format_vnd(discount)}"},
        "shipping": {
            "label": "Phí vận chuyển",
            "value": "Miễn phí" if shipping_fee == 0 else format_vnd(shipping_fee),
        },
    }
    return {
        "code": code,
        "items": items,
        "item_count": len(items),
        "quantity_total": quantity_total,
        "subtotal": subtotal,
        "discount": discount,
        "shipping_fee": shipping_fee,
        "total": subtotal - discount + shipping_fee,
        "coupon_code": coupon["code"],
        "rows": [rows[key] for key in row_order],
    }


def get_product(sku: str | None = None, *, color: str | None = None,
                size: str | None = None) -> dict[str, Any]:
    """products + product_images + colors + variants -> 1 dict cho trang chi tiết."""
    product = dict(PRODUCTS.get(sku or "", PRODUCTS[DEFAULT_SKU]))
    product.setdefault("images", [_image(product["tone"], "Ảnh sản phẩm")] * 6)
    product.setdefault("colors", [
        {"name": product.get("color", "Mặc định"), "slug": "mac-dinh", "tone": product["tone"]}
    ])
    product.setdefault("sizes", ["S", "M", "L", "XL"])
    product.setdefault("rating", 4.9)
    product.setdefault("review_count", 128)
    product["specs"] = [
        {"label": "Chất liệu", "value": product.get("material", "")},
        {"label": "Người mẫu", "value": product.get("model_info", "")},
        {"label": "Ghi chú", "value": product.get("care", "")},
    ]
    product["selected_color"] = color or product["colors"][0]["slug"]
    product["selected_size"] = size or "M"
    product["selected_color_name"] = next(
        (c["name"] for c in product["colors"] if c["slug"] == product["selected_color"]),
        product["colors"][0]["name"],
    )
    product["rating_display"] = f"{product['rating']:.1f}".replace(".", ",")
    product["category_slug"] = {"Nữ": "nu", "Nam": "nam"}.get(
        product["department"], "phu-kien"
    )
    return product


def get_related(sku: str | None = None) -> list[dict[str, Any]]:
    """4 gợi ý: vẫn là dict products, template tự lọc bỏ sản phẩm hiện tại."""
    wanted = ["FR-OXF-001", "FR-JEA-003", "FR-TEE-004", "FR-KNT-005"]
    return [
        {
            "sku": key, "name": PRODUCTS[key]["name"],
            "color": PRODUCTS[key]["color"], "price": PRODUCTS[key]["price"],
            "tone": PRODUCTS[key]["tone"], "image": _image(PRODUCTS[key]["tone"]),
        }
        for key in wanted if key != sku
    ]


def _history_line(product_sku: str, size: str, color: str,
                  quantity: int) -> dict[str, Any]:
    """Một order_items của các đơn cũ trong lịch sử."""
    product = PRODUCTS[product_sku]
    return _decorate_line({
        "id": product["id"], "variant_id": product["id"] * 10,
        "sku": f"{product_sku}-{size}", "product_sku": product_sku,
        "product_slug": product["slug"], "name": product["name"],
        "color": color, "size": size, "tone": product["tone"],
        "price": product["price"], "compare_price": None, "quantity": quantity,
    })


def get_order_history() -> list[dict[str, Any]]:
    """orders + order_items cho trang lịch sử: mỗi đơn là 1 card ngoài."""
    return [
        {
            "code": DEFAULT_ORDER_CODE, "date": "01/11/2026",
            "status": "Đang chuẩn bị hàng", "badge": "badge-warn",
            "items": _lines(), "total": 1257300, "show_total": True,
            "note": "2 dòng sản phẩm · Tổng số lượng: 3",
            "action_label": "Xem chi tiết đơn hàng", "reorder_label": None,
        },
        {
            "code": "FR261015092", "date": "15/10/2026",
            "status": "Đã giao hàng", "badge": "badge-ok",
            "items": [_history_line("FR-OXF-001", "M", "Trắng kem", 1)],
            "total": 489000, "show_total": False,
            "note": f"Tổng cộng {format_vnd(489000)} · Đã nhận ngày 18/10/2026",
            "action_label": "Xem chi tiết", "reorder_label": "Đánh giá / Mua lại",
        },
        {
            "code": "FR261002036", "date": "02/10/2026",
            "status": "Đã hủy", "badge": "badge-danger",
            "items": [_history_line("FR-JEA-003", "29", "Xanh đậm", 1)],
            "total": 649000, "show_total": False,
            "note": "Đã hoàn tiền theo yêu cầu của bạn · Chưa thanh toán",
            "action_label": "Xem chi tiết", "reorder_label": "Mua lại",
        },
    ]


def get_cart() -> dict[str, Any]:
    """Giỏ hàng: danh sách card + khung tóm tắt dùng chung (có mã giảm giá)."""
    items = _lines()
    order = build_order_summary(
        items,
        subtotal_unit="lines",
        row_order=("subtotal", "shipping", "discount"),
        discount_label="Giảm giá (TUDO10 · 10%)",
    )
    return {"items": items, "order": order}


def get_order() -> dict[str, Any]:
    """Đơn hàng dùng cho shipping / checkout / xác nhận / chi tiết đơn."""
    return build_order_summary(_lines())
