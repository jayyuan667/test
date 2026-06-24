# -*- coding: utf-8 -*-
"""Flask decorators for authentication and authorization."""

from functools import wraps
from flask import request, g
from .auth_service import decode_token
from . import auth_store
from .api._response import fail, ERR_UNAUTHORIZED, ERR_FORBIDDEN


def login_required(f):
    """Require a valid JWT from the gn_token cookie.

    On success sets g.current_user to the user dict.
    On failure returns a 401 error response.
    """
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

        user = auth_store.get_user_by_id(int(payload["sub"]))
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
