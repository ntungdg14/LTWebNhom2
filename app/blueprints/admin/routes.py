"""Khu vực quản trị (URL bắt đầu bằng /admin).

Các trang danh sách, biểu mẫu thêm mới và phân quyền tài khoản.
Dữ liệu là mock tĩnh; form POST chỉ xác nhận rồi điều hướng về trang danh sách.
"""
import re
import secrets
import sqlite3
import unicodedata
from pathlib import Path

from flask import abort, current_app, redirect, render_template, request, url_for

from ...common.helpers import Fields, as_int, check_role
from ...db import get_db, transaction
from ...common.services import vnd
from . import admin_bp, data

DEPARTMENTS = (("nu", "Nữ"), ("nam", "Nam"), ("phu-kien", "Phụ kiện"))
PRODUCT_SIZES = ("XS", "S", "M", "L", "XL", "XXL")
SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,39}$")
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 3 * 1024 * 1024  # 3 MB mỗi ảnh (tổng request tối đa 16 MB theo MAX_CONTENT_LENGTH)


def _image_dir() -> Path:
    """Thư mục lưu ảnh sản phẩm: app/static/images (đổi được qua config PRODUCT_IMAGE_DIR, dùng cho test)."""
    return Path(current_app.config.get("PRODUCT_IMAGE_DIR") or Path(current_app.static_folder) / "images")


def _image_ext(filename: str, data: bytes) -> str | None:
    """Kiểm tra đuôi file và chữ ký nhị phân (magic bytes); trả về đuôi chuẩn hoặc None."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("jpg", "jpeg") and data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if ext == "png" and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if ext == "webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _form_context(db) -> dict:
    return {
        "categories": db.execute("SELECT id, name FROM categories ORDER BY position, id").fetchall(),
        "colors": db.execute("SELECT id, name FROM colors ORDER BY name").fetchall(),
        "departments": DEPARTMENTS, "sizes": PRODUCT_SIZES, "values": {}, "errors": {}, "max_images": MAX_IMAGES,
    }


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "san-pham"


def _unique_slug(db, base: str) -> str:
    slug, n = base, 2
    while db.execute("SELECT 1 FROM products WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


@admin_bp.before_request
def require_admin():
    """Toàn bộ /admin: chưa đăng nhập -> redirect login?next=...; không phải admin -> 403."""
    return check_role("admin")

@admin_bp.app_template_filter("vnd")
def _vnd_filter(amount):
    return vnd(int(amount or 0))


@admin_bp.app_template_filter("vn_datetime")
def _vn_datetime(value, with_time=True):
    """'2026-11-01 10:42:00' -> '01/11/2026 · 10:42'."""
    if not value:
        return "—"
    day, _, clock = str(value).partition(" ")
    y, m, d = (day.split("-") + ["", "", ""])[:3]
    text = f"{d}/{m}/{y}"
    return f"{text} · {clock[:5]}" if with_time and clock else text


@admin_bp.context_processor
def _admin_helpers():
    return {"link": data.link}


# Danh sách tài khoản dùng cho form phân quyền (mock, không có CSDL).
ACCOUNTS = (
    {"name": "Nguyễn Minh Anh", "email": "minhanh.nguyen@gmail.com", "initials": "MA", "role": "customer"},
    {"name": "Trần Hoàng Nam", "email": "nam.tran@gmail.com", "initials": "TN", "role": "customer"},
    {"name": "Lê Thu Hà", "email": "ha.le@gmail.com", "initials": "LH", "role": "customer"},
    {"name": "Phạm Khánh Linh", "email": "linh.pham@gmail.com", "initials": "PK", "role": "customer"},
    {"name": "Vũ Quốc Bảo", "email": "bao.vu@gmail.com", "initials": "QB", "role": "customer"},
    {"name": "Minh Anh", "email": "minhanh@freesion.vn", "initials": "MA", "role": "admin"},
    {"name": "Nguyễn Tùng Dương", "email": "tungduong@freesion.vn", "initials": "TD", "role": "admin"},
    {"name": "Freesion Admin", "email": "admin@freesion.vn", "initials": "FA", "role": "admin"},
)

ROLE_LABELS = {"admin": "Quản trị viên", "customer": "Khách hàng"}


def _fold(text: str) -> str:
    """Bỏ dấu tiếng Việt để tìm kiếm 'Hoang' vẫn khớp 'Hoàng'."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


@admin_bp.route("")
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/products")
def products():
    return render_template("admin/products.html", **data.products(get_db()))


@admin_bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    db = get_db()
    context = _form_context(db)
    if request.method == "GET":
        return render_template("admin/product_new.html", **context)

    form = request.form
    f = Fields(form.to_dict())
    name = f.text("name", "Tên sản phẩm", max_len=150)
    sku = f.text("sku", "SKU", max_len=40)
    if sku:
        sku = sku.upper()
        if not SKU_RE.match(sku):
            f.fail("sku", "SKU chỉ gồm chữ, số, dấu - hoặc _ (2-40 ký tự).")
        elif db.execute("SELECT 1 FROM products WHERE sku = ?", (sku,)).fetchone():
            f.fail("sku", "SKU này đã tồn tại.")
    category_id = as_int(form.get("category_id"))
    category = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone() if category_id else None
    if category is None:
        f.fail("category_id", "Vui lòng chọn danh mục.")
    department = f.choice("department", "Bộ phận", [k for k, _ in DEPARTMENTS], required=True)
    description = f.text("description", "Mô tả sản phẩm", max_len=2000)
    price = f.integer("price", "Giá bán", minimum=1000, maximum=100_000_000)
    color_id = as_int(form.get("color_id"))
    color = db.execute("SELECT * FROM colors WHERE id = ?", (color_id,)).fetchone() if color_id else None
    if color is None:
        f.fail("color_id", "Vui lòng chọn màu sắc.")

    chosen = [sz for sz in form.getlist("sizes") if sz in PRODUCT_SIZES]
    stocks: dict[str, int] = {}
    if not chosen:
        f.fail("sizes", "Chọn ít nhất một size.")
    for sz in chosen:
        qty = as_int(form.get(f"stock_{sz}"))
        if qty is None or not 0 <= qty <= 99_999:
            f.fail("sizes", f"Nhập tồn kho (0 - 99999) cho size {sz}.")
        else:
            stocks[sz] = qty

    files = [fl for fl in request.files.getlist("images") if fl and fl.filename]
    images: list[tuple[bytes, str]] = []
    if not files:
        f.fail("images", "Vui lòng tải lên ít nhất một ảnh sản phẩm.")
    elif len(files) > MAX_IMAGES:
        f.fail("images", f"Tối đa {MAX_IMAGES} ảnh cho mỗi sản phẩm.")
    else:
        for fl in files:
            data = fl.read(MAX_IMAGE_BYTES + 1)
            ext = _image_ext(fl.filename, data)
            if ext is None:
                f.fail("images", f"'{fl.filename}' không phải ảnh JPG, PNG hoặc WebP hợp lệ.")
            elif len(data) > MAX_IMAGE_BYTES:
                f.fail("images", f"'{fl.filename}' vượt quá {MAX_IMAGE_BYTES // 1024 // 1024} MB.")
            else:
                images.append((data, ext))

    if f.errors:
        values = {k: form.get(k, "") for k in ("name", "sku", "category_id", "department", "description", "price", "color_id")}
        values["sizes"] = chosen
        values.update({f"stock_{sz}": form.get(f"stock_{sz}", "") for sz in PRODUCT_SIZES})
        context.update(values=values, errors=f.errors)
        return render_template("admin/product_new.html", **context), 422

    image_dir = _image_dir()
    image_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    try:
        for data, ext in images:
            path = image_dir / f"{re.sub(r'[^a-z0-9]+', '-', sku.lower()).strip('-')}-{secrets.token_hex(6)}.{ext}"
            path.write_bytes(data)
            saved.append(path)
        slug = _unique_slug(db, _slugify(name))
        with transaction(db):
            cur = db.execute(
                """INSERT INTO products (slug, sku, name, description, price, category_id, department, tone, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (slug, sku, name, description, price, category["id"], department, category["tone"]),
            )
            pid = cur.lastrowid
            for pos, path in enumerate(saved):
                db.execute(
                    "INSERT INTO product_images (product_id, url, tone, position) VALUES (?, ?, ?, ?)",
                    (pid, f"/static/images/{path.name}", category["tone"], pos),
                )
            for sz in chosen:
                db.execute(
                    "INSERT INTO variants (product_id, color_id, size, sku, stock) VALUES (?, ?, ?, ?, ?)",
                    (pid, color["id"], sz, f"{sku}-{color['slug'].upper()}-{sz}", stocks[sz]),
                )
    except sqlite3.IntegrityError:
        for path in saved:
            path.unlink(missing_ok=True)
        context.update(values={k: form.get(k, "") for k in ("name", "sku", "description", "price")}, errors={"sku": "SKU hoặc mã biến thể đã tồn tại."})
        return render_template("admin/product_new.html", **context), 422
    except BaseException:
        for path in saved:
            path.unlink(missing_ok=True)
        raise
    return redirect(url_for("admin.products", created="product"))


@admin_bp.route("/products/<sku>/edit")
def product_edit(sku):
    """Mở lại biểu mẫu sản phẩm ở chế độ chỉnh sửa."""
    return render_template("admin/product_new.html", editing=True, sku=sku, **_form_context(get_db()))


@admin_bp.route("/categories")
def categories():
    return render_template("admin/categories.html", **data.categories(get_db()))


@admin_bp.route("/categories/new", methods=["GET", "POST"])
def category_new():
    if request.method == "POST":
        return redirect(url_for("admin.categories", created="category"))
    return render_template("admin/category_new.html")


@admin_bp.route("/orders")
def orders():
    return render_template("admin/orders.html", **data.orders(get_db()))


@admin_bp.route("/orders/<order_id>")
def order_detail(order_id):
    context = data.order_detail(get_db(), order_id)
    if context is None:
        abort(404)
    return render_template("admin/order_detail.html", **context)


@admin_bp.route("/users")
def users():
    return render_template("admin/users.html", **data.users(get_db()))


@admin_bp.route("/users/new", methods=["GET", "POST"])
def user_new():
    if request.method == "POST":
        return redirect(url_for("admin.users", created="user"))
    return render_template("admin/user_new.html")


@admin_bp.route("/users/<customer_id>")
def user_detail(customer_id):
    context = data.user_detail(get_db(), customer_id)
    if context is None:
        abort(404)
    return render_template("admin/user_detail.html", **context)


@admin_bp.route("/permissions", methods=["GET", "POST"])
def permissions():
    """Form phân quyền: tìm kiếm + lọc vai trò + danh sách quyền hiện tại."""
    if request.method == "POST":
        return redirect(url_for(
            "admin.permissions",
            q=request.form.get("q", "").strip(),
            role=request.form.get("role", "all"),
            saved=1,
        ))

    query = request.args.get("q", "").strip()
    role = request.args.get("role", "all")
    if role not in ("all", "admin", "customer"):
        role = "all"

    needle = _fold(query)
    accounts = [
        account
        for account in ACCOUNTS
        if (not needle or needle in _fold(account["name"])
            or needle in _fold(account["email"]))
        and (role == "all" or account["role"] == role)
    ]
    return render_template(
        "admin/permissions.html",
        accounts=accounts,
        query=query,
        role=role,
        total=len(ACCOUNTS),
        role_labels=ROLE_LABELS,
    )
