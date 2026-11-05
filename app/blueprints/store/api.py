"""Danh mục sản phẩm (công khai, chỉ trả sản phẩm status = 'active').

    GET  /api/home                          dữ liệu trang chủ
    GET  /api/categories                    danh mục
    GET  /api/colors                        nhóm màu + màu (bộ lọc ở trang Shop)
    GET  /api/products                      danh sách + lọc + sắp xếp + phân trang
    GET  /api/products/<slug>               chi tiết (ảnh, màu/size/tồn kho, điểm đánh giá)
    GET  /api/products/<slug>/related       "Có thể bạn cũng thích"
    GET  /api/products/<slug>/reviews       đánh giá (phân trang)
    POST /api/products/<slug>/reviews       gửi đánh giá (cần đăng nhập)

Tham số của /api/products:
    department=nu|nam|phu-kien   category=ao-so-mi,quan-jean   color=den,trang (nhóm màu)
    size=S,M   price_min  price_max   q (tìm không dấu)   is_new=1   sale=1   featured=1
    exclude=slug1,slug2   sort=featured|newest|price_asc|price_desc|bestseller
    page  per_page (mặc định 12, tối đa 48)
"""
from __future__ import annotations

import math

from flask import jsonify, request

from ...db import get_db
from . import store_api_bp as api_bp
from ...common.helpers import ApiError, Fields, arg_int, arg_list, as_int, current_user, json_body
from ...common.serializers import PRODUCT_CARD_SELECT, product_cards, product_detail, review_json, review_summary
from ...common.services import placeholders

SORTS = {
    "featured": "p.is_featured DESC, p.sold_count DESC, p.id DESC",
    "newest": "p.created_at DESC, p.id DESC",
    "price_asc": "p.price ASC, p.id DESC",
    "price_desc": "p.price DESC, p.id DESC",
    "bestseller": "p.sold_count DESC, p.id DESC",
}


def _like_pattern(text: str) -> str:
    from ...db import unaccent

    escaped = unaccent(text.strip()).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def build_filters(skip: tuple[str, ...] = ()):
    """Dựng mệnh đề WHERE từ query string. `skip` bỏ qua một bộ lọc (dùng cho facet)."""
    where = ["p.status = 'active'"]
    params: list = []
    args = request.args

    department = args.get("department")
    if department:
        if department not in ("nu", "nam", "phu-kien"):
            raise ApiError("department phải là nu, nam hoặc phu-kien.", 400, "invalid_param")
        where.append("p.department = ?")
        params.append(department)

    categories = arg_list("category")
    if categories and "category" not in skip:
        where.append(f"p.category_id IN (SELECT id FROM categories WHERE slug IN ({placeholders(categories)}))")
        params += categories

    families, sizes = arg_list("color"), [s.upper() for s in arg_list("size")]
    if families or sizes:  # màu và size phải cùng thuộc một biến thể còn hiệu lực
        clause = ["v.product_id = p.id"]
        if families:
            clause.append(f"c.family IN ({placeholders(families)})")
            params += families
        if sizes:
            clause.append(f"upper(v.size) IN ({placeholders(sizes)})")
            params += sizes
        where.append(
            "EXISTS (SELECT 1 FROM variants v JOIN colors c ON c.id = v.color_id WHERE " + " AND ".join(clause) + ")"
        )

    for name, op in (("price_min", ">="), ("price_max", "<=")):
        if args.get(name) not in (None, ""):
            value = as_int(args.get(name))
            if value is None or value < 0:
                raise ApiError(f"{name} phải là số nguyên không âm.", 400, "invalid_param")
            where.append(f"p.price {op} ?")
            params.append(value)

    if args.get("is_new") == "1":
        where.append("p.is_new = 1")
    if args.get("featured") == "1":
        where.append("p.is_featured = 1")
    if args.get("sale") == "1":
        where.append("p.compare_price IS NOT NULL")

    q = (args.get("q") or "").strip()
    if q:
        where.append("(unaccent(p.name) LIKE ? ESCAPE '\\' OR unaccent(p.sku) LIKE ? ESCAPE '\\' "
                     "OR unaccent(p.description) LIKE ? ESCAPE '\\')")
        pattern = _like_pattern(q)
        params += [pattern, pattern, pattern]

    excluded = arg_list("exclude")
    if excluded:
        where.append(f"p.slug NOT IN ({placeholders(excluded)})")
        params += excluded
    return where, params


@api_bp.get("/home")
def home():
    db = get_db()
    categories = db.execute("SELECT slug, name, tone FROM categories ORDER BY position, id").fetchall()

    def cards(extra: str, limit: int):
        rows = db.execute(
            f"{PRODUCT_CARD_SELECT} WHERE p.status = 'active' {extra} LIMIT ?", (limit,)
        ).fetchall()
        return product_cards(db, rows)

    testimonials = db.execute(
        """SELECT t.id, t.author, t.city, t.rating, t.quote, p.slug AS product_slug, p.name AS product_name
           FROM testimonials t LEFT JOIN products p ON p.id = t.product_id
           WHERE t.is_active = 1 ORDER BY t.id"""
    ).fetchall()
    return jsonify(
        categories=[dict(c) for c in categories],
        featured=cards(f"AND p.is_featured = 1 ORDER BY {SORTS['featured']}", 4),
        new_arrivals=cards(f"AND p.is_new = 1 ORDER BY {SORTS['newest']}", 4),
        sale=cards(f"AND p.compare_price IS NOT NULL ORDER BY {SORTS['bestseller']}", 4),
        testimonials=[dict(t) for t in testimonials],
    )


@api_bp.get("/categories")
def categories():
    rows = get_db().execute(
        """SELECT c.id, c.slug, c.name, c.tone, COUNT(p.id) AS product_count
           FROM categories c LEFT JOIN products p ON p.category_id = c.id AND p.status = 'active'
           GROUP BY c.id ORDER BY c.position, c.id"""
    ).fetchall()
    return jsonify(items=[dict(r) for r in rows])


@api_bp.get("/colors")
def colors():
    db = get_db()
    families = [dict(r) for r in db.execute("SELECT slug, name, hex FROM color_families ORDER BY position, slug")]
    by_family = {f["slug"]: [] for f in families}
    for c in db.execute("SELECT slug, name, hex, family FROM colors ORDER BY id"):
        by_family.setdefault(c["family"], []).append({"slug": c["slug"], "name": c["name"], "hex": c["hex"]})
    for f in families:
        f["colors"] = by_family[f["slug"]]
    return jsonify(items=families)


@api_bp.get("/products")
def list_products():
    db = get_db()
    page = arg_int("page", 1)
    per_page = arg_int("per_page", 12, maximum=48)
    sort = request.args.get("sort", "featured")
    if sort not in SORTS:
        raise ApiError(f"sort phải là một trong: {', '.join(SORTS)}.", 400, "invalid_param")

    where, params = build_filters()
    clause = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) FROM products p WHERE {clause}", params).fetchone()[0]
    rows = db.execute(
        f"{PRODUCT_CARD_SELECT} WHERE {clause} ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()

    # Số lượng theo danh mục (áp dụng mọi bộ lọc trừ chính bộ lọc danh mục).
    f_where, f_params = build_filters(skip=("category",))
    facet_rows = db.execute(
        f"""SELECT c.slug, c.name, COUNT(p.id) AS count FROM categories c
            LEFT JOIN products p ON p.category_id = c.id AND {" AND ".join(f_where)}
            GROUP BY c.id ORDER BY c.position, c.id""",
        f_params,
    ).fetchall()
    return jsonify(
        items=product_cards(db, rows),
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
        facets={"categories": [dict(r) for r in facet_rows]},
    )


def _active_product(db, slug: str):
    row = db.execute(f"{PRODUCT_CARD_SELECT} WHERE p.slug = ? AND p.status = 'active'", (slug,)).fetchone()
    if row is None:
        raise ApiError("Không tìm thấy sản phẩm.", 404, "product_not_found")
    return row


@api_bp.get("/products/<slug>")
def get_product(slug):
    db = get_db()
    return jsonify(product=product_detail(db, _active_product(db, slug)))


@api_bp.get("/products/<slug>/related")
def related_products(slug):
    db = get_db()
    product = _active_product(db, slug)
    limit = arg_int("limit", 4, maximum=12)
    rows = db.execute(
        f"""{PRODUCT_CARD_SELECT} WHERE p.status = 'active' AND p.id != ?
            ORDER BY (p.category_id = ?) DESC, (p.department = ?) DESC, p.is_featured DESC, p.sold_count DESC, p.id DESC
            LIMIT ?""",
        (product["id"], product["category_id"], product["department"], limit),
    ).fetchall()
    return jsonify(items=product_cards(db, rows))


def list_reviews(slug):
    db = get_db()
    product = _active_product(db, slug)
    page = arg_int("page", 1)
    per_page = arg_int("per_page", 10, maximum=50)
    where, params = "product_id = ?", [product["id"]]
    rating = as_int(request.args.get("rating")) if request.args.get("rating") else None
    if rating is not None:
        if not 1 <= rating <= 5:
            raise ApiError("rating phải từ 1 đến 5.", 400, "invalid_param")
        where += " AND rating = ?"
        params.append(rating)
    total = db.execute(f"SELECT COUNT(*) FROM reviews WHERE {where}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM reviews WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    return jsonify(
        items=[review_json(r) for r in rows],
        summary=review_summary(db, product["id"]),
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


def create_review(slug):
    if current_user() is None:
        raise ApiError("Bạn cần đăng nhập để đánh giá sản phẩm.", 401, "unauthorized")
    db = get_db()
    product = _active_product(db, slug)
    user = current_user()
    data = json_body()
    f = Fields(data)
    rating = f.integer("rating", "Số sao", minimum=1, maximum=5)
    fit = f.integer("fit", "Độ vừa vặn", minimum=1, maximum=5, required=False)
    title = f.text("title", "Tiêu đề", required=False, max_len=120)
    body = f.text("body", "Nội dung đánh giá", max_len=2000)
    body_info = f.text("body_info", "Thông tin cơ thể", required=False, max_len=120)
    city = f.text("city", "Thành phố", required=False, max_len=80)
    f.done()

    if db.execute("SELECT 1 FROM reviews WHERE product_id = ? AND user_id = ?", (product["id"], user["id"])).fetchone():
        raise ApiError("Bạn đã đánh giá sản phẩm này rồi.", 409, "already_reviewed")
    verified = db.execute(
        """SELECT 1 FROM order_items oi JOIN orders o ON o.id = oi.order_id
           WHERE o.user_id = ? AND o.status = 'delivered' AND oi.product_id = ? LIMIT 1""",
        (user["id"], product["id"]),
    ).fetchone()
    cur = db.execute(
        """INSERT INTO reviews (product_id, user_id, author_name, city, rating, fit, title, body, body_info, verified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (product["id"], user["id"], user["full_name"], city, rating, fit, title, body, body_info, int(bool(verified))),
    )
    review = db.execute("SELECT * FROM reviews WHERE id = ?", (cur.lastrowid,)).fetchone()
    response = jsonify(review=review_json(review), summary=review_summary(db, product["id"]))
    response.status_code = 201
    return response


@api_bp.route("/products/<slug>/reviews", methods=["GET", "POST"])
def product_reviews(slug):
    """Một URL, hai phương thức (test kiểm tra mỗi đường dẫn chỉ đăng ký một lần)."""
    return create_review(slug) if request.method == "POST" else list_reviews(slug)
