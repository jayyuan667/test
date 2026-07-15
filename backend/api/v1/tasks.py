"""Authenticated v1 task read endpoints."""

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ...auth_utils import login_required
from ...services.task_snapshot import build_task_snapshot
from ...services.task_event_stream import stream_v1_events
from ...task_store import build_task_dict, get_events, get_task
from .._utils import assert_task_access


tasks_v1_bp = Blueprint("tasks_v1", __name__)


@tasks_v1_bp.get("/tasks/<task_id>")
@login_required
def get_task_snapshot(task_id):
    ok, error = assert_task_access(task_id)
    if not ok:
        return error
    task = build_task_dict(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(build_task_snapshot(task_id, task))


@tasks_v1_bp.get("/tasks/<task_id>/events")
@login_required
def get_task_events(task_id):
    ok, error = assert_task_access(task_id)
    if not ok:
        return error
    raw_after = request.args.get("after", request.headers.get("Last-Event-ID", "0"))
    try:
        after = max(0, int(raw_after))
    except (TypeError, ValueError):
        return jsonify({"error": "after must be a non-negative integer"}), 400
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    }
    return Response(
        stream_with_context(stream_v1_events(task_id, after, get_events, get_task)),
        content_type="text/event-stream; charset=utf-8",
        headers=headers,
    )
