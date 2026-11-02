"""Khu vực quản trị (URL bắt đầu bằng /admin)."""
from flask import render_template

from . import admin_bp


@admin_bp.route("")
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/products")
def products():
    return render_template("admin/products.html")


@admin_bp.route("/orders")
def orders():
    return render_template("admin/orders.html")


@admin_bp.route("/users")
def users():
    return render_template("admin/users.html")
