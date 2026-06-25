# -*- coding: utf-8 -*-
"""Status endpoint for task progress."""

from flask import Blueprint, jsonify

from ..auth_utils import login_required
from ._utils import get_enterprise_scope

status_bp = Blueprint("status", __name__)

tasks = {}


def set_tasks(tasks_dict):
    """Inject tasks dictionary from app.py."""
    global tasks
    tasks = tasks_dict


@status_bp.route("/status/<task_id>", methods=["GET"])
@login_required
def get_status(task_id):
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    task = tasks[task_id]

    # ── Enterprise isolation check ──
    ent_id, is_super = get_enterprise_scope()
    if not is_super and ent_id is not None:
        task_ent = task.get("enterprise_id")
        if task_ent is not None and task_ent != ent_id:
            return jsonify({"error": "Task not found"}), 404

    return jsonify(
        {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0),
            "pdf_name": task.get("pdf_name", ""),
        }
    )
