# -*- coding: utf-8 -*-
"""Flask decorators for authentication and authorization."""

from functools import wraps
from flask import request, g, jsonify, make_response
from .auth_service import decode_token
from . import auth_store
from . import config
from .api._response import fail, ERR_UNAUTHORIZED, ERR_FORBIDDEN


def _unauth(message: str, reason: str = "session_expired"):
    """Return a 401 response with cleared auth cookie."""
    body = {"success": False, "error": {"code": ERR_UNAUTHORIZED, "message": message, "reason": reason}}
    resp = make_response(jsonify(body), 401)
    resp.delete_cookie(config.AUTH_COOKIE_NAME)
    return resp


def login_required(f):
    """Require a valid JWT from the configured auth cookie.

    On success sets g.current_user to the user dict.
    On failure returns a 401 error response.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get(config.AUTH_COOKIE_NAME, "")
        if not token:
            # Fallback: check Authorization Bearer header (for cross-origin frontend)
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            # Fallback: check ?token= query param (for EventSource SSE which can't set headers)
            token = request.args.get("token", "")
        if not token:
            body = {"success": False, "error": {"code": ERR_UNAUTHORIZED, "message": "请先登录", "reason": "cookie_missing"}}
            return make_response(jsonify(body), 401)

        payload = decode_token(token)
        if not payload:
            return _unauth("登录已过期，请重新登录")

        user = auth_store.get_user_by_id(int(payload["sub"]))
        if not user:
            return _unauth("用户不存在")

        if not user["is_active"]:
            return _unauth("账号已被停用")

        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_role(*roles: str):
    """Factory: require the current user to have one of the given roles.

    Must be used after @login_required (so g.current_user is set).
    """
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
    """Check and consume one inference quota.

    Must be used after @login_required (so g.current_user is set).
    Super admins are exempt from quota consumption.
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
