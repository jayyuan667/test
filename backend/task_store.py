# -*- coding: utf-8 -*-
"""SQLite task persistence — authoritative data source.

Memory dicts serve as a runtime cache. SQLite is the single source of truth.
All endpoints can reconstruct task state from the database after restarts.
"""

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_store.db")


def _conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                pdf_name TEXT,
                prt_name TEXT,
                source_name TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                output_dir TEXT,
                prefix_hint TEXT,
                error TEXT,
                library_key TEXT DEFAULT 'public',
                source_kind TEXT DEFAULT 'prt'
            );

            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                step INTEGER,
                message TEXT,
                data TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );

            CREATE TABLE IF NOT EXISTS task_results (
                task_id TEXT PRIMARY KEY,
                result_json TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
            CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id);

            CREATE TABLE IF NOT EXISTS prt_cache (
                file_hash TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                feature_text TEXT NOT NULL,
                prefix_hint TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_prt_cache_hash ON prt_cache(file_hash);
        """)

        # Migration: add source_name column if missing (for existing DBs)
        columns = {r[1] for r in c.execute("PRAGMA table_info(tasks)")}
        if "source_name" not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN source_name TEXT DEFAULT ''")
            c.execute("UPDATE tasks SET source_name = COALESCE(prt_name, pdf_name, task_id) WHERE source_name = '' OR source_name IS NULL")

        # Migration: add enterprise_id column (data isolation)
        columns = {r[1] for r in c.execute("PRAGMA table_info(tasks)")}
        if "enterprise_id" not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN enterprise_id INTEGER")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_enterprise ON tasks(enterprise_id)")


def insert_task(task_id: str, pdf_name: str = "", prt_name: str = "",
                output_dir: str = "", prefix_hint: str = "",
                library_key: str = "public", source_kind: str = "prt",
                enterprise_id: int | None = None):
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tasks (task_id, pdf_name, prt_name, status, progress, created_at, updated_at, output_dir, prefix_hint, library_key, source_kind, enterprise_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (task_id, pdf_name, prt_name, "pending", 0, now, now, output_dir, prefix_hint, library_key, source_kind, enterprise_id),
        )


def update_task_status(task_id: str, status: str, progress: int = 0, error: str = ""):
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE tasks SET status=?, progress=?, error=?, updated_at=? WHERE task_id=?",
            (status, progress, error, now, task_id),
        )


def add_event(task_id: str, event_type: str, step: int = 0, message: str = "", data: Dict = None):
    with _conn() as c:
        c.execute(
            "INSERT INTO task_events (task_id, event_type, step, message, data) VALUES (?,?,?,?,?)",
            (task_id, event_type, step, message, json.dumps(data) if data else None),
        )


def save_event(task_id: str, event_type: str, payload: dict):
    """Persist an event payload to the task_events table.

    Unlike add_event which stores step/message in separate columns,
    save_event serialises the entire payload into the data JSON column
    for structured SSE replay.
    """
    with _conn() as c:
        c.execute(
            "INSERT INTO task_events (task_id, event_type, data) VALUES (?, ?, ?)",
            (task_id, event_type, json.dumps(payload, ensure_ascii=False)),
        )


def save_result(task_id: str, result: Dict):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO task_results (task_id, result_json, completed_at) VALUES (?,?,?)",
            (task_id, json.dumps(result, ensure_ascii=False), datetime.now().isoformat()),
        )


def get_task(task_id: str) -> Optional[Dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT task_id, pdf_name, prt_name, status, progress, created_at, updated_at, output_dir, prefix_hint, error, library_key, source_kind, enterprise_id FROM tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "task_id": row[0], "pdf_name": row[1], "prt_name": row[2],
        "status": row[3], "progress": row[4], "created_at": row[5],
        "updated_at": row[6], "output_dir": row[7], "prefix_hint": row[8],
        "error": row[9], "library_key": row[10], "source_kind": row[11],
        "enterprise_id": row[12],
    }


def get_events(task_id: str, since_id: int = 0) -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, event_type, step, message, data, created_at FROM task_events WHERE task_id=? AND id>? ORDER BY id",
            (task_id, since_id),
        ).fetchall()
    return [{"id": r[0], "type": r[1], "step": r[2], "message": r[3], "data": r[4], "created_at": r[5]} for r in rows]


def get_result(task_id: str) -> Optional[Dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT result_json FROM task_results WHERE task_id=?", (task_id,)
        ).fetchone()
    return json.loads(row[0]) if row and row[0] else None


def delete_task_with_files(task_id: str) -> bool:
    """Delete a task and its output directory.

    Removes: tasks / task_events / task_results rows + the output_dir on disk.
    Returns True if the task existed, False if not found.
    """
    if not task_id:
        return False
    with _conn() as c:
        row = c.execute("SELECT output_dir FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            return False
        out_dir = row[0]
        c.execute("DELETE FROM task_results WHERE task_id=?", (task_id,))
        c.execute("DELETE FROM task_events  WHERE task_id=?", (task_id,))
        c.execute("DELETE FROM tasks        WHERE task_id=?", (task_id,))
    if out_dir:
        target = Path(out_dir)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    return True


def list_tasks(limit: int = 50, offset: int = 0, status_filter: str = "") -> List[Dict]:
    with _conn() as c:
        if status_filter:
            rows = c.execute(
                "SELECT task_id, pdf_name, prt_name, status, progress, created_at, updated_at, error, library_key, source_kind, enterprise_id FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status_filter, limit, offset),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT task_id, pdf_name, prt_name, status, progress, created_at, updated_at, error, library_key, source_kind, enterprise_id FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [{"task_id": r[0], "pdf_name": r[1], "prt_name": r[2], "status": r[3], "progress": r[4], "created_at": r[5], "updated_at": r[6], "error": r[7], "library_key": r[8], "source_kind": r[9], "enterprise_id": r[10]} for r in rows]


def count_tasks(status_filter: str = "") -> int:
    with _conn() as c:
        if status_filter:
            row = c.execute("SELECT COUNT(*) FROM tasks WHERE status=?", (status_filter,)).fetchone()
        else:
            row = c.execute("SELECT COUNT(*) FROM tasks").fetchone()
    return row[0] if row else 0


def cancel_stale_tasks() -> int:
    """Mark tasks interrupted by a backend restart as cancelled.

    Tasks stuck in pending/processing were left by a previous process that
    no longer exists. They will never complete, so cancel them immediately.
    Returns the number of rows updated.
    """
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE tasks SET status='cancelled', updated_at=? WHERE status IN ('pending','processing')",
            (now,),
        )
        return c.execute("SELECT changes()").fetchone()[0]


def build_task_dict(task_id: str) -> dict | None:
    """Reconstruct a full task dict from SQLite — the authoritative source."""
    row = get_task(task_id)
    if not row:
        return None
    result = get_result(task_id)
    task = {
        "task_id": task_id,
        "pdf_name": row.get("pdf_name", task_id),
        "prt_name": row.get("prt_name", ""),
        "source_name": row.get("pdf_name", task_id),
        "output_dir": row.get("output_dir", ""),
        "prefix_hint": row.get("prefix_hint", ""),
        "status": row.get("status", "pending"),
        "progress": row.get("progress", 0),
        "created_at": row.get("created_at", ""),
        "error": row.get("error", ""),
        "library_key": row.get("library_key", "public"),
        "source_kind": row.get("source_kind", "prt"),
        "enterprise_id": row.get("enterprise_id"),
        "result": result or {},
    }
    if result:
        if result.get("process_flow"):
            task["process_flow"] = result["process_flow"]
        if result.get("preview_image_urls"):
            task["preview_image_urls"] = result["preview_image_urls"]
        if result.get("review_text"):
            task["review_text"] = result["review_text"]
        if result.get("feature_report_text"):
            task["feature_report_text"] = result["feature_report_text"]
        if result.get("feature_report_json"):
            task["feature_report_json"] = result["feature_report_json"]
    return task

# ── PRT file cache ──────────────────────────────────────────────────────────

def get_prt_cache(file_hash: str) -> dict | None:
    """Look up a cached PRT result by file hash. Returns dict or None."""
    with _conn() as c:
        row = c.execute(
            "SELECT task_id, feature_text, prefix_hint, created_at FROM prt_cache WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
    if not row:
        return None
    return {
        "file_hash": file_hash,
        "task_id": row[0],
        "feature_text": row[1],
        "prefix_hint": row[2],
        "created_at": row[3],
    }


def save_prt_cache(file_hash: str, task_id: str, feature_text: str, prefix_hint: str = ""):
    """Save a PRT processing result to cache, keyed by file hash."""
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO prt_cache (file_hash, task_id, feature_text, prefix_hint) VALUES (?, ?, ?, ?)",
            (file_hash, task_id, feature_text, prefix_hint),
        )


# Auto-init on import
init_db()
