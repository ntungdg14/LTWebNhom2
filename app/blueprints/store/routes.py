"""Các trang cửa hàng: trang chủ, danh sách, chi tiết sản phẩm, giỏ hàng.

Ngoài ra có 3 trang thông tin tĩnh dùng cho các liên kết chân trang / biểu mẫu.
"""
import math

from flask import abort, flash, redirect, render_template, request, url_for

from ...common.helpers import ApiError, arg_int, login_required_page
from ...common.serializers import PRODUCT_CARD_SELECT, product_cards, product_detail as product_json, review_json, review_summary
from ...common.services import compute_totals, find_cart, line_issue, load_cart_rows, set_item_quantity, touch_cart
from ...db import get_db
from . import store_bp
from .api import SORTS, build_filters

INFO_PAGES = {
    "terms": (
        "Điều khoản sử dụng",
        "Khi sử dụng Freesion, bạn đồng ý cung cấp thông tin chính xác và tôn trọng "
        "quy định đặt hàng, thanh toán, đổi trả trong vòng 30 ngày.",
    ),
    "privacy": (
        "Chính sách bảo mật",
        "Freesion chỉ dùng thông tin cá nhân để xác nhận đơn hàng, giao hàng và hỗ trợ "
        "khách hàng. Chúng tôi không chia sẻ dữ liệu cho bên thứ ba.",
    ),
    "help": (
        "Hỗ trợ kỹ thuật",
        "Cần hỗ trợ? Liên hệ 1900 636 028 hoặc hello@freesion.vn, 8:30–21:00 mỗi ngày.",
    ),
}


@store_bp.route("/")
def home():
    return render_template("store/home.html")


PER_PAGE = 12
SORT_LABELS = {
    "featured": "Nổi bật",
    "newest": "Mới nhất",
    "bestseller": "Bán chạy",
    "price_asc": "Giá tăng dần",
    "price_desc": "Giá giảm dần",
}
PRICE_RANGES = {
    "under-500": ("Dưới 500.000₫", None, 499999),
    "500-1000": ("500.000₫ – 1.000.000₫", 500000, 1000000),
    "over-1000": ("Trên 1.000.000₫", 1000001, None),
}
DEPARTMENTS = {"nu": "Nữ", "nam": "Nam", "phu-kien": "Phụ kiện"}
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]
# Liên kết cũ ở trang chủ: ?category=hang-moi / sale / tat-ca
SPECIAL_CATEGORIES = {"hang-moi": "is_new", "sale": "sale", "tat-ca": None}


def _selected(name):
    return [v.strip() for raw in request.args.getlist(name) for v in raw.split(",") if v.strip()]


def _shop_url(**changes):
    """Giữ nguyên bộ lọc hiện tại, đổi/bỏ tham số (None hoặc [] = bỏ); luôn bỏ `page` trừ khi được đặt."""
    args = {k: request.args.getlist(k) for k in request.args if k != "page"}
    for key, value in changes.items():
        if value in (None, "", []):
            args.pop(key, None)
        else:
            args[key] = value
    return url_for("store.shop", **args)


@store_bp.route("/shop")
def shop():
    db = get_db()
    special = [c for c in _selected("category") if c in SPECIAL_CATEGORIES]
    if special:  # chuyển liên kết cũ sang tham số thật
        args = {k: request.args.getlist(k) for k in request.args if k != "category"}
        args["category"] = [c for c in _selected("category") if c not in SPECIAL_CATEGORIES]
        for c in special:
            if SPECIAL_CATEGORIES[c]:
                args["is_new" if c == "hang-moi" else "sale"] = "1"
        args = {k: v for k, v in args.items() if v}
        return redirect(url_for("store.shop", **args))

    try:
        where, params = build_filters()
        page = arg_int("page", 1)
    except ApiError:
        return redirect(url_for("store.shop"))

    price = request.args.get("price", "")
    if price in PRICE_RANGES:
        _, low, high = PRICE_RANGES[price]
        if low is not None:
            where.append("p.price >= ?")
            params.append(low)
        if high is not None:
            where.append("p.price <= ?")
            params.append(high)
    else:
        price = ""

    sort = request.args.get("sort", "featured")
    if sort not in SORTS:
        sort = "featured"

    clause = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) FROM products p WHERE {clause}", params).fetchone()[0]
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(page, pages)
    rows = db.execute(
        f"{PRODUCT_CARD_SELECT} WHERE {clause} ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?",
        [*params, PER_PAGE, (page - 1) * PER_PAGE],
    ).fetchall()

    f_where, f_params = build_filters(skip=("category",))
    categories = db.execute(
        f"""SELECT c.slug, c.name, COUNT(p.id) AS count FROM categories c
            LEFT JOIN products p ON p.category_id = c.id AND {" AND ".join(f_where)}
            GROUP BY c.id ORDER BY c.position, c.id""",
        f_params,
    ).fetchall()
    families = db.execute("SELECT slug, name, hex FROM color_families ORDER BY position, slug").fetchall()
    sizes = [r[0] for r in db.execute(
        "SELECT DISTINCT upper(v.size) FROM variants v JOIN products p ON p.id = v.product_id WHERE p.status = 'active'"
    )]
    sizes.sort(key=lambda s: (SIZE_ORDER.index(s) if s in SIZE_ORDER else 99, s))

    shown = [i for i in (page - 1, page, page + 1) if 1 <= i <= pages]
    return render_template(
        "store/shop.html",
        products=product_cards(db, rows),
        total=total,
        page=page,
        pages=pages,
        page_links=[(n, _shop_url(page=n if n > 1 else None)) for n in shown],
        prev_url=_shop_url(page=page - 1 if page > 2 else None) if page > 1 else None,
        next_url=_shop_url(page=page + 1) if page < pages else None,
        categories=categories,
        families=families,
        sizes=sizes,
        price_ranges=PRICE_RANGES,
        departments=DEPARTMENTS,
        sort_labels=SORT_LABELS,
        sel={
            "category": _selected("category"),
            "color": _selected("color"),
            "size": [x.upper() for x in _selected("size")],
            "price": price,
            "sort": sort,
            "department": request.args.get("department", ""),
            "q": (request.args.get("q") or "").strip(),
            "is_new": request.args.get("is_new") == "1",
            "sale": request.args.get("sale") == "1",
        },
        shop_url=_shop_url,
    )


def _pick_variant(product, color_slug, size):
    """Chọn biến thể theo ?color=&size=; thiếu/không hợp lệ thì lấy màu, size còn hàng đầu tiên."""
    colors = product["colors"]
    color = next((c for c in colors if c["slug"] == color_slug), None)
    if color is None:
        color = next((c for c in colors if c["in_stock"]), colors[0] if colors else None)
    if color is None:
        return None, None
    chosen = next((s for s in color["sizes"] if s["size"].upper() == (size or "").upper()), None)
    if chosen is None:
        chosen = next((s for s in color["sizes"] if s["stock"] > 0), color["sizes"][0])
    return color, chosen


@store_bp.route("/product")
def product_detail():
    ident = (request.args.get("sku") or request.args.get("slug") or "").strip()
    db = get_db()
    row = db.execute(
        f"{PRODUCT_CARD_SELECT} WHERE (p.sku = ? OR p.slug = ?) AND p.status = 'active'", (ident, ident)
    ).fetchone() if ident else None
    if row is None:
        abort(404)
    product = product_json(db, row)
    color, variant = _pick_variant(product, request.args.get("color"), request.args.get("size"))
    related = db.execute(
        f"""{PRODUCT_CARD_SELECT} WHERE p.status = 'active' AND p.id != ?
            ORDER BY (p.category_id = ?) DESC, (p.department = ?) DESC, p.is_featured DESC, p.sold_count DESC, p.id DESC
            LIMIT 4""",
        (row["id"], row["category_id"], row["department"]),
    ).fetchall()
    reviews = [
        review_json(r)
        for r in db.execute(
            "SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC, id DESC LIMIT 5", (row["id"],)
        )
    ]
    image = next((i for i in product["images"] if i["url"]), None) or (product["images"][0] if product["images"] else None)
    return render_template(
        "store/product_detail.html",
        product=product,
        color=color,
        variant=variant,
        image=image,
        related=product_cards(db, related),
        reviews=reviews,
        rating=product["rating"],
        departments=DEPARTMENTS,
        pick=lambda **kw: url_for(
            "store.product_detail", sku=product["sku"],
            **{"color": color["slug"] if color else None, "size": variant["size"] if variant else None, **kw},
        ),
    )


@store_bp.post("/cart/add")
@login_required_page
def cart_add():
    """Thêm một biến thể vào giỏ từ trang chi tiết (form HTML). `buy_now` = chuyển thẳng tới thanh toán."""
    back = request.form.get("back") or url_for("store.shop")
    if not back.startswith("/") or back.startswith("//"):
        back = url_for("store.shop")
    try:
        variant_id = int(request.form.get("variant_id", ""))
        quantity = max(1, min(int(request.form.get("quantity", "1") or 1), 99))
    except ValueError:
        flash("Vui lòng chọn màu và kích cỡ.", "error")
        return redirect(back)
    db = get_db()
    try:
        set_item_quantity(db, find_cart(db, create=True)["id"], variant_id, quantity, add=True)
    except ApiError as exc:
        flash(str(exc.message if hasattr(exc, "message") else exc), "error")
        return redirect(back)
    if request.form.get("buy_now"):
        return redirect(url_for("checkout.checkout"))
    flash("Đã thêm sản phẩm vào giỏ hàng.", "success")
    return redirect(url_for("store.cart"))


@store_bp.route("/cart")
@login_required_page
def cart():
    db = get_db()
    cart_row = find_cart(db)
    rows = load_cart_rows(db, cart_row["id"]) if cart_row else []
    if cart_row and cart_row["coupon_code"]:  # không còn tính năng mã giảm giá
        db.execute("UPDATE carts SET coupon_code = NULL WHERE id = ?", (cart_row["id"],))
    items = [{**dict(r), "issue": line_issue(r), "line_total": r["price"] * r["quantity"]} for r in rows]
    return render_template(
        "store/cart.html",
        items=items,
        totals=compute_totals(db, rows, None),
        has_issues=any(i["issue"] for i in items),
    )


@store_bp.post("/cart/update")
@login_required_page
def cart_update():
    """Đổi số lượng một dòng trong giỏ (quantity <= 0 = xóa dòng)."""
    db = get_db()
    cart_row = find_cart(db)
    try:
        item_id = int(request.form.get("item_id", ""))
        quantity = max(0, min(int(request.form.get("quantity", "")), 99))
    except ValueError:
        return redirect(url_for("store.cart"))
    item = (
        db.execute("SELECT * FROM cart_items WHERE id = ? AND cart_id = ?", (item_id, cart_row["id"])).fetchone()
        if cart_row else None
    )
    if item is None:
        flash("Không tìm thấy sản phẩm trong giỏ hàng.", "error")
    elif quantity == 0:
        db.execute("DELETE FROM cart_items WHERE id = ?", (item["id"],))
        touch_cart(db, cart_row["id"])
    else:
        try:
            set_item_quantity(db, cart_row["id"], item["variant_id"], quantity)
        except ApiError as exc:
            flash(exc.message, "error")
    return redirect(url_for("store.cart"))


def _render_info(key):
    title, content = INFO_PAGES[key]
    return render_template("store/info.html", title=title, content=content)


@store_bp.route("/terms")
def terms():
    return _render_info("terms")


@store_bp.route("/privacy")
def privacy():
    return _render_info("privacy")


@store_bp.route("/help")
def help_page():
    return _render_info("help")
