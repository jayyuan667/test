# -*- coding: utf-8 -*-
"""Authentication and user management endpoints."""

from flask import Blueprint, request, jsonify, g

from ..auth_service import register_user, verify_password, create_token
from .. import auth_store
from .. import config
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

    resp = jsonify({
        "success": True,
        "data": {
            "user": _user_to_dict(user, include_quota=True),
            "access_token": token,
        }
    })
    # Cookie 也设上（同域时自动带）
    resp.set_cookie(
        config.AUTH_COOKIE_NAME, token,
        httponly=False, samesite="Lax", max_age=86400,
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
    resp.delete_cookie(config.AUTH_COOKIE_NAME)
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
