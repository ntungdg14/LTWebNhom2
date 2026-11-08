"""Kết nối SQLite dùng chung cho toàn bộ ứng dụng.

- Mỗi request dùng một connection (lưu trong ``g``), tự đóng khi request kết thúc.
- Connection chạy ở chế độ autocommit; các thao tác nhiều bước dùng ``transaction()``.
- Có hàm SQL ``unaccent()`` để tìm kiếm tiếng Việt không dấu.
- CLI: ``flask --app run init-db`` và ``flask --app run seed-db``.
"""
from __future__ import annotations

import os
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path

import click
from flask import Flask, current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def unaccent(value):
    """Bỏ dấu tiếng Việt + chữ thường: 'Áo Đẹp' -> 'ao dep'."""
    if value is None:
        return None
    text = str(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower()


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.create_function("unaccent", 1, unaccent, deterministic=True)
    conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction(db: sqlite3.Connection):
    """BEGIN IMMEDIATE ... COMMIT; lỗi thì ROLLBACK. Không lồng nhau."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


def init_db() -> None:
    """Tạo bảng nếu chưa có (schema dùng CREATE TABLE IF NOT EXISTS)."""
    path = current_app.config["DATABASE"]
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def _seed_if_empty() -> None:
    """Lần chạy đầu (chưa có sản phẩm nào) tự nạp dữ liệu mẫu để shop không trống.

    Chỉ chạy khi bảng products rỗng nên không ghi đè dữ liệu đã chỉnh sửa trong admin.
    """
    db = get_db()
    if db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
        return
    from .seed import seed
    from .seed_extra import seed_extra

    seed(db)
    seed_extra(db)


def init_app(app: Flask) -> None:
    default_path = os.environ.get("DATABASE") or str(Path(app.instance_path) / "freesion.db")
    app.config.setdefault("DATABASE", default_path)
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command():
        """Tạo các bảng trong cơ sở dữ liệu."""
        init_db()
        click.echo("Đã khởi tạo cơ sở dữ liệu.")

    @app.cli.command("seed-db")
    def seed_db_command():
        """Nạp dữ liệu mẫu (chỉ chạy khi chưa có sản phẩm)."""
        from .seed import seed
        from .seed_extra import seed_extra

        init_db()
        db = get_db()
        click.echo("Đã nạp dữ liệu mẫu." if seed(db) else "Đã có dữ liệu gốc, bỏ qua.")
        stats = seed_extra(db)
        click.echo(f"Sản phẩm bổ sung: thêm {stats['added']}, sản phẩm theo ảnh thật {stats['catalog']}, cập nhật thông tin {stats['info']}, gắn {stats['images']} ảnh.")

    if not app.config.get("TESTING"):
        with app.app_context():
            init_db()
            _seed_if_empty()
            close_db()
