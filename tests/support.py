"""Tiện ích dùng chung cho test: app + SQLite tạm, tạo user, đăng nhập qua form HTML, lấy CSRF token."""
from __future__ import annotations

import os
import tempfile

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import connect, init_db
from app.seed import seed

PASSWORD = "Matkhau123"
CUSTOMER_EMAIL = "khach@example.com"
ADMIN_EMAIL = "admin@example.com"


def make_app(with_seed: bool = False):
    """Trả về (app, đường_dẫn_db). Nhớ gọi remove_db(path) trong tearDown."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app("testing")
    app.config["DATABASE"] = path
    with app.app_context():
        init_db()
    conn = connect(path)
    if with_seed:
        seed(conn)
    conn.close()
    return app, path


def remove_db(path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


def add_user(path: str, email: str, password: str = PASSWORD, role: str = "customer", name: str = "Người Dùng") -> int:
    conn = connect(path)
    cur = conn.execute(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), role),
    )
    lastrowid = cur.lastrowid
    conn.close()
    assert lastrowid is not None
    return lastrowid


def csrf_token(client, path: str = "/login") -> str:
    """GET một trang có form (hoặc header đã đăng nhập) rồi đọc CSRF token trong session."""
    client.get(path)
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def login(client, email: str, password: str = PASSWORD, **extra):
    data = {"email": email, "password": password, "csrf_token": csrf_token(client, "/login"), **extra}
    return client.post("/login", data=data)
