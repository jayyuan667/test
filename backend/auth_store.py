# -*- coding: utf-8 -*-
"""SQLite auth persistence — users, enterprises, quotas, admin grants.

Database file: backend/auth.db
Pattern: sqlite3 + WAL + _conn() helper + sqlite3.Row row_factory.
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional

from werkzeug.security import generate_password_hash

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")


def _conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def init_auth_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS enterprises (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active   INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                role            TEXT NOT NULL DEFAULT 'user',
                enterprise_id   INTEGER,
                is_active       INTEGER DEFAULT 1,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
            );

            CREATE TABLE IF NOT EXISTS enterprise_admin_grants (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER UNIQUE NOT NULL,
                enterprise_id   INTEGER NOT NULL,
                granted_by      INTEGER NOT NULL,
                expires_at      TIMESTAMP NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (enterprise_id) REFERENCES enterprises(id),
                FOREIGN KEY (granted_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS quotas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL UNIQUE,
                total_granted   INTEGER DEFAULT 10,
                used            INTEGER DEFAULT 0,
                granted_by      INTEGER,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)

        # Bootstrap: ensure at least one super_admin exists
        count = c.execute(
            "SELECT COUNT(*) FROM users WHERE role='super_admin'"
        ).fetchone()[0]
        if count == 0:
            pw_hash = generate_password_hash("admin123")
            cur = c.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'super_admin')",
                ("admin", pw_hash),
            )
            admin_id = cur.lastrowid
            c.execute(
                "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, 999999, 0)",
                (admin_id,),
            )


# ── Users ─────────────────────────────────────────────────────────────────────


def create_user(
    username: str,
    password_hash: str,
    role: str = "user",
    enterprise_id: Optional[int] = None,
) -> dict:
    """Create a user and their default quota. Returns the created user dict."""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, enterprise_id) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, enterprise_id),
        )
        user_id = cur.lastrowid
        c.execute(
            "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, 10, 0)",
            (user_id,),
        )
        row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _row_to_dict(row)


def get_user_by_username(username: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE id=?", (user_id,)
        ).fetchone()
    return _row_to_dict(row)


def update_user(user_id: int, **kwargs):
    """Update allowed user fields: username, password_hash, role, enterprise_id, is_active."""
    allowed = {"username", "password_hash", "role", "enterprise_id", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [user_id]
    with _conn() as c:
        c.execute(
            f"UPDATE users SET {set_clause} WHERE id=?", values
        )
        row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _row_to_dict(row)


def list_all_users() -> list[dict]:
    """Return all users with enterprise_name via LEFT JOIN."""
    with _conn() as c:
        rows = c.execute("""
            SELECT u.*, e.name AS enterprise_name
            FROM users u
            LEFT JOIN enterprises e ON u.enterprise_id = e.id
            ORDER BY u.created_at DESC
        """).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_enterprise_users(enterprise_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM users WHERE enterprise_id=? ORDER BY created_at DESC",
            (enterprise_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ── Enterprises ───────────────────────────────────────────────────────────────


def create_enterprise(name: str) -> dict:
    with _conn() as c:
        cur = c.execute("INSERT INTO enterprises (name) VALUES (?)", (name,))
        row = c.execute(
            "SELECT * FROM enterprises WHERE id=?", (cur.lastrowid,)
        ).fetchone()
    return _row_to_dict(row)


def get_enterprise(enterprise_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM enterprises WHERE id=?", (enterprise_id,)
        ).fetchone()
    return _row_to_dict(row)


def list_enterprises(is_active: Optional[bool] = None) -> list[dict]:
    with _conn() as c:
        if is_active is not None:
            rows = c.execute(
                "SELECT * FROM enterprises WHERE is_active=? ORDER BY created_at DESC",
                (1 if is_active else 0,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM enterprises ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_enterprise(enterprise_id: int, **kwargs) -> Optional[dict]:
    """Only allowed fields: name, is_active."""
    allowed = {"name", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [enterprise_id]
    with _conn() as c:
        c.execute(f"UPDATE enterprises SET {set_clause} WHERE id=?", values)
        row = c.execute(
            "SELECT * FROM enterprises WHERE id=?", (enterprise_id,)
        ).fetchone()
    return _row_to_dict(row)


# ── Quotas ────────────────────────────────────────────────────────────────────


def get_or_create_quota(user_id: int, initial: int = 10) -> dict:
    """Get a user's quota, creating one with `initial` total if none exists."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM quotas WHERE user_id=?", (user_id,)
        ).fetchone()
        if row is None:
            c.execute(
                "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, ?, 0)",
                (user_id, initial),
            )
            row = c.execute(
                "SELECT * FROM quotas WHERE user_id=?", (user_id,)
            ).fetchone()
    return _row_to_dict(row)


def get_user_quota(user_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM quotas WHERE user_id=?", (user_id,)
        ).fetchone()
    return _row_to_dict(row)


def consume_quota(user_id: int) -> bool:
    """Atomically increment used quota.

    Returns True if quota was available and consumed, False if exhausted.
    """
    with _conn() as c:
        c.execute(
            "UPDATE quotas SET used = used + 1 WHERE user_id=? AND used < total_granted",
            (user_id,),
        )
        return c.execute("SELECT changes()").fetchone()[0] > 0


def set_quota(user_id: int, total_granted: int):
    """Upsert a user's total_granted quota. Resets used to 0."""
    with _conn() as c:
        c.execute(
            "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, ?, 0) "
            "ON CONFLICT(user_id) DO UPDATE SET total_granted=excluded.total_granted, used=excluded.used",
            (user_id, total_granted),
        )


# ── Enterprise Admin Grants ───────────────────────────────────────────────────


def create_enterprise_admin_grant(
    user_id: int, enterprise_id: int, granted_by: int, expires_at: str
) -> dict:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO enterprise_admin_grants (user_id, enterprise_id, granted_by, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, enterprise_id, granted_by, expires_at),
        )
        row = c.execute(
            "SELECT * FROM enterprise_admin_grants WHERE user_id=?", (user_id,)
        ).fetchone()
    return _row_to_dict(row)


def get_enterprise_admin_grant(user_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM enterprise_admin_grants WHERE user_id=?", (user_id,)
        ).fetchone()
    return _row_to_dict(row)


def is_enterprise_admin_expired(user_id: int) -> bool:
    """Check if the grant's expires_at is in the past."""
    with _conn() as c:
        row = c.execute(
            "SELECT expires_at FROM enterprise_admin_grants WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if row is None:
        return True  # No grant means expired
    return row["expires_at"] < datetime.now().isoformat()


# ── Composite Checks ──────────────────────────────────────────────────────────


def check_user_can_infer(user_id: int) -> Optional[str]:
    """Check if a user is allowed to perform inference.

    Returns None if OK, or a Chinese error message string explaining why not.
    """
    user = get_user_by_id(user_id)
    if not user:
        return "用户不存在"

    if not user["is_active"]:
        return "账号已被停用，请联系管理员"

    if user["role"] == "super_admin":
        return None

    # Check enterprise admin grant expiry
    if user["role"] == "enterprise_admin":
        if is_enterprise_admin_expired(user_id):
            return "企业管理员授权已到期，请联系超级管理员续期"
        return None

    if user["enterprise_id"] is None:
        return "账号尚未分配到企业，请联系管理员"

    enterprise = get_enterprise(user["enterprise_id"])
    if enterprise and not enterprise["is_active"]:
        return "所属企业已被停用，请联系管理员"

    # Check if enterprise admin grant for this enterprise exists and is expired
    grant = get_enterprise_admin_grant(user_id)
    if grant and grant["expires_at"] < datetime.now().isoformat():
        return "所属企业管理员授权已到期，企业功能暂不可用"

    # Check quota
    quota = get_user_quota(user_id)
    if quota and quota["used"] >= quota["total_granted"]:
        return "推理次数已用完，请联系企业管理员增加配额"

    return None


# Auto-init on import
init_auth_db()
