# -*- coding: utf-8 -*-
"""Result endpoint for getting task results."""

import os
import json
from flask import Blueprint, jsonify, send_from_directory

from ..auth_utils import login_required
from ..config import OUTPUT_FOLDER, KB_PREVIEW_FOLDER
from ._response import fail, ERR_TASK_NOT_FOUND
from ._utils import get_enterprise_scope


def _pending_review_file(task_id: str):
    return os.path.join(OUTPUT_FOLDER, task_id, "pending_review.json")

result_bp = Blueprint("result", __name__)

tasks = {}


def _result_dir(task_id: str):
    if task_id.startswith("kb_"):
        return os.path.join(KB_PREVIEW_FOLDER, task_id)
    return os.path.join(OUTPUT_FOLDER, task_id)


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _collect_image_files(task_id: str, task_data: dict | None = None):
    seen = set()
    image_files = []

    result_dir = _result_dir(task_id)
    for path in (task_data or {}).get("png_paths", []) or []:
        if not path:
            continue
        filename = os.path.relpath(path, result_dir)
        if filename.lower().endswith(IMAGE_EXTS) and filename not in seen:
            seen.add(filename)
            image_files.append(filename)

    if os.path.isdir(result_dir):
        # Top-level images first
        for filename in sorted(os.listdir(result_dir)):
            if filename.lower().endswith(IMAGE_EXTS) and filename not in seen:
                seen.add(filename)
                image_files.append(filename)
        # Subdirectory: pages (common for PDF page renders)
        pages_dir = os.path.join(result_dir, "pages")
        if os.path.isdir(pages_dir):
            for filename in sorted(os.listdir(pages_dir)):
                if filename.lower().endswith(IMAGE_EXTS) and filename not in seen:
                    seen.add(filename)
                    image_files.append("pages/" + filename)
        # Subdirectory: creo_views (common for Creo screenshots)
        creo_dir = os.path.join(result_dir, "creo_views")
        if os.path.isdir(creo_dir):
            for filename in sorted(os.listdir(creo_dir)):
                if filename.lower().endswith(IMAGE_EXTS) and filename not in seen:
                    seen.add(filename)
                    image_files.append("creo_views/" + filename)

    return image_files


def _build_preview_urls(task_id: str, task_data: dict | None = None):
    files = _collect_image_files(task_id, task_data)
    return [f"/api/result/{task_id}/asset/{filename}" for filename in files]


def _enrich_result_payload(task_id: str, payload: dict, task_data: dict | None = None):
    result = dict(payload or {})
    preview_urls = _build_preview_urls(task_id, task_data)
    result["task_id"] = result.get("task_id") or task_id
    result["preview_image_urls"] = preview_urls
    result["preview_images"] = [os.path.basename(url) for url in preview_urls]
    result["image_url"] = preview_urls[0] if preview_urls else result.get("image_url", "")
    result["png_count"] = result.get("png_count") or len(preview_urls)
    return result


def set_tasks(tasks_dict):
    """Inject tasks dictionary from app.py."""
    global tasks
    tasks = tasks_dict


@result_bp.route("/result/<task_id>", methods=["GET"])
@login_required
def get_result(task_id):
    # 1. Check in-memory cache
    if task_id in tasks:
        task = tasks[task_id]
        # ── Enterprise isolation check ──
        ent_id, is_super = get_enterprise_scope()
        if not is_super and ent_id is not None:
            task_ent = task.get("enterprise_id")
            if task_ent is not None and task_ent != ent_id:
                return jsonify({"error": "Task not found"}), 404
        if task.get("status") != "completed":
            return jsonify(
                _enrich_result_payload(task_id, {
                    "status": task.get("status"),
                    "progress": task.get("progress"),
                    "message": "Processing not completed",
                    "pdf_name": task.get("pdf_name", task_id),
                    "source_name": task.get("source_name", task.get("pdf_name", task_id)),
                    "review_text": task.get("review_text") or "",
                    "feature_report": task.get("review_text") or "",
                    "raw_review_text": task.get("raw_review_text") or "",
                    "vision_descriptions": task.get("vision_descriptions") or [],
                    "vision_failures": task.get("vision_failures") or [],
                }, task)
            )
        return jsonify(_enrich_result_payload(task_id, task.get("result", {}), task))

    # 2. Read from persistent store (SQLite)
    try:
        from ..task_store import build_task_dict
    except ImportError:
        from backend.task_store import build_task_dict
    db_task = build_task_dict(task_id)
    if db_task:
        # ── Enterprise isolation check (SQLite path) ──
        ent_id, is_super = get_enterprise_scope()
        if not is_super and ent_id is not None:
            task_ent = db_task.get("enterprise_id")
            if task_ent is not None and task_ent != ent_id:
                return jsonify({"error": "Task not found"}), 404
        return jsonify(_enrich_result_payload(task_id, db_task.get("result", {}), db_task))

    # 3. Fall back to file-based result.json

    result_file = os.path.join(OUTPUT_FOLDER, task_id, "result.json")
    if os.path.exists(result_file):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                result_data = json.load(f)
            # ── Enterprise isolation check ──
            ent_id, is_super = get_enterprise_scope()
            if not is_super and ent_id is not None:
                task_ent = result_data.get("enterprise_id")
                if task_ent is not None and int(task_ent) != ent_id:
                    return jsonify({"error": "Task not found"}), 404
            return jsonify(_enrich_result_payload(task_id, result_data))
        except Exception as e:
            return fail("INTERNAL_ERROR", f"Failed to read result file: {str(e)}", 500)

    pending_file = _pending_review_file(task_id)
    if os.path.exists(pending_file):
        try:
            with open(pending_file, "r", encoding="utf-8") as f:
                pending_data = json.load(f)
            # ── Enterprise isolation check ──
            ent_id, is_super = get_enterprise_scope()
            if not is_super and ent_id is not None:
                task_ent = pending_data.get("enterprise_id")
                if task_ent is not None and int(task_ent) != ent_id:
                    return jsonify({"error": "Task not found"}), 404
            return jsonify(
                _enrich_result_payload(task_id, {
                    "task_id": task_id,
                    "status": pending_data.get("status", "awaiting_review"),
                    "progress": pending_data.get("progress", 50),
                    "message": "Waiting for review",
                    "review_text": pending_data.get("review_text", ""),
                    "feature_report": pending_data.get("review_text", ""),
                    "raw_review_text": pending_data.get("raw_review_text", ""),
                    "vision_descriptions": pending_data.get("vision_descriptions", []),
                    "vision_failures": pending_data.get("vision_failures", []),
                    "pdf_name": pending_data.get("pdf_name", task_id),
                }, pending_data)
            )
        except Exception as e:
            return fail("INTERNAL_ERROR", f"Failed to read pending review file: {str(e)}", 500)

    return fail(ERR_TASK_NOT_FOUND, "Task not found", 404)


@result_bp.route("/result/<task_id>/asset/<path:filename>", methods=["GET"])
@login_required
def get_result_asset(task_id, filename):
    result_dir = _result_dir(task_id)
    file_path = os.path.join(result_dir, filename)
    if not os.path.isfile(file_path):
        return fail(ERR_TASK_NOT_FOUND, "Asset not found", 404)
    resp = send_from_directory(result_dir, filename)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    if ext in mime_map:
        resp.headers["Content-Type"] = mime_map[ext]
    return resp
