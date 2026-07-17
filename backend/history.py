# -*- coding: utf-8 -*-
"""History file operations for the PDF Process Analysis System."""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history.json"
)

VISIBLE_TASK_STATUSES = {
    "pending",
    "processing",
    "awaiting_review",
    "awaiting_annotation",
    "completed",
    "error",
    "cancelled",
}


def load_history_from_file() -> List[Dict[str, Any]]:
    """Load history records from file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load history file: {e}")
    return []


def save_history_to_file(history: List[Dict[str, Any]]) -> None:
    """Save history records to file."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error: Failed to save history file: {e}")


def add_history_entry(
    task_id: str,
    pdf_name: str,
    progress: int,
    created_at: str,
    completed_at: Optional[str] = None,
    file_count: Optional[int] = None,
    enterprise_id: Optional[int] = None,
) -> None:
    """Add a new entry to the history file."""
    history_entry = {
        "task_id": task_id,
        "pdf_name": pdf_name,
        "progress": progress,
        "created_at": created_at,
        "completed_at": completed_at or datetime.now().isoformat(),
    }
    if file_count is not None:
        history_entry["file_count"] = file_count
    if enterprise_id is not None:
        history_entry["enterprise_id"] = enterprise_id

    global_history = load_history_from_file()
    global_history = [item for item in global_history if item.get("task_id") != task_id]
    global_history.insert(0, history_entry)

    save_history_to_file(global_history)


def delete_history_entry(task_id: str) -> bool:
    """Delete a history entry by task_id. Returns True if found and deleted."""
    global_history = load_history_from_file()
    original_len = len(global_history)
    global_history = [h for h in global_history if h.get("task_id") != task_id]

    if len(global_history) == original_len:
        return False

    save_history_to_file(global_history)
    return True


def _task_to_history_entry(task: Dict[str, Any]) -> Dict[str, Any]:
    status = task.get("status") or "pending"
    entry = {
        "task_id": task.get("task_id"),
        "pdf_name": (
            task.get("pdf_name")
            or task.get("source_name")
            or task.get("prt_name")
            or task.get("task_id")
        ),
        "progress": task.get("progress", 0),
        "status": status,
        "created_at": task.get("created_at") or task.get("updated_at") or "",
        "completed_at": task.get("updated_at") if status == "completed" else None,
    }
    if task.get("enterprise_id") is not None:
        entry["enterprise_id"] = task.get("enterprise_id")
    if task.get("error"):
        entry["error"] = task.get("error")
    return entry


def _sort_history_key(entry: Dict[str, Any]) -> str:
    return (
        entry.get("completed_at")
        or entry.get("updated_at")
        or entry.get("created_at")
        or ""
    )


def _merge_task_store_entries(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = list(history)
    seen = {item.get("task_id") for item in merged if item.get("task_id")}
    try:
        from .task_store import list_tasks

        for task in list_tasks(limit=1000):
            task_id = task.get("task_id")
            if not task_id or task_id in seen:
                continue
            if task.get("status") not in VISIBLE_TASK_STATUSES:
                continue
            merged.append(_task_to_history_entry(task))
            seen.add(task_id)
    except Exception as e:
        print(f"Warning: Failed to merge task_store history: {e}")
    return sorted(merged, key=_sort_history_key, reverse=True)


def get_history(limit: Optional[int] = None, enterprise_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get history records, most recent first."""
    history = _merge_task_store_entries(load_history_from_file())
    if enterprise_id is not None:
        history = [h for h in history
                   if h.get("enterprise_id") == enterprise_id]
    if limit is None:
        return history
    return history[:max(0, int(limit))]
