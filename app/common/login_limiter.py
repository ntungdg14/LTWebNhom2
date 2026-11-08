"""Giới hạn đăng nhập sai bằng bảng SQLite ``login_attempts`` (không dùng thư viện ngoài).

Sai MAX_FAILURES lần trong WINDOW_SECONDS (theo cặp email chuẩn hóa + IP) thì khóa
LOCK_SECONDS kể từ lần sai gần nhất. Trong lúc khóa không ghi thêm lần sai (không kéo dài khóa).
Đăng nhập thành công thì xóa bộ đếm của cặp đó.
"""
from __future__ import annotations

import time

from flask import request

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
LOCK_SECONDS = 15 * 60
LOCKED_MESSAGE = "Bạn đã nhập sai quá nhiều lần. Thử lại sau {minutes} phút."


def normalize_email(value) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def client_ip() -> str:
    return request.remote_addr or "unknown"


def seconds_locked(db, email: str, ip: str | None = None, now: int | None = None) -> int:
    """Số giây còn bị khóa (0 nếu không bị khóa)."""
    now = int(time.time()) if now is None else now
    ip = ip or client_ip()
    rows = db.execute(
        "SELECT attempted_at FROM login_attempts WHERE email = ? AND ip = ? AND attempted_at > ? "
        "ORDER BY attempted_at DESC LIMIT ?",
        (email, ip, now - WINDOW_SECONDS, MAX_FAILURES),
    ).fetchall()
    if len(rows) < MAX_FAILURES:
        return 0
    return max(rows[0]["attempted_at"] + LOCK_SECONDS - now, 0)


def locked_message(seconds: int) -> str:
    return LOCKED_MESSAGE.format(minutes=max(1, -(-seconds // 60)))


def record_failure(db, email: str, ip: str | None = None, now: int | None = None) -> None:
    now = int(time.time()) if now is None else now
    db.execute("DELETE FROM login_attempts WHERE attempted_at <= ?", (now - max(WINDOW_SECONDS, LOCK_SECONDS),))
    db.execute(
        "INSERT INTO login_attempts (email, ip, attempted_at) VALUES (?, ?, ?)", (email, ip or client_ip(), now)
    )


def clear_failures(db, email: str, ip: str | None = None) -> None:
    db.execute("DELETE FROM login_attempts WHERE email = ? AND ip = ?", (email, ip or client_ip()))
