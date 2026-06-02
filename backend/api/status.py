# -*- coding: utf-8 -*-
"""Status endpoint for task progress."""

from flask import Blueprint, jsonify

status_bp = Blueprint("status", __name__)

tasks = {}


def set_tasks(tasks_dict):
    """Inject tasks dictionary from app.py."""
    global tasks
    tasks = tasks_dict


@status_bp.route("/status/<task_id>", methods=["GET"])
def get_status(task_id):
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    task = tasks[task_id]
    return jsonify(
        {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0),
            "pdf_name": task.get("pdf_name", ""),
        }
    )
