# -*- coding: utf-8 -*-
"""Gated rollout helpers for process-generation fixes."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

TRUE_VALUES = {"1", "true", "yes", "on"}


def env_flag_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def enterprise_in_rollout(enterprise_id: int | None) -> bool:
    if enterprise_id is None:
        return False
    raw = os.getenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "").strip()
    if raw == "*":
        return True
    allowed = {part.strip() for part in raw.split(",") if part.strip()}
    return str(enterprise_id) in allowed


def _role(user: dict | None) -> str:
    return str((user or {}).get("role") or "user")


def _enterprise_id(user: dict | None) -> int | None:
    value = (user or {}).get("enterprise_id")
    return int(value) if value is not None else None


def _is_scope_accessible(scope: dict[str, Any] | None, user: dict | None) -> bool:
    if not scope:
        return False
    if scope.get("scope_type") == "public":
        return True
    if _role(user) == "super_admin":
        return True
    return scope.get("enterprise_id") == _enterprise_id(user)


def _first_private_scope_for_enterprise(enterprise_id: int | None) -> dict[str, Any] | None:
    if enterprise_id is None:
        return None
    from ..library_scope import list_scopes

    for scope in list_scopes():
        if scope.get("scope_type") != "public" and scope.get("enterprise_id") == enterprise_id:
            return scope
    return None


def resolve_generation_library_key(
    requested_key: str | None,
    user: dict | None,
) -> tuple[str, dict[str, Any]]:
    from ..library_scope import PUBLIC_LIBRARY_KEY, resolve_scope

    role = _role(user)
    enterprise_id = _enterprise_id(user)
    requested = (requested_key or "").strip()

    if not env_flag_enabled("PROCESS_LIBRARY_RESOLUTION_V2"):
        return requested or PUBLIC_LIBRARY_KEY, {"source": "legacy_default"}

    if role != "super_admin" and not enterprise_in_rollout(enterprise_id):
        return requested or PUBLIC_LIBRARY_KEY, {"source": "legacy_default"}

    if requested:
        explicit = resolve_scope(requested)
        if _is_scope_accessible(explicit, user):
            return explicit["library_key"], {"source": "explicit", "scope": explicit}

    if role == "super_admin":
        return PUBLIC_LIBRARY_KEY, {"source": "super_admin_default"}

    private_scope = _first_private_scope_for_enterprise(enterprise_id)
    if private_scope:
        meta = {"source": "enterprise_default", "scope": private_scope}
        if requested:
            meta["rejected_requested_key"] = requested
        return private_scope["library_key"], meta

    fallback_meta = {"source": "public_fallback"}
    if requested:
        fallback_meta["rejected_requested_key"] = requested
    logger.warning(
        "[process_rollout] no private library for enterprise_id=%s; falling back to public",
        enterprise_id,
    )
    return PUBLIC_LIBRARY_KEY, fallback_meta


def _row_count(process_rows: list[Any] | None) -> int:
    return len(process_rows or [])


def evaluate_process_quality(
    process_rows: list[Any] | None,
    feature_text: str,
    constraints: dict[str, Any] | None,
    vision_degraded: bool = False,
) -> dict[str, Any]:
    if vision_degraded:
        return {"ok": True, "degraded": True, "reasons": []}

    hard = (constraints or {}).get("hard_constraints", {}) or {}
    soft = (constraints or {}).get("soft_features", {}) or {}
    text = feature_text or ""
    reasons: list[str] = []

    if _row_count(process_rows) < 2:
        reasons.append("too_few_rows")
    if "板料" in str(hard.get("material_form") or "") or "板料" in text:
        reasons.append("plate_material")
    if hard.get("surface_treatment") or "表面处理" in text or "氧化" in text or "镀" in text:
        reasons.append("surface_treatment")
    if soft.get("holes_threads") or re.search(r"孔|螺纹|螺孔|攻丝|M\d|φ\d|Φ\d", text):
        reasons.append("holes_or_threads")
    if hard.get("flip_face"):
        reasons.append("flip_face")
    if re.search(r"刻字|标识", text):
        reasons.append("marking")

    nontrivial = any(reason != "too_few_rows" for reason in reasons)
    ok = not ("too_few_rows" in reasons and nontrivial)
    return {"ok": ok, "degraded": False, "reasons": sorted(set(reasons))}


def detect_missing_pages_warning(feature_text: str, processed_pages: int) -> dict[str, Any] | None:
    text = feature_text or ""
    expected = None
    patterns = [
        r"共\s*(\d+)\s*张",
        r"【页数】\s*(\d+)",
        r"第\s*(\d+)\s*张",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = int(match.group(1))
            expected = max(expected or 0, value)

    processed = int(processed_pages or 0)
    if expected is None or processed >= expected:
        return None

    return {
        "expected_pages": expected,
        "processed_pages": processed,
        "message": f"检测到图纸文本提及第{expected}张/G面，但当前仅处理{processed}页，请人工确认是否缺页。",
    }
