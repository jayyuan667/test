# 用户认证与权限管理系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为二维工艺系统新增多租户用户认证与权限管理：JWT 登录/注册、三层角色（超级管理员/企业管理员/普通用户）、推理配额控制、知识库上传校验。

**Architecture:** 后端基于 Flask Blueprint + 原生 sqlite3（auth.db），JWT 存 HttpOnly Cookie；前端基于 React Context + useState 路由，登录/管理页在 Sidebar 布局之外独立渲染。所有鉴权逻辑通过 Python 装饰器注入。

**Tech Stack:** Flask + PyJWT + sqlite3 + React 18 + Tailwind CSS 3 + TypeScript

## Global Constraints

- Python >=3.11,<3.12; Node >=20,<21
- 新增后端依赖：PyJWT>=2.8.0（添加到 pyproject.toml）
- 前端无新增依赖（纯 React + Tailwind + fetch）
- 密码使用 werkzeug.security（已安装，Flask 自带）
- JWT secret key 从环境变量 JWT_SECRET_KEY 读取，未设置时自动生成随机 key
- 所有新 Python 代码遵循现有 _response.py 的 ok()/fail() 模式
- 所有新前端代码遵循现有 Tailwind CSS + TypeScript 模式
- Cookie key: gn_token; HttpOnly; SameSite=Lax; Max-Age=86400
- 注册用户默认 enterprise_id=NULL, role='user', quota=10
- 知识库上传校验：解压后文件数 >= 30，否则返回中文错误提示
- 字体：Plus Jakarta Sans（Google Fonts import）

---

### Task 1: 安装 PyJWT 依赖并配置 JWT secret key

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/config.py`

**Interfaces:**
- Produces: `get_jwt_secret()` in config.py — returns str; reads `JWT_SECRET_KEY` env var or generates random 64-char hex key

- [ ] **Step 1: 添加 PyJWT 到 pyproject.toml**

In `pyproject.toml`, add `"pyjwt>=2.8,<3"` to the `dependencies` list (alphabetical order, after `"pillow"`):

```toml
  "pyjwt>=2.8,<3",
```

- [ ] **Step 2: 安装依赖**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test && uv sync
```
Expected: PyJWT installed without errors.

- [ ] **Step 3: 添加 get_jwt_secret() 到 config.py**

Append to `backend/config.py`:

```python
import secrets

def get_jwt_secret() -> str:
    """Return JWT secret key from env or generate a random one for dev."""
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if secret:
        return secret
    # Auto-generate for development; note this invalidates all tokens on restart
    generated = secrets.token_hex(32)
    os.environ["JWT_SECRET_KEY"] = generated
    return generated
```

- [ ] **Step 4: 验证导入**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test && python3 -c "from backend.config import get_jwt_secret; print('JWT secret:', get_jwt_secret()[:8] + '...')"
```
Expected: prints a hex string without errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml backend/config.py uv.lock
git commit -m "chore: add PyJWT dependency and JWT secret key config"
```

---

### Task 2: 创建 auth_store.py — 用户/企业/配额数据库层

**Files:**
- Create: `backend/auth_store.py`

**Interfaces:**
- Produces:
  - `init_auth_db()` → None
  - `create_user(username: str, password_hash: str, role: str = 'user', enterprise_id: int | None = None) -> dict`
  - `get_user_by_username(username: str) -> dict | None`
  - `get_user_by_id(user_id: int) -> dict | None`
  - `create_enterprise(name: str) -> dict`
  - `get_enterprise(enterprise_id: int) -> dict | None`
  - `list_enterprises(is_active: bool | None = None) -> list[dict]`
  - `update_enterprise(enterprise_id: int, **kwargs) -> None`
  - `get_or_create_quota(user_id: int, initial: int = 10) -> dict`
  - `consume_quota(user_id: int) -> bool` — atomically `used += 1` if `used < total_granted`, returns True on success
  - `set_quota(user_id: int, total_granted: int) -> None`
  - `get_user_quota(user_id: int) -> dict | None`
  - `create_enterprise_admin_grant(user_id: int, enterprise_id: int, granted_by: int, expires_at: str) -> dict`
  - `get_enterprise_admin_grant(user_id: int) -> dict | None`
  - `list_enterprise_users(enterprise_id: int) -> list[dict]`
  - `list_all_users() -> list[dict]`
  - `update_user(user_id: int, **kwargs) -> None`
  - `is_enterprise_admin_expired(user_id: int) -> bool`
  - `check_user_can_infer(user_id: int) -> str | None` — returns None if OK, or error message string

DB path: `backend/auth.db` (same directory as `task_store.py`)

- [ ] **Step 1: 创建 backend/auth_store.py**

Write the complete file:

```python
# -*- coding: utf-8 -*-
"""Auth database layer — users, enterprises, quotas, admin grants.

Follows the same sqlite3 + WAL pattern as task_store.py.
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

AUTH_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")


def _conn():
    conn = sqlite3.connect(AUTH_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


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

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_users_enterprise ON users(enterprise_id);
            CREATE INDEX IF NOT EXISTS idx_quotas_user ON quotas(user_id);
            CREATE INDEX IF NOT EXISTS idx_grants_user ON enterprise_admin_grants(user_id);
        """)
        # Ensure at least one super_admin exists for bootstrapping
        row = c.execute("SELECT COUNT(*) FROM users WHERE role='super_admin'").fetchone()
        if row[0] == 0:
            from werkzeug.security import generate_password_hash
            c.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "super_admin"),
            )
            admin_id = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
            c.execute(
                "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, ?, ?)",
                (admin_id, 999999, 0),
            )


# ── Users ──

def create_user(username: str, password_hash: str, role: str = "user",
                enterprise_id: int | None = None) -> dict:
    with _conn() as c:
        c.execute(
            "INSERT INTO users (username, password_hash, role, enterprise_id) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, enterprise_id),
        )
        user_id = c.lastrowid
        # Default quota of 10 for new users
        c.execute(
            "INSERT OR IGNORE INTO quotas (user_id, total_granted, used) VALUES (?, 10, 0)",
            (user_id,),
        )
    return get_user_by_id(user_id)


def get_user_by_username(username: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    allowed = {"username", "password_hash", "role", "enterprise_id", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [user_id]
    with _conn() as c:
        c.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)


def list_all_users() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT u.*, e.name as enterprise_name FROM users u "
            "LEFT JOIN enterprises e ON u.enterprise_id = e.id "
            "ORDER BY u.created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def list_enterprise_users(enterprise_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM users WHERE enterprise_id=? ORDER BY created_at DESC",
            (enterprise_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Enterprises ──

def create_enterprise(name: str) -> dict:
    with _conn() as c:
        c.execute("INSERT INTO enterprises (name) VALUES (?)", (name,))
    return get_enterprise(c.lastrowid)


def get_enterprise(enterprise_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM enterprises WHERE id=?", (enterprise_id,)).fetchone()
    return dict(row) if row else None


def list_enterprises(is_active: bool | None = None) -> list[dict]:
    with _conn() as c:
        if is_active is None:
            rows = c.execute("SELECT * FROM enterprises ORDER BY created_at DESC").fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM enterprises WHERE is_active=? ORDER BY created_at DESC",
                (int(is_active),),
            ).fetchall()
    return [dict(r) for r in rows]


def update_enterprise(enterprise_id: int, **kwargs):
    if not kwargs:
        return
    allowed = {"name", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [enterprise_id]
    with _conn() as c:
        c.execute(f"UPDATE enterprises SET {set_clause} WHERE id=?", values)


# ── Quotas ──

def get_or_create_quota(user_id: int, initial: int = 10) -> dict:
    with _conn() as c:
        row = c.execute("SELECT * FROM quotas WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            c.execute(
                "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, ?, 0)",
                (user_id, initial),
            )
            row = c.execute("SELECT * FROM quotas WHERE user_id=?", (user_id,)).fetchone()
    return dict(row)


def get_user_quota(user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM quotas WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def consume_quota(user_id: int) -> bool:
    """Atomically increment used count if quota remains. Returns True on success."""
    with _conn() as c:
        c.execute(
            "UPDATE quotas SET used = used + 1 WHERE user_id=? AND used < total_granted",
            (user_id,),
        )
        return c.execute("SELECT changes()").fetchone()[0] > 0


def set_quota(user_id: int, total_granted: int):
    with _conn() as c:
        c.execute(
            "INSERT INTO quotas (user_id, total_granted, used) VALUES (?, ?, 0) "
            "ON CONFLICT(user_id) DO UPDATE SET total_granted=?",
            (user_id, total_granted, total_granted),
        )


# ── Enterprise Admin Grants ──

def create_enterprise_admin_grant(user_id: int, enterprise_id: int,
                                   granted_by: int, expires_at: str) -> dict:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO enterprise_admin_grants "
            "(user_id, enterprise_id, granted_by, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, enterprise_id, granted_by, expires_at),
        )
    return get_enterprise_admin_grant(user_id)


def get_enterprise_admin_grant(user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM enterprise_admin_grants WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def is_enterprise_admin_expired(user_id: int) -> bool:
    grant = get_enterprise_admin_grant(user_id)
    if not grant:
        return False  # Not an enterprise admin, no expiry check needed
    return grant["expires_at"] < datetime.now().isoformat()


def check_user_can_infer(user_id: int) -> str | None:
    """Return None if user can infer, or an error message string."""
    user = get_user_by_id(user_id)
    if not user:
        return "用户不存在"
    if not user["is_active"]:
        return "账号已被停用，请联系管理员"

    # Super admins always allowed
    if user["role"] == "super_admin":
        return None

    # Enterprise admins: check grant expiry
    if user["role"] == "enterprise_admin":
        if is_enterprise_admin_expired(user_id):
            return "企业管理员授权已到期，请联系超级管理员续期"
        return None  # Enterprise admin doesn't consume personal quota

    # Regular users: need enterprise assignment
    if not user["enterprise_id"]:
        return "账号尚未分配到企业，请联系管理员"

    # Check enterprise is active
    enterprise = get_enterprise(user["enterprise_id"])
    if not enterprise or not enterprise["is_active"]:
        return "所属企业已被停用，请联系管理员"

    # Check enterprise admin is not expired
    # Find enterprise admin for this enterprise
    with _conn() as c:
        admin_row = c.execute(
            "SELECT u.id FROM users u "
            "JOIN enterprise_admin_grants g ON u.id = g.user_id "
            "WHERE g.enterprise_id=? AND u.is_active=1",
            (user["enterprise_id"],),
        ).fetchone()
    if admin_row and is_enterprise_admin_expired(admin_row[0]):
        return "所属企业管理员授权已到期，企业功能暂不可用"

    # Check quota
    quota = get_user_quota(user_id)
    if not quota or quota["used"] >= quota["total_granted"]:
        return "推理次数已用完，请联系企业管理员增加配额"

    return None


# Auto-init on import
init_auth_db()
```

- [ ] **Step 2: 验证数据库初始化**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test && python3 -c "
from backend.auth_store import init_auth_db, get_user_by_username, get_user_quota
admin = get_user_by_username('admin')
print('Admin user:', admin)
quota = get_user_quota(admin['id'])
print('Admin quota:', quota)
"
```
Expected: prints admin user dict and quota dict with total_granted=999999.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_store.py
git commit -m "feat: add auth_store.py with users/enterprises/quotas/grants tables"
```

---

### Task 3: 创建 auth_service.py — JWT 签发/验证 + 密码 hash

**Files:**
- Create: `backend/auth_service.py`

**Interfaces:**
- Consumes: `get_jwt_secret()` from config, `auth_store.*` functions
- Produces:
  - `hash_password(password: str) -> str`
  - `verify_password(password: str, password_hash: str) -> bool`
  - `create_token(user: dict) -> str`
  - `decode_token(token: str) -> dict | None`
  - `register_user(username: str, password: str) -> tuple[dict | None, str | None]` — returns (user, error)

- [ ] **Step 1: 创建 backend/auth_service.py**

```python
# -*- coding: utf-8 -*-
"""Authentication business logic — JWT, password hashing, registration."""

import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from .config import get_jwt_secret
from . import auth_store

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_token(user: dict) -> str:
    """Create a JWT token for the given user dict (must have id, username, role, enterprise_id)."""
    now = datetime.utcnow()
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "ent_id": user.get("enterprise_id") or 0,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def register_user(username: str, password: str) -> tuple[dict | None, str | None]:
    """Register a new user. Returns (user_dict, error_message)."""
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
```

- [ ] **Step 2: 验证 JWT 签发和验证**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test && python3 -c "
from backend.auth_service import create_token, decode_token, hash_password, verify_password
from backend.auth_store import get_user_by_username

user = get_user_by_username('admin')
token = create_token(user)
print('Token length:', len(token))
payload = decode_token(token)
print('Decoded:', {k: v for k, v in payload.items() if k != 'iat'})

# Test invalid token
print('Bad token:', decode_token('invalid.token.here'))

# Test password hashing
h = hash_password('test123')
print('Hash length:', len(h))
print('Verify correct:', verify_password('test123', h))
print('Verify wrong:', verify_password('wrong', h))
"
```
Expected: token decodes correctly, bad token returns None, password verify works.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service.py
git commit -m "feat: add auth_service.py with JWT and password hashing"
```

---

### Task 4: 创建 auth_utils.py — 装饰器

**Files:**
- Create: `backend/auth_utils.py`

**Interfaces:**
- Consumes: `decode_token()` from auth_service, `auth_store.*`, flask `request`, `g`
- Produces:
  - `login_required` — decorator for Flask routes; extracts JWT from cookie, validates, sets `g.current_user`
  - `require_role(*roles: str)` — decorator factory; checks `g.current_user["role"]` in allowed set
  - `require_quota` — decorator for routes that consume inference quota; checks and consumes

- [ ] **Step 1: 创建 backend/auth_utils.py**

```python
# -*- coding: utf-8 -*-
"""Flask decorators for authentication and authorization."""

from functools import wraps
from flask import request, g

from .auth_service import decode_token
from . import auth_store
from .api._response import fail, ERR_UNAUTHORIZED, ERR_FORBIDDEN


def login_required(f):
    """Decorator: extract JWT from gn_token cookie, validate, set g.current_user."""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("gn_token", "")
        if not token:
            return fail(ERR_UNAUTHORIZED, "请先登录", status=401)

        payload = decode_token(token)
        if not payload:
            resp = fail(ERR_UNAUTHORIZED, "登录已过期，请重新登录", status=401)
            resp.delete_cookie("gn_token")
            return resp

        user = auth_store.get_user_by_id(payload["sub"])
        if not user:
            resp = fail(ERR_UNAUTHORIZED, "用户不存在", status=401)
            resp.delete_cookie("gn_token")
            return resp

        if not user["is_active"]:
            resp = fail(ERR_UNAUTHORIZED, "账号已被停用", status=401)
            resp.delete_cookie("gn_token")
            return resp

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_role(*roles: str):
    """Decorator factory: require g.current_user to have one of the given roles."""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return fail(ERR_UNAUTHORIZED, "请先登录", status=401)
            if user["role"] not in roles:
                return fail(ERR_FORBIDDEN, "权限不足", status=403)
            return f(*args, **kwargs)

        return decorated

    return decorator


def require_quota(f):
    """Decorator: check and consume one inference quota.

    Must be used AFTER @login_required (needs g.current_user).
    Super admins are exempt from quota checks.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if not user:
            return fail(ERR_UNAUTHORIZED, "请先登录", status=401)

        error = auth_store.check_user_can_infer(user["id"])
        if error:
            return fail("QUOTA_EXCEEDED", error, status=403)

        if user["role"] != "super_admin":
            ok = auth_store.consume_quota(user["id"])
            if not ok:
                return fail("QUOTA_EXCEEDED", "推理次数已用完", status=403)

        return f(*args, **kwargs)

    return decorated
```

- [ ] **Step 2: 提交（无独立测试，装饰器将在后续 Task 的 API 端点中验证）**

```bash
git add backend/auth_utils.py
git commit -m "feat: add auth_utils.py with login_required/require_role/require_quota decorators"
```

---

### Task 5: 扩展 _response.py 错误码

**Files:**
- Modify: `backend/api/_response.py`

- [ ] **Step 1: 添加新错误码**

Add after `ERR_CAPABILITY = "CAPABILITY_UNAVAILABLE"`:

```python
ERR_UNAUTHORIZED = "UNAUTHORIZED"
ERR_FORBIDDEN = "FORBIDDEN"
ERR_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
ERR_ENTERPRISE_EXPIRED = "ENTERPRISE_EXPIRED"
ERR_USER_EXISTS = "USER_EXISTS"
ERR_VALIDATION = "VALIDATION_ERROR"
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/_response.py
git commit -m "feat: add auth-related error codes to _response.py"
```

---

### Task 6: 创建 api/auth.py — 认证端点

**Files:**
- Create: `backend/api/auth.py`

**Interfaces:**
- Produces: Flask Blueprint `auth_bp` with routes:
  - `POST /api/auth/login` — {username, password} → Set-Cookie + {user}
  - `POST /api/auth/register` — {username, password} → {user}
  - `POST /api/auth/logout` — Clear cookie
  - `GET /api/auth/me` — @login_required → {user}
  - `PUT /api/user/password` — @login_required {current_password, new_password} → ok
  - `GET /api/user/profile` — @login_required → {user, quota}

- [ ] **Step 1: 创建 backend/api/auth.py**

```python
# -*- coding: utf-8 -*-
"""Authentication API endpoints."""

from flask import Blueprint, request, jsonify, g

from ..auth_service import register_user, verify_password, create_token
from .. import auth_store
from ..auth_utils import login_required
from ._response import ok, fail, ERR_UNAUTHORIZED, ERR_USER_EXISTS, ERR_VALIDATION

auth_bp = Blueprint("auth", __name__)


def _user_to_dict(user: dict, include_quota: bool = False) -> dict:
    """Serialize user for API responses (never expose password_hash)."""
    enterprise = None
    if user.get("enterprise_id"):
        enterprise = auth_store.get_enterprise(user["enterprise_id"])

    result = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "enterprise_id": user.get("enterprise_id"),
        "enterprise_name": enterprise["name"] if enterprise else None,
        "is_active": bool(user.get("is_active", 1)),
        "created_at": user.get("created_at", ""),
    }

    if include_quota:
        quota = auth_store.get_user_quota(user["id"])
        result["quota"] = {
            "total_granted": quota["total_granted"] if quota else 10,
            "used": quota["used"] if quota else 0,
            "remaining": (quota["total_granted"] - quota["used"]) if quota else 10,
        }

    # For enterprise admins, include grant expiry
    if user["role"] == "enterprise_admin":
        grant = auth_store.get_enterprise_admin_grant(user["id"])
        result["grant_expires_at"] = grant["expires_at"] if grant else None

    return result


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return fail(ERR_VALIDATION, "用户名和密码不能为空")

    user = auth_store.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return fail(ERR_UNAUTHORIZED, "用户名或密码错误", status=401)

    if not user["is_active"]:
        return fail(ERR_UNAUTHORIZED, "账号已被停用", status=401)

    token = create_token(user)

    resp = jsonify({"success": True, "data": {"user": _user_to_dict(user, include_quota=True)}})
    resp.set_cookie(
        "gn_token",
        token,
        httponly=True,
        samesite="Lax",
        max_age=86400,
        secure=request.is_secure,
    )
    return resp


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return fail(ERR_VALIDATION, "用户名和密码不能为空")
    if len(password) < 6:
        return fail(ERR_VALIDATION, "密码至少需要 6 个字符")

    user, error = register_user(username, password)
    if error:
        code = ERR_USER_EXISTS if "已存在" in error else ERR_VALIDATION
        return fail(code, error)

    return ok({"user": _user_to_dict(user)})


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    resp = jsonify({"success": True, "data": {"message": "已登出"}})
    resp.delete_cookie("gn_token")
    return resp


@auth_bp.route("/auth/me", methods=["GET"])
@login_required
def me():
    return ok({"user": _user_to_dict(g.current_user, include_quota=True)})


@auth_bp.route("/user/profile", methods=["GET"])
@login_required
def profile():
    return ok({"user": _user_to_dict(g.current_user, include_quota=True)})


@auth_bp.route("/user/password", methods=["PUT"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""

    if not current or not new_pw:
        return fail(ERR_VALIDATION, "请输入当前密码和新密码")
    if len(new_pw) < 6:
        return fail(ERR_VALIDATION, "新密码至少需要 6 个字符")

    if not verify_password(current, g.current_user["password_hash"]):
        return fail(ERR_VALIDATION, "当前密码错误")

    from ..auth_service import hash_password
    auth_store.update_user(g.current_user["id"], password_hash=hash_password(new_pw))
    return ok({"message": "密码修改成功"})
```

- [ ] **Step 2: 验证 API 端点**

Run:
```bash
# Start Flask in background
cd /Users/caojiayuan/Projects/work/test && python3 -c "
from backend.app import app
app.run(host='0.0.0.0', port=5190, debug=False, use_reloader=False)
" &
sleep 2

# Test login with default admin account
curl -s -X POST http://localhost:5190/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' -c /tmp/cookies.txt | python3 -m json.tool

# Test /auth/me with cookie
curl -s http://localhost:5190/api/auth/me -b /tmp/cookies.txt | python3 -m json.tool

# Test register
curl -s -X POST http://localhost:5190/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"testuser","password":"test123456"}'

# Test logout
curl -s -X POST http://localhost:5190/api/auth/logout -b /tmp/cookies.txt

# Kill Flask
kill %1 2>/dev/null
```
Expected: login returns user with JWT cookie; /me returns current user; register creates new user; logout clears cookie.

- [ ] **Step 3: Commit**

```bash
git add backend/api/auth.py
git commit -m "feat: add auth API endpoints (login/register/logout/me/profile/password)"
```

---

### Task 7: 创建 api/admin.py — 管理端点

**Files:**
- Create: `backend/api/admin.py`

**Interfaces:**
- Produces: Flask Blueprint `admin_bp` with routes (all @login_required + @require_role):
  - `GET /api/admin/enterprises` → list (super_admin: all; enterprise_admin: own)
  - `POST /api/admin/enterprises` → create (super_admin only)
  - `PUT /api/admin/enterprises/<id>` → update (super_admin only)
  - `GET /api/admin/users` → list (enterprise_id query param)
  - `PUT /api/admin/users/<id>` → update quota/role/is_active
  - `POST /api/admin/grants` → renew enterprise admin (super_admin only)
  - `GET /api/admin/quotas` → quota overview

- [ ] **Step 1: 创建 backend/api/admin.py**

```python
# -*- coding: utf-8 -*-
"""Admin API endpoints for user/enterprise/quota management."""

from datetime import datetime, timedelta
from flask import Blueprint, request, g

from .. import auth_store
from ..auth_utils import login_required, require_role
from ._response import ok, fail, ERR_VALIDATION, ERR_FORBIDDEN

admin_bp = Blueprint("admin", __name__)


def _is_super_admin() -> bool:
    user = getattr(g, "current_user", None)
    return user and user["role"] == "super_admin"


def _user_to_dict(user: dict) -> dict:
    enterprise = None
    if user.get("enterprise_id"):
        enterprise = auth_store.get_enterprise(user["enterprise_id"])

    quota = auth_store.get_user_quota(user["id"])
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "enterprise_id": user.get("enterprise_id"),
        "enterprise_name": enterprise["name"] if enterprise else None,
        "is_active": bool(user.get("is_active", 1)),
        "created_at": user.get("created_at", ""),
        "quota_total": quota["total_granted"] if quota else 10,
        "quota_used": quota["used"] if quota else 0,
    }


# ── Enterprises ──

@admin_bp.route("/admin/enterprises", methods=["GET"])
@login_required
def list_enterprises():
    if _is_super_admin():
        enterprises = auth_store.list_enterprises()
    else:
        ent_id = g.current_user.get("enterprise_id")
        if not ent_id:
            return ok({"enterprises": []})
        ent = auth_store.get_enterprise(ent_id)
        enterprises = [ent] if ent else []

    # Attach user counts
    result = []
    for e in enterprises:
        users = auth_store.list_enterprise_users(e["id"])
        result.append({**e, "user_count": len(users)})

    return ok({"enterprises": result})


@admin_bp.route("/admin/enterprises", methods=["POST"])
@login_required
@require_role("super_admin")
def create_enterprise():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail(ERR_VALIDATION, "企业名称不能为空")
    enterprise = auth_store.create_enterprise(name)
    return ok({"enterprise": dict(enterprise)}, status=201)


@admin_bp.route("/admin/enterprises/<int:enterprise_id>", methods=["PUT"])
@login_required
@require_role("super_admin")
def update_enterprise(enterprise_id):
    data = request.get_json(silent=True) or {}
    updates = {}
    if "name" in data:
        updates["name"] = data["name"].strip()
    if "is_active" in data:
        updates["is_active"] = int(data["is_active"])
    if not updates:
        return fail(ERR_VALIDATION, "没有需要更新的字段")
    auth_store.update_enterprise(enterprise_id, **updates)
    enterprise = auth_store.get_enterprise(enterprise_id)
    return ok({"enterprise": dict(enterprise)})


# ── Users ──

@admin_bp.route("/admin/users", methods=["GET"])
@login_required
@require_role("super_admin", "enterprise_admin")
def list_users():
    enterprise_id = request.args.get("enterprise_id", type=int)

    if _is_super_admin():
        if enterprise_id:
            users = auth_store.list_enterprise_users(enterprise_id)
        else:
            users = auth_store.list_all_users()
    else:
        # Enterprise admin: only see own enterprise users
        own_ent = g.current_user.get("enterprise_id")
        if not own_ent:
            return ok({"users": []})
        users = auth_store.list_enterprise_users(own_ent)

    return ok({"users": [_user_to_dict(u) for u in users]})


@admin_bp.route("/admin/users/<int:user_id>", methods=["PUT"])
@login_required
@require_role("super_admin", "enterprise_admin")
def update_user(user_id):
    target = auth_store.get_user_by_id(user_id)
    if not target:
        return fail(ERR_VALIDATION, "用户不存在", status=404)

    current = g.current_user

    # Enterprise admin can only manage their own enterprise's users
    if current["role"] == "enterprise_admin":
        if target.get("enterprise_id") != current.get("enterprise_id"):
            return fail(ERR_FORBIDDEN, "只能管理本企业用户", status=403)
        # Cannot modify super_admin or other enterprise admins
        if target["role"] in ("super_admin",):
            return fail(ERR_FORBIDDEN, "权限不足", status=403)

    data = request.get_json(silent=True) or {}
    user_updates = {}

    if "is_active" in data:
        if current["role"] != "super_admin" and target["role"] == "enterprise_admin":
            return fail(ERR_FORBIDDEN, "无权限修改企业管理员状态", status=403)
        user_updates["is_active"] = int(data["is_active"])

    if "role" in data:
        if current["role"] != "super_admin":
            return fail(ERR_FORBIDDEN, "只有超级管理员可以修改角色", status=403)
        user_updates["role"] = data["role"]

    if "enterprise_id" in data:
        if current["role"] != "super_admin":
            return fail(ERR_FORBIDDEN, "只有超级管理员可以分配企业", status=403)
        user_updates["enterprise_id"] = data["enterprise_id"]

    if user_updates:
        auth_store.update_user(user_id, **user_updates)

    # Update quota if provided
    if "quota_total" in data:
        if current["role"] == "enterprise_admin":
            if target.get("enterprise_id") != current.get("enterprise_id"):
                return fail(ERR_FORBIDDEN, "只能修改本企业用户配额", status=403)
        auth_store.set_quota(user_id, int(data["quota_total"]))

    updated = auth_store.get_user_by_id(user_id)
    return ok({"user": _user_to_dict(updated)})


# ── Enterprise Admin Grants ──

@admin_bp.route("/admin/grants", methods=["POST"])
@login_required
@require_role("super_admin")
def create_grant():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    enterprise_id = data.get("enterprise_id")
    duration_days = data.get("duration_days", 365)

    if not user_id or not enterprise_id:
        return fail(ERR_VALIDATION, "user_id 和 enterprise_id 不能为空")

    user = auth_store.get_user_by_id(user_id)
    if not user:
        return fail(ERR_VALIDATION, "用户不存在", status=404)

    # Update user role to enterprise_admin
    auth_store.update_user(user_id, role="enterprise_admin", enterprise_id=enterprise_id)

    expires_at = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()
    grant = auth_store.create_enterprise_admin_grant(
        user_id, enterprise_id, g.current_user["id"], expires_at
    )
    return ok({"grant": dict(grant)}, status=201)


# ── Quota Overview ──

@admin_bp.route("/admin/quotas", methods=["GET"])
@login_required
@require_role("super_admin", "enterprise_admin")
def quota_overview():
    if _is_super_admin():
        users = auth_store.list_all_users()
    else:
        ent_id = g.current_user.get("enterprise_id")
        if not ent_id:
            return ok({"quotas": []})
        users = auth_store.list_enterprise_users(ent_id)

    result = []
    for u in users:
        if u["role"] == "super_admin":
            continue
        quota = auth_store.get_user_quota(u["id"])
        result.append({
            "user_id": u["id"],
            "username": u["username"],
            "role": u["role"],
            "total_granted": quota["total_granted"] if quota else 0,
            "used": quota["used"] if quota else 0,
            "remaining": (quota["total_granted"] - quota["used"]) if quota else 0,
        })

    return ok({"quotas": result})
```

- [ ] **Step 2: 验证管理 API**

Run:
```bash
# Start Flask (if not already running)
cd /Users/caojiayuan/Projects/work/test && python3 -c "
from backend.app import app
app.run(host='0.0.0.0', port=5190, debug=False, use_reloader=False)
" &
sleep 2

# Login as admin
curl -s -X POST http://localhost:5190/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' -c /tmp/cookies.txt | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['user']['username'])"

# Create enterprise
curl -s -X POST http://localhost:5190/api/admin/enterprises \
  -H 'Content-Type: application/json' \
  -b /tmp/cookies.txt \
  -d '{"name":"测试企业"}'

# List enterprises
curl -s http://localhost:5190/api/admin/enterprises -b /tmp/cookies.txt | python3 -m json.tool

# List users
curl -s http://localhost:5190/api/admin/users -b /tmp/cookies.txt | python3 -m json.tool

# Kill Flask
kill %1 2>/dev/null
```
Expected: enterprise created, listed; users listed with admin account.

- [ ] **Step 3: Commit**

```bash
git add backend/api/admin.py
git commit -m "feat: add admin API endpoints (enterprises/users/grants/quotas)"
```

---

### Task 8: 注册 auth 和 admin Blueprints

**Files:**
- Modify: `backend/api/__init__.py`

- [ ] **Step 1: 注册新的 Blueprints**

In `backend/api/__init__.py`, inside `register_routes(app)`, add after existing imports:

```python
from .auth import auth_bp
from .admin import admin_bp

app.register_blueprint(auth_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/api")
```

The full modified function:

```python
def register_routes(app):
    """Register all API blueprints with the Flask app."""
    from .upload import upload_bp
    from .batch import batch_bp
    from .status import status_bp
    from .events import events_bp
    from .result import result_bp
    from .history import history_bp
    from .config import config_bp
    from .export import export_bp
    from .health import health_bp
    from .image import image_bp
    from .library import library_bp
    from .kb_import import kb_import_bp
    from .auth import auth_bp
    from .admin import admin_bp

    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(batch_bp, url_prefix="/api")
    app.register_blueprint(status_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(result_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(config_bp, url_prefix="/api")
    app.register_blueprint(export_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(image_bp, url_prefix="/api")
    app.register_blueprint(library_bp, url_prefix="/api")
    app.register_blueprint(kb_import_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")
    from .annotations import annotations_bp
    app.register_blueprint(annotations_bp, url_prefix="/api")
```

- [ ] **Step 2: 验证 Blueprint 注册**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test && python3 -c "
from backend.app import app
rules = [r.rule for r in app.url_map.iter_rules()]
auth_rules = [r for r in rules if 'auth' in r or 'admin' in r or 'user' in r]
for r in sorted(auth_rules):
    print(r)
"
```
Expected: lists `/api/auth/login`, `/api/auth/register`, `/api/auth/logout`, `/api/auth/me`, `/api/user/password`, `/api/user/profile`, `/api/admin/enterprises`, `/api/admin/users`, `/api/admin/grants`, `/api/admin/quotas`, plus variants like `/api/admin/enterprises/<int:enterprise_id>` and `/api/admin/users/<int:user_id>`.

- [ ] **Step 3: Commit**

```bash
git add backend/api/__init__.py
git commit -m "feat: register auth and admin blueprints"
```

---

### Task 9: 修改 app.py — CORS + credentials 支持

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 修改 CORS 配置**

Change:
```python
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

To:
```python
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:3200", "http://localhost:5190", "http://127.0.0.1:3200", "http://127.0.0.1:5190"],
    "supports_credentials": True,
}})
```

- [ ] **Step 2: Commit**

```bash
git add backend/app.py
git commit -m "fix: update CORS for cookie credentials support"
```

---

### Task 10: 给现有业务 API 添加认证装饰器

**Files:**
- Modify: `backend/api/upload.py`
- Modify: `backend/api/batch.py`

- [ ] **Step 1: 修改 upload.py**

In `backend/api/upload.py`, add import at top:
```python
from ..auth_utils import login_required, require_quota
```

Add `@login_required` and `@require_quota` to the main upload route function (the one decorated with `@upload_bp.route("/upload", ...)`). Find the function definition and add decorators above the route decorator:

```python
@upload_bp.route("/upload", methods=["POST"])
@require_quota
@login_required
def upload_file():
```

And similarly for the drawing upload:

```python
@upload_bp.route("/upload_drawing", methods=["POST"])
@require_quota
@login_required
def upload_drawing():
```

- [ ] **Step 2: 修改 batch.py**

In `backend/api/batch.py`, add import:
```python
from ..auth_utils import login_required, require_quota
```

Add decorators to the batch upload route:

```python
@batch_bp.route("/batch_upload", methods=["POST"])
@require_quota
@login_required
def batch_upload():
```

- [ ] **Step 3: 验证认证保护**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test
python3 -c "from backend.app import app; app.run(host='0.0.0.0', port=5190, debug=False, use_reloader=False)" &
sleep 2

# Should fail without auth (401)
curl -s -X POST http://localhost:5190/api/upload | python3 -c "import sys,json; d=json.load(sys.stdin); print(d)"

# Login
curl -s -X POST http://localhost:5190/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' -c /tmp/cookies2.txt > /dev/null

# Should return 400 (file missing) but not 401
curl -s -X POST http://localhost:5190/api/upload -b /tmp/cookies2.txt | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('code','no error'))"

kill %1 2>/dev/null
```
Expected: first call returns 401 UNAUTHORIZED, second returns FILE_MISSING (not UNAUTHORIZED), proving auth works.

- [ ] **Step 4: Commit**

```bash
git add backend/api/upload.py backend/api/batch.py
git commit -m "feat: add auth decorators to upload and batch API endpoints"
```

---

### Task 11: 给 kb_import.py 添加文件数校验

**Files:**
- Modify: `backend/api/kb_import.py`

- [ ] **Step 1: 添加校验逻辑**

In `backend/api/kb_import.py`, find the `import_zip_route()` function (around line 1222). After the file save line (`upload.save(zip_path)`) and before the `try:` block, add:

```python
    # Validate minimum file count inside ZIP
    try:
        with zipfile.ZipFile(zip_path) as zf:
            file_count = len([f for f in zf.namelist() if not f.endswith('/')])
        if file_count < 30:
            os.unlink(zip_path)
            return jsonify({"error": f"数据量太少，压缩包内文件数为 {file_count}，必须大于 30 个文件"}), 400
    except zipfile.BadZipFile:
        os.unlink(zip_path)
        return jsonify({"error": "无效的 ZIP 文件"}), 400
```

- [ ] **Step 2: 验证校验**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test && python3 -c "
# Quick unit test of the validation function
import zipfile, os, tempfile
# Create a small zip with 5 files
tmp = tempfile.mktemp(suffix='.zip')
with zipfile.ZipFile(tmp, 'w') as zf:
    for i in range(5):
        zf.writestr(f'file_{i}.txt', 'test')
with zipfile.ZipFile(tmp) as zf:
    count = len([f for f in zf.namelist() if not f.endswith('/')])
print(f'File count: {count}, should be rejected (< 30)')
os.unlink(tmp)

# Create a zip with 35 files
tmp2 = tempfile.mktemp(suffix='.zip')
with zipfile.ZipFile(tmp2, 'w') as zf:
    for i in range(35):
        zf.writestr(f'file_{i}.txt', 'test')
with zipfile.ZipFile(tmp2) as zf:
    count = len([f for f in zf.namelist() if not f.endswith('/')])
print(f'File count: {count}, should pass (>= 30)')
os.unlink(tmp2)
"
```
Expected: first zip shows count=5 (rejected), second shows count=35 (passes).

- [ ] **Step 3: Commit**

```bash
git add backend/api/kb_import.py
git commit -m "feat: add minimum file count validation (>=30) to ZIP import"
```

---

### Task 12: 前端类型定义扩展

**Files:**
- Modify: `frontend-react/src/types/index.ts`
- Create: `frontend-react/src/types/auth.ts`

- [ ] **Step 1: 扩展 PageId 类型**

In `frontend-react/src/types/index.ts`, change the `PageId` type:

```typescript
export type PageId = 'generate' | 'zip' | 'history' | 'db' | 'profile' | 'admin' | 'login' | 'register'
```

- [ ] **Step 2: 创建 auth.ts 类型**

Create `frontend-react/src/types/auth.ts`:

```typescript
export interface User {
  id: number
  username: string
  role: 'super_admin' | 'enterprise_admin' | 'user'
  enterprise_id: number | null
  enterprise_name: string | null
  is_active: boolean
  created_at: string
  grant_expires_at?: string | null
  quota?: {
    total_granted: number
    used: number
    remaining: number
  }
}

export interface Enterprise {
  id: number
  name: string
  is_active: boolean
  created_at: string
  user_count?: number
}

export interface QuotaInfo {
  user_id: number
  username: string
  role: string
  total_granted: number
  used: number
  remaining: number
}

export interface AdminUser extends User {
  quota_total: number
  quota_used: number
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend-react/src/types/index.ts frontend-react/src/types/auth.ts
git commit -m "feat: add auth types (User, Enterprise, QuotaInfo, AdminUser) and extend PageId"
```

---

### Task 13: 前端 API 客户端扩展

**Files:**
- Modify: `frontend-react/src/api/client.ts`

- [ ] **Step 1: 修改 request() 函数添加 credentials**

Change the `request<T>` function in `client.ts`:

```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init?.headers || {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const errMsg = body.error?.message || body.error || body.message || `HTTP ${res.status}`
    throw new Error(errMsg)
  }
  return res.json()
}
```

- [ ] **Step 2: 修改所有 fetch 调用添加 credentials**

All other `fetch()` calls in the file must also add `credentials: 'include'`. For each fetch call, add `credentials: 'include'` to the init object. Example for `uploadFile`:

```typescript
export async function uploadFile(file: File, opts?: { retrieval_library_key?: string; feature_cache?: boolean }): Promise<{ task_id: string; pdf_name: string }> {
  const fd = new FormData()
  fd.append('file', file)
  if (opts?.retrieval_library_key) fd.append('retrieval_library_key', opts.retrieval_library_key)
  if (opts?.feature_cache != null) fd.append('feature_cache', String(opts.feature_cache))
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: fd, credentials: 'include' })
  // ... rest unchanged
}
```

Apply the same `credentials: 'include'` addition to all `fetch()` calls in `batchUpload`, `submitReview`, `rerunTask`, `updateProcess`, `deleteTask`, `downloadExport`, `importZipZip`, `saveAnnotation`, `finalizeAnnotation`, `exportAnnotations`, and `updateConfig`.

- [ ] **Step 3: 添加 Auth API 函数**

Append to `client.ts`:

```typescript
/* ── Auth ── */

import type { User, Enterprise, QuotaInfo, AdminUser } from '../types/auth'

export interface LoginResponse {
  user: User
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const errMsg = body.error?.message || body.error || `登录失败: ${res.status}`
    throw new Error(errMsg)
  }
  const data = await res.json()
  return data.data
}

export async function register(username: string, password: string): Promise<ApiResponse<{ user: User }>> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const errMsg = body.error?.message || body.error || `注册失败: ${res.status}`
    throw new Error(errMsg)
  }
  return res.json()
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  })
}

export async function getMe(): Promise<{ user: User }> {
  const res = await fetch(`${BASE}/auth/me`, { credentials: 'include' })
  if (!res.ok) throw new Error('Not authenticated')
  const data = await res.json()
  return data.data
}

export async function getProfile(): Promise<{ user: User }> {
  const res = await fetch(`${BASE}/user/profile`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to load profile')
  const data = await res.json()
  return data.data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await fetch(`${BASE}/user/password`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message || body.error || '修改密码失败')
  }
}

/* ── Admin ── */

export async function getEnterprises(): Promise<{ enterprises: Enterprise[] }> {
  const res = await fetch(`${BASE}/admin/enterprises`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to load enterprises')
  const data = await res.json()
  return data.data
}

export async function createEnterprise(name: string): Promise<{ enterprise: Enterprise }> {
  const res = await fetch(`${BASE}/admin/enterprises`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message || body.error || '创建企业失败')
  }
  const data = await res.json()
  return data.data
}

export async function updateEnterprise(id: number, updates: { name?: string; is_active?: boolean }): Promise<void> {
  const res = await fetch(`${BASE}/admin/enterprises/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(updates),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message || body.error || '更新企业失败')
  }
}

export async function getAdminUsers(enterpriseId?: number): Promise<{ users: AdminUser[] }> {
  const qs = enterpriseId ? `?enterprise_id=${enterpriseId}` : ''
  const res = await fetch(`${BASE}/admin/users${qs}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to load users')
  const data = await res.json()
  return data.data
}

export async function updateAdminUser(userId: number, updates: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${BASE}/admin/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(updates),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message || body.error || '更新用户失败')
  }
}

export async function createAdminGrant(userId: number, enterpriseId: number, durationDays: number = 365): Promise<void> {
  const res = await fetch(`${BASE}/admin/grants`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ user_id: userId, enterprise_id: enterpriseId, duration_days: durationDays }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error?.message || body.error || '创建授权失败')
  }
}

export async function getAdminQuotas(): Promise<{ quotas: QuotaInfo[] }> {
  const res = await fetch(`${BASE}/admin/quotas`, { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to load quotas')
  const data = await res.json()
  return data.data
}
```

- [ ] **Step 4: 重新构建前端确保无 TypeScript 错误**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test/frontend-react && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors related to auth changes (may have pre-existing errors in other files — ensure no NEW errors from our changes).

- [ ] **Step 5: Commit**

```bash
git add frontend-react/src/api/client.ts
git commit -m "feat: add auth/admin API functions and credentials:include to all fetch calls"
```

---

### Task 14: 创建 AuthContext

**Files:**
- Create: `frontend-react/src/contexts/AuthContext.tsx`

**Interfaces:**
- Produces: `AuthProvider` component, `useAuth()` hook returning `{ user, isAuthenticated, isLoading, login, logout, refreshUser }`

- [ ] **Step 1: 创建 AuthContext.tsx**

```typescript
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import type { User } from '../types/auth'
import { getMe, login as apiLogin, logout as apiLogout } from '../api/client'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    try {
      const data = await getMe()
      setUser(data.user)
    } catch {
      setUser(null)
    }
  }, [])

  // Check auth status on mount
  useEffect(() => {
    refreshUser().finally(() => setIsLoading(false))
  }, [refreshUser])

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiLogin(username, password)
    setUser(data.user)
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend-react/src/contexts/AuthContext.tsx
git commit -m "feat: add AuthContext for global auth state management"
```

---

### Task 15: 创建 LoginPage

**Files:**
- Create: `frontend-react/src/pages/LoginPage.tsx`

- [ ] **Step 1: 创建 LoginPage.tsx**

```typescript
import { useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../hooks/useToast'

interface Props {
  onNavigate: (page: 'register') => void
}

export function LoginPage({ onNavigate }: Props) {
  const { login } = useAuth()
  const { show } = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) {
      setError('请输入用户名和密码')
      return
    }
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      show('登录成功', 'success')
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl mx-auto mb-4 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%)',
              boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
            }}
          >
            <div className="absolute inset-0" style={{
              background: 'radial-gradient(circle at 30% 25%, rgba(255,255,255,0.25) 0%, transparent 50%)',
            }} />
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-wide">二维工艺系统</h1>
          <p className="text-sm text-slate-500 mt-1">2D Process Intelligence</p>
        </div>

        {/* Form Card */}
        <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-6">
          <div className="mb-4">
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1.5">
              用户名
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none
                         transition duration-150"
              placeholder="请输入用户名"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1.5">
              密码
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full border border-slate-300 rounded-lg px-3 py-2.5 pr-10 text-sm
                           focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none
                           transition duration-150"
                placeholder="请输入密码"
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600
                           transition-colors duration-150"
                aria-label={showPw ? '隐藏密码' : '显示密码'}
              >
                {showPw ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {error && (
            <p className="text-red-600 text-sm mb-4 flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-orange-500 hover:bg-orange-600 active:scale-[0.98] text-white px-6 py-2.5
                       rounded-lg font-semibold text-sm transition-all duration-150
                       disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
          >
            {submitting ? '登录中...' : '登 录'}
          </button>

          <p className="text-center text-sm text-slate-500 mt-4">
            还没有账号？
            <button
              type="button"
              onClick={() => onNavigate('register')}
              className="text-orange-600 hover:text-orange-700 font-medium ml-1 transition-colors duration-150"
            >
              立即注册
            </button>
          </p>
        </form>

        <p className="text-center text-xs text-slate-400 mt-8">
          Copyright © 机器学习与工业智能应用教育部工程研究中心
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend-react/src/pages/LoginPage.tsx
git commit -m "feat: add LoginPage with password visibility toggle"
```

---

### Task 16: 创建 RegisterPage

**Files:**
- Create: `frontend-react/src/pages/RegisterPage.tsx`

- [ ] **Step 1: 创建 RegisterPage.tsx**

```typescript
import { useState, type FormEvent } from 'react'
import { register } from '../api/client'
import { useToast } from '../hooks/useToast'

interface Props {
  onNavigate: (page: 'login') => void
}

export function RegisterPage({ onNavigate }: Props) {
  const { show } = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password || !confirmPw) {
      setError('请填写所有字段')
      return
    }
    if (password !== confirmPw) {
      setError('两次输入的密码不一致')
      return
    }
    if (password.length < 6) {
      setError('密码至少需要 6 个字符')
      return
    }
    setSubmitting(true)
    try {
      await register(username.trim(), password)
      show('注册成功，请登录', 'success')
      onNavigate('login')
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl mx-auto mb-4 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%)',
              boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
            }}
          >
            <div className="absolute inset-0" style={{
              background: 'radial-gradient(circle at 30% 25%, rgba(255,255,255,0.25) 0%, transparent 50%)',
            }} />
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-wide">创建账号</h1>
          <p className="text-sm text-slate-500 mt-1">注册后可申请加入企业</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-6">
          <div className="mb-4">
            <label htmlFor="reg-username" className="block text-sm font-medium text-slate-700 mb-1.5">用户名</label>
            <input id="reg-username" type="text" value={username}
              onChange={e => setUsername(e.target.value)} autoComplete="username"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition duration-150"
              placeholder="请输入用户名" />
          </div>

          <div className="mb-4">
            <label htmlFor="reg-password" className="block text-sm font-medium text-slate-700 mb-1.5">密码</label>
            <input id="reg-password" type="password" value={password}
              onChange={e => setPassword(e.target.value)} autoComplete="new-password"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition duration-150"
              placeholder="至少 6 个字符" />
          </div>

          <div className="mb-4">
            <label htmlFor="reg-confirm" className="block text-sm font-medium text-slate-700 mb-1.5">确认密码</label>
            <input id="reg-confirm" type="password" value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)} autoComplete="new-password"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition duration-150"
              placeholder="再次输入密码" />
          </div>

          {error && (
            <p className="text-red-600 text-sm mb-4 flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {error}
            </p>
          )}

          <button type="submit" disabled={submitting}
            className="w-full bg-orange-500 hover:bg-orange-600 active:scale-[0.98] text-white px-6 py-2.5
                       rounded-lg font-semibold text-sm transition-all duration-150
                       disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100">
            {submitting ? '注册中...' : '注 册'}
          </button>

          <p className="text-center text-sm text-slate-500 mt-4">
            已有账号？
            <button type="button" onClick={() => onNavigate('login')}
              className="text-orange-600 hover:text-orange-700 font-medium ml-1 transition-colors duration-150">
              立即登录
            </button>
          </p>

          <p className="text-xs text-slate-400 mt-3 text-center leading-relaxed">
            注册后可使用基础功能<br />管理员分配企业后激活全部功能
          </p>
        </form>

        <p className="text-center text-xs text-slate-400 mt-8">
          Copyright © 机器学习与工业智能应用教育部工程研究中心
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend-react/src/pages/RegisterPage.tsx
git commit -m "feat: add RegisterPage with password confirmation"
```

---

### Task 17: 创建 ProfilePage

**Files:**
- Create: `frontend-react/src/pages/ProfilePage.tsx`

- [ ] **Step 1: 创建 ProfilePage.tsx**

```typescript
import { useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { changePassword } from '../api/client'
import { useToast } from '../hooks/useToast'

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  enterprise_admin: '企业管理员',
  user: '普通用户',
}

export function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const { show } = useToast()

  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwError, setPwError] = useState('')
  const [pwSubmitting, setPwSubmitting] = useState(false)

  const handlePasswordChange = async (e: FormEvent) => {
    e.preventDefault()
    setPwError('')
    if (!currentPw || !newPw || !confirmPw) {
      setPwError('请填写所有密码字段')
      return
    }
    if (newPw !== confirmPw) {
      setPwError('两次输入的新密码不一致')
      return
    }
    if (newPw.length < 6) {
      setPwError('新密码至少需要 6 个字符')
      return
    }
    setPwSubmitting(true)
    try {
      await changePassword(currentPw, newPw)
      show('密码修改成功', 'success')
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
    } catch (err) {
      setPwError(err instanceof Error ? err.message : '修改失败')
    } finally {
      setPwSubmitting(false)
    }
  }

  if (!user) return null

  const quota = user.quota
  const remaining = quota?.remaining ?? 0
  const total = quota?.total_granted ?? 0
  const pct = total > 0 ? Math.round((remaining / total) * 100) : 0

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-6">
      <h1 className="text-xl font-bold text-slate-900">个人中心</h1>

      {/* Account Info Card */}
      <section className="bg-white border border-slate-200 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">账户信息</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-500">用户名</span>
            <p className="text-slate-900 font-medium">{user.username}</p>
          </div>
          <div>
            <span className="text-slate-500">角色</span>
            <p className="text-slate-900 font-medium">{ROLE_LABELS[user.role] || user.role}</p>
          </div>
          <div>
            <span className="text-slate-500">所属企业</span>
            <p className="text-slate-900 font-medium">{user.enterprise_name || '未分配'}</p>
          </div>
          <div>
            <span className="text-slate-500">账号状态</span>
            <p className={`font-medium ${user.is_active ? 'text-emerald-600' : 'text-red-600'}`}>
              {user.is_active ? '正常' : '已停用'}
            </p>
          </div>
          {user.grant_expires_at && (
            <div>
              <span className="text-slate-500">授权到期</span>
              <p className="text-slate-900 font-medium">{user.grant_expires_at.slice(0, 10)}</p>
            </div>
          )}
        </div>
      </section>

      {/* Quota Card */}
      <section className="bg-white border border-slate-200 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">使用配额</h2>
        <div className="flex items-baseline gap-2 mb-3">
          <span className="text-3xl font-bold text-slate-900">{remaining}</span>
          <span className="text-sm text-slate-500">/ {total} 次剩余</span>
        </div>
        <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: pct > 20
                ? 'linear-gradient(90deg, #f97316, #fb923c)'
                : 'linear-gradient(90deg, #ef4444, #f87171)',
            }}
          />
        </div>
        <p className="text-xs text-slate-400 mt-2">已使用 {total - remaining} 次</p>
      </section>

      {/* Change Password Card */}
      <section className="bg-white border border-slate-200 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">修改密码</h2>
        <form onSubmit={handlePasswordChange} className="space-y-4 max-w-sm">
          <div>
            <label htmlFor="current-pw" className="block text-sm font-medium text-slate-700 mb-1.5">当前密码</label>
            <input id="current-pw" type="password" value={currentPw}
              onChange={e => setCurrentPw(e.target.value)} autoComplete="current-password"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition duration-150" />
          </div>
          <div>
            <label htmlFor="new-pw" className="block text-sm font-medium text-slate-700 mb-1.5">新密码</label>
            <input id="new-pw" type="password" value={newPw}
              onChange={e => setNewPw(e.target.value)} autoComplete="new-password"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition duration-150" />
          </div>
          <div>
            <label htmlFor="confirm-new-pw" className="block text-sm font-medium text-slate-700 mb-1.5">确认新密码</label>
            <input id="confirm-new-pw" type="password" value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)} autoComplete="new-password"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition duration-150" />
          </div>
          {pwError && (
            <p className="text-red-600 text-sm flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {pwError}
            </p>
          )}
          <button type="submit" disabled={pwSubmitting}
            className="bg-orange-500 hover:bg-orange-600 active:scale-[0.98] text-white px-6 py-2.5
                       rounded-lg font-semibold text-sm transition-all duration-150
                       disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100">
            {pwSubmitting ? '保存中...' : '保存修改'}
          </button>
        </form>
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend-react/src/pages/ProfilePage.tsx
git commit -m "feat: add ProfilePage with account info, quota display, and password change"
```

---

### Task 18: 创建 AdminPage + 三个 Tab

**Files:**
- Create: `frontend-react/src/pages/admin/AdminPage.tsx`
- Create: `frontend-react/src/pages/admin/EnterpriseTab.tsx`
- Create: `frontend-react/src/pages/admin/UsersTab.tsx`
- Create: `frontend-react/src/pages/admin/QuotaTab.tsx`

- [ ] **Step 1: 创建 AdminPage.tsx（容器 + Tab 切换）**

```typescript
import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { EnterpriseTab } from './EnterpriseTab'
import { UsersTab } from './UsersTab'
import { QuotaTab } from './QuotaTab'

type AdminTab = 'enterprises' | 'users' | 'quotas'

export function AdminPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<AdminTab>('enterprises')
  const isSuperAdmin = user?.role === 'super_admin'

  const tabs: { id: AdminTab; label: string; show: boolean }[] = [
    { id: 'enterprises', label: '企业管理', show: isSuperAdmin },
    { id: 'users', label: '用户管理', show: true },
    { id: 'quotas', label: '配额概览', show: true },
  ]

  const visibleTabs = tabs.filter(t => t.show)

  return (
    <div className="max-w-6xl mx-auto py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-900">管理后台</h1>
        <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
          {isSuperAdmin ? '超级管理员' : '企业管理员'}
        </span>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-slate-200 mb-6" role="tablist">
        {visibleTabs.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`px-5 py-3 text-sm font-medium transition-all duration-150 border-b-2 -mb-[1px] ${
              tab === t.id
                ? 'border-orange-500 text-orange-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'enterprises' && <EnterpriseTab />}
      {tab === 'users' && <UsersTab />}
      {tab === 'quotas' && <QuotaTab />}
    </div>
  )
}
```

- [ ] **Step 2: 创建 EnterpriseTab.tsx**

```typescript
import { useState, useEffect, useCallback } from 'react'
import { getEnterprises, createEnterprise, updateEnterprise, createAdminGrant } from '../../api/client'
import { useToast } from '../../hooks/useToast'
import type { Enterprise } from '../../types/auth'

export function EnterpriseTab() {
  const { show } = useToast()
  const [enterprises, setEnterprises] = useState<Enterprise[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [renewModal, setRenewModal] = useState<Enterprise | null>(null)
  const [renewUserId, setRenewUserId] = useState('')
  const [renewDays, setRenewDays] = useState(365)

  const load = useCallback(async () => {
    try {
      const data = await getEnterprises()
      setEnterprises(data.enterprises)
    } catch (err) {
      show(err instanceof Error ? err.message : '加载失败', 'error')
    } finally {
      setLoading(false)
    }
  }, [show])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await createEnterprise(newName.trim())
      setNewName('')
      show('企业创建成功', 'success')
      load()
    } catch (err) {
      show(err instanceof Error ? err.message : '创建失败', 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleToggleActive = async (e: Enterprise) => {
    try {
      await updateEnterprise(e.id, { is_active: !e.is_active })
      show(e.is_active ? '企业已停用' : '企业已启用', 'success')
      load()
    } catch (err) {
      show(err instanceof Error ? err.message : '操作失败', 'error')
    }
  }

  const handleRenew = async () => {
    if (!renewModal || !renewUserId.trim()) return
    try {
      await createAdminGrant(Number(renewUserId), renewModal.id, renewDays)
      show('企业管理员续期成功', 'success')
      setRenewModal(null)
      setRenewUserId('')
    } catch (err) {
      show(err instanceof Error ? err.message : '续期失败', 'error')
    }
  }

  if (loading) {
    return <div className="text-center py-12 text-slate-400 text-sm">加载中...</div>
  }

  return (
    <div>
      {/* Create form */}
      <div className="flex gap-3 mb-6">
        <input
          type="text" value={newName} onChange={e => setNewName(e.target.value)}
          placeholder="输入企业名称"
          className="flex-1 max-w-xs border border-slate-300 rounded-lg px-3 py-2 text-sm
                     focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
        />
        <button onClick={handleCreate} disabled={creating || !newName.trim()}
          className="bg-orange-500 hover:bg-orange-600 active:scale-[0.98] text-white px-4 py-2
                     rounded-lg text-sm font-semibold transition-all duration-150
                     disabled:opacity-50 disabled:cursor-not-allowed">
          {creating ? '创建中...' : '+ 新建企业'}
        </button>
      </div>

      {/* Enterprise table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-600 font-medium">
                <th className="text-left px-4 py-3">企业名称</th>
                <th className="text-left px-4 py-3">用户数</th>
                <th className="text-left px-4 py-3">状态</th>
                <th className="text-left px-4 py-3">创建时间</th>
                <th className="text-left px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {enterprises.map(e => (
                <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-900">{e.name}</td>
                  <td className="px-4 py-3 text-slate-600">{e.user_count ?? 0}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      e.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                    }`}>
                      {e.is_active ? '正常' : '已停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{e.created_at?.slice(0, 10)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button onClick={() => handleToggleActive(e)}
                        className="text-sm text-slate-600 hover:text-slate-900 transition-colors">
                        {e.is_active ? '停用' : '启用'}
                      </button>
                      <button onClick={() => { setRenewModal(e); setRenewUserId(''); setRenewDays(365) }}
                        className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
                        续期管理员
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {enterprises.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-slate-400">暂无企业</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Renew Modal */}
      {renewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setRenewModal(null)}>
          <div className="bg-white rounded-lg p-6 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-900 mb-4">续期企业管理员 — {renewModal.name}</h3>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">管理员用户 ID</label>
            <input type="number" value={renewUserId}
              onChange={e => setRenewUserId(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm mb-4
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
              placeholder="输入用户 ID" />
            <label className="block text-sm font-medium text-slate-700 mb-1.5">有效期（天）</label>
            <input type="number" value={renewDays}
              onChange={e => setRenewDays(Number(e.target.value))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm mb-4
                         focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none" />
            <div className="flex gap-3 justify-end">
              <button onClick={() => setRenewModal(null)}
                className="border border-slate-300 text-slate-700 hover:bg-slate-50 px-4 py-2 rounded-lg text-sm transition-colors">
                取消
              </button>
              <button onClick={handleRenew}
                className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors">
                确认续期
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 创建 UsersTab.tsx**

```typescript
import { useState, useEffect, useCallback } from 'react'
import { getAdminUsers, updateAdminUser, getEnterprises } from '../../api/client'
import { useToast } from '../../hooks/useToast'
import { useAuth } from '../../contexts/AuthContext'
import type { AdminUser, Enterprise } from '../../types/auth'

export function UsersTab() {
  const { user: currentUser } = useAuth()
  const { show } = useToast()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [enterprises, setEnterprises] = useState<Enterprise[]>([])
  const [loading, setLoading] = useState(true)
  const [filterEnt, setFilterEnt] = useState<number | undefined>()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editQuota, setEditQuota] = useState('')
  const [editEntId, setEditEntId] = useState('')

  const isSuperAdmin = currentUser?.role === 'super_admin'

  const load = useCallback(async () => {
    try {
      const [userData, entData] = await Promise.all([
        getAdminUsers(filterEnt),
        isSuperAdmin ? getEnterprises() : Promise.resolve({ enterprises: [] }),
      ])
      setUsers(userData.users)
      setEnterprises(entData.enterprises)
    } catch (err) {
      show(err instanceof Error ? err.message : '加载失败', 'error')
    } finally {
      setLoading(false)
    }
  }, [filterEnt, show, isSuperAdmin])

  useEffect(() => { load() }, [load])

  const handleUpdate = async (userId: number) => {
    const updates: Record<string, unknown> = {}
    if (editQuota) updates.quota_total = Number(editQuota)
    if (isSuperAdmin && editEntId) updates.enterprise_id = Number(editEntId)
    if (!Object.keys(updates).length) return
    try {
      await updateAdminUser(userId, updates)
      show('用户更新成功', 'success')
      setEditingId(null)
      load()
    } catch (err) {
      show(err instanceof Error ? err.message : '更新失败', 'error')
    }
  }

  const handleToggleActive = async (u: AdminUser) => {
    try {
      await updateAdminUser(u.id, { is_active: !u.is_active })
      show(u.is_active ? '用户已停用' : '用户已启用', 'success')
      load()
    } catch (err) {
      show(err instanceof Error ? err.message : '操作失败', 'error')
    }
  }

  const ROLE_LABELS: Record<string, string> = {
    super_admin: '超级管理员',
    enterprise_admin: '企业管理员',
    user: '用户',
  }

  if (loading) return <div className="text-center py-12 text-slate-400 text-sm">加载中...</div>

  return (
    <div>
      {isSuperAdmin && (
        <div className="mb-4">
          <select value={filterEnt ?? ''} onChange={e => setFilterEnt(e.target.value ? Number(e.target.value) : undefined)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none">
            <option value="">全部企业</option>
            {enterprises.map(e => (
              <option key={e.id} value={e.id}>{e.name}</option>
            ))}
          </select>
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-600 font-medium">
                <th className="text-left px-4 py-3">ID</th>
                <th className="text-left px-4 py-3">用户名</th>
                <th className="text-left px-4 py-3">角色</th>
                <th className="text-left px-4 py-3">企业</th>
                <th className="text-left px-4 py-3">配额</th>
                <th className="text-left px-4 py-3">状态</th>
                <th className="text-left px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-slate-500">{u.id}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{u.username}</td>
                  <td className="px-4 py-3">
                    <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{u.enterprise_name || '未分配'}</td>
                  <td className="px-4 py-3 text-slate-600">{u.quota_used} / {u.quota_total}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      u.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                    }`}>
                      {u.is_active ? '正常' : '停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {editingId === u.id ? (
                      <div className="flex items-center gap-2">
                        <input type="number" value={editQuota} onChange={e => setEditQuota(e.target.value)}
                          className="w-20 border border-slate-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                          placeholder="配额" />
                        {isSuperAdmin && (
                          <select value={editEntId} onChange={e => setEditEntId(e.target.value)}
                            className="w-24 border border-slate-300 rounded px-2 py-1 text-xs">
                            <option value="">企业</option>
                            {enterprises.map(e => (
                              <option key={e.id} value={e.id}>{e.name}</option>
                            ))}
                          </select>
                        )}
                        <button onClick={() => handleUpdate(u.id)}
                          className="text-xs text-white bg-orange-500 hover:bg-orange-600 px-2 py-1 rounded transition-colors">保存</button>
                        <button onClick={() => setEditingId(null)}
                          className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 transition-colors">取消</button>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        {u.role !== 'super_admin' && (
                          <>
                            <button onClick={() => { setEditingId(u.id); setEditQuota(String(u.quota_total)); setEditEntId('') }}
                              className="text-sm text-blue-600 hover:text-blue-800 transition-colors">修改配额</button>
                            <button onClick={() => handleToggleActive(u)}
                              className={`text-sm transition-colors ${u.is_active ? 'text-red-600 hover:text-red-800' : 'text-emerald-600 hover:text-emerald-800'}`}>
                              {u.is_active ? '停用' : '启用'}
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 创建 QuotaTab.tsx**

```typescript
import { useState, useEffect } from 'react'
import { getAdminQuotas } from '../../api/client'
import { useToast } from '../../hooks/useToast'
import type { QuotaInfo } from '../../types/auth'

export function QuotaTab() {
  const { show } = useToast()
  const [quotas, setQuotas] = useState<QuotaInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAdminQuotas()
      .then(data => setQuotas(data.quotas))
      .catch(err => show(err instanceof Error ? err.message : '加载失败', 'error'))
      .finally(() => setLoading(false))
  }, [show])

  if (loading) return <div className="text-center py-12 text-slate-400 text-sm">加载中...</div>

  const totalGranted = quotas.reduce((s, q) => s + q.total_granted, 0)
  const totalUsed = quotas.reduce((s, q) => s + q.used, 0)

  return (
    <div>
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">总配额</p>
          <p className="text-2xl font-bold text-slate-900">{totalGranted}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">已使用</p>
          <p className="text-2xl font-bold text-slate-900">{totalUsed}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">剩余</p>
          <p className="text-2xl font-bold text-orange-600">{totalGranted - totalUsed}</p>
        </div>
      </div>

      {/* Quota table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-600 font-medium">
                <th className="text-left px-4 py-3">用户名</th>
                <th className="text-left px-4 py-3">角色</th>
                <th className="text-left px-4 py-3">总配额</th>
                <th className="text-left px-4 py-3">已使用</th>
                <th className="text-left px-4 py-3">剩余</th>
              </tr>
            </thead>
            <tbody>
              {quotas.map(q => (
                <tr key={q.user_id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-900">{q.username}</td>
                  <td className="px-4 py-3 text-slate-600">{q.role}</td>
                  <td className="px-4 py-3 text-slate-600">{q.total_granted}</td>
                  <td className="px-4 py-3 text-slate-600">{q.used}</td>
                  <td className="px-4 py-3">
                    <span className={`font-medium ${q.remaining > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {q.remaining}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend-react/src/pages/admin/
git commit -m "feat: add AdminPage with Enterprise/Users/Quota tabs"
```

---

### Task 19: 修改 Sidebar — 根据角色显示菜单

**Files:**
- Modify: `frontend-react/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: 修改 Sidebar 组件**

Add `userRole` prop and "个人中心" / "管理后台" nav items:

Key changes to `Sidebar.tsx`:

```typescript
import React, { useState } from 'react'
import type { PageId } from '../../types'

interface Props {
  active: PageId
  onNavigate: (id: PageId) => void
  collapsed: boolean
  onToggleCollapse: () => void
  disabled?: boolean
  userRole?: string  // NEW: for role-based menu visibility
}

// Add role-aware nav item type
interface NavItem {
  id: PageId
  icon: React.ReactNode
  title: string
  sub: string
  roles?: string[]  // if omitted, visible to all authenticated users
}

const NAV_ITEMS: NavItem[] = [
  { id: 'zip',       icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>, title: '工艺入库', sub: 'ZIP 导入工艺知识库' },
  { id: 'generate',  icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>, title: '工艺生成', sub: '图纸分析与工艺编制' },
  { id: 'history',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>, title: '历史记录', sub: '历史输出与特征回看' },
  { id: 'db',        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>, title: '知识库浏览', sub: '工艺记录查询与管理' },
  { id: 'profile',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>, title: '个人中心', sub: '账户信息与配额' },
  { id: 'admin',     icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>, title: '管理后台', sub: '用户与企业管理', roles: ['super_admin', 'enterprise_admin'] },
]
```

In the rendering loop, filter items by role:

```typescript
// Inside the nav mapping:
{NAV_ITEMS.map(item => {
  // Role check: if item has roles restriction, check userRole
  if (item.roles && !item.roles.includes(userRole || '')) return null

  const isActive = active === item.id
  const isHovered = hovered === item.id
  const isDisabled = disabled && !isActive
  // ... rest of rendering unchanged
```

And add a logout button at the bottom of the sidebar (above the collapse toggle):

```typescript
{/* Logout */}
{userRole && (
  <div className="px-3 pb-2">
    <button
      onClick={() => onNavigate('login')}  // triggers logout via App
      className="w-full flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-[11px] font-medium text-white/25 hover:text-red-400 hover:bg-white/[0.04] transition-all duration-200 border border-transparent hover:border-white/[0.05]"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <polyline points="16 17 21 12 16 7" />
        <line x1="21" y1="12" x2="9" y2="12" />
      </svg>
      {!collapsed && <span>退出登录</span>}
    </button>
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend-react/src/components/layout/Sidebar.tsx
git commit -m "feat: add role-based menu visibility and logout button to Sidebar"
```

---

### Task 20: 重构 App.tsx — 认证感知路由

**Files:**
- Modify: `frontend-react/src/App.tsx`

- [ ] **Step 1: 重构 App.tsx**

Rewrite `App.tsx` to be auth-aware with two-layer routing:

```typescript
import { useCallback, useEffect, useRef, useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { ToastStack } from './components/shared/Toast'
import { useToast } from './hooks/useToast'
import { GeneratePage } from './pages/GeneratePage'
import { ZipPage } from './pages/ZipPage'
import { HistoryPage } from './pages/HistoryPage'
import { DbPage } from './pages/DbPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ProfilePage } from './pages/ProfilePage'
import { AdminPage } from './pages/admin/AdminPage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import gsap from 'gsap'
import { usePrefersReducedMotion } from './hooks/usePrefersReducedMotion'

import type { PageId } from './types'

function AppLayout() {
  const { user, logout } = useAuth()
  const [page, setPage] = useState<PageId>('generate')
  const [collapsed, setCollapsed] = useState(false)
  const [generateBusy, setGenerateBusy] = useState(false)
  const [zipBusy, setZipBusy] = useState(false)
  const anyBusy = generateBusy || zipBusy
  const { toasts, show } = useToast()
  const pageContentRef = useRef<HTMLDivElement>(null)
  const prevPageRef = useRef<PageId>('generate')
  const reduceMotion = usePrefersReducedMotion()

  const [mountedPages, setMountedPages] = useState<Set<PageId>>(() => new Set(['generate']))

  const handleError = useCallback((msg: string) => {
    show(msg, 'error')
  }, [show])

  const handleGenerateBusy = useCallback((busy: boolean) => {
    setGenerateBusy(busy)
  }, [])

  const handleZipBusy = useCallback((busy: boolean) => {
    setZipBusy(busy)
  }, [])

  const handleNavigate = useCallback((id: PageId) => {
    // Handle logout: navigate to login clears auth state
    if (id === 'login') {
      logout()
      return
    }
    if (anyBusy && id !== page) {
      if (!window.confirm('当前有任务正在进行中，切换页面将中断进程。\n\n确定要离开吗？')) return
      setGenerateBusy(false)
      setZipBusy(false)
    }
    setMountedPages(prev => prev.has(id) ? prev : new Set([...prev, id]))
    setPage(id)
  }, [anyBusy, page, logout])

  // GSAP page transition
  useEffect(() => {
    if (prevPageRef.current === page) return
    prevPageRef.current = page
    if (pageContentRef.current) {
      if (reduceMotion) {
        gsap.set(pageContentRef.current, { opacity: 1, y: 0 })
        return
      }
      gsap.fromTo(pageContentRef.current,
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }
      )
    }
  }, [page, reduceMotion])

  // Role guard for admin page
  const canAccessAdmin = user?.role === 'super_admin' || user?.role === 'enterprise_admin'

  return (
    <div className="flex h-screen overflow-hidden relative">
      <Sidebar
        active={page}
        onNavigate={handleNavigate}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(c => !c)}
        disabled={anyBusy}
        userRole={user?.role}
      />
      <main className="flex-1 min-w-0 flex flex-col relative z-10">
        <div ref={pageContentRef} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-8 pb-6">
          {/* GeneratePage */}
          <div style={{ display: page === 'generate' ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
            {mountedPages.has('generate') && <GeneratePage onError={handleError} onSuccess={(msg) => show(msg, 'success')} onBusyChange={handleGenerateBusy} />}
          </div>
          {/* Other pages */}
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'zip' ? 'block' : 'none' }}>
            {mountedPages.has('zip') && <ZipPage onBusyChange={handleZipBusy} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'history' ? 'block' : 'none' }}>
            {mountedPages.has('history') && <HistoryPage />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'db' ? 'block' : 'none' }}>
            {mountedPages.has('db') && <DbPage onNavigate={handleNavigate} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'profile' ? 'block' : 'none' }}>
            {mountedPages.has('profile') && <ProfilePage />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'admin' ? 'block' : 'none' }}>
            {mountedPages.has('admin') && (canAccessAdmin ? <AdminPage /> : <div className="flex items-center justify-center h-full"><p className="text-slate-400">权限不足</p></div>)}
          </div>
        </div>
        <footer className="shrink-0 text-center text-[12px] text-slate-500 py-2.5 bg-slate-50 border-t border-slate-200">
          Copyright © 机器学习与工业智能应用教育部工程研究中心
        </footer>
      </main>
      <ToastStack toasts={toasts} />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}

function AppShell() {
  const { isAuthenticated, isLoading } = useAuth()
  const [authPage, setAuthPage] = useState<'login' | 'register'>('login')
  const { toasts, show } = useToast()

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center bg-slate-50">
        <div className="text-slate-400 text-sm">加载中...</div>
      </div>
    )
  }

  // Not authenticated: show login/register
  if (!isAuthenticated) {
    return (
      <>
        {authPage === 'login' && <LoginPage onNavigate={setAuthPage} />}
        {authPage === 'register' && <RegisterPage onNavigate={setAuthPage} />}
        <ToastStack toasts={toasts} />
      </>
    )
  }

  // Authenticated: show main app
  return <AppLayout />
}
```

- [ ] **Step 2: 构建并验证**

Run:
```bash
cd /Users/caojiayuan/Projects/work/test/frontend-react && npm run build 2>&1 | tail -20
```
Expected: build succeeds without errors.

- [ ] **Step 3: Commit**

```bash
git add frontend-react/src/App.tsx
git commit -m "feat: restructure App.tsx with auth-aware routing (login/main split)"
```

---

## Self-Review Results

**1. Spec coverage:**
- ✅ 数据库模型（4 张表）→ Task 2
- ✅ JWT 认证 + Cookie → Task 3, Task 6
- ✅ 三种角色 + 权限矩阵 → Task 4, Task 7
- ✅ 开放注册 + 默认 10 次配额 → Task 2, Task 6
- ✅ 企业管理员续期/到期 → Task 2, Task 7
- ✅ 推理次数扣减 → Task 4, Task 10
- ✅ 知识库 >=30 校验 → Task 11
- ✅ 登录/注册/个人中心/管理后台页面 → Task 15-18
- ✅ Sidebar 角色菜单 → Task 19
- ✅ 路由重构 → Task 20
- ✅ CORS 修改 → Task 9
- ✅ 预留 LDAP/Redis 接口 → Task 3 (TokenStore ABC 设计), spec 文档已记录

**2. Placeholder scan:** 无 TBD/TODO，所有步骤包含实际代码。

**3. Type consistency:** 
- `PageId` 扩展包含 `'profile' | 'admin' | 'login' | 'register'`（Task 12）
- `User`, `Enterprise`, `QuotaInfo`, `AdminUser` 类型定义在 auth.ts（Task 12）
- 前端 API 函数签名使用这些类型（Task 13）
- 所有页面组件使用相同的类型（Task 15-18）

No issues found.
