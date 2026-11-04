"""API cửa hàng: trang chủ, danh mục, danh sách/chi tiết sản phẩm, đánh giá, tìm kiếm, địa điểm."""
from __future__ import annotations

from typing import Any

from flask import jsonify, request

from ...db import get_db
from . import api_bp
from .service import (FREE_SHIPPING_THRESHOLD, PAYMENT_METHODS, PRODUCT_CARD_SELECT, RETURN_DAYS,
                      SHIPPING_METHODS, discount_percent, product_cards)
from .utils import (ApiError, current_user, iso, json_body, login_required, page_meta, paginate_args,
                    raise_if, text, to_int)

DEPARTMENTS = {"nu": "Nữ", "nam": "Nam", "phu-kien": "Phụ kiện"}
SORTS = {
    "featured": "p.is_featured DESC, p.sold_count DESC, p.id",
    "newest": "p.is_new DESC, p.created_at DESC, p.id DESC",
    "price_asc": "p.price ASC, p.id",
    "price_desc": "p.price DESC, p.id",
    "bestseller": "p.sold_count DESC, p.id",
}
PRICE_BUCKETS = {  # khớp bộ lọc "Mức giá" trong Figma
    "under-500": (None, 499_999),
    "500-1000": (500_000, 1_000_000),
    "over-1000": (1_000_001, None),
}
SIZES = ("S", "M", "L", "XL", "XXL")


def _multi(name: str) -> list[str]:
    """Đọc tham số lặp hoặc phân tách bằng dấu phẩy: ?category=a&category=b hoặc ?category=a,b"""
    out: list[str] = []
    for raw in request.args.getlist(name):
        out += [x.strip() for x in raw.split(",") if x.strip()]
    return out


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _filters(*, facets_only: bool = False) -> tuple[str, list[Any]]:
    """Dựng mệnh đề WHERE từ query string. facets_only: chỉ áp dụng bộ lọc 'ngữ cảnh'."""
    where, args = ["p.status = 'active'"], []
    dept = request.args.get("department")
    if dept:
        if dept not in DEPARTMENTS:
            raise ApiError("department không hợp lệ.", 400, "bad_request")
        where.append("p.department = ?")
        args.append(dept)
    if request.args.get("new") in ("1", "true"):
        where.append("p.is_new = 1")
    if request.args.get("sale") in ("1", "true"):
        where.append("p.compare_price IS NOT NULL")
    q = (request.args.get("q") or "").strip()
    if q:
        where.append("(p.name LIKE ? ESCAPE '\\' OR p.sku LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')")
        args += [_like(q)] * 3
    if facets_only:
        return " AND ".join(where), args

    cats = _multi("category")
    if cats:
        where.append(f"c.slug IN ({','.join('?' * len(cats))})")
        args += cats
    colors, sizes = _multi("color"), [s.upper() for s in _multi("size")]
    if colors or sizes:
        cond = []
        if colors:
            cond.append(f"co.family IN ({','.join('?' * len(colors))})")
            args += colors
        if sizes:
            cond.append(f"v.size IN ({','.join('?' * len(sizes))}) AND v.stock > 0")
            args += sizes
        where.append("EXISTS (SELECT 1 FROM variants v JOIN colors co ON co.id = v.color_id "
                     f"WHERE v.product_id = p.id AND {' AND '.join(cond)})")
    lo = hi = None
    bucket = request.args.get("price")
    if bucket:
        if bucket not in PRICE_BUCKETS:
            raise ApiError("price phải là under-500, 500-1000 hoặc over-1000.", 400, "bad_request")
        lo, hi = PRICE_BUCKETS[bucket]
    if request.args.get("price_min"):
        lo = to_int(request.args["price_min"], 0, 0)
    if request.args.get("price_max"):
        hi = to_int(request.args["price_max"], 0, 0)
    if lo is not None:
        where.append("p.price >= ?")
        args.append(lo)
    if hi is not None:
        where.append("p.price <= ?")
        args.append(hi)
    return " AND ".join(where), args


@api_bp.get("/config")
def site_config():
    return jsonify({
        "currency": "VND",
        "free_shipping_threshold": FREE_SHIPPING_THRESHOLD,
        "return_days": RETURN_DAYS,
        "banner": f"Miễn phí vận chuyển đơn từ {FREE_SHIPPING_THRESHOLD:,}₫ · Đổi trả trong {RETURN_DAYS} ngày".replace(",", "."),
        "support": {"hotline": "1900 636 028", "email": "hello@freesion.vn", "hours": "8:30–21:00 mỗi ngày"},
        "departments": [{"slug": k, "name": v} for k, v in DEPARTMENTS.items()],
        "shipping_methods": [{"id": k, "label": v["label"], "note": v["note"]} for k, v in SHIPPING_METHODS.items()],
        "payment_methods": [{"id": k, "label": v["label"], "description": v["description"]} for k, v in PAYMENT_METHODS.items()],
        "sort_options": [{"id": "featured", "label": "Nổi bật"}, {"id": "newest", "label": "Mới nhất"},
                         {"id": "price_asc", "label": "Giá tăng dần"}, {"id": "price_desc", "label": "Giá giảm dần"},
                         {"id": "bestseller", "label": "Bán chạy"}],
        "sizes": list(SIZES),
    })


@api_bp.get("/categories")
def categories():
    rows = get_db().execute(
        """SELECT c.id, c.slug, c.name, c.tone,
                  (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') AS product_count
           FROM categories c ORDER BY c.position""").fetchall()
    return jsonify({"items": [dict(r) for r in rows]})


@api_bp.get("/home")
def home():
    db = get_db()
    cats = [dict(r) for r in db.execute(
        """SELECT c.slug, c.name, c.tone,
                  (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') AS product_count
           FROM categories c ORDER BY c.position""")]

    def section(where: str, order: str, limit: int = 4):
        rows = db.execute(f"{PRODUCT_CARD_SELECT} WHERE p.status = 'active' AND {where} ORDER BY {order} LIMIT {limit}")
        return product_cards(rows)

    t = db.execute(
        """SELECT t.author, t.city, t.rating, t.quote, p.slug, p.name AS product_name
           FROM testimonials t LEFT JOIN products p ON p.id = t.product_id
           WHERE t.is_active = 1 ORDER BY t.id DESC LIMIT 1""").fetchone()
    max_discount = db.execute(
        "SELECT MAX(ROUND((compare_price - price) * 100.0 / compare_price)) FROM products "
        "WHERE status = 'active' AND compare_price IS NOT NULL").fetchone()[0]
    return jsonify({
        "categories": cats,
        "featured": section("p.is_featured = 1", SORTS["featured"]),
        "new_arrivals": section("p.is_new = 1", SORTS["newest"]),
        "sale": {"max_discount_percent": int(max_discount) if max_discount else None,
                 "items": section("p.compare_price IS NOT NULL", "(p.compare_price - p.price) * 1.0 / p.compare_price DESC")},
        "testimonial": dict(t) if t else None,
        "perks": [
            {"title": "Miễn phí vận chuyển", "description": f"Cho đơn hàng từ {FREE_SHIPPING_THRESHOLD:,}₫ trên toàn quốc.".replace(",", ".")},
            {"title": "Đổi trả dễ dàng", "description": f"Đổi size, đổi mẫu trong vòng {RETURN_DAYS} ngày."},
            {"title": "Cửa hàng khắp nơi", "description": "Có mặt tại TP. Hồ Chí Minh, Hà Nội, Đà Nẵng và nhiều tỉnh thành."},
        ],
    })


@api_bp.get("/products")
def list_products():
    where, args = _filters()
    sort = request.args.get("sort", "featured")
    if sort not in SORTS:
        raise ApiError(f"sort phải là một trong: {', '.join(SORTS)}.", 400, "bad_request")
    page, per_page = paginate_args(default_per_page=9)
    db = get_db()
    total = db.execute(
        f"SELECT COUNT(*) FROM products p JOIN categories c ON c.id = p.category_id WHERE {where}", args).fetchone()[0]
    rows = db.execute(
        f"{PRODUCT_CARD_SELECT} WHERE {where} ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?",
        [*args, per_page, (page - 1) * per_page]).fetchall()
    return jsonify({"items": product_cards(rows), "pagination": page_meta(page, per_page, total), "sort": sort})


@api_bp.get("/products/filters")
def product_filters():
    """Dữ liệu cho sidebar bộ lọc kèm số lượng (áp dụng department/q/new/sale hiện tại)."""
    where, args = _filters(facets_only=True)
    db = get_db()
    base = f"FROM products p JOIN categories c ON c.id = p.category_id WHERE {where}"
    cats = db.execute(
        f"""SELECT c.slug, c.name, COUNT(p.id) AS count FROM categories c
            LEFT JOIN products p ON p.category_id = c.id AND p.status = 'active'
              AND p.id IN (SELECT p.id {base})
            GROUP BY c.id ORDER BY c.position""", args).fetchall()
    colors = db.execute(
        f"""SELECT f.slug, f.name, f.hex,
                   (SELECT COUNT(DISTINCT v.product_id) FROM variants v JOIN colors co ON co.id = v.color_id
                    WHERE co.family = f.slug AND v.product_id IN (SELECT p.id {base})) AS count
            FROM color_families f ORDER BY f.position""", args).fetchall()
    sizes = [{"size": s, "count": db.execute(
        f"""SELECT COUNT(DISTINCT v.product_id) FROM variants v
            WHERE v.size = ? AND v.stock > 0 AND v.product_id IN (SELECT p.id {base})""", [s, *args]).fetchone()[0]}
        for s in SIZES]
    total = db.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
    prices = []
    for key, (lo, hi) in PRICE_BUCKETS.items():
        cond, a = [], list(args)
        if lo is not None:
            cond.append("p.price >= ?")
            a.append(lo)
        if hi is not None:
            cond.append("p.price <= ?")
            a.append(hi)
        count = db.execute(f"SELECT COUNT(*) {base} AND {' AND '.join(cond)}", a).fetchone()[0]
        prices.append({"id": key, "min": lo, "max": hi, "count": count})
    return jsonify({"total": total, "categories": [dict(r) for r in cats], "colors": [dict(r) for r in colors],
                    "sizes": sizes, "prices": prices})


@api_bp.get("/search/suggest")
def search_suggest():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"items": []})
    rows = get_db().execute(
        f"{PRODUCT_CARD_SELECT} WHERE p.status = 'active' AND (p.name LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\') "
        "ORDER BY p.sold_count DESC LIMIT 6", (_like(q), _like(q))).fetchall()
    return jsonify({"items": [{"slug": c["slug"], "name": c["name"], "price": c["price"], "image": c["image"]}
                              for c in product_cards(rows)]})


def _product_row(slug: str):
    row = get_db().execute(
        f"{PRODUCT_CARD_SELECT} WHERE p.slug = ? AND p.status = 'active'", (slug,)).fetchone()
    if row is None:
        raise ApiError("Không tìm thấy sản phẩm.", 404, "not_found")
    return row


@api_bp.get("/products/<slug>")
def product_detail(slug: str):
    db = get_db()
    row = _product_row(slug)
    extra = db.execute("SELECT description, material, model_info, care FROM products WHERE id = ?", (row["id"],)).fetchone()
    card = product_cards([row])[0]
    images = [dict(r) for r in db.execute(
        "SELECT url, tone, label FROM product_images WHERE product_id = ? ORDER BY position", (row["id"],))]

    colors: dict[str, dict] = {}
    for v in db.execute(
            """SELECT v.id, v.size, v.stock, v.sku, co.slug, co.name, co.hex FROM variants v
               JOIN colors co ON co.id = v.color_id WHERE v.product_id = ? ORDER BY v.id""", (row["id"],)):
        c = colors.setdefault(v["slug"], {"slug": v["slug"], "name": v["name"], "hex": v["hex"], "sizes": []})
        c["sizes"].append({"size": v["size"], "variant_id": v["id"], "sku": v["sku"], "stock": v["stock"],
                           "available": v["stock"] > 0})
    for c in colors.values():
        c["sizes"].sort(key=lambda s: SIZES.index(s["size"]) if s["size"] in SIZES else 99)

    dept = card["department"]
    card.update({
        "description": extra["description"],
        "specs": {"material": extra["material"], "model": extra["model_info"], "care": extra["care"]},
        "images": images,
        "colors": list(colors.values()),
        "sizes": [s for s in SIZES if any(x["size"] == s for c in colors.values() for x in c["sizes"])],
        "rating": _rating_summary(row["id"]),
        "breadcrumb": [{"label": "Trang chủ", "url": "/"},
                       {"label": DEPARTMENTS[dept], "url": f"/shop?department={dept}"},
                       {"label": row["category_name"], "url": f"/shop?department={dept}&category={row['category_slug']}"},
                       {"label": row["name"], "url": None}],
        "perks": [
            {"title": "Miễn phí vận chuyển", "description": f"Cho đơn từ {FREE_SHIPPING_THRESHOLD:,}₫ trên toàn quốc.".replace(",", ".")},
            {"title": "Đổi trả dễ dàng", "description": f"Đổi size hoặc đổi mẫu trong {RETURN_DAYS} ngày."},
        ],
    })
    return jsonify(card)


def _rating_summary(product_id: int) -> dict[str, Any]:
    db = get_db()
    agg = db.execute("SELECT COUNT(*) AS n, ROUND(AVG(rating), 1) AS avg, AVG(fit) AS fit FROM reviews WHERE product_id = ?",
                     (product_id,)).fetchone()
    dist = {str(i): 0 for i in range(5, 0, -1)}
    for r in db.execute("SELECT rating, COUNT(*) AS n FROM reviews WHERE product_id = ? GROUP BY rating", (product_id,)):
        dist[str(r["rating"])] = r["n"]
    return {"average": agg["avg"], "count": agg["n"], "distribution": dist,
            "fit": round(agg["fit"], 1) if agg["fit"] else None}  # 1 = chật … 5 = rộng


@api_bp.get("/products/<slug>/related")
def related_products(slug: str):
    row = _product_row(slug)
    limit = to_int(request.args.get("limit"), 4, 1, 12)
    rows = get_db().execute(
        f"""{PRODUCT_CARD_SELECT} WHERE p.status = 'active' AND p.id != ?
            ORDER BY (p.category_id = ?) DESC, (p.department = ?) DESC, p.sold_count DESC, p.id LIMIT ?""",
        (row["id"], row["category_id"], row["department"], limit)).fetchall()
    return jsonify({"items": product_cards(rows)})


@api_bp.get("/products/<slug>/reviews")
def product_reviews(slug: str):
    row = _product_row(slug)
    page, per_page = paginate_args(default_per_page=6, max_per_page=30)
    where, args = "product_id = ?", [row["id"]]
    if request.args.get("rating"):
        where += " AND rating = ?"
        args.append(to_int(request.args["rating"], 5, 1, 5))
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM reviews WHERE {where}", args).fetchone()[0]
    rows = db.execute(
        f"""SELECT id, author_name, city, rating, fit, title, body, body_info, verified, created_at,
                   CAST(julianday('now') - julianday(created_at) AS INTEGER) AS days_ago
            FROM reviews WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
        [*args, per_page, (page - 1) * per_page]).fetchall()
    return jsonify({
        "summary": _rating_summary(row["id"]),
        "items": [{**dict(r), "verified": bool(r["verified"]), "created_at": iso(r["created_at"])} for r in rows],
        "pagination": page_meta(page, per_page, total),
    })


@api_bp.post("/products/<slug>/reviews")
@login_required
def create_review(slug: str):
    row = _product_row(slug)
    user, db, data, errors = current_user(), get_db(), json_body(), {}
    rating = data.get("rating")
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        errors["rating"] = "Số sao phải từ 1 đến 5."
    fit = data.get("fit")
    if fit is not None and (not isinstance(fit, int) or isinstance(fit, bool) or not 1 <= fit <= 5):
        errors["fit"] = "Độ vừa vặn phải từ 1 (chật) đến 5 (rộng)."
    title = text(data, "title", "tiêu đề", errors, required=False, max_len=120)
    body = text(data, "body", "nội dung đánh giá", errors, max_len=2000)
    info = text(data, "body_info", "thông tin người mặc", errors, required=False, max_len=120)
    raise_if(errors)

    bought = db.execute(
        """SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id = o.id
           WHERE o.user_id = ? AND o.status = 'delivered' AND oi.product_id = ? LIMIT 1""",
        (user["id"], row["id"])).fetchone()
    if not bought:
        raise ApiError("Bạn chỉ có thể đánh giá sản phẩm đã mua và nhận hàng.", 403, "not_purchased")
    if db.execute("SELECT 1 FROM reviews WHERE user_id = ? AND product_id = ?", (user["id"], row["id"])).fetchone():
        raise ApiError("Bạn đã đánh giá sản phẩm này rồi.", 409, "already_reviewed")
    city = db.execute("SELECT province FROM addresses WHERE user_id = ? ORDER BY is_default DESC LIMIT 1",
                      (user["id"],)).fetchone()
    cur = db.execute(
        """INSERT INTO reviews (product_id, user_id, author_name, city, rating, fit, title, body, body_info, verified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (row["id"], user["id"], user["full_name"], city["province"] if city else None, rating, fit, title, body, info))
    db.commit()
    return jsonify({"id": cur.lastrowid, "rating": _rating_summary(row["id"])}), 201


# ---------- địa điểm (dropdown Tỉnh/Thành phố → Phường/Xã) ----------
@api_bp.get("/locations/provinces")
def provinces():
    rows = get_db().execute("SELECT code, name FROM provinces ORDER BY name").fetchall()
    return jsonify({"items": [dict(r) for r in rows]})


@api_bp.get("/locations/provinces/<code>/wards")
def wards(code: str):
    db = get_db()
    if db.execute("SELECT 1 FROM provinces WHERE code = ?", (code.upper(),)).fetchone() is None:
        raise ApiError("Không tìm thấy tỉnh/thành phố.", 404, "not_found")
    rows = db.execute("SELECT name FROM wards WHERE province_code = ? ORDER BY name", (code.upper(),)).fetchall()
    return jsonify({"items": [r["name"] for r in rows]})
