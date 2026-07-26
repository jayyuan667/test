# -*- coding: utf-8 -*-
"""Authentication business logic — JWT signing/verification and password hashing."""

import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from .config import get_jwt_secret
from . import auth_store

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def hash_password(password: str) -> str:
    """Hash a plaintext password using werkzeug's pbkdf2:sha256."""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a werkzeug hash."""
    return check_password_hash(password_hash, password)


def create_token(user: dict) -> str:
    """Create a signed JWT for the given user dict.

    Payload fields:
        sub      — user id
        username — display / login name
        role     — user role string
        ent_id   — enterprise id (0 if not set)
        iat      — issued at (UTC)
        exp      — expires at (UTC, 24 h from now)
    """
    now = datetime.utcnow()
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "ent_id": user.get("enterprise_id") or 0,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns the payload dict or None on failure."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def register_user(username: str, password: str) -> tuple[dict | None, str | None]:
    """Register a new user with validation.

    Returns (user_dict, None) on success, or (None, error_message) on failure.
    Validates: username non-empty, >= 2 chars; password >= 6 chars; username unique.
    """
    username = (username or "").strip()
    if not username:
        return None, "用户名不能为空"
    if len(username) < 2:
        return None, "用户名至少需要 2 个字符"
    if len(password) < 6:
        return None, "密码至少需要 6 个字符"

    existing = auth_store.get_user_by_username(username)
    if existing:
        return None, "用户名已存在"

    password_hash = hash_password(password)
    user = auth_store.create_user(username, password_hash)
    return user, None
