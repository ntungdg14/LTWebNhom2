"""Sản phẩm bổ sung + thông tin chi tiết từng sản phẩm + gắn ảnh thật.

Chạy:  flask --app run seed-db
- Thêm các sản phẩm bổ sung (bỏ qua sản phẩm đã có theo slug) nên chạy lại bao nhiêu lần cũng an toàn.
- Điền mô tả / thông tin người mẫu / cách giặt riêng cho từng sản phẩm (kể cả 9 sản phẩm gốc).
- Gắn ảnh: bỏ ảnh vào app/static/images/products/ đặt tên <SKU>-<số>.jpg (số 1..6, đuôi jpg/jpeg/png/webp),
  ví dụ FR-BOM-002-1.jpg; chạy lại lệnh trên là ảnh được gắn vào sản phẩm.
Tách khỏi seed.py để bộ kiểm thử (dùng seed.py) không bị đổi số liệu.
"""
from __future__ import annotations

from pathlib import Path

from .seed import JEANS, TOPS

IMAGE_DIR = Path(__file__).resolve().parent / "static" / "images" / "products"
IMAGE_URL = "/static/images/products/"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
IMAGE_LABELS = ["mặt trước", "mặt sau", "cổ áo/lưng quần", "chi tiết", "người mẫu", "chất liệu"]

# slug, sku, tên, giá, giá gốc, danh mục, bộ phận, tone, màu, size, mới, nổi bật, đã bán, chất liệu
EXTRA_PRODUCTS = [
    ("ao-so-mi-linen-basic", "FR-LIN-009", "Áo sơ mi Linen Basic", 549_000, None, "ao-so-mi", "nu", "beige",
     ["be-cat", "trang-kem"], TOPS, 1, 1, 150, "100% linen"),
    ("ao-so-mi-flannel-ke-caro", "FR-FLA-010", "Áo sơ mi Flannel kẻ caro", 599_000, 749_000, "ao-so-mi", "nam", "olive",
     ["reu", "nau-dua"], TOPS, 0, 0, 90, "100% cotton flannel 180gsm"),
    ("quan-jean-straight-fit", "FR-JEA-011", "Quần jean Straight Fit", 699_000, None, "quan-jean", "nam", "denim",
     ["xanh-dam", "den-vintage"], JEANS, 0, 1, 260, "99% cotton, 1% elastane"),
    ("quan-jean-baggy-wash", "FR-BAG-012", "Quần jean Baggy wash", 749_000, 899_000, "quan-jean", "nu", "denim",
     ["xam-khoi", "indigo-dam"], JEANS, 1, 0, 120, "100% cotton denim 12oz"),
    ("ao-polo-pique", "FR-POL-013", "Áo polo Piqué", 359_000, None, "ao-thun", "nam", "cream",
     ["trang", "den"], TOPS, 0, 1, 380, "100% cotton piqué"),
    ("ao-thun-oversize-in-chu", "FR-OVT-014", "Áo thun Oversize in chữ", 319_000, None, "ao-thun", "nu", "taupe",
     ["den-vintage", "be-cat"], TOPS, 1, 0, 205, "100% cotton 240gsm"),
    ("ao-len-co-lo-merino", "FR-MER-015", "Áo len cổ lọ Merino", 899_000, None, "ao-len", "nu", "rose",
     ["den", "xam-khoi"], TOPS, 1, 1, 70, "50% len merino, 50% acrylic"),
    ("ao-cardigan-len-det", "FR-CAR-016", "Áo cardigan len dệt", 679_000, 849_000, "ao-len", "nu", "beige",
     ["be-cat", "reu"], TOPS, 0, 0, 85, "60% cotton, 40% acrylic"),
    ("ao-khoac-corduroy", "FR-COR-017", "Áo khoác Corduroy", 899_000, None, "ao-khoac", "nam", "olive",
     ["reu", "nau-dua"], TOPS, 1, 1, 110, "100% cotton corduroy"),
    ("ao-khoac-denim-trucker", "FR-TRK-018", "Áo khoác denim Trucker", 849_000, None, "ao-khoac", "nam", "denim",
     ["xanh-dam"], TOPS, 0, 0, 95, "100% cotton denim 11oz"),
    ("quan-dai-relaxed", "FR-REL-019", "Quần dài Relaxed", 559_000, None, "quan-dai", "nam", "taupe",
     ["den", "be-cat", "xam-khoi"], JEANS, 0, 0, 140, "65% polyester, 33% viscose, 2% elastane"),
    ("quan-dai-linen-lung-thun", "FR-LNP-020", "Quần dài linen lưng thun", 489_000, 589_000, "quan-dai", "nu", "cream",
     ["trang-kem", "nau-dua"], TOPS, 0, 0, 160, "55% linen, 45% cotton"),
]

# sku -> (mô tả, thông tin người mẫu, cách giặt)
PRODUCT_INFO = {
    "FR-OXF-001": ("Áo sơ mi Oxford dáng rộng, vải dệt basket dày dặn, cổ button-down gọn gàng. Mặc đi làm hay đi chơi đều hợp, xắn tay lên vẫn đẹp.",
                   "Cao 1m65, nặng 52kg, mặc size M", "Giặt máy nước lạnh, ủi mặt trái ở nhiệt độ vừa"),
    "FR-JEA-002": ("Quần jean ống suông màu indigo đậm, cạp cao, ống rộng vừa phải giúp dáng đứng và dễ phối với áo sơ mi hoặc áo thun.",
                   "Cao 1m68, nặng 54kg, mặc size 29", "Giặt lộn trái, nước lạnh, không dùng chất tẩy"),
    "FR-TEE-003": ("Áo thun cotton Essential cổ tròn, form vừa, vải compact 220gsm dày mịn, không xù và giữ form sau nhiều lần giặt.",
                   "Cao 1m70, nặng 58kg, mặc size M", "Giặt máy nước lạnh, không sấy nhiệt cao"),
    "FR-WAF-004": ("Áo len dệt họa tiết waffle cổ tròn, bề mặt nổi nhẹ, mềm và ấm vừa đủ cho những ngày se lạnh.",
                   "Cao 1m62, nặng 48kg, mặc size S", "Giặt tay hoặc chế độ len, phơi phẳng"),
    "FR-OVS-005": ("Áo overshirt Heavyweight bằng cotton twill dày, có thể mặc như áo khoác mỏng hoặc áo sơ mi khoác ngoài.",
                   "Cao 1m65, nặng 52kg, mặc size M", "Giặt máy nước lạnh, phơi trong bóng râm"),
    "FR-CHI-006": ("Quần dài ống đứng Chino màu be cát, lưng vừa, vải cotton co giãn nhẹ, thoải mái cả ngày dài.",
                   "Cao 1m68, nặng 54kg, mặc size 29", "Giặt máy nước lạnh, ủi ở nhiệt độ vừa"),
    "FR-BOX-007": ("Áo thun Boxy dáng ngắn, vai rộng, vải 260gsm dày dặn đứng form, phối đẹp với quần ống rộng.",
                   "Cao 1m65, nặng 50kg, mặc size M", "Giặt lộn trái, nước lạnh, không sấy"),
    "FR-JSL-008": ("Quần jean slim co giãn nhẹ, ôm vừa phải, màu indigo đậm dễ mặc hằng ngày.",
                   "Cao 1m70, nặng 60kg, mặc size 30", "Giặt lộn trái, nước lạnh, không dùng chất tẩy"),
    "FR-BOM-002": ("Áo khoác bomber dáng suông, cổ bo gọn với khóa kéo kim loại. Lớp lót mỏng giữ ấm vừa đủ cho những ngày se lạnh, dễ mặc ngoài áo thun hay sơ mi.",
                   "Cao 1m78, nặng 68kg, mặc size M", "Giặt máy nhẹ nhàng, không dùng chất tẩy"),
    "FR-LIN-009": ("Áo sơ mi linen thoáng mát, bề mặt có vân tự nhiên, càng mặc càng mềm. Hợp những ngày nắng và phối cùng quần jean hoặc quần chino.",
                   "Cao 1m65, nặng 50kg, mặc size M", "Giặt tay hoặc máy nhẹ, ủi khi vải còn hơi ẩm"),
    "FR-FLA-010": ("Áo sơ mi flannel kẻ caro mềm và ấm, dùng như áo khoác mỏng ngoài áo thun. Cúc cài chắc, đường may kép ở vai.",
                   "Cao 1m75, nặng 65kg, mặc size L", "Giặt máy nước lạnh, phơi mặt trái"),
    "FR-JEA-011": ("Quần jean Straight Fit ống đứng cổ điển, vải denim đứng dáng, ít giãn nên giữ form rất tốt.",
                   "Cao 1m75, nặng 66kg, mặc size 31", "Giặt lộn trái, nước lạnh, giặt riêng lần đầu"),
    "FR-BAG-012": ("Quần jean Baggy wash màu xám khói, cạp cao, ống rộng thoải mái, hiệu ứng wash nhẹ cho vẻ ngoài vintage.",
                   "Cao 1m66, nặng 51kg, mặc size 28", "Giặt lộn trái, nước lạnh, không sấy"),
    "FR-POL-013": ("Áo polo vải piqué thoáng, cổ bẻ đứng form, bo tay ôm nhẹ. Mặc đi làm hoặc đi chơi đều lịch sự.",
                   "Cao 1m76, nặng 66kg, mặc size L", "Giặt máy nước lạnh, không dùng chất tẩy"),
    "FR-OVT-014": ("Áo thun Oversize in chữ nhỏ trước ngực, form rộng thoải mái, vải 240gsm dày vừa không bị xuyên thấu.",
                   "Cao 1m63, nặng 49kg, mặc size M", "Giặt lộn trái, nước lạnh, không sấy"),
    "FR-MER-015": ("Áo len cổ lọ pha merino, mềm mịn và giữ ấm tốt mà không ngứa. Dễ phối lớp trong áo khoác hoặc mặc riêng.",
                   "Cao 1m65, nặng 50kg, mặc size M", "Giặt tay nước lạnh, phơi phẳng, không vắt mạnh"),
    "FR-CAR-016": ("Áo cardigan len dệt cài cúc, dáng lửng, bề mặt dệt nổi nhẹ. Khoác ngoài váy hoặc áo thun đều đẹp.",
                   "Cao 1m64, nặng 49kg, mặc size S", "Giặt tay hoặc chế độ len, phơi phẳng"),
    "FR-COR-017": ("Áo khoác Corduroy vải nhung tăm dày dặn, cổ bẻ, hai túi ngực. Màu đất ấm, dễ phối với jean và chino.",
                   "Cao 1m76, nặng 67kg, mặc size L", "Giặt máy nước lạnh, lộn trái, không sấy"),
    "FR-TRK-018": ("Áo khoác denim Trucker kiểu cổ điển với hai túi ngực và khuy kim loại. Vải denim 11oz đứng dáng, càng mặc càng đẹp.",
                   "Cao 1m74, nặng 64kg, mặc size M", "Giặt riêng lần đầu, lộn trái, nước lạnh"),
    "FR-REL-019": ("Quần dài Relaxed ống rộng, chất vải rủ nhẹ, lưng có dây rút kín đáo. Phù hợp đi làm và đi chơi.",
                   "Cao 1m78, nặng 68kg, mặc size 30", "Giặt máy nước lạnh, ủi nhiệt độ thấp"),
    "FR-LNP-020": ("Quần dài linen lưng thun, nhẹ và thoáng, phù hợp thời tiết nóng. Ống suông gọn, có hai túi bên.",
                   "Cao 1m65, nặng 50kg, mặc size M", "Giặt tay hoặc máy nhẹ, ủi khi vải còn hơi ẩm"),
}
DEFAULT_INFO = (
    "Thiết kế tinh gọn, chất liệu bền đẹp, dễ phối với nhiều trang phục hằng ngày.",
    "Cao 1m78, nặng 68kg, mặc size M",
    "Giặt máy nước lạnh, không dùng chất tẩy",
)


# ---------------------------------------------------------------------------
# Bộ sản phẩm theo ảnh thật (LTW2): mỗi sản phẩm 1 ảnh, ảnh nằm ở static/images/products/<SKU>-1.<đuôi>
# ---------------------------------------------------------------------------
NEW_CATEGORIES = [  # slug, tên, tone, vị trí
    ("vay", "Váy", "rose", 6),
    ("do-cong-so", "Đồ công sở", "taupe", 7),
    ("phu-kien", "Phụ kiện", "beige", 8),
]
NEW_COLORS = [  # slug, tên, hex, nhóm màu
    ("xanh-nhat", "Xanh nhạt", "#A9C4E3", "xanh-duong"),
    ("xanh-jean", "Xanh jean", "#5E7FA6", "xanh-duong"),
    ("cam", "Cam", "#D9732F", "nau"),
    ("ke-caro", "Kẻ caro đen trắng", "#2B2B2B", "den"),
]
FREE = ["Free size"]
# slug, sku, tên, giá, giá gốc, danh mục, bộ phận, tone, màu, size, mới, nổi bật, đã bán, chất liệu, mô tả, người mẫu, cách giặt
CATALOG_PRODUCTS = [
    ("ao-khoac-du-form-rong", "FR-DUO-021", "Áo khoác dù Form rộng", 649_000, 799_000, "ao-khoac", "nam", "taupe",
     ["den"], TOPS + ["XXL"], 1, 1, 260, "100% polyester dù chống gió nhẹ",
     "Áo khoác dù form rộng, cổ đứng, khóa kéo giữa và bo gấu rút dây. Vải dù nhẹ chắn gió, đi mưa phùn hay đi làm sớm đều tiện.",
     "Cao 1m76, nặng 66kg, mặc size L", "Giặt máy nước lạnh, không sấy nhiệt cao, không ủi trực tiếp lên logo"),
    ("ao-khoac-corduroy-lot-long", "FR-CDL-022", "Áo khoác Corduroy lót lông", 1_099_000, None, "ao-khoac", "nam", "taupe",
     ["nau-dua"], TOPS, 1, 1, 140, "Vải nhung tăm, lót lông cừu nhân tạo",
     "Áo khoác nhung tăm màu nâu đất, cổ lót lông mềm và hai túi ngực nắp cài. Giữ ấm tốt cho mùa thu đông, phối đẹp với jean và chino.",
     "Cao 1m75, nặng 65kg, mặc size L", "Giặt tay hoặc giặt máy nhẹ, phơi mặt trái, không sấy"),
    ("ao-so-mi-oxford-xanh-nhat", "FR-OXB-023", "Áo sơ mi Oxford xanh nhạt", 449_000, None, "ao-so-mi", "nam", "denim",
     ["xanh-nhat"], TOPS, 0, 1, 330, "100% cotton Oxford",
     "Áo sơ mi Oxford xanh nhạt, cổ button-down, một túi ngực. Vải dệt Oxford dày vừa, đứng form, mặc đi làm hay đi chơi đều lịch sự.",
     "Cao 1m72, nặng 62kg, mặc size M", "Giặt máy nước lạnh, ủi mặt trái ở nhiệt độ vừa"),
    ("ao-ni-sweatshirt-co-tron", "FR-SWE-024", "Áo nỉ Sweatshirt cổ tròn", 399_000, None, "ao-thun", "nam", "taupe",
     ["den"], TOPS, 0, 1, 290, "80% cotton, 20% polyester nỉ da cá",
     "Áo nỉ cổ tròn màu đen trơn, form rộng nhẹ, bo cổ và bo gấu chắc chắn. Bề mặt nỉ mịn, dễ mặc riêng hoặc làm lớp trong áo khoác.",
     "Cao 1m73, nặng 63kg, mặc size M", "Giặt lộn trái, nước lạnh, không sấy nhiệt cao"),
    ("ao-thun-boxy-in-chu-chiu", "FR-CHU-025", "Áo thun Boxy in chữ “chịu”", 299_000, None, "ao-thun", "nam", "cream",
     ["cam"], TOPS, 1, 0, 180, "100% cotton 240gsm",
     "Áo thun boxy màu cam đất, in chữ “chịu” ở ngực. Form ngắn, vai rộng, vải dày vừa không bị xuyên thấu.",
     "Cao 1m70, nặng 60kg, mặc size M", "Giặt lộn trái, nước lạnh, không sấy để giữ hình in"),
    ("set-vest-cong-so-chan-vay", "FR-SET-026", "Set vest công sở chân váy", 1_290_000, 1_590_000, "do-cong-so", "nu", "taupe",
     ["den"], TOPS, 1, 1, 95, "70% polyester, 28% viscose, 2% elastane",
     "Bộ vest nữ gồm áo blazer hai cúc và chân váy bút chì. Phom ôm vừa, vải đứng dáng, thích hợp đi làm, phỏng vấn và dự họp.",
     "Cao 1m65, nặng 51kg, mặc size M", "Giặt khô hoặc giặt tay nhẹ, ủi nhiệt độ thấp qua lớp vải lót"),
    ("khan-len-ke-caro", "FR-SCA-027", "Khăn len kẻ caro", 289_000, None, "phu-kien", "phu-kien", "beige",
     ["ke-caro"], FREE, 1, 0, 220, "100% acrylic mềm, tua rua hai đầu",
     "Khăn quàng cổ kẻ caro đen trắng điểm sọc đỏ, tua rua hai đầu. Mềm, nhẹ và ấm, dễ phối với áo khoác tối màu.",
     "Một size, quàng cổ hoặc choàng vai", "Giặt tay nước lạnh, phơi phẳng, không vắt mạnh"),
    ("quan-dai-basic-kaki", "FR-BAS-028", "Quần dài Basic kaki", 499_000, None, "quan-dai", "nam", "beige",
     ["be-cat"], JEANS, 0, 0, 170, "98% cotton, 2% elastane",
     "Quần dài ống đứng màu be kaki, lưng vừa, túi chéo hai bên. Phom gọn, dễ phối với áo sơ mi hoặc áo thun.",
     "Cao 1m75, nặng 66kg, mặc size 30", "Giặt máy nước lạnh, ủi nhiệt độ vừa"),
    ("quan-jean-slimfit-xanh", "FR-SLM-029", "Quần jean Slimfit xanh", 599_000, 749_000, "quan-jean", "nam", "denim",
     ["xanh-jean"], JEANS, 0, 1, 310, "98% cotton, 2% elastane",
     "Quần jean slimfit xanh wash nhẹ, ôm vừa phải ở đùi và ống. Vải denim co giãn nhẹ, mặc thoải mái cả ngày.",
     "Cao 1m74, nặng 64kg, mặc size 30", "Giặt lộn trái, nước lạnh, giặt riêng lần đầu"),
    ("tui-xach-tay-da", "FR-BAG-030", "Túi xách tay dáng hộp", 749_000, None, "phu-kien", "phu-kien", "beige",
     ["be-cat"], FREE, 1, 1, 120, "Da PU cao cấp, lót vải",
     "Túi xách tay màu be cát, dáng hộp gọn, quai xách đôi. Hợp đi làm và đi chơi, đựng vừa laptop mỏng, ví và đồ dùng hằng ngày.",
     "Một size", "Lau bằng khăn ẩm, tránh nước và ánh nắng trực tiếp"),
    ("vay-den-xoe-tre-vai", "FR-DRS-031", "Váy đen xòe trễ vai", 699_000, None, "vay", "nu", "rose",
     ["den"], TOPS, 1, 1, 150, "Vải tuyết mưa, lót trong",
     "Váy đen cổ chéo trễ vai, eo ôm và chân váy xòe. Thanh lịch cho tiệc tối, sinh nhật hoặc buổi hẹn.",
     "Cao 1m62, nặng 47kg, mặc size S", "Giặt tay hoặc chế độ nhẹ, ủi nhiệt độ thấp mặt trái"),
    ("ao-len-cable-hoa-tiet-kim-cuong", "FR-CAB-032", "Áo len cable họa tiết kim cương", 649_000, None, "ao-len", "nam", "cream",
     ["be-cat"], TOPS, 0, 1, 125, "60% cotton, 40% acrylic",
     "Áo len dệt họa tiết cable kim cương ở thân, tay dệt gân dọc. Màu be ấm, cổ tròn, mặc riêng hay lót trong áo khoác đều đẹp.",
     "Cao 1m74, nặng 64kg, mặc size M", "Giặt tay hoặc chế độ len, phơi phẳng"),
]


def _find_catalog_image(sku: str) -> str | None:
    return _find_image(sku, 1)


def seed_catalog(db) -> int:
    """Thêm danh mục/màu còn thiếu và bộ sản phẩm CATALOG_PRODUCTS (bỏ qua nếu slug đã có). Gọi trong transaction."""
    for slug, name, tone, pos in NEW_CATEGORIES:
        db.execute("INSERT OR IGNORE INTO categories (slug, name, tone, position) VALUES (?, ?, ?, ?)", (slug, name, tone, pos))
    for slug, name, hex_, family in NEW_COLORS:
        db.execute("INSERT OR IGNORE INTO colors (slug, name, hex, family) VALUES (?, ?, ?, ?)", (slug, name, hex_, family))
    color_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM colors")}
    category_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM categories")}
    existing = {r["slug"] for r in db.execute("SELECT slug FROM products")}
    added = 0
    for (slug, sku, name, price, compare, cat, dept, tone, colors, sizes, is_new, featured, sold, material,
         description, model_info, care) in CATALOG_PRODUCTS:
        if slug in existing:
            continue
        pid = db.execute(
            """INSERT INTO products (slug, sku, name, description, price, compare_price, category_id, department,
                                     tone, material, model_info, care, is_new, is_featured, sold_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, sku, name, description, price, compare, category_id[cat], dept, tone, material,
             model_info, care, is_new, featured, sold),
        ).lastrowid
        db.execute("INSERT INTO product_images (product_id, url, tone, label, position) VALUES (?, ?, ?, ?, 0)",
                   (pid, _find_catalog_image(sku), tone, "Ảnh 1 – mặt trước"))
        for c in colors:
            for size in sizes:
                db.execute("INSERT INTO variants (product_id, color_id, size, sku, stock) VALUES (?, ?, ?, ?, ?)",
                           (pid, color_id[c], size, f"{sku}-{c.upper()}-{size.replace(' ', '').upper()}", 25))
        added += 1
    return added


# Sản phẩm chưa có ảnh riêng thì dùng chung ảnh của sản phẩm cùng loại (sku -> sku có ảnh).
# Có ảnh riêng <SKU>-1.jpg trong static/images/products/ thì ảnh riêng được ưu tiên.
FALLBACK_IMAGES = {
    # áo sơ mi -> sơ mi Oxford xanh nhạt
    "FR-OXF-001": "FR-OXB-023", "FR-LIN-009": "FR-OXB-023", "FR-FLA-010": "FR-OXB-023",
    # quần jean -> jean Slimfit xanh
    "FR-JEA-002": "FR-SLM-029", "FR-JSL-008": "FR-SLM-029", "FR-JEA-011": "FR-SLM-029", "FR-BAG-012": "FR-SLM-029",
    # áo thun / polo -> áo thun Boxy cam
    "FR-TEE-003": "FR-CHU-025", "FR-BOX-007": "FR-CHU-025", "FR-POL-013": "FR-CHU-025", "FR-OVT-014": "FR-CHU-025",
    # áo len / cardigan -> áo len cable
    "FR-WAF-004": "FR-CAB-032", "FR-MER-015": "FR-CAB-032", "FR-CAR-016": "FR-CAB-032",
    # quần dài -> quần kaki
    "FR-CHI-006": "FR-BAS-028", "FR-REL-019": "FR-BAS-028", "FR-LNP-020": "FR-BAS-028",
    # áo khoác: bomber -> khoác dù; overshirt, corduroy, trucker -> khoác corduroy
    "FR-BOM-002": "FR-DUO-021",
    "FR-OVS-005": "FR-CDL-022", "FR-COR-017": "FR-CDL-022", "FR-TRK-018": "FR-CDL-022",
}


def _find_image(sku: str, number: int) -> str | None:
    for ext in IMAGE_EXTS:
        if (IMAGE_DIR / f"{sku}-{number}{ext}").exists():
            return f"{IMAGE_URL}{sku}-{number}{ext}"
    return None


def attach_images(db) -> int:
    """Gắn ảnh trong static/images/products vào product_images. Trả về số ảnh đã gắn."""
    count = 0
    for p in db.execute("SELECT id, sku FROM products").fetchall():
        for row in db.execute("SELECT id, position FROM product_images WHERE product_id = ?", (p["id"],)).fetchall():
            url = _find_image(p["sku"], row["position"] + 1)
            if not url and row["position"] == 0 and p["sku"] in FALLBACK_IMAGES:
                url = _find_image(FALLBACK_IMAGES[p["sku"]], 1)
            if url:
                db.execute("UPDATE product_images SET url = ? WHERE id = ?", (url, row["id"]))
                count += 1
    return count


def seed_extra(db) -> dict:
    """Thêm sản phẩm bổ sung, cập nhật thông tin chi tiết, gắn ảnh. Idempotent."""
    stats = {"added": 0, "info": 0, "images": 0, "catalog": 0}
    db.execute("BEGIN IMMEDIATE")
    try:
        color_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM colors")}
        category_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM categories")}
        existing = {r["slug"] for r in db.execute("SELECT slug FROM products")}

        for (slug, sku, name, price, compare, cat, dept, tone, colors, sizes, is_new, featured, sold, material) in EXTRA_PRODUCTS:
            if slug in existing:
                continue
            description, model_info, care = PRODUCT_INFO.get(sku, DEFAULT_INFO)
            cur = db.execute(
                """INSERT INTO products (slug, sku, name, description, price, compare_price, category_id, department,
                                         tone, material, model_info, care, is_new, is_featured, sold_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, sku, name, description, price, compare, category_id[cat], dept, tone, material,
                 model_info, care, is_new, featured, sold),
            )
            pid = cur.lastrowid
            for pos, label in enumerate(IMAGE_LABELS):
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
            stats["added"] += 1

        for sku, (description, model_info, care) in PRODUCT_INFO.items():
            cur = db.execute(
                "UPDATE products SET description = ?, model_info = ?, care = ? WHERE sku = ?",
                (description, model_info, care, sku),
            )
            stats["info"] += cur.rowcount

        stats["catalog"] = seed_catalog(db)
        stats["images"] = attach_images(db)
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return stats
