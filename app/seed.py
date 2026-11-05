"""Dữ liệu mẫu theo thiết kế (danh mục, màu, sản phẩm, mã giảm giá, tỉnh/phường...).

Chạy: flask --app run seed-db   (chỉ nạp khi bảng products còn trống)
"""
from __future__ import annotations

CATEGORIES = [  # slug, tên, tone
    ("ao-so-mi", "Áo sơ mi", "beige"),
    ("quan-jean", "Quần jean", "denim"),
    ("ao-thun", "Áo thun", "cream"),
    ("quan-dai", "Quần dài", "olive"),
    ("ao-len", "Áo len", "rose"),
    ("ao-khoac", "Áo khoác", "taupe"),
]

COLOR_FAMILIES = [  # slug, tên, hex
    ("den", "Đen", "#161616"),
    ("trang", "Trắng", "#FFFFFF"),
    ("be", "Be", "#DCC8B0"),
    ("xanh-duong", "Xanh dương", "#5E7596"),
    ("xanh-la", "Xanh lá", "#6F8068"),
    ("hong", "Hồng", "#C9A5A0"),
    ("nau", "Nâu", "#8B6B4A"),
    ("xam", "Xám", "#9E9C97"),
]

COLORS = [  # slug, tên, hex, nhóm
    ("trang-kem", "Trắng kem", "#F3EBDD", "trang"),
    ("trang", "Trắng", "#FFFFFF", "trang"),
    ("den-vintage", "Đen vintage", "#2B2B2B", "den"),
    ("den", "Đen", "#161616", "den"),
    ("nau-dua", "Nâu dừa", "#8B6B4A", "nau"),
    ("be-cat", "Be cát", "#D9C3A0", "be"),
    ("xanh-dam", "Xanh đậm", "#3F5879", "xanh-duong"),
    ("indigo-dam", "Indigo đậm", "#2F4468", "xanh-duong"),
    ("hong-dat", "Hồng đất", "#C9A5A0", "hong"),
    ("reu", "Rêu", "#4F5E48", "xanh-la"),
    ("xam-khoi", "Xám khói", "#9E9C97", "xam"),
]

TOPS = ["S", "M", "L", "XL"]
JEANS = ["28", "29", "30", "31"]

PRODUCTS = [
    # slug, sku, tên, giá, giá gốc, danh mục, bộ phận, tone, màu, size, mới, nổi bật, đã bán, chất liệu
    ("ao-so-mi-oxford-dang-rong", "FR-OXF-001", "Áo sơ mi Oxford dáng rộng", 459_000, None, "ao-so-mi", "nu", "beige",
     ["trang-kem", "xam-khoi"], TOPS, 1, 1, 320, "100% cotton Oxford"),
    ("quan-jean-ong-suong-indigo", "FR-JEA-002", "Quần jean ống suông Indigo", 649_000, None, "quan-jean", "nu", "denim",
     ["xanh-dam"], JEANS, 1, 1, 210, "98% cotton, 2% elastane"),
    ("ao-thun-cotton-essential", "FR-TEE-003", "Áo thun cotton Essential", 249_000, None, "ao-thun", "nu", "taupe",
     ["den-vintage", "trang"], TOPS, 0, 1, 840, "100% cotton compact 220gsm"),
    ("ao-len-det-waffle-co-tron", "FR-WAF-004", "Áo len dệt waffle cổ tròn", 589_000, None, "ao-len", "nu", "rose",
     ["hong-dat"], TOPS, 1, 0, 95, "70% cotton, 30% acrylic"),
    ("ao-overshirt-heavyweight", "FR-OVS-005", "Áo overshirt Heavyweight", 799_000, None, "ao-khoac", "nu", "olive",
     ["reu"], TOPS, 0, 0, 60, "100% cotton twill"),
    ("quan-dai-ong-dung-chino", "FR-CHI-006", "Quần dài ống đứng Chino", 529_000, None, "quan-dai", "nu", "beige",
     ["be-cat"], JEANS, 1, 0, 130, "97% cotton, 3% elastane"),
    ("ao-thun-boxy-day-dan", "FR-BOX-007", "Áo thun Boxy dày dặn", 289_000, None, "ao-thun", "nu", "cream",
     ["trang"], TOPS, 1, 0, 410, "100% cotton 260gsm"),
    ("quan-jean-slim-co-gian", "FR-JSL-008", "Quần jean slim co giãn", 699_000, None, "quan-jean", "nu", "denim",
     ["indigo-dam"], JEANS, 0, 0, 175, "92% cotton, 6% polyester, 2% elastane"),
    ("ao-khoac-bomber-uniform", "FR-BOM-002", "Áo khoác bomber Uniform", 899_000, 1_199_000, "ao-khoac", "nam", "taupe",
     ["nau-dua", "den", "reu", "be-cat"], TOPS + ["XXL"], 0, 1, 480, "65% polyester tái chế, 35% cotton"),
]

PROVINCES = {
    "79": ("TP. Hồ Chí Minh", ["Phường Sài Gòn", "Phường Bến Thành", "Phường Bến Nghé", "Phường Thủ Đức"]),
    "01": ("Hà Nội", ["Phường Hoàn Kiếm", "Phường Ba Đình", "Phường Cầu Giấy", "Phường Đống Đa"]),
    "48": ("Đà Nẵng", ["Phường Hải Châu", "Phường Thanh Khê", "Phường Sơn Trà", "Phường Ngũ Hành Sơn"]),
}


def seed(db) -> bool:
    """Nạp dữ liệu mẫu. Trả về False nếu đã có sản phẩm."""
    if db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
        return False
    db.execute("BEGIN IMMEDIATE")
    try:
        for pos, (slug, name, tone) in enumerate(CATEGORIES):
            db.execute("INSERT INTO categories (slug, name, tone, position) VALUES (?, ?, ?, ?)", (slug, name, tone, pos))
        for pos, (slug, name, hex_) in enumerate(COLOR_FAMILIES):
            db.execute("INSERT INTO color_families (slug, name, hex, position) VALUES (?, ?, ?, ?)", (slug, name, hex_, pos))
        for slug, name, hex_, family in COLORS:
            db.execute("INSERT INTO colors (slug, name, hex, family) VALUES (?, ?, ?, ?)", (slug, name, hex_, family))
        color_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM colors")}
        category_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM categories")}

        for (slug, sku, name, price, compare, cat, dept, tone, colors, sizes, is_new, featured, sold, material) in PRODUCTS:
            cur = db.execute(
                """INSERT INTO products (slug, sku, name, description, price, compare_price, category_id, department,
                                         tone, material, model_info, care, is_new, is_featured, sold_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    slug, sku, name,
                    "Thiết kế tinh gọn, chất liệu bền đẹp, dễ phối với nhiều trang phục hằng ngày.",
                    price, compare, category_id[cat], dept, tone, material,
                    "Cao 1m78, nặng 68kg, mặc size M", "Giặt máy nước lạnh, không dùng chất tẩy",
                    is_new, featured, sold,
                ),
            )
            pid = cur.lastrowid
            for pos, label in enumerate(["mặt trước", "mặt sau", "cổ áo/lưng quần", "chi tiết", "người mẫu", "chất liệu"]):
                db.execute(
                    "INSERT INTO product_images (product_id, tone, label, position) VALUES (?, ?, ?, ?)",
                    (pid, tone, f"Ảnh {pos + 1} – {label}", pos),
                )
            for c in colors:
                for size in sizes:
                    db.execute(
                        "INSERT INTO variants (product_id, color_id, size, sku, stock) VALUES (?, ?, ?, ?, ?)",
                        (pid, color_id[c], size, f"{sku}-{c.upper()}-{size}", 25),
                    )

        db.execute(
            "INSERT INTO coupons (code, percent, min_order, max_discount, expires_at) VALUES ('TUDO10', 10, 0, 200000, '2030-12-31')"
        )
        db.execute(
            "INSERT INTO coupons (code, percent, min_order, max_discount) VALUES ('FREESION20', 20, 1000000, 300000)"
        )
        oxford = db.execute("SELECT id FROM products WHERE slug = 'ao-so-mi-oxford-dang-rong'").fetchone()["id"]
        db.execute(
            "INSERT INTO testimonials (author, city, product_id, rating, quote) VALUES (?, ?, ?, 5, ?)",
            (
                "Minh Anh", "TP. Hồ Chí Minh", oxford,
                "Áo mặc rất thích, vải dày dặn mà không bị cứng. Đi làm hay đi chơi đều hợp. Chắc chắn sẽ mua thêm màu khác!",
            ),
        )
        for code, (name, wards) in PROVINCES.items():
            db.execute("INSERT INTO provinces (code, name) VALUES (?, ?)", (code, name))
            for ward in wards:
                db.execute("INSERT INTO wards (province_code, name) VALUES (?, ?)", (code, ward))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return True
