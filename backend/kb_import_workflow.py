# -*- coding: utf-8 -*-
"""Workflow-specific guards for ZIP knowledge-base imports.

Each function operates on the vector database (same DB_PATH as the rest
of the pipeline) so it can verify written records against the claims in
the import report.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from typing import Any

from .library_scope import (
    PUBLIC_LIBRARY_KEY,
    ensure_scope,
    is_public_scope_type,
    mark_scope_batch,
    resolve_scope,
    sanitize_identifier,
)
from .vector_map_rag import DB_PATH, invalidate_index_cache
from .workflow_harness import (
    get_workflow_run,
    restore_rollback_snapshots,
    delete_rollback_snapshots,
)


# ── Cache key ──────────────────────────────────────────────────────────────


def build_zip_cache_key(
    *,
    zip_hash: str,
    enterprise_id: int | None,
    library_key: str,
    conflict_mode: str,
) -> str:
    """Deterministic cache key from ZIP content + target context."""
    payload = {
        "zip_hash": zip_hash or "",
        "enterprise_id": enterprise_id,
        "library_key": library_key or "",
        "conflict_mode": conflict_mode or "",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ── Permission ─────────────────────────────────────────────────────────────


def resolve_zip_import_permission(
    *,
    library_mode: str,
    library_name: str,
    library_key: str,
    enterprise_id: int | None,
    is_super_admin: bool,
    batch_id: str,
) -> tuple[dict[str, Any] | None, tuple[dict[str, str], int] | None]:
    """Resolve the target scope for a ZIP import, enforcing permission rules.

    Returns (scope, None) on success or (None, (error_body, status_code)).
    """
    normalized_mode = (
        library_mode
        if library_mode in {"private_seed_public", "private_empty", "public"}
        else "private_seed_public"
    )

    # ── Public library ────────────────────────────────────────────────────
    if normalized_mode == "public":
        if not is_super_admin:
            return None, (
                {"error": "当前账号无权写入公共工艺库"},
                403,
            )
        scope = resolve_scope(PUBLIC_LIBRARY_KEY)
        return scope, None

    # ── Private library ───────────────────────────────────────────────────
    if enterprise_id is None and not is_super_admin:
        return None, (
            {"error": "未分配企业，不能写入私有工艺库"},
            403,
        )

    # P0-3: super_admin writing to a private library MUST have an explicit
    # target enterprise.  Without it the scope would be created with
    # enterprise_id=NULL, which is an orphan in our data-isolation model.
    if is_super_admin and enterprise_id is None:
        if library_key and (existing_scope := resolve_scope(library_key)):
            if not is_public_scope_type(existing_scope.get("scope_type")):
                if existing_scope.get("enterprise_id") is None:
                    return None, (
                        {"error": "目标私有工艺库归属未知，不能写入"},
                        403,
                    )
                mark_scope_batch(existing_scope["library_key"], batch_id)
                return existing_scope, None
        # Creating a NEW private scope without an enterprise is forbidden.
        if not library_key or not resolve_scope(library_key):
            return None, (
                {
                    "error": (
                        "超级管理员创建私有工艺库时必须指定目标企业。"
                        "请先切换到目标企业或选择已有的私有工艺库。"
                    ),
                },
                403,
            )

    # ── Existing scope (reuse) ────────────────────────────────────────────
    if library_key and (existing_scope := resolve_scope(library_key)):
        if is_public_scope_type(existing_scope.get("scope_type")):
            if not is_super_admin:
                return None, (
                    {"error": "当前账号无权写入公共工艺库"},
                    403,
                )
            return existing_scope, None

        scope_ent = existing_scope.get("enterprise_id")
        if not is_super_admin and scope_ent != enterprise_id:
            return None, (
                {"error": "目标工艺库不存在或无权访问"},
                404,
            )
        if scope_ent is None:
            return None, (
                {"error": "目标工艺库归属未知，不能写入"},
                403,
            )
        mark_scope_batch(existing_scope["library_key"], batch_id)
        return existing_scope, None

    # ── New private scope ─────────────────────────────────────────────────
    proposed_key = sanitize_identifier(
        library_key or library_name or f"user_{batch_id}"
    )
    proposed_name = (library_name or proposed_key).strip() or proposed_key
    scope = ensure_scope(
        proposed_key,
        proposed_name,
        scope_type="private",
        seed_public=normalized_mode == "private_seed_public",
        last_batch_id=batch_id,
        enterprise_id=enterprise_id,
    )
    return scope, None


# ── Database helpers ──────────────────────────────────────────────────────


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _has_column(cursor: sqlite3.Cursor, table_name: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return column in {row[1] for row in cursor.fetchall()}


# ── Cache-result validation (P0-2) ────────────────────────────────────────


def validate_cached_result(
    *,
    cached_report: dict[str, Any],
    cached_workflow_run_id: str,
    zip_hash: str,
    enterprise_id: int | None,
    is_super_admin: bool,
    library_key: str,
    conflict_mode: str,
) -> dict[str, Any]:
    """Validate that a cached ZIP import result is still trustworthy.

    A cache hit does NOT automatically pass — we must confirm:
      1. The historical workflow run exists and is 'completed'.
      2. Enterprise isolation is intact.
      3. The target scope is still reachable and has the right type.
      4. The cache key ingredients match (library_key, conflict_mode, zip_hash).
    """
    result: dict[str, Any] = {
        "status": "failed",
        "cached": True,
        "checks": {},
    }

    # 1. Historical workflow run
    hist = get_workflow_run(cached_workflow_run_id)
    if not hist:
        result["error_code"] = "cache_workflow_missing"
        result["checks"]["workflow_exists"] = False
        return result
    result["checks"]["workflow_exists"] = True

    if hist.get("status") != "completed":
        result["error_code"] = "cache_workflow_not_completed"
        result["checks"]["workflow_completed"] = False
        return result
    result["checks"]["workflow_completed"] = True

    # 2. Enterprise match
    hist_ent = hist.get("enterprise_id")
    if hist_ent != enterprise_id:
        result["error_code"] = "cache_enterprise_mismatch"
        result["checks"]["enterprise_match"] = False
        return result
    result["checks"]["enterprise_match"] = True

    # 3. Target scope still reachable
    scope = resolve_scope(library_key)
    if not scope:
        result["error_code"] = "cache_scope_gone"
        result["checks"]["scope_exists"] = False
        return result
    result["checks"]["scope_exists"] = True

    # 4. Scope type hasn't changed in a way that leaks data
    scope_type = scope.get("scope_type") or ""
    if is_public_scope_type(scope_type):
        # Public scope is fine — super_admin already passed permission for it
        pass
    else:
        # Private scope must still belong to the same enterprise
        scope_ent = scope.get("enterprise_id")
        if scope_ent is not None and scope_ent != enterprise_id:
            result["error_code"] = "cache_scope_enterprise_changed"
            result["checks"]["scope_enterprise_match"] = False
            return result
        # P0-3 guard: orphan private scope (enterprise_id=NULL) is not OK
        if scope_ent is None and not is_super_admin:
            result["error_code"] = "cache_scope_orphan"
            result["checks"]["scope_not_orphan"] = False
            return result
    result["checks"]["scope_valid"] = True

    # 5. Cache-key ingredients match
    hist_cache_key = hist.get("cache_key") or ""
    expected_cache_key = build_zip_cache_key(
        zip_hash=zip_hash,
        enterprise_id=enterprise_id,
        library_key=library_key,
        conflict_mode=conflict_mode,
    )
    if hist_cache_key != expected_cache_key:
        result["error_code"] = "cache_key_mismatch"
        result["checks"]["cache_key_match"] = False
        return result
    result["checks"]["cache_key_match"] = True

    # All checks passed
    result["status"] = "passed"
    return result


# ── Post-import validation ────────────────────────────────────────────────


def validate_zip_import_result(
    report: dict[str, Any],
    enterprise_id: int | None,
    is_super_admin: bool,
) -> dict[str, Any]:
    """Verify that the database contains exactly what the report claims.

    Checks:
      - inserted rows == report.imported_count
      - visible rows (with correct enterprise_id) == inserted rows
      - no orphan rows (enterprise_id=NULL on private scope)
    """
    scope = report.get("target_library") or {}
    vector_table = scope.get("vector_table") or ""
    scope_type = scope.get("scope_type") or ""
    workflow_run_id = report.get("workflow_run_id") or ""
    imported_count = int((report.get("summary") or {}).get("imported_count") or 0)

    if not vector_table:
        return {
            "status": "failed",
            "error_code": "missing_target_scope",
            "visible_count": 0,
            "inserted_count": 0,
        }

    conn = _connect()
    try:
        cursor = conn.cursor()
        if not _has_column(cursor, vector_table, "workflow_run_id"):
            return {
                "status": "failed",
                "error_code": "missing_workflow_column",
                "visible_count": 0,
                "inserted_count": 0,
            }

        # Count all real rows for this workflow run
        cursor.execute(
            f"SELECT COUNT(*) FROM {vector_table} "
            f"WHERE workflow_run_id = ? AND COALESCE(real, 1) = 1",
            (workflow_run_id,),
        )
        inserted_count = int(cursor.fetchone()[0] or 0)

        # Count visible rows (enterprise-scoped)
        if is_public_scope_type(scope_type):
            visible_where = (
                "workflow_run_id = ? AND COALESCE(real, 1) = 1"
            )
            params: tuple[Any, ...] = (workflow_run_id,)
        elif enterprise_id is not None:
            visible_where = (
                "workflow_run_id = ? AND enterprise_id = ? "
                "AND COALESCE(real, 1) = 1"
            )
            params = (workflow_run_id, enterprise_id)
        else:
            # enterprise_id is None but scope is private — no rows should be
            # visible to a user without enterprise assignment
            visible_where = "1 = 0"
            params = ()

        cursor.execute(
            f"SELECT COUNT(*) FROM {vector_table} WHERE {visible_where}",
            params,
        )
        visible_count = int(cursor.fetchone()[0] or 0)

        # Detect orphans on private scopes
        if not is_public_scope_type(scope_type):
            cursor.execute(
                f"SELECT COUNT(*) FROM {vector_table} "
                f"WHERE workflow_run_id = ? "
                f"AND enterprise_id IS NULL AND COALESCE(real, 1) = 1",
                (workflow_run_id,),
            )
            orphan_count = int(cursor.fetchone()[0] or 0)
        else:
            orphan_count = 0
    finally:
        conn.close()

    if inserted_count != imported_count:
        return {
            "status": "failed",
            "error_code": "count_mismatch",
            "visible_count": visible_count,
            "inserted_count": inserted_count,
            "expected_count": imported_count,
            "orphan_count": orphan_count,
        }
    if visible_count != inserted_count or orphan_count:
        return {
            "status": "failed",
            "error_code": "visibility_mismatch",
            "visible_count": visible_count,
            "inserted_count": inserted_count,
            "expected_count": imported_count,
            "orphan_count": orphan_count,
        }
    return {
        "status": "passed",
        "visible_count": visible_count,
        "inserted_count": inserted_count,
        "expected_count": imported_count,
        "orphan_count": orphan_count,
    }


# ── Rollback ──────────────────────────────────────────────────────────────


def rollback_zip_import(
    report: dict[str, Any],
    workflow_run_id: str = "",
) -> dict[str, Any]:
    """Delete records created by a failed ZIP import run, and restore any
    records that were replaced during the import (P0-1 compensation).

    Returns a dict with rollback status.  Callers MUST check the status —
    if rollback itself fails the workflow MUST be marked rollback_failed.
    """
    scope = report.get("target_library") or {}
    vector_table = scope.get("vector_table") or ""
    enterprise_id = report.get("enterprise_id")
    batch_id = report.get("batch_id") or ""

    if not vector_table:
        return {"attempted": False, "status": "skipped", "deleted_records": 0}

    conn = _connect()
    deleted = 0
    restored = 0
    try:
        cursor = conn.cursor()
        has_wf_col = _has_column(cursor, vector_table, "workflow_run_id")

        # ── P0-1: Restore replaced records FIRST ─────────────────────────
        # Restoring old records before deleting current ones ensures that
        # prefix-unique rows are returned to their original state without
        # a window where neither old nor new record exists.
        if workflow_run_id:
            restored = restore_rollback_snapshots(workflow_run_id)

        # ── Delete current workflow's rows ──────────────────────────────
        if workflow_run_id and has_wf_col:
            cursor.execute(
                f"SELECT COUNT(*) FROM {vector_table} "
                f"WHERE workflow_run_id = ?",
                (workflow_run_id,),
            )
            deleted = int(cursor.fetchone()[0] or 0)
            cursor.execute(
                f"DELETE FROM {vector_table} WHERE workflow_run_id = ?",
                (workflow_run_id,),
            )
        else:
            # Fallback for old tables without workflow_run_id column
            preview_prefix = f"kb_{batch_id}_%"
            cursor.execute(
                f"SELECT COUNT(*) FROM {vector_table} "
                f"WHERE enterprise_id IS ? AND preview_task_id LIKE ?",
                (enterprise_id, preview_prefix),
            )
            deleted = int(cursor.fetchone()[0] or 0)
            cursor.execute(
                f"DELETE FROM {vector_table} "
                f"WHERE enterprise_id IS ? AND preview_task_id LIKE ?",
                (enterprise_id, preview_prefix),
            )

        # Clean up tracking tables
        cursor.execute(
            "DELETE FROM kb_import_batches WHERE batch_id = ?", (batch_id,)
        )
        cursor.execute(
            "DELETE FROM kb_import_items WHERE batch_id = ?", (batch_id,)
        )

        # Clean up rollback snapshots
        if workflow_run_id:
            try:
                delete_rollback_snapshots(workflow_run_id)
            except Exception:
                pass

        conn.commit()
    finally:
        conn.close()

    invalidate_index_cache(scope.get("library_key") or None)

    return {
        "attempted": True,
        "status": "completed",
        "deleted_records": deleted,
        "restored_snapshots": restored,
    }


def rollback_zip_import_safe(
    report: dict[str, Any],
    workflow_run_id: str = "",
) -> dict[str, Any]:
    """Wrapper that NEVER raises — always returns a status dict.

    If the inner rollback throws, the result includes status='rollback_failed'
    so the caller can surface "部分数据可能需要管理员处理" (P1-5).
    """
    try:
        return rollback_zip_import(report, workflow_run_id=workflow_run_id)
    except Exception as exc:
        return {
            "attempted": True,
            "status": "rollback_failed",
            "deleted_records": 0,
            "restored_snapshots": 0,
            "error": str(exc),
        }
