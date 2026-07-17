# -*- coding: utf-8 -*-
"""Status endpoint for task progress."""

from flask import Blueprint, jsonify

from ..auth_utils import login_required
from ._utils import assert_task_access

status_bp = Blueprint("status", __name__)

tasks = {}


def set_tasks(tasks_dict):
    """Inject tasks dictionary from app.py."""
    global tasks
    tasks = tasks_dict


@status_bp.route("/status/<task_id>", methods=["GET"])
@login_required
def get_status(task_id):
    ok, err = assert_task_access(task_id)
    if not ok:
        return err

    from ..task_store import get_task

    # SQLite is authoritative across gunicorn workers. A different worker may
    # still have an older in-memory snapshot for the same task.
    task = get_task(task_id) or tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(
        {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0),
            "pdf_name": task.get("pdf_name", ""),
        }
    )
