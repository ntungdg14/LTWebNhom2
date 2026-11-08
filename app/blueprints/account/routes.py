"""Khu vực tài khoản cá nhân (URL bắt đầu bằng /account)."""
from flask import redirect, render_template, request, url_for

from ...common.helpers import current_user
from . import account_bp


@account_bp.before_request
def require_login():
    """Chưa đăng nhập thì chuyển sang trang đăng nhập (đăng nhập xong quay lại đúng trang đang mở)."""
    if current_user() is None:
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


@account_bp.context_processor
def inject_account_user():
    user = current_user()
    return {"account_user_name": user["full_name"] if user else ""}


@account_bp.route("")
def profile():
    return render_template("account/profile.html")


@account_bp.route("/orders")
def order_history():
    return render_template("account/order_history.html")


@account_bp.route("/orders/<order_id>")
def order_detail(order_id):
    return render_template("account/order_detail.html", order_id=order_id)


@account_bp.route("/address")
def address():
    return render_template("account/address.html")


@account_bp.route("/wishlist")
def wishlist():
    return render_template("account/wishlist.html")
