"""Khu vực quản trị (URL bắt đầu bằng /admin).

Các trang danh sách, biểu mẫu thêm mới và phân quyền tài khoản.
Dữ liệu là mock tĩnh; form POST chỉ xác nhận rồi điều hướng về trang danh sách.
"""
import unicodedata

from flask import redirect, render_template, request, url_for

from ...common.helpers import check_role
from . import admin_bp


@admin_bp.before_request
def require_admin():
    """Toàn bộ /admin: chưa đăng nhập -> redirect login?next=...; không phải admin -> 403."""
    return check_role("admin")

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
    return render_template("admin/products.html")


@admin_bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    if request.method == "POST":
        return redirect(url_for("admin.products", created="product"))
    return render_template("admin/product_new.html")


@admin_bp.route("/products/<sku>/edit")
def product_edit(sku):
    """Mở lại biểu mẫu sản phẩm ở chế độ chỉnh sửa."""
    return render_template("admin/product_new.html", editing=True, sku=sku)


@admin_bp.route("/categories")
def categories():
    return render_template("admin/categories.html")


@admin_bp.route("/categories/new", methods=["GET", "POST"])
def category_new():
    if request.method == "POST":
        return redirect(url_for("admin.categories", created="category"))
    return render_template("admin/category_new.html")


@admin_bp.route("/orders")
def orders():
    return render_template("admin/orders.html")


@admin_bp.route("/orders/<order_id>")
def order_detail(order_id):
    return render_template("admin/order_detail.html", order_id=order_id)


@admin_bp.route("/users")
def users():
    return render_template("admin/users.html")


@admin_bp.route("/users/new", methods=["GET", "POST"])
def user_new():
    if request.method == "POST":
        return redirect(url_for("admin.users", created="user"))
    return render_template("admin/user_new.html")


@admin_bp.route("/users/<customer_id>")
def user_detail(customer_id):
    return render_template("admin/user_detail.html", customer_id=customer_id)


# Các mục còn lại trong sidebar quản trị (dùng chung một khung nội dung tĩnh).
ADMIN_SECTIONS = {
    "inventory": ("Quản lý kho hàng", "Theo dõi tồn kho, nhập xuất và cảnh báo sắp hết hàng."),
    "promotions": ("Quản lý khuyến mãi", "Tạo mã giảm giá, chương trình ưu đãi theo mùa."),
    "reports": ("Báo cáo", "Doanh thu, đơn hàng và hiệu quả bán hàng theo thời gian."),
}


def _render_section(key):
    title, description = ADMIN_SECTIONS[key]
    return render_template("admin/section.html", title=title, description=description, section=key)


@admin_bp.route("/inventory")
def inventory():
    return _render_section("inventory")


@admin_bp.route("/promotions")
def promotions():
    return _render_section("promotions")


@admin_bp.route("/messages")
def messages():
    """Hộp thư chat với khách. Dữ liệu thật: trang gọi /api/shop/chat/... (cần đăng nhập bằng tài khoản role=admin)."""
    return render_template("admin/messages.html")


@admin_bp.route("/reports")
def reports():
    return _render_section("reports")


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
