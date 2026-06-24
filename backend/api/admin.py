# -*- coding: utf-8 -*-
"""Admin endpoints for enterprise and user management."""

from datetime import datetime, timedelta
from flask import Blueprint, request, g
from .. import auth_store
from ..auth_utils import login_required, require_role
from ._response import ok, fail, ERR_VALIDATION, ERR_FORBIDDEN

admin_bp = Blueprint("admin", __name__)


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


# ----------------------------------------------------------------
#  Enterprises
# ----------------------------------------------------------------


@admin_bp.route("/admin/enterprises", methods=["GET"])
@login_required
def list_enterprises():
    """List enterprises. Super admin sees all; enterprise admin sees only own."""
    user = g.current_user
    if user["role"] == "super_admin":
        enterprises = auth_store.list_enterprises()
    elif user["role"] == "enterprise_admin":
        eid = user.get("enterprise_id")
        ent = auth_store.get_enterprise(eid) if eid else None
        enterprises = [ent] if ent else []
    else:
        return fail(ERR_FORBIDDEN, "权限不足", status=403)

    result = []
    for ent in enterprises:
        users = auth_store.list_enterprise_users(ent["id"])
        result.append({
            "id": ent["id"],
            "name": ent["name"],
            "is_active": bool(ent.get("is_active", 1)),
            "created_at": ent.get("created_at", ""),
            "user_count": len(users),
        })
    return ok({"enterprises": result})


@admin_bp.route("/admin/enterprises", methods=["POST"])
@login_required
@require_role("super_admin")
def create_enterprise():
    """Create a new enterprise."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return fail(ERR_VALIDATION, "企业名称不能为空")

    enterprise = auth_store.create_enterprise(name)
    return ok({"enterprise": enterprise}, status=201)


@admin_bp.route("/admin/enterprises/<int:enterprise_id>", methods=["PUT"])
@login_required
@require_role("super_admin")
def update_enterprise(enterprise_id):
    """Update enterprise name and/or is_active."""
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return fail(ERR_VALIDATION, "企业名称不能为空")
        kwargs["name"] = name
    if "is_active" in data:
        kwargs["is_active"] = bool(data["is_active"])

    if not kwargs:
        return fail(ERR_VALIDATION, "没有需要更新的字段")

    enterprise = auth_store.update_enterprise(enterprise_id, **kwargs)
    if enterprise is None:
        return fail(ERR_VALIDATION, "企业不存在")
    return ok({"enterprise": enterprise})


# ----------------------------------------------------------------
#  Users
# ----------------------------------------------------------------


@admin_bp.route("/admin/users", methods=["GET"])
@login_required
@require_role("super_admin", "enterprise_admin")
def list_users():
    """List users.

    Super admin: all users, optionally filtered by ?enterprise_id=.
    Enterprise admin: only own enterprise users.
    """
    user = g.current_user
    if user["role"] == "super_admin":
        enterprise_id = request.args.get("enterprise_id", type=int)
        if enterprise_id:
            users = auth_store.list_enterprise_users(enterprise_id)
        else:
            users = auth_store.list_all_users()
    else:
        eid = user.get("enterprise_id")
        if not eid:
            users = []
        else:
            users = auth_store.list_enterprise_users(eid)

    return ok({"users": [_user_to_dict(u) for u in users]})


@admin_bp.route("/admin/users/<int:user_id>", methods=["PUT"])
@login_required
@require_role("super_admin", "enterprise_admin")
def update_user(user_id):
    """Update a user's properties.

    Enterprise admin can only manage users in their own enterprise.
    Super admin users cannot be modified by anyone.
    """
    data = request.get_json(silent=True) or {}
    current_user = g.current_user

    target = auth_store.get_user_by_id(user_id)
    if not target:
        return fail(ERR_VALIDATION, "用户不存在")

    # Cannot modify super_admin users
    if target["role"] == "super_admin":
        return fail(ERR_FORBIDDEN, "不能修改超级管理员账号", status=403)

    # Enterprise admin can only manage own enterprise
    if current_user["role"] == "enterprise_admin":
        if target.get("enterprise_id") != current_user.get("enterprise_id"):
            return fail(ERR_FORBIDDEN, "只能管理本企业用户", status=403)
        # Enterprise admin cannot change role or enterprise_id
        if "role" in data or "enterprise_id" in data:
            return fail(ERR_FORBIDDEN, "无权修改角色或所属企业", status=403)

    kwargs = {}
    if "is_active" in data:
        kwargs["is_active"] = bool(data["is_active"])
    if "role" in data and current_user["role"] == "super_admin":
        kwargs["role"] = data["role"]
    if "enterprise_id" in data and current_user["role"] == "super_admin":
        eid = data.get("enterprise_id")
        if eid is not None:
            enterprise = auth_store.get_enterprise(eid)
            if not enterprise:
                return fail(ERR_VALIDATION, "企业不存在")
        kwargs["enterprise_id"] = eid
    if "quota_total" in data:
        try:
            total = int(data["quota_total"])
        except ValueError:
            return fail(ERR_VALIDATION, "配额必须为整数")
        if total < 0:
            return fail(ERR_VALIDATION, "配额不能为负数")
        auth_store.set_quota(user_id, total)

    if kwargs:
        auth_store.update_user(user_id, **kwargs)

    updated = auth_store.get_user_by_id(user_id)
    return ok({"user": _user_to_dict(updated)})


# ----------------------------------------------------------------
#  Grants
# ----------------------------------------------------------------


@admin_bp.route("/admin/grants", methods=["POST"])
@login_required
@require_role("super_admin")
def create_grant():
    """Grant enterprise admin privileges to a user.

    Sets the user's role to enterprise_admin and associates an enterprise.
    Creates a grant record with an expiration date.
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    enterprise_id = data.get("enterprise_id")
    try:
        duration_days = int(data.get("duration_days", 365))
    except ValueError:
        return fail(ERR_VALIDATION, "授权天数必须为整数")

    if not user_id or not enterprise_id:
        return fail(ERR_VALIDATION, "user_id 和 enterprise_id 不能为空")

    user = auth_store.get_user_by_id(user_id)
    if not user:
        return fail(ERR_VALIDATION, "用户不存在")

    if user["role"] == "super_admin":
        return fail(ERR_VALIDATION, "不能为超级管理员授权")

    enterprise = auth_store.get_enterprise(enterprise_id)
    if not enterprise:
        return fail(ERR_VALIDATION, "企业不存在")

    if duration_days < 1:
        return fail(ERR_VALIDATION, "授权天数至少为 1")

    # Update user role and enterprise
    auth_store.update_user(user_id, role="enterprise_admin", enterprise_id=enterprise_id)

    # Create grant record
    expires_at = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()
    grant = auth_store.create_enterprise_admin_grant(user_id, enterprise_id, g.current_user["id"], expires_at)

    updated_user = auth_store.get_user_by_id(user_id)
    return ok({"user": _user_to_dict(updated_user), "grant": grant}, status=201)


# ----------------------------------------------------------------
#  Quotas
# ----------------------------------------------------------------


@admin_bp.route("/admin/quotas", methods=["GET"])
@login_required
@require_role("super_admin", "enterprise_admin")
def list_quotas():
    """List quota information for non-super-admin users."""
    current_user = g.current_user
    if current_user["role"] == "super_admin":
        users = auth_store.list_all_users()
    else:
        eid = current_user.get("enterprise_id")
        if not eid:
            users = []
        else:
            users = auth_store.list_enterprise_users(eid)

    # Skip super_admin users in the quota list
    result = []
    for u in users:
        if u["role"] == "super_admin":
            continue
        quota = auth_store.get_user_quota(u["id"])
        enterprise = None
        if u.get("enterprise_id"):
            enterprise = auth_store.get_enterprise(u["enterprise_id"])
        result.append({
            "user_id": u["id"],
            "username": u["username"],
            "role": u["role"],
            "enterprise_id": u.get("enterprise_id"),
            "enterprise_name": enterprise["name"] if enterprise else None,
            "quota_total": quota["total_granted"] if quota else 10,
            "quota_used": quota["used"] if quota else 0,
            "quota_remaining": (quota["total_granted"] - quota["used"]) if quota else 10,
        })
    return ok({"quotas": result})
