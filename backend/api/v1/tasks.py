"""Authenticated v1 task command and read endpoints."""

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ...auth_utils import login_required
from ...services.task_snapshot import build_task_snapshot
from ...services.task_event_stream import stream_v1_events
from ...services import legacy_task_commands
from ...task_store import build_task_dict, get_events, get_task
from .._utils import assert_task_access


tasks_v1_bp = Blueprint("tasks_v1", __name__)


def _snapshot(task_id):
    """Build a snapshot from persisted data plus richer live workflow state."""
    from ..upload import tasks

    persisted = build_task_dict(task_id)
    if persisted is None:
        return None
    task = {**persisted, **(tasks.get(task_id) or {})}
    stored = get_task(task_id)
    if stored is not None:
        task["updated_at"] = stored.get("updated_at")
    result = dict(task.get("result") or {})
    if task.get("review_text") is not None:
        result.setdefault("feature_text", task["review_text"])
    return build_task_snapshot(task_id, task, result)


def _error_response(result, task_id=None):
    status = result.status_code
    body = result.json()
    legacy_error = body.get("error")
    if status >= 500:
        code = "INTERNAL_ERROR"
        message = "Internal server error"
        details = {}
        retryable = False
        phase = None
    elif isinstance(legacy_error, dict):
        code = legacy_error.get("code", "COMMAND_FAILED")
        message = legacy_error.get("message", "Command failed")
        details = legacy_error.get("details", legacy_error.get("detail", {}))
        retryable = bool(legacy_error.get("retryable", False))
        phase = legacy_error.get("phase")
    else:
        code = "TASK_NOT_FOUND" if status == 404 else "INVALID_TASK_STATE"
        message = str(legacy_error or body.get("message") or "Command failed")
        details = {}
        retryable = False
        phase = None
    if phase is None and task_id:
        snapshot = _snapshot(task_id)
        phase = snapshot["task"]["phase"] if snapshot else None
    return jsonify({"error": {
        "code": code,
        "message": message,
        "retryable": retryable,
        "phase": phase,
        "details": details,
    }}), status


def _command_snapshot(task_id, response):
    if response.status_code >= 400:
        return _error_response(response, task_id)
    return jsonify(_snapshot(task_id)), response.status_code


@tasks_v1_bp.post("/tasks")
@login_required
def create_task():
    result = legacy_task_commands.create_task()
    if result.status_code >= 400:
        return _error_response(result)
    task_id = result.json()["task_id"]
    return jsonify(_snapshot(task_id)), 202


@tasks_v1_bp.post("/tasks/<task_id>/annotations/finalize")
@login_required
def finalize_task_annotations(task_id):
    return _command_snapshot(task_id, legacy_task_commands.finalize_annotations(task_id))


@tasks_v1_bp.post("/tasks/<task_id>/review")
@login_required
def review_task(task_id):
    return _command_snapshot(task_id, legacy_task_commands.review_task(task_id))


@tasks_v1_bp.post("/tasks/<task_id>/cancel")
@login_required
def cancel_task(task_id):
    return _command_snapshot(task_id, legacy_task_commands.cancel_task(task_id))


@tasks_v1_bp.route("/tasks/<task_id>/export", methods=["GET", "POST"])
@login_required
def export_task(task_id):
    result = legacy_task_commands.export_task(task_id)
    if result.status_code >= 400:
        return _error_response(result, task_id)
    return result.response


@tasks_v1_bp.get("/tasks/<task_id>")
@login_required
def get_task_snapshot(task_id):
    ok, error = assert_task_access(task_id)
    if not ok:
        return error
    snapshot = _snapshot(task_id)
    if snapshot is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(snapshot)


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
