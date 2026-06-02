# -*- coding: utf-8 -*-
"""Review session persistence and restoration helpers.

Extracted from backend/api/upload.py to keep route handlers thin.
"""
import json
import os
import threading

from ..config import OUTPUT_FOLDER


def _pending_review_file(task_id: str, output_dir: str = ""):
    base_dir = output_dir or os.path.join(OUTPUT_FOLDER, task_id)
    return os.path.join(base_dir, "pending_review.json")


def persist_review_payload(task: dict) -> None:
    """Write the current review-state snapshot to disk."""
    output_dir = task.get("output_dir") or os.path.join(OUTPUT_FOLDER, task.get("task_id", ""))
    if not output_dir:
        return
    os.makedirs(output_dir, exist_ok=True)
    payload = {
        "task_id": task.get("task_id"),
        "pdf_name": task.get("pdf_name"),
        "output_dir": output_dir,
        "prefix_hint": task.get("prefix_hint"),
        "png_paths": task.get("png_paths", []),
        "created_at": task.get("created_at", ""),
        "status": task.get("status", "awaiting_review"),
        "progress": task.get("progress", 50),
        "review_text": task.get("review_text") or "",
        "raw_review_text": task.get("raw_review_text") or "",
        "vision_descriptions": task.get("vision_descriptions") or [],
        "vision_failures": task.get("vision_failures") or [],
        "feature_report_json": task.get("feature_report_json") or {},
        "feature_report_text": task.get("feature_report_text") or "",
        "feature_report_path": task.get("feature_report_path") or "",
        "vlm_mode": task.get("vlm_mode") or "none",
        "step_path": task.get("step_path") or "",
        "creo_views_dir": task.get("creo_views_dir") or "",
        "creo_views_generated": task.get("creo_views_generated") or False,
        "creo_zhushi_path": task.get("creo_zhushi_path") or "",
        "creo_zhushi_text": task.get("creo_zhushi_text") or "",
        "flags": task.get("flags") or {},
    }
    with open(_pending_review_file(task.get("task_id", ""), output_dir), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_pending_review(task_id: str) -> dict | None:
    pending_file = _pending_review_file(task_id)
    if not os.path.exists(pending_file):
        return None
    with open(pending_file, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_pending_review(task_id: str, output_dir: str = ""):
    pending_file = _pending_review_file(task_id, output_dir)
    if os.path.exists(pending_file):
        os.remove(pending_file)


def restore_task_from_pending(task_id: str, tasks: dict, event_data: dict, event_locks: dict) -> dict | None:
    pending = load_pending_review(task_id)
    if not pending:
        return None
    restored = {
        "task_id": task_id,
        "pdf_name": pending.get("pdf_name", task_id),
        "output_dir": pending.get("output_dir") or os.path.join(OUTPUT_FOLDER, task_id),
        "prefix_hint": pending.get("prefix_hint"),
        "png_paths": pending.get("png_paths", []),
        "status": pending.get("status", "awaiting_review"),
        "progress": pending.get("progress", 50),
        "created_at": pending.get("created_at", ""),
        "review_event": threading.Event(),
        "review_text": pending.get("review_text") or "",
        "raw_review_text": pending.get("raw_review_text") or "",
        "vision_descriptions": pending.get("vision_descriptions") or [],
        "vision_failures": pending.get("vision_failures") or [],
        "feature_report_json": pending.get("feature_report_json") or {},
        "feature_report_text": pending.get("feature_report_text") or "",
        "feature_report_path": pending.get("feature_report_path") or "",
        "keep_after_complete": True,
        "restored_from_pending": True,
    }
    tasks[task_id] = restored
    if task_id not in event_data:
        event_data[task_id] = []
    if task_id not in event_locks:
        event_locks[task_id] = threading.Lock()
    return restored


def restore_task_from_result(task_id: str, tasks: dict, event_data: dict, event_locks: dict) -> dict | None:
    result_file = os.path.join(OUTPUT_FOLDER, task_id, "result.json")
    if not os.path.exists(result_file):
        return None

    with open(result_file, "r", encoding="utf-8") as f:
        result = json.load(f)

    output_dir = os.path.join(OUTPUT_FOLDER, task_id)

    from ..api._utils import extract_prefix_from_filename
    restored = {
        "task_id": task_id,
        "pdf_name": result.get("pdf_name", task_id),
        "output_dir": output_dir,
        "prefix_hint": extract_prefix_from_filename(result.get("pdf_name") or task_id),
        "png_paths": [],
        "status": result.get("status", "completed"),
        "progress": result.get("progress", 100),
        "created_at": result.get("created_at", ""),
        "review_event": threading.Event(),
        "review_text": result.get("review_text") or result.get("feature_report_text") or result.get("feature_report") or "",
        "raw_review_text": result.get("raw_review_text") or "",
        "vision_descriptions": result.get("vision_descriptions") or [],
        "vision_failures": result.get("vision_failures") or [],
        "feature_report_json": result.get("feature_report_json") or {},
        "feature_report_text": result.get("feature_report_text") or result.get("feature_report") or "",
        "feature_report_path": result.get("feature_report_path") or "",
        "library_key": result.get("library_key") or "public",
        "keep_after_complete": True,
        "restored_from_result": True,
        "result": result,
    }
    tasks[task_id] = restored
    if task_id not in event_data:
        event_data[task_id] = []
    if task_id not in event_locks:
        event_locks[task_id] = threading.Lock()
    return restored
