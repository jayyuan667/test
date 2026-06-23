# -*- coding: utf-8 -*-
"""Library ingest endpoints for building/querying the工艺库."""

import json
import os
import re
import sqlite3
import uuid
import logging

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from ..config import OUTPUT_FOLDER, validate_vision_config
from ..feature_report import build_feature_report, write_feature_report_json
from ..pipeline.vision_analyzer import VisionAnalyzer
from ..pipeline.local_vision_analyzer import LocalVisionAnalyzer
from ..pipeline.vlm_feature import build_vlm_feature_text
from ..prt_pipeline import prepare_prt_artifacts
from ..vector_map_rag import (
    DB_PATH,
    create_query_vector,
    extract_all_features,
    extract_key_features_text,
    extract_structured_features,
    invalidate_index_cache,
    query_by_fused_text,
    query_by_vector_similarity,
)
from ..library_scope import (
    PUBLIC_LIBRARY_KEY,
    browse_unlock_status,
    initialize_library_storage,
    list_scopes,
    resolve_scope,
)
from ._utils import PRT_FILE_RE


library_bp = Blueprint("library", __name__)
logger = logging.getLogger(__name__)

tasks = {}


def _json_safe(value):
    """Convert numpy/pandas scalars and nested structures to JSON-safe Python types."""
    try:
        import numpy as np
    except Exception:
        np = None

    if np is not None and isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


def _load_feature_report_json(feature_report_path: str = ""):
    path = str(feature_report_path or "").strip()
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_feature_report_payload(feature_report_path: str = "", fallback_text: str = ""):
    payload = _load_feature_report_json(feature_report_path)
    if payload:
        return payload
    text = str(fallback_text or "").strip()
    if text:
        return {"report_text": text, "pages": []}
    return {}


def _persist_feature_report_json(feature_report_json: dict, feature_report_path: str = "", prefix: str = "", record_id: int | None = None):
    report = _json_safe(feature_report_json if isinstance(feature_report_json, dict) else {})
    if not report:
        return "", {}

    pages = report.get("pages")
    if isinstance(pages, list) and pages:
        report = _json_safe(build_feature_report(pages, prefix_hint=report.get("prefix_hint") or prefix, total_pages=report.get("page_count") or len(pages)))

    report_text = str(report.get("report_text") or "").strip()
    if not report_text and isinstance(report.get("pages"), list) and report.get("pages"):
        report["report_text"] = str(build_feature_report(report.get("pages") or [], prefix_hint=report.get("prefix_hint") or prefix, total_pages=report.get("page_count") or len(report.get("pages") or [])).get("report_text", "")).strip()

    target_path = str(feature_report_path or report.get("feature_report_json_path") or "").strip()
    if target_path and os.path.isdir(target_path):
        target_path = os.path.join(target_path, "feature_report.json")

    if not target_path:
        safe_prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", str(prefix or "").strip().upper()) or f"record_{record_id or uuid.uuid4().hex[:8]}"
        output_dir = os.path.join(OUTPUT_FOLDER, "library_reports", safe_prefix)
        target_path = write_feature_report_json(output_dir, report)
        return target_path, report

    target_dir = os.path.dirname(target_path)
    if not target_dir:
        safe_prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", str(prefix or "").strip().upper()) or f"record_{record_id or uuid.uuid4().hex[:8]}"
        target_dir = os.path.join(OUTPUT_FOLDER, "library_reports", safe_prefix)
        target_path = os.path.join(target_dir, os.path.basename(target_path) or "feature_report.json")
    os.makedirs(target_dir, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return target_path, report


def _ensure_context_column():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vectors_v2'")
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(vectors_v2)")
        columns = {row[1] for row in cursor.fetchall()}
        if "context" not in columns:
            cursor.execute("ALTER TABLE vectors_v2 ADD COLUMN context TEXT")
            conn.commit()
    finally:
        conn.close()


_VECTOR_TABLE_COLUMNS = (
    # provenance columns (original)
    ("source_type", "TEXT DEFAULT ''"),
    ("source_task_id", "TEXT DEFAULT ''"),
    ("preview_task_id", "TEXT DEFAULT ''"),
    ("preview_total_pages", "INTEGER DEFAULT 0"),
    ("preview_image_urls", "TEXT DEFAULT ''"),
    ("feature_report_text", "TEXT DEFAULT ''"),
    ("feature_report_path", "TEXT DEFAULT ''"),
    # structured filter columns (merged from drawing_features)
    ("blank_type", "TEXT"),
    ("overall_length_min", "REAL"),
    ("overall_length_max", "REAL"),
    ("main_diameter_min", "REAL"),
    ("main_diameter_max", "REAL"),
    ("tolerance_levels", "TEXT DEFAULT '[]'"),
    ("thread_specs", "TEXT DEFAULT '[]'"),
    ("hole_specs", "TEXT DEFAULT '[]'"),
    ("roughness", "TEXT DEFAULT '[]'"),
    ("heat_treatment", "TEXT"),
    ("inspection_standards", "TEXT"),
    ("special_requirements", "TEXT DEFAULT ''"),
    ("vector_content", "TEXT DEFAULT ''"),
)


def _migrate_vector_table(cursor, table_name: str):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        return
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    for column, sql_type in _VECTOR_TABLE_COLUMNS:
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} {sql_type}")


def _ensure_provenance_columns():
    # Migrate all registered library vector tables + the public vectors_v2
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    scopes = list_scopes()
    tables = {"vectors_v2"} | {s["vector_table"] for s in scopes if s.get("vector_table")}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        for table in tables:
            _migrate_vector_table(cursor, table)
        conn.commit()
    finally:
        conn.close()


def _ensure_scope_columns(scope: dict):
    if not scope:
        return
    vector_table = scope.get("vector_table")
    if not vector_table:
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        _migrate_vector_table(cursor, vector_table)
        conn.commit()
    finally:
        conn.close()


_ensure_context_column()
initialize_library_storage()
_ensure_provenance_columns()


def _scope_from_key(library_key: str = ""):
    scope = resolve_scope(library_key or PUBLIC_LIBRARY_KEY)
    scope = scope or resolve_scope(PUBLIC_LIBRARY_KEY)
    _ensure_scope_columns(scope)
    return scope


def _library_ready_status(library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{vector_table}'")
        if not cursor.fetchone():
            unlock = browse_unlock_status()
            return {"ready": False, "record_count": 0, "can_browse": unlock["can_browse"], "scopes": list_scopes(), "active_scope": scope}

        cursor.execute(f"SELECT COUNT(*) FROM {vector_table} WHERE COALESCE(real, 1) = 1")
        record_count = int(cursor.fetchone()[0] or 0)
        unlock = browse_unlock_status()
        return {
            "ready": record_count > 0,
            "record_count": record_count,
            "can_browse": unlock["can_browse"],
            "imported_batches": unlock["imported_batches"],
            "scopes": list_scopes(),
            "active_scope": scope,
        }
    finally:
        conn.close()


def _vision_analyzer():
    vision_mode = os.getenv("VISION_MODE", "doubao").lower()
    if vision_mode == "local" or not all(os.getenv(name) for name in ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")):
        return LocalVisionAnalyzer()
    return VisionAnalyzer()


def _rows_from_text(text: str):
    rows = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if line:
            rows.append(line)
    return rows or ([text.strip()] if text and text.strip() else [])


def _trace_step(trace: list, message: str):
    if message:
        trace.append(message)
        logger.info("[Library] %s", message)


def _build_draft(prefix: str, source_name: str, source_type: str, source_text: str, content_rows):
    structured = extract_structured_features(source_text)
    key_features_map = structured.get("key_features", {}) or {}
    extracted = extract_all_features(source_text)

    tech_requirement = extracted.get("tech_requirement") or key_features_map.get("技术要求") or ""
    product_type = key_features_map.get("类型") or ""
    materials = extracted.get("materials", []) or []

    vector_text = extract_key_features_text(source_text) or source_text
    context = source_text.strip()
    content = json.dumps(content_rows, ensure_ascii=False)

    process_summary = "；".join(content_rows[:4])

    return {
        "prefix": prefix,
        "source_name": source_name,
        "source_type": source_type,
        "source_text": source_text,
        "context": context,
        "vector_text": vector_text,
        "process_list": content_rows,
        "content": content,
        "product_type": product_type,
        "process_summary": process_summary,
        "key_features": key_features_map,
        "key_features_text": vector_text,
        "materials": materials,
        "tech_requirement": tech_requirement,
        "real": 1,
        "structured": structured,
    }


def set_shared_state(tasks_dict, event_data_dict=None, event_locks_dict=None):
    """Inject shared state from app.py."""
    global tasks
    tasks = tasks_dict


def _extract_prefix(text: str, fallback: str = "") -> str:
    patterns = [
        r"【图号】\s*([1-9][A-Z]\d{4,6})",
        r"(?:^|[^\w])([1-9][A-Z]\d{4,6})(?:[A-Z]|$|[^\w])",
    ]
    for pattern in patterns:
        match = re.findall(pattern, text or "", re.IGNORECASE)
        if match:
            return match[0].upper()
    fallback_value = (fallback or "").strip()
    if fallback_value:
        basename = os.path.basename(fallback_value)
        stem, ext = os.path.splitext(basename)
        if ext.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".stp", ".step"} and stem:
            return stem.upper()
    return fallback_value.upper()


def _extract_trades_from_rows(process_list):
    """Extract unique trade labels from process rows (three-segment format: NNNN@工种@内容)."""
    trades = []
    seen = set()
    for row in (process_list or []):
        text = str(row or "").strip()
        parts = [p.strip() for p in text.split("@") if p.strip()]
        if len(parts) >= 3 and re.match(r'^[一-鿿\-\d]{1,8}$', parts[1]) and not parts[1].startswith(('工种', '设备', '工时')):
            trade = parts[1]
            if trade and trade not in seen:
                seen.add(trade)
                trades.append(trade)
    return trades


def _parse_process_text(raw_text: str):
    """Parse process text into canonical `0010@...` rows."""
    rows = []
    for raw_line in (raw_text or "").splitlines():
        line = raw_line.strip().lstrip("-*•")
        if not line:
            continue
        match = re.match(r"^(\d{4})\s*[:：@]\s*(.+)$", line)
        if match:
            tag = match.group(1)
            content = match.group(2).strip()
            rows.append(f"{tag}@{content}")
        elif line:
            rows.append(line)
    return rows


def _load_result_payload(task_id: str):
    task = tasks.get(task_id, {})
    if task.get("result"):
        return task["result"], task

    result_file = os.path.join(OUTPUT_FOLDER, task_id, "result.json")
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            return json.load(f), task

    return None, task


def _fetch_existing_record(prefix: str, library_key: str = ""):
    if not prefix:
        return None

    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT id, prefix, vector, content, context, product_type, process_summary,
               key_features, materials, created_at, tech_requirement, real,
               source_type, source_task_id, preview_task_id, preview_total_pages, preview_image_urls,
               feature_report_text, feature_report_path
        FROM {vector_table}
        WHERE UPPER(prefix) = ?
        """,
        (prefix.upper(),),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    (
        row_id,
        row_prefix,
        _vector,
        content,
        context,
        product_type,
        process_summary,
        key_features,
        materials,
        created_at,
        tech_requirement,
        real_flag,
        source_type,
        source_task_id,
        preview_task_id,
        preview_total_pages,
        preview_image_urls,
        feature_report_text,
        feature_report_path,
    ) = row

    try:
        process_list = json.loads(content) if content else []
    except Exception:
        process_list = [content] if content else []

    feature_report_json = _load_feature_report_payload(feature_report_path, feature_report_text)

    return {
        "id": row_id,
        "prefix": row_prefix,
        "product_type": product_type,
        "process_summary": process_summary,
        "key_features": key_features,
        "context": context,
        "materials": materials,
        "created_at": created_at,
        "tech_requirement": tech_requirement,
        "real": real_flag,
        "process_list": process_list,
        "source_type": source_type,
        "source_task_id": source_task_id,
        "preview_task_id": preview_task_id,
        "preview_total_pages": preview_total_pages or 0,
        "preview_image_urls": preview_image_urls or "",
        "feature_report_text": feature_report_text or "",
        "feature_report_path": feature_report_path or "",
        "feature_report_json": feature_report_json,
    }


def _fetch_record_by_id(record_id: int, library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
        SELECT id, prefix, content, context, product_type, process_summary,
                   key_features, materials, created_at, tech_requirement, real,
                   source_type, source_task_id, preview_task_id, preview_total_pages, preview_image_urls,
                   feature_report_text, feature_report_path
            FROM {vector_table}
            WHERE id = ?
            """,
            (record_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    (
        row_id,
        row_prefix,
        content,
        context,
        product_type,
        process_summary,
        key_features,
        materials,
        created_at,
        tech_requirement,
        real_flag,
        source_type,
        source_task_id,
        preview_task_id,
        preview_total_pages,
        preview_image_urls,
        feature_report_text,
        feature_report_path,
    ) = row

    try:
        process_list = json.loads(content) if content else []
    except Exception:
        process_list = [content] if content else []

    feature_report_json = _load_feature_report_payload(feature_report_path, feature_report_text)

    return {
        "id": row_id,
        "prefix": row_prefix,
        "product_type": product_type,
        "process_summary": process_summary,
        "key_features": key_features,
        "context": context,
        "materials": materials,
        "created_at": created_at,
        "tech_requirement": tech_requirement,
        "real": real_flag,
        "process_list": process_list,
        "trades": _extract_trades_from_rows(process_list),
        "source_type": source_type,
        "source_task_id": source_task_id,
        "preview_task_id": preview_task_id,
        "preview_total_pages": preview_total_pages or 0,
        "preview_image_urls": preview_image_urls or "",
        "feature_report_text": feature_report_text or "",
        "feature_report_path": feature_report_path or "",
        "feature_report_json": feature_report_json,
    }


def _list_records(page: int = 1, page_size: int = 20, query: str = "", product_type: str = "", library_key: str = ""):
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 20), 100), 1)
    offset = (page - 1) * page_size
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]

    where = ["COALESCE(real, 1) = 1"]
    params = []
    if query:
        where.append("(UPPER(prefix) LIKE ? OR UPPER(context) LIKE ? OR UPPER(process_summary) LIKE ? OR UPPER(content) LIKE ? OR UPPER(feature_report_text) LIKE ?)")
        keyword = f"%{query.strip().upper()}%"
        params.extend([keyword, keyword, keyword, keyword, keyword])
    if product_type:
        where.append("product_type = ?")
        params.append(product_type)

    where_sql = " AND ".join(where)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {vector_table} WHERE {where_sql}", params)
        total = int(cursor.fetchone()[0] or 0)

        cursor.execute(
            f"""
            SELECT id, prefix, product_type, process_summary, context, tech_requirement, created_at, content,
                   source_type, source_task_id, preview_task_id, preview_total_pages, preview_image_urls,
                   feature_report_text, feature_report_path
            FROM {vector_table}
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        rows = cursor.fetchall()

        cursor.execute(
            f"SELECT DISTINCT product_type FROM {vector_table} WHERE COALESCE(real, 1) = 1 AND product_type IS NOT NULL AND TRIM(product_type) != '' ORDER BY product_type"
        )
        product_types = [row[0] for row in cursor.fetchall() if row and row[0]]
    finally:
        conn.close()

    items = []
    for row in rows:
        row_id, prefix, row_product_type, process_summary, context, tech_requirement, created_at, content, source_type, source_task_id, preview_task_id, preview_total_pages, preview_image_urls, feature_report_text, feature_report_path = row
        try:
            process_list = json.loads(content) if content else []
        except Exception:
            process_list = [content] if content else []
        if isinstance(process_list, list):
            content_text = "\n".join([str(item).strip() for item in process_list if str(item).strip()])
        else:
            content_text = str(content or "")
        items.append(
            {
                "id": row_id,
                "prefix": prefix,
                "product_type": row_product_type or "",
                "process_summary": process_summary or "",
                "context": context or "",
                "tech_requirement": tech_requirement or "",
                "created_at": created_at,
                "process_count": len(process_list),
                "content": content_text,
                "process_list": process_list,
                "trades": _extract_trades_from_rows(process_list),
                "source_type": source_type or "",
                "source_task_id": source_task_id or "",
                "preview_task_id": preview_task_id or "",
                "preview_total_pages": preview_total_pages or 0,
                "preview_image_urls": preview_image_urls or "",
                "feature_report_text": feature_report_text or "",
                "feature_report_path": feature_report_path or "",
                "feature_report_json": _load_feature_report_payload(feature_report_path, feature_report_text),
            }
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max((total + page_size - 1) // page_size, 1),
        "product_types": product_types,
        "active_scope": scope,
    }


def _update_record(record_id: int, payload: dict, library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]
    feature_table = scope["feature_table"]
    existing = _fetch_record_by_id(record_id, library_key=library_key)
    if not existing:
        return None

    prefix = (payload.get("prefix") or existing.get("prefix") or "").strip().upper()
    product_type = (payload.get("product_type") or existing.get("product_type") or "").strip()
    process_summary = (payload.get("process_summary") or existing.get("process_summary") or "").strip()
    context = (payload.get("context") or existing.get("context") or "").strip()
    tech_requirement = (payload.get("tech_requirement") or existing.get("tech_requirement") or "").strip()
    source_type = (payload.get("source_type") or existing.get("source_type") or "").strip()
    source_task_id = (payload.get("source_task_id") or existing.get("source_task_id") or "").strip()
    preview_task_id = (payload.get("preview_task_id") or existing.get("preview_task_id") or "").strip()
    preview_total_pages = int(payload.get("preview_total_pages") or existing.get("preview_total_pages") or 0)
    preview_image_urls = payload.get("preview_image_urls")
    if isinstance(preview_image_urls, list):
        preview_image_urls = json.dumps(preview_image_urls, ensure_ascii=False)
    elif not isinstance(preview_image_urls, str) or not preview_image_urls.strip():
        preview_image_urls = existing.get("preview_image_urls") or ""
    feature_report_text = (payload.get("feature_report_text") or existing.get("feature_report_text") or "").strip()
    feature_report_path = (payload.get("feature_report_path") or existing.get("feature_report_path") or "").strip()
    feature_report_json = payload.get("feature_report_json")
    if isinstance(feature_report_json, dict) and feature_report_json:
        feature_report_path, feature_report_json = _persist_feature_report_json(feature_report_json, feature_report_path, prefix=prefix, record_id=record_id)
        if not feature_report_text:
            feature_report_text = str(feature_report_json.get("report_text") or "").strip()
    else:
        feature_report_json = _load_feature_report_payload(feature_report_path, feature_report_text)
    process_list = payload.get("process_list")
    raw_content = payload.get("content")
    if not isinstance(process_list, list):
        if isinstance(raw_content, str) and raw_content.strip():
            process_list = [line.strip() for line in raw_content.splitlines() if line.strip()]
        else:
            process_list = existing.get("process_list") or []

    content = json.dumps(process_list, ensure_ascii=False)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            UPDATE {vector_table}
            SET prefix = ?, product_type = ?, process_summary = ?, context = ?, tech_requirement = ?, content = ?,
                source_type = ?, source_task_id = ?, preview_task_id = ?, preview_total_pages = ?, preview_image_urls = ?,
                feature_report_text = ?, feature_report_path = ?
            WHERE id = ?
            """,
            (
                prefix,
                product_type,
                process_summary,
                context,
                tech_requirement,
                content,
                source_type,
                source_task_id,
                preview_task_id,
                preview_total_pages,
                preview_image_urls,
                feature_report_text,
                feature_report_path,
                record_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    invalidate_index_cache()
    return _fetch_record_by_id(record_id, library_key=library_key)


def _delete_record(record_id: int, library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]
    feature_table = scope.get("feature_table") or ""
    existing = _fetch_record_by_id(record_id, library_key=library_key)
    if not existing:
        return None

    prefix = existing.get("prefix", "")
    source_task_id = existing.get("source_task_id", "")
    preview_task_id = existing.get("preview_task_id", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {vector_table} WHERE id = ?", (record_id,))
        if prefix and feature_table:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (feature_table,))
            if cursor.fetchone():
                cursor.execute(f"DELETE FROM {feature_table} WHERE drawing_id = ?", (prefix,))
        conn.commit()
    finally:
        conn.close()

    # Clean up task output directories and task_store records
    try:
        from ..task_store import delete_task_with_files
        delete_task_with_files(source_task_id)
        if preview_task_id and preview_task_id != source_task_id:
            delete_task_with_files(preview_task_id)
    except Exception as e:
        logger.warning("[library] file cleanup failed for record %s: %s", record_id, e)

    invalidate_index_cache()
    return existing


def _clear_scope_records(library_key: str = ""):
    scope = _scope_from_key(library_key)
    if scope.get("library_key") == PUBLIC_LIBRARY_KEY:
        return None, "Public library is read-only"

    vector_table = scope["vector_table"]
    feature_table = scope["feature_table"]  # may or may not exist (legacy)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {vector_table} WHERE COALESCE(real, 1) = 1")
        vector_count = int(cursor.fetchone()[0] or 0)

        cursor.execute(f"DROP TABLE IF EXISTS {vector_table}")
        cursor.execute(f"DROP TABLE IF EXISTS {feature_table}")  # no-op if table doesn't exist
        cursor.execute("DELETE FROM kb_library_scopes WHERE library_key = ?", (scope["library_key"],))
        conn.commit()
    finally:
        conn.close()

    invalidate_index_cache()
    return {
        "library_key": scope["library_key"],
        "library_name": scope["library_name"],
        "scope_type": scope["scope_type"],
        "vector_table": vector_table,
        "feature_table": feature_table,
        "deleted_vector_count": vector_count,
    }, None


def _build_draft_from_task(task_id: str):
    result, task = _load_result_payload(task_id)
    if not result:
        return None, None, "Task result not found"

    source_name = result.get("pdf_name") or task.get("pdf_name") or task_id
    vision_descriptions = result.get("vision_descriptions") or task.get("vision_descriptions") or []
    feature_report_json = result.get("feature_report_json") or task.get("feature_report_json") or {}
    feature_report_text_raw = (result.get("feature_report_text") or task.get("feature_report_text") or "").strip()
    review_text = (result.get("review_text") or task.get("review_text") or "").strip()
    # Reviewed text (user-confirmed) takes priority over raw extraction text
    feature_report_text = review_text or feature_report_text_raw
    vision_text = "\n\n".join(
        [d.get("description", "") for d in vision_descriptions if d.get("description")]
    )
    source_text = feature_report_text or vision_text or result.get("expert_judgment") or ""

    # Keep original pages for per-image reference but update report_text to the reviewed version
    if feature_report_text and isinstance(feature_report_json, dict):
        feature_report_json = {**feature_report_json, "report_text": feature_report_text}

    process_flow = result.get("process_flow") or {}
    process_rows = []
    if isinstance(process_flow, dict) and process_flow.get("data"):
        process_rows = [
            f"{row[0]}@{row[1]}" if isinstance(row, (list, tuple)) and len(row) >= 2 else str(row)
            for row in process_flow.get("data", [])
        ]
    elif isinstance(process_flow, dict) and process_flow.get("raw"):
        process_rows = _parse_process_text(process_flow.get("raw", ""))
    else:
        process_rows = _parse_process_text(result.get("process_flow_raw", ""))

    prefix = _extract_prefix(source_text, source_name)
    draft = _build_draft(prefix, source_name, "task", source_text, process_rows)
    draft["source_task_id"] = task_id
    draft["preview_task_id"] = task_id
    draft["preview_total_pages"] = len(task.get("png_paths") or []) or int(result.get("png_count") or 0)
    draft["preview_image_urls"] = result.get("preview_image_urls") or []
    draft["feature_report_json"] = feature_report_json
    draft["feature_report_text"] = feature_report_text
    draft["feature_report_path"] = result.get("feature_report_path") or task.get("feature_report_path") or ""
    existing = _fetch_existing_record(prefix)
    similar = query_by_fused_text(source_text or draft["vector_text"], top_k=3, min_similarity=0.25, prefix_hint=prefix)
    return draft, existing, similar


def _build_draft_from_text(prefix: str, source_name: str, raw_text: str):
    progress_trace = []
    _trace_step(progress_trace, "1. 解析 TXT 内容")
    prefix = _extract_prefix(raw_text, prefix or source_name or f"TXT-{uuid.uuid4().hex[:8].upper()}")
    content_rows = _rows_from_text(raw_text)
    _trace_step(progress_trace, "2. 提取上下文与特征")
    draft = _build_draft(prefix, source_name or prefix, "text", raw_text, content_rows)
    existing = _fetch_existing_record(prefix)
    _trace_step(progress_trace, "3. 相似记录检索中")
    similar = query_by_fused_text(
        raw_text or draft["vector_text"],
        top_k=3,
        min_similarity=0.25,
        prefix_hint=prefix,
        log_callback=lambda msg: _trace_step(progress_trace, msg),
    )
    _trace_step(progress_trace, "4. 文本草稿生成完成")
    draft["progress_trace"] = progress_trace
    return draft, existing, similar


def _build_draft_from_file(file_storage, prefix: str, source_name: str):
    progress_trace = []
    filename = secure_filename(file_storage.filename or "library_input")
    if not PRT_FILE_RE.search(filename):
        raise ValueError("Only PRT files (including .prt.N) allowed")

    ensure_dir = os.path.join(OUTPUT_FOLDER, "library_ingest")
    os.makedirs(ensure_dir, exist_ok=True)

    ingest_id = str(uuid.uuid4())
    source_path = os.path.join(ensure_dir, f"{ingest_id}_{filename}")
    file_storage.save(source_path)
    _trace_step(progress_trace, "1. 文件已保存，准备分析")

    preview_task_id = f"library_{ingest_id}"
    work_dir = os.path.join(OUTPUT_FOLDER, f"library_{ingest_id}")
    os.makedirs(work_dir, exist_ok=True)

    _trace_step(progress_trace, "2. PRT 正在转换为 STEP 和三视图")
    artifacts = prepare_prt_artifacts(source_path, work_dir)
    png_paths = artifacts["view_paths"]
    step_path = artifacts.get("step_path") or ""
    _trace_step(progress_trace, f"3. 模型预处理完成，共 {len(png_paths)} 张视图")

    # ── VLM-only 特征提取链路（与 upload.py 对齐） ─────────────────────────
    _trace_step(progress_trace, "4. VLM 模型正在提取特征")
    vlm_text, vlm_mode = build_vlm_feature_text(
        freecad_views_dir=artifacts.get("views_dir", ""),
        creo_views_dir=artifacts.get("creo_views_dir", ""),
        creo_txt_path=artifacts.get("creo_zhushi_path", ""),
        step_path=step_path,
    )
    stem = os.path.splitext(filename)[0]
    source_text = (vlm_text + f"\n【图号】{prefix or stem}") if vlm_text else f"【图号】{prefix or stem}"
    _trace_step(progress_trace, f"5. VLM 特征提取完成（模式: {vlm_mode}）")
    prefix = _extract_prefix(source_text, prefix or source_name or stem)
    draft = _build_draft(prefix, source_name or filename, "prt", source_text, [])
    draft["feature_report_json"] = {"report_text": source_text, "pages": []}
    draft["feature_report_text"] = source_text
    draft["feature_report_path"] = write_feature_report_json(work_dir, {"report_text": source_text, "pages": []})
    existing = _fetch_existing_record(prefix)
    _trace_step(progress_trace, "6. 相似记录检索中")
    similar = query_by_fused_text(
        source_text or draft["vector_text"],
        top_k=3,
        min_similarity=0.25,
        prefix_hint=prefix,
        log_callback=lambda msg: _trace_step(progress_trace, msg),
    )
    _trace_step(progress_trace, "7. 文件草稿生成完成")
    draft["progress_trace"] = progress_trace
    draft["preview_task_id"] = preview_task_id
    draft["preview_total_pages"] = len(png_paths)
    draft["source_task_id"] = preview_task_id
    draft["preview_image_urls"] = [f"/api/result/{preview_task_id}/asset/{os.path.relpath(path, os.path.join(OUTPUT_FOLDER, preview_task_id)).replace(os.sep, '/')}" for path in png_paths]
    return draft, existing, similar


def _normalise_searchable_text(draft: dict) -> tuple[str, str]:
    """Return source_text and vector_text for storage and retrieval."""
    source_text = (
        draft.get("source_text")
        or draft.get("feature_report_text")
        or draft.get("context")
        or draft.get("key_features_text")
        or draft.get("vector_content")
        or ""
    )
    source_text = str(source_text or "").strip()
    vector_text = str(draft.get("vector_text") or source_text or "").strip()
    return source_text, vector_text


def _build_retrieval_check(prefix: str, vector_text: str, library_key: str = ""):
    normalized_prefix = str(prefix or "").strip().upper()
    text = str(vector_text or "").strip()
    if not text:
        return {
            "status": "skipped",
            "searchable": False,
            "matched_prefix": "",
            "similarity": 0,
            "reason": "vector_text is empty",
        }
    if not os.getenv("EMBEDDING_API_KEY", ""):
        return {
            "status": "skipped",
            "searchable": False,
            "matched_prefix": "",
            "similarity": 0,
            "reason": "EMBEDDING_API_KEY not configured",
        }

    try:
        matches = query_by_vector_similarity(
            text,
            top_k=5,
            min_similarity=0.0,
            library_key=library_key or None,
        )
    except Exception as exc:
        logger.warning("[Library] retrieval self-check failed prefix=%s: %s", normalized_prefix, exc)
        return {
            "status": "failed",
            "searchable": False,
            "matched_prefix": "",
            "similarity": 0,
            "reason": str(exc) or "retrieval self-check failed",
        }

    for match in matches or []:
        matched_prefix = str(match.get("drawing_id") or match.get("prefix") or "").strip().upper()
        if matched_prefix == normalized_prefix:
            return {
                "status": "ok",
                "searchable": True,
                "matched_prefix": normalized_prefix,
                "similarity": float(match.get("similarity") or 0),
                "reason": "",
            }

    return {
        "status": "failed",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "saved prefix not returned by retrieval self-check",
    }


def _upsert_record(draft: dict, replace: bool, library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]

    source_text, vector_text = _normalise_searchable_text(draft)
    vector = create_query_vector(vector_text)
    vector_blob = vector.tobytes() if vector is not None else None
    prefix = draft["prefix"].strip().upper()
    process_list = draft.get("process_list", [])
    content = json.dumps(process_list, ensure_ascii=False)
    context = draft.get("context") or source_text
    key_features_text = draft.get("key_features_text") or vector_text or source_text
    key_features = key_features_text
    materials = json.dumps(draft.get("materials", []), ensure_ascii=False)
    product_type = draft.get("product_type") or ""
    process_summary = draft.get("process_summary") or ""
    tech_requirement = draft.get("tech_requirement") or ""
    real_flag = 1 if draft.get("real", 1) else 0
    source_type = draft.get("source_type") or ""
    source_task_id = draft.get("source_task_id") or ""
    preview_task_id = draft.get("preview_task_id") or ""
    preview_total_pages = int(draft.get("preview_total_pages") or 0)
    preview_image_urls = draft.get("preview_image_urls") or []
    feature_report_text = (draft.get("feature_report_text") or source_text).strip()
    feature_report_path = (draft.get("feature_report_path") or "").strip()
    feature_report_json = draft.get("feature_report_json")
    if isinstance(preview_image_urls, list):
        preview_image_urls = json.dumps(preview_image_urls, ensure_ascii=False)
    elif not isinstance(preview_image_urls, str):
        preview_image_urls = ""

    if isinstance(feature_report_json, dict) and feature_report_json:
        feature_report_path, feature_report_json = _persist_feature_report_json(feature_report_json, feature_report_path, prefix=prefix)
        if not feature_report_text:
            feature_report_text = str(feature_report_json.get("report_text") or "").strip()
    else:
        feature_report_json = _load_feature_report_payload(feature_report_path, feature_report_text)

    structured = draft.get("structured") or extract_structured_features(key_features_text)
    structured_features = structured.get("key_features", {}) if isinstance(structured, dict) else {}
    blank_type = structured_features.get("毛坯类型")
    overall_length = structured.get("structured_filter", {}).get("overall_length") if isinstance(structured, dict) else None
    main_diameter = structured.get("structured_filter", {}).get("main_diameter") if isinstance(structured, dict) else None
    tolerance_levels = json.dumps(structured.get("structured_filter", {}).get("tolerance_levels", []), ensure_ascii=False) if isinstance(structured, dict) else "[]"
    thread_specs = json.dumps(structured.get("structured_filter", {}).get("thread_specs", []), ensure_ascii=False) if isinstance(structured, dict) else "[]"
    hole_specs = json.dumps(structured.get("structured_filter", {}).get("hole_specs", []), ensure_ascii=False) if isinstance(structured, dict) else "[]"
    roughness = json.dumps(structured.get("structured_filter", {}).get("roughness", []), ensure_ascii=False) if isinstance(structured, dict) else "[]"
    heat_treatment = structured_features.get("热处理与探伤") if isinstance(structured_features, dict) else None
    inspection_standards = structured_features.get("标识与检验") if isinstance(structured_features, dict) else None
    special_requirements = structured.get("process_reference", "") if isinstance(structured, dict) else ""
    vector_content = structured.get("vector_index", vector_text or key_features_text) if isinstance(structured, dict) else (vector_text or key_features_text)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO {vector_table}
            (prefix, vector, content, context, product_type, process_summary, key_features, materials, tech_requirement, real,
             source_type, source_task_id, preview_task_id, preview_total_pages, preview_image_urls, feature_report_text, feature_report_path,
             blank_type, overall_length_min, overall_length_max, main_diameter_min, main_diameter_max,
             tolerance_levels, thread_specs, hole_specs, roughness,
             heat_treatment, inspection_standards, special_requirements, vector_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prefix,
                vector_blob,
                content,
                context,
                product_type,
                process_summary,
                key_features,
                materials,
                tech_requirement,
                real_flag,
                source_type,
                source_task_id,
                preview_task_id,
                preview_total_pages,
                preview_image_urls,
                feature_report_text,
                feature_report_path,
                blank_type,
                overall_length[0] if overall_length else None,
                overall_length[1] if overall_length else None,
                main_diameter[0] if main_diameter else None,
                main_diameter[1] if main_diameter else None,
                tolerance_levels,
                thread_specs,
                hole_specs,
                roughness,
                heat_treatment,
                inspection_standards,
                special_requirements,
                vector_content,
            ),
        )

        conn.commit()
    finally:
        conn.close()

    invalidate_index_cache(library_key or None)
    return {"prefix": prefix, "source_text": source_text, "vector_text": vector_text}


@library_bp.route("/library/preview", methods=["POST"])
def preview_library_record():
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    source_type = payload.get("source_type") or request.form.get("source_type")
    logger.info("[Library] preview requested source_type=%s", source_type)

    if source_type == "task":
        task_id = payload.get("task_id")
        if not task_id:
            return jsonify({"error": "task_id required"}), 400
        draft, existing, similar = _build_draft_from_task(task_id)
        if not draft:
            return jsonify({"error": "Task result not found"}), 404
    elif source_type == "file":
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "file required"}), 400
        draft, existing, similar = _build_draft_from_file(
            file,
            payload.get("prefix") or "",
            payload.get("source_name") or payload.get("name") or file.filename,
        )
    elif source_type == "text":
        raw_text = payload.get("text") or ""
        if not raw_text.strip():
            return jsonify({"error": "text required"}), 400
        draft, existing, similar = _build_draft_from_text(
            payload.get("prefix") or "",
            payload.get("source_name") or payload.get("name") or "手工工艺",
            raw_text,
        )
    else:
        return jsonify({"error": "Unsupported source_type"}), 400

    return jsonify(
        _json_safe(
        {
            "draft": draft,
            "existing": existing,
            "conflict": bool(existing),
            "similar_matches": (similar or {}).get("matches", []),
            "query_context": (similar or {}).get("rag_context", ""),
            "progress_trace": (draft or {}).get("progress_trace", []),
            "preview_task_id": (draft or {}).get("preview_task_id"),
            "preview_total_pages": (draft or {}).get("preview_total_pages", 0),
        }
        )
    )


@library_bp.route("/library/status", methods=["GET"])
def library_status():
    library_key = request.args.get("library_key", "")
    return jsonify(_json_safe(_library_ready_status(library_key)))


@library_bp.route("/library/scopes", methods=["GET"])
def library_scopes():
    return jsonify(_json_safe({"items": list_scopes(), **browse_unlock_status()}))


@library_bp.route("/library/records", methods=["GET"])
def list_library_records():
    page = request.args.get("page", 1)
    page_size = request.args.get("page_size", 20)
    query = request.args.get("query", "")
    product_type = request.args.get("product_type", "")
    library_key = request.args.get("library_key", "")
    return jsonify(_json_safe(_list_records(page, page_size, query, product_type, library_key=library_key)))


@library_bp.route("/library/records/<int:record_id>", methods=["GET"])
def get_library_record(record_id):
    record = _fetch_record_by_id(record_id, library_key=request.args.get("library_key", ""))
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(_json_safe(record))


@library_bp.route("/library/records/<int:record_id>", methods=["PUT"])
def update_library_record(record_id):
    payload = request.get_json(silent=True) or {}
    record = _update_record(record_id, payload, library_key=payload.get("library_key") or request.args.get("library_key", ""))
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(_json_safe(record))


@library_bp.route("/library/records/<int:record_id>", methods=["DELETE"])
def delete_library_record(record_id):
    library_key = request.args.get("library_key", "")
    record = _delete_record(record_id, library_key=library_key)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(_json_safe({"message": "Record deleted", "record": record}))


@library_bp.route("/library/scopes/<string:library_key>", methods=["DELETE"])
def clear_library_scope(library_key):
    scope, error = _clear_scope_records(library_key)
    if error:
        return jsonify({"error": error}), 403
    return jsonify(_json_safe({"message": "Library cleared", "scope": scope}))


@library_bp.route("/library/commit", methods=["POST"])
def commit_library_record():
    payload = request.get_json(silent=True) or {}
    draft = payload.get("draft")
    action = payload.get("action", "replace")
    library_key = payload.get("library_key", "")
    logger.info("[Library] commit requested action=%s prefix=%s", action, (draft or {}).get("prefix"))

    if not draft or not draft.get("prefix"):
        return jsonify({"error": "draft prefix required"}), 400

    existing = _fetch_existing_record(draft["prefix"], library_key=library_key)
    if existing and action == "keep":
        return jsonify({"message": "Existing record kept", "existing": existing, "draft": draft})

    replace = action != "keep"
    saved_meta = _upsert_record(draft, replace=replace, library_key=library_key)
    retrieval_check = _build_retrieval_check(
        saved_meta["prefix"],
        saved_meta["vector_text"],
        library_key=library_key,
    )
    logger.info(
        "[Library] commit finished prefix=%s replaced=%s retrieval_status=%s",
        draft.get("prefix"),
        replace,
        retrieval_check.get("status"),
    )

    fresh = _fetch_existing_record(draft["prefix"], library_key=library_key)
    return jsonify(
        _json_safe(
        {
            "message": "Library record saved",
            "draft": draft,
            "existing": existing,
            "saved": fresh,
            "replaced": bool(existing) and replace,
            "active_scope": _scope_from_key(library_key),
            "retrieval_check": retrieval_check,
        }
        )
    )
