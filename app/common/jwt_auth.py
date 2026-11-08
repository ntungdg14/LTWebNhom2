"""JWT HS256 in HttpOnly cookie; Flask session remains only for guest cart/order state."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlsplit

from flask import current_app, g, request

from ..db import get_db

COOKIE = "access_token"
CSRF_COOKIE = "csrf_token"
ISSUER = "freesion"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _signature(message: str) -> str:
    key = current_app.config["SECRET_KEY"].encode()
    return _b64(hmac.new(key, message.encode(), hashlib.sha256).digest())


def issue(user, remember: bool = False):
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": str(user["id"]), "sv": user["session_version"],
        "iat": now, "exp": now + (30 * 86400 if remember else 12 * 3600),
        "jti": secrets.token_urlsafe(24), "csrf": secrets.token_urlsafe(32),
        "remember": bool(remember),
    }
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    message = header + "." + body
    return message + "." + _signature(message), payload


def verify(token: str | None):
    if not token or len(token) > 4096:
        return None
    try:
        header, body, signature = token.split(".")
        if not hmac.compare_digest(_signature(header + "." + body), signature):
            return None
        meta = json.loads(_decode(header))
        payload = json.loads(_decode(body))
        now = int(time.time())
        if meta != {"alg": "HS256", "typ": "JWT"} or payload.get("iss") != ISSUER:
            return None
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= now:
            return None
        if not isinstance(payload.get("iat"), int) or payload["iat"] > now + 60:
            return None
        if not isinstance(payload.get("sv"), int) or not isinstance(payload.get("csrf"), str):
            return None
        if not isinstance(payload.get("jti"), str) or not payload["jti"]:
            return None
        if not isinstance(payload.get("sub"), str) or not payload["sub"].isdigit():
            return None
        revoked = get_db().execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (payload["jti"],)).fetchone()
        return None if revoked else payload
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        return None


def revoke(payload):
    if payload:
        db = get_db()
        db.execute("DELETE FROM revoked_tokens WHERE expires_at <= ?", (int(time.time()),))
        db.execute("INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)",
                   (payload["jti"], payload["exp"]))


def init_app(app):
    from .helpers import ApiError, current_user

    @app.before_request
    def protect_cookie_requests():
        if request.method in ("GET", "HEAD", "OPTIONS") or not request.path.startswith("/api/"):
            return
        # Origin check also protects login CSRF. Origin is supplied by browsers for fetch POST/PATCH/DELETE.
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            raise ApiError("Nguồn yêu cầu không hợp lệ.", 403, "invalid_origin")
        if request.path in ("/api/auth/login", "/api/auth/register", "/api/auth/forgot-password", "/api/auth/reset-password"):
            return
        if not request.cookies.get(COOKIE):
            return  # guest endpoints retain their original API behavior
        if current_user() is None:
            return  # protected endpoints return 401 through login_required
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(csrf, g.jwt_payload["csrf"]):
            raise ApiError("Thiếu hoặc sai mã CSRF.", 403, "invalid_csrf")

    @app.after_request
    def write_auth_cookies(response):
        secure = app.config["SESSION_COOKIE_SECURE"]
        same_site = app.config["SESSION_COOKIE_SAMESITE"]
        if getattr(g, "jwt_clear", False):
            response.delete_cookie(COOKIE, secure=secure, samesite=same_site)
            response.delete_cookie(CSRF_COOKIE, secure=secure, samesite=same_site)
        issued = getattr(g, "jwt_issue", None)
        if issued is not None:
            token, payload = issue(*issued)
            max_age = payload["exp"] - int(time.time())
            response.set_cookie(COOKIE, token, httponly=True, secure=secure, samesite=same_site, max_age=max_age)
            response.set_cookie(CSRF_COOKIE, payload["csrf"], httponly=False, secure=secure,
                                samesite=same_site, max_age=max_age)
        return response
