# -*- coding: utf-8 -*-
"""History file operations for the PDF Process Analysis System."""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history.json"
)


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


def get_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get history records, most recent first."""
    history = load_history_from_file()
    if limit is None:
        return history
    return history[:max(0, int(limit))]
