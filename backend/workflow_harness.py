# -*- coding: utf-8 -*-
"""Lightweight persisted workflow state for long-running backend operations.

Provides workflow_runs, workflow_events, and workflow_rollback_snapshots
tables in the same SQLite database used by the knowledge-base import pipeline.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from .vector_map_rag import DB_PATH

DEFAULT_RUNNING_TTL_SECONDS = int(os.getenv("ZIP_IMPORT_RUNNING_TTL_SECONDS", "3600"))


def _now() -> str:
    return datetime.now().isoformat()


def _get_latest_event_time(run_id: str) -> str | None:
    """Return the created_at of the latest workflow_events row for this run, or None."""
    ensure_workflow_tables()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT created_at FROM workflow_events WHERE run_id = ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return row["created_at"] if row else None
    finally:
        conn.close()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_stale_timestamp(value: str | None, stale_after_seconds: int) -> bool:
    started_at = _parse_iso_datetime(value)
    if not started_at:
        return False
    return (datetime.now() - started_at).total_seconds() > stale_after_seconds


def _is_stale_timestamp_at(
    value: str | None,
    stale_after_seconds: int,
    now: datetime | None = None,
) -> bool:
    started_at = _parse_iso_datetime(value)
    if not started_at:
        return False
    current = now or datetime.now()
    return (current - started_at).total_seconds() > stale_after_seconds


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH); conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_workflow_tables() -> None:
    """Create workflow tables and indexes if they do not exist (idempotent)."""
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                workflow_type TEXT NOT NULL,
                status TEXT NOT NULL,
                enterprise_id INTEGER,
                user_id INTEGER,
                library_key TEXT DEFAULT '',
                batch_id TEXT DEFAULT '',
                input_hash TEXT DEFAULT '',
                cache_key TEXT DEFAULT '',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error_code TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                result_json TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_type_status ON workflow_runs(workflow_type, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_cache ON workflow_runs(cache_key, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_runs_enterprise ON workflow_runs(enterprise_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                progress_hint INTEGER,
                payload_json TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_events_run_id ON workflow_events(run_id, id)"
        )
        # ── Rollback snapshots for replace-mode compensation (P0-1) ─────────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_rollback_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id TEXT NOT NULL,
                vector_table TEXT NOT NULL,
                prefix TEXT NOT NULL,
                record_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rollback_snapshots_run ON workflow_rollback_snapshots(workflow_run_id)"
        )
        conn.commit()
    finally:
        conn.close()


# ── Run lifecycle ──────────────────────────────────────────────────────────


def create_workflow_run(
    workflow_type: str,
    enterprise_id: int | None,
    user_id: int | None,
    library_key: str = "",
    batch_id: str = "",
    input_hash: str = "",
    cache_key: str = "",
) -> dict[str, Any]:
    ensure_workflow_tables()
    safe_type = (workflow_type or "workflow").strip()
    run_id = (
        f"wf_{safe_type}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_"
        f"{uuid.uuid4().hex[:8]}"
    )
    started_at = _now()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO workflow_runs
            (run_id, workflow_type, status, enterprise_id, user_id,
             library_key, batch_id, input_hash, cache_key, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                safe_type,
                "running",
                enterprise_id,
                user_id,
                library_key or "",
                batch_id or "",
                input_hash or "",
                cache_key or "",
                started_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_workflow_run(run_id) or {"run_id": run_id, "status": "running"}


def update_workflow_metadata(
    run_id: str,
    *,
    library_key: str = "",
    batch_id: str = "",
    cache_key: str = "",
) -> dict[str, Any] | None:
    """Update mutable metadata fields on an existing workflow run.

    Callers MUST call this after target-scope resolution to persist the
    final library_key and cache_key (P0-4).  Returns the updated run dict.
    """
    ensure_workflow_tables()
    conn = _connect()
    try:
        sets: list[str] = []
        params: list[Any] = []
        if library_key:
            sets.append("library_key = ?")
            params.append(library_key)
        if batch_id:
            sets.append("batch_id = ?")
            params.append(batch_id)
        if cache_key:
            sets.append("cache_key = ?")
            params.append(cache_key)
        if not sets:
            return get_workflow_run(run_id)
        params.append(run_id)
        conn.execute(
            f"UPDATE workflow_runs SET {', '.join(sets)} WHERE run_id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()
    return get_workflow_run(run_id)


def find_running_workflow(
    workflow_type: str,
    *,
    enterprise_id: int | None,
    library_key: str = "",
    exclude_run_id: str = "",
    stale_after_seconds: int | None = None,
) -> dict[str, Any] | None:
    ensure_workflow_tables()
    stale_seconds = DEFAULT_RUNNING_TTL_SECONDS if stale_after_seconds is None else stale_after_seconds
    conn = _connect()
    try:
        params: list[Any] = [workflow_type, library_key or ""]
        where = [
            "workflow_type = ?",
            "status = 'running'",
            "library_key = ?",
        ]
        if enterprise_id is None:
            where.append("enterprise_id IS NULL")
        else:
            where.append("enterprise_id = ?")
            params.append(enterprise_id)
        if exclude_run_id:
            where.append("run_id != ?")
            params.append(exclude_run_id)
        rows = conn.execute(
            f"SELECT run_id, started_at FROM workflow_runs WHERE {' AND '.join(where)} ORDER BY id ASC",
            params,
        ).fetchall()
        for row in rows:
            run_id = row["run_id"]
            last_event_at = _get_latest_event_time(run_id) or row["started_at"]
            if stale_seconds > 0 and _is_stale_timestamp(last_event_at, stale_seconds):
                conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status = 'failed',
                        finished_at = ?,
                        error_code = 'stale_worker_interrupted',
                        error_message = '后台任务超时未更新，已释放入库并发锁。'
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (_now(), run_id),
                )
                conn.commit()
                continue
            return get_workflow_run(run_id)
        return None
    finally:
        conn.close()


def count_running_workflows(
    workflow_type: str,
    *,
    exclude_run_id: str = "",
    stale_after_seconds: int | None = None,
) -> int:
    """Return active running workflows after releasing stale rows."""
    ensure_workflow_tables()
    cleanup_stale_workflow_runs(
        workflow_type,
        stale_after_seconds=stale_after_seconds,
    )
    conn = _connect()
    try:
        params: list[Any] = [workflow_type]
        where = ["workflow_type = ?", "status = 'running'"]
        if exclude_run_id:
            where.append("run_id != ?")
            params.append(exclude_run_id)
        row = conn.execute(
            f"SELECT COUNT(*) AS count FROM workflow_runs WHERE {' AND '.join(where)}",
            params,
        ).fetchone()
        return int(row["count"] if row else 0)
    finally:
        conn.close()


def claim_workflow_slot(
    workflow_type: str,
    run_id: str,
    *,
    max_running: int,
    stale_after_seconds: int | None = None,
) -> dict[str, Any]:
    """Check whether run_id is within the first max_running active rows.

    The current run is created before admission control so every worker can use
    the same SQLite ordering across gunicorn processes.
    """
    ensure_workflow_tables()
    cleanup_stale_workflow_runs(
        workflow_type,
        stale_after_seconds=stale_after_seconds,
    )
    limit = max(1, int(max_running or 1))
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """
            SELECT run_id
            FROM workflow_runs
            WHERE workflow_type = ? AND status = 'running'
            ORDER BY id ASC
            """,
            (workflow_type,),
        ).fetchall()
        ordered_run_ids = [row["run_id"] for row in rows]
        try:
            position = ordered_run_ids.index(run_id) + 1
        except ValueError:
            position = 0
        conn.commit()
        return {
            "allowed": bool(position and position <= limit),
            "active_count": len(ordered_run_ids),
            "max_running": limit,
            "position": position,
        }
    finally:
        conn.close()


def find_prior_running_workflow(
    workflow_type: str,
    *,
    current_run_id: str,
    enterprise_id: int | None,
    library_key: str = "",
    stale_after_seconds: int | None = None,
) -> dict[str, Any] | None:
    """Return an older active workflow for the same scope, if one exists."""
    ensure_workflow_tables()
    cleanup_stale_workflow_runs(
        workflow_type,
        stale_after_seconds=stale_after_seconds,
    )
    conn = _connect()
    try:
        params: list[Any] = [workflow_type, library_key or ""]
        where = [
            "workflow_type = ?",
            "status = 'running'",
            "library_key = ?",
        ]
        if enterprise_id is None:
            where.append("enterprise_id IS NULL")
        else:
            where.append("enterprise_id = ?")
            params.append(enterprise_id)
        rows = conn.execute(
            f"SELECT run_id FROM workflow_runs WHERE {' AND '.join(where)} ORDER BY id ASC",
            params,
        ).fetchall()
        for row in rows:
            candidate_run_id = row["run_id"]
            if candidate_run_id == current_run_id:
                return None
            return get_workflow_run(candidate_run_id)
        return None
    finally:
        conn.close()


def cleanup_stale_workflow_runs(
    workflow_type: str = "zip_import",
    *,
    stale_after_seconds: int | None = None,
    now: datetime | None = None,
) -> int:
    """Mark stale running workflow rows failed and return the number cleaned."""
    ensure_workflow_tables()
    stale_seconds = DEFAULT_RUNNING_TTL_SECONDS if stale_after_seconds is None else stale_after_seconds
    if stale_seconds <= 0:
        return 0

    conn = _connect()
    cleaned = 0
    try:
        rows = conn.execute(
            """
            SELECT run_id, started_at
            FROM workflow_runs
            WHERE workflow_type = ? AND status = 'running'
            ORDER BY id ASC
            """,
            (workflow_type,),
        ).fetchall()
        for row in rows:
            run_id = row["run_id"]
            last_event_at = _get_latest_event_time(run_id) or row["started_at"]
            if not _is_stale_timestamp_at(last_event_at, stale_seconds, now=now):
                continue
            cursor = conn.execute(
                """
                UPDATE workflow_runs
                SET status = 'failed',
                    finished_at = ?,
                    error_code = 'stale_worker_interrupted',
                    error_message = '后台任务超时未更新，已释放入库并发锁。'
                WHERE run_id = ? AND status = 'running'
                """,
                ((now or datetime.now()).isoformat(), run_id),
            )
            cleaned += cursor.rowcount
        conn.commit()
        return cleaned
    finally:
        conn.close()


def record_workflow_event(
    run_id: str,
    stage: str,
    message: str,
    level: str = "info",
    progress_hint: int | None = None,
    payload: dict | None = None,
) -> None:
    ensure_workflow_tables()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO workflow_events
            (run_id, stage, level, message, progress_hint, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                stage,
                level,
                message,
                progress_hint,
                json.dumps(payload or {}, ensure_ascii=False),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def finish_workflow_run(
    run_id: str,
    status: str,
    error_code: str = "",
    error_message: str = "",
    result: dict | None = None,
) -> dict[str, Any]:
    ensure_workflow_tables()
    result_json = (
        json.dumps(result or {}, ensure_ascii=False)
        if result is not None
        else ""
    )
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE workflow_runs
            SET status = ?, finished_at = ?, error_code = ?, error_message = ?, result_json = ?
            WHERE run_id = ?
            """,
            (status, _now(), error_code or "", error_message or "", result_json, run_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_workflow_run(run_id) or {"run_id": run_id, "status": status}


def _decode_json(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _json_default(value: Any) -> Any:
    """JSON default encoder: hex-encode BLOB values so they survive serialization."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__bytes_hex__": bytes(value).hex()}
    return str(value)


def _decode_snapshot_value(value: Any) -> Any:
    """Reverse _json_default: decode hex-encoded BLOBs back to bytes."""
    if isinstance(value, dict) and "__bytes_hex__" in value:
        return bytes.fromhex(str(value["__bytes_hex__"]))
    return value


def _quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier safely, rejecting suspicious input."""
    if not identifier or not identifier.replace("_", "").isalnum():
        raise ValueError(f"unsafe sqlite identifier: {identifier!r}")
    return f'"{identifier}"'


def get_workflow_run(
    run_id: str, include_events: bool = False
) -> dict[str, Any] | None:
    ensure_workflow_tables()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["result"] = _decode_json(data.pop("result_json", ""))
        if include_events:
            event_rows = conn.execute(
                "SELECT stage, level, message, progress_hint, payload_json, created_at "
                "FROM workflow_events WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
            data["events"] = [
                {
                    "stage": event["stage"],
                    "level": event["level"],
                    "message": event["message"],
                    "progress_hint": event["progress_hint"],
                    "payload": _decode_json(event["payload_json"]),
                    "created_at": event["created_at"],
                }
                for event in event_rows
            ]
        return data
    finally:
        conn.close()


# ── Rollback snapshots (P0-1: replace-mode compensation) ──────────────────


def save_rollback_snapshot(
    workflow_run_id: str,
    vector_table: str,
    prefix: str,
    existing_record: dict[str, Any],
) -> None:
    """Save the full existing record before an INSERT OR REPLACE overwrites it.

    On rollback these snapshots are restored so that old records are not
    permanently lost when a replace-then-validate-failure occurs.
    """
    ensure_workflow_tables()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO workflow_rollback_snapshots
            (workflow_run_id, vector_table, prefix, record_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workflow_run_id,
                vector_table,
                prefix,
                json.dumps(existing_record, ensure_ascii=False, default=str),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def snapshot_existing_record(
    workflow_run_id: str,
    vector_table: str,
    prefix: str,
) -> bool:
    """Save the raw DB row for prefix before replace-mode overwrite.

    This is lossless: it preserves BLOB vector, raw JSON content, provenance,
    and every current vector-table column. Returns False when no row exists.
    """
    ensure_workflow_tables()
    table_sql = _quote_identifier(vector_table)
    conn = _connect()
    try:
        row = conn.execute(
            f"SELECT * FROM {table_sql} WHERE UPPER(prefix) = ? AND COALESCE(real, 1) = 1",
            (prefix.upper(),),
        ).fetchone()
        if not row:
            return False
        record = dict(row)
        conn.execute(
            """
            INSERT INTO workflow_rollback_snapshots
            (workflow_run_id, vector_table, prefix, record_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workflow_run_id,
                vector_table,
                prefix,
                json.dumps(record, ensure_ascii=False, default=_json_default),
                _now(),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def restore_rollback_snapshots(workflow_run_id: str) -> int:
    """Restore snapshotted records for a workflow run.  Returns count restored.

    Each snapshot is INSERT OR REPLACE'd back into its original vector table.
    Call BEFORE deleting the current workflow's rows so that prefix-uniqueness
    replaces the new record with the old one.

    Raises RuntimeError when a snapshot cannot be decoded or restored, so that
    callers can surface rollback_failed instead of silently losing data.
    """
    ensure_workflow_tables()
    conn = _connect()
    restored = 0
    try:
        rows = conn.execute(
            "SELECT id, vector_table, prefix, record_json "
            "FROM workflow_rollback_snapshots WHERE workflow_run_id = ?",
            (workflow_run_id,),
        ).fetchall()
        for row in rows:
            try:
                record = json.loads(row["record_json"])
            except Exception as exc:
                raise RuntimeError(
                    f"rollback snapshot {row['id']} for {row['vector_table']} is not valid JSON"
                ) from exc
            # Build column/value lists dynamically from the saved dict,
            # filtering to only the columns that exist in the target table.
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({row['vector_table']})")
            valid_cols = {r[1] for r in cursor.fetchall()}
            cols = [k for k in record.keys() if k in valid_cols]
            if not cols:
                raise RuntimeError(
                    f"rollback snapshot {row['id']} has no restorable columns for {row['vector_table']}"
                )
            placeholders = ", ".join("?" for _ in cols)
            col_list = ", ".join(cols)
            values = [_decode_snapshot_value(record.get(c)) for c in cols]
            conn.execute(
                f"INSERT OR REPLACE INTO {row['vector_table']} ({col_list}) "
                f"VALUES ({placeholders})",
                values,
            )
            restored += 1
        conn.commit()
    finally:
        conn.close()
    return restored


def delete_rollback_snapshots(workflow_run_id: str) -> int:
    """Delete snapshots after a successful validation (cleanup).  Returns count."""
    ensure_workflow_tables()
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM workflow_rollback_snapshots WHERE workflow_run_id = ?",
            (workflow_run_id,),
        )
        count = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            "DELETE FROM workflow_rollback_snapshots WHERE workflow_run_id = ?",
            (workflow_run_id,),
        )
        conn.commit()
        return count
    finally:
        conn.close()
