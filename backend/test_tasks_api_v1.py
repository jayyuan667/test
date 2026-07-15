import os
import io
import tempfile
import threading

import pytest
from werkzeug.security import generate_password_hash

from backend import auth_store, task_store
from backend.app import app


@pytest.fixture
def client(monkeypatch):
    auth_fd, auth_path = tempfile.mkstemp(suffix=".db")
    task_fd, task_path = tempfile.mkstemp(suffix=".db")
    os.close(auth_fd)
    os.close(task_fd)
    monkeypatch.setattr(auth_store, "DB_FILE", auth_path)
    monkeypatch.setattr(task_store, "DB_FILE", task_path)
    auth_store.init_auth_db()
    task_store.init_db()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
    os.unlink(auth_path)
    os.unlink(task_path)


def _enterprise_user(name):
    enterprise = auth_store.create_enterprise(name)
    auth_store.create_user(
        f"{name}-user",
        generate_password_hash("secret"),
        enterprise_id=enterprise["id"],
    )
    return enterprise


def _login(client, name):
    response = client.post(
        "/api/auth/login", json={"username": f"{name}-user", "password": "secret"}
    )
    assert response.status_code == 200


def test_snapshot_requires_login(client):
    assert client.get("/api/v1/tasks/missing").status_code == 401


def test_owned_task_returns_v1_snapshot(client):
    enterprise = _enterprise_user("owned")
    task_store.insert_task("task-owned", pdf_name="drawing.pdf", enterprise_id=enterprise["id"])
    _login(client, "owned")

    response = client.get("/api/v1/tasks/task-owned")

    assert response.status_code == 200
    assert response.get_json()["schema_version"] == "1.0"


def test_snapshot_maps_persisted_result_and_preserves_full_envelope(client):
    enterprise = _enterprise_user("result")
    task_store.insert_task("task-result", pdf_name="drawing.pdf", enterprise_id=enterprise["id"])
    task_store.save_result("task-result", {
        "features": [{"id": "feature-1", "kind": "hole", "label": "M8"}],
        "process_operations": [["10", "车削", "粗车", "CNC", "5min"]],
    })
    _login(client, "result")

    snapshot = client.get("/api/v1/tasks/task-result").get_json()

    assert set(snapshot) == {
        "schema_version", "task", "drawing", "features", "review",
        "process_operations", "reuse_candidates", "capabilities",
    }
    assert snapshot["features"][0]["id"] == "feature-1"
    assert snapshot["process_operations"][0]["code"] == "10"
    assert snapshot["task"]["updated_at"] is not None


def test_snapshot_route_preserves_persisted_updated_at(client):
    enterprise = _enterprise_user("timestamp")
    task_store.insert_task("task-time", pdf_name="drawing.pdf", enterprise_id=enterprise["id"])
    persisted = task_store.get_task("task-time")
    _login(client, "timestamp")
    assert client.get("/api/v1/tasks/task-time").get_json()["task"]["updated_at"] == persisted["updated_at"]


def test_snapshot_revision_increases_with_persisted_events(client):
    enterprise = _enterprise_user("revision")
    task_store.insert_task("task-revision", pdf_name="drawing.pdf", enterprise_id=enterprise["id"])
    _login(client, "revision")
    before = client.get("/api/v1/tasks/task-revision").get_json()["task"]["revision"]
    task_store.add_event("task-revision", "annotation_required", data={"pages": 1})
    after = client.get("/api/v1/tasks/task-revision").get_json()["task"]["revision"]
    assert after > before


def test_other_enterprise_task_is_hidden(client):
    owner = _enterprise_user("owner")
    _enterprise_user("outsider")
    task_store.insert_task("task-secret", pdf_name="secret.pdf", enterprise_id=owner["id"])
    _login(client, "outsider")

    assert client.get("/api/v1/tasks/task-secret").status_code == 404


def test_upload_drawing_returns_initial_v1_snapshot(client, monkeypatch):
    _enterprise_user("uploader")
    _login(client, "uploader")
    monkeypatch.setattr("backend.api.upload.threading.Thread.start", lambda self: None)

    response = client.post(
        "/api/v1/tasks",
        data={"file": (io.BytesIO(b"\x89PNG\r\n\x1a\n"), "drawing.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 202
    snapshot = response.get_json()
    assert snapshot["schema_version"] == "1.0"
    assert snapshot["drawing"]["name"] == "drawing.png"


def _live_task(enterprise, task_id, status):
    from backend.api import upload as upload_api

    task_store.insert_task(
        task_id, pdf_name="drawing.png", enterprise_id=enterprise["id"]
    )
    task_store.update_task_status(task_id, status, 35)
    task = {
        "task_id": task_id,
        "pdf_name": "drawing.png",
        "status": status,
        "progress": 35,
        "enterprise_id": enterprise["id"],
        "annotation_event": threading.Event(),
        "review_event": threading.Event(),
    }
    upload_api.tasks[task_id] = task
    return task


def test_finalize_annotations_returns_updated_snapshot(client):
    enterprise = _enterprise_user("annotator")
    task = _live_task(enterprise, "task-annotation", "awaiting_annotation")
    _login(client, "annotator")

    response = client.post("/api/v1/tasks/task-annotation/annotations/finalize")

    assert response.status_code == 200
    assert task["annotation_event"].is_set()
    assert response.get_json()["task"]["id"] == "task-annotation"


def test_review_returns_updated_snapshot(client):
    enterprise = _enterprise_user("reviewer")
    task = _live_task(enterprise, "task-review", "awaiting_review")
    _login(client, "reviewer")

    response = client.post(
        "/api/v1/tasks/task-review/review", json={"review_text": "confirmed"}
    )

    assert response.status_code == 200
    assert task["review_event"].is_set()
    assert response.get_json()["review"]["raw_text"] == "confirmed"


def test_cancel_returns_cancelled_snapshot(client):
    enterprise = _enterprise_user("canceller")
    _live_task(enterprise, "task-cancel", "processing")
    _login(client, "canceller")

    response = client.post("/api/v1/tasks/task-cancel/cancel")

    assert response.status_code == 200
    assert response.get_json()["task"]["state"] == "cancelled"


def test_export_delegates_to_existing_export_behavior(client, monkeypatch):
    enterprise = _enterprise_user("exporter")
    _live_task(enterprise, "task-export", "completed")
    _login(client, "exporter")
    monkeypatch.setattr(
        "backend.api.export.export_result", lambda task_id: (b"workbook", 200)
    )

    response = client.get("/api/v1/tasks/task-export/export?format=xlsx")

    assert response.status_code == 200
    assert response.data == b"workbook"


def test_command_errors_use_exact_v1_envelope(client):
    _enterprise_user("missing-command")
    _login(client, "missing-command")

    response = client.post("/api/v1/tasks/missing/cancel")

    assert response.status_code == 404
    error = response.get_json()["error"]
    assert set(error) == {"code", "message", "retryable", "phase", "details"}
    assert error["code"] == "TASK_NOT_FOUND"


def test_post_export_uses_real_handler_with_edited_rows(client, monkeypatch):
    enterprise = _enterprise_user("post-exporter")
    task = _live_task(enterprise, "task-post-export", "completed")
    task["result"] = {"process_flow": {"data": [["old", "old"]]}}
    _login(client, "post-exporter")
    captured = {}

    def fake_excel(task_id, result_data):
        captured["task_id"] = task_id
        captured["rows"] = result_data["process_flow"]["data"]
        return b"serialized-workbook"

    monkeypatch.setattr("backend.api.export._excel_response", fake_excel)
    rows = [["0050", "车工", "粗车外圆"]]

    response = client.post(
        "/api/v1/tasks/task-post-export/export?format=xlsx", json={"rows": rows}
    )

    assert response.status_code == 200
    assert response.data == b"serialized-workbook"
    assert captured == {"task_id": "task-post-export", "rows": rows}


@pytest.mark.parametrize("command", [
    "annotations/finalize", "review", "cancel", "export",
])
def test_commands_hide_cross_enterprise_tasks_without_mutation(client, command):
    owner = _enterprise_user(f"owner-{command.replace('/', '-')}")
    _enterprise_user(f"outsider-{command.replace('/', '-')}")
    status = "awaiting_annotation" if command.startswith("annotations") else "awaiting_review"
    task = _live_task(owner, f"secret-{command.replace('/', '-')}", status)
    original_status = task["status"]
    _login(client, f"outsider-{command.replace('/', '-')}")

    response = client.post(
        f"/api/v1/tasks/{task['task_id']}/{command}",
        json={"review_text": "must-not-apply", "rows": [["mutated"]]},
    )

    assert response.status_code == 404
    assert task["status"] == original_status
    assert not task["annotation_event"].is_set()
    assert not task["review_event"].is_set()
    assert task.get("review_text") is None


@pytest.mark.parametrize("status,legacy_body,expected_code", [
    (400, {"error": "bad state"}, "INVALID_TASK_STATE"),
    (403, {"error": {"code": "QUOTA_EXCEEDED", "message": "quota"}}, "QUOTA_EXCEEDED"),
    (409, {"error": "already completed"}, "INVALID_TASK_STATE"),
    (500, {"error": "/private/tmp/secret traceback.py:9 boom"}, "INTERNAL_ERROR"),
])
def test_command_error_contract_and_internal_sanitization(
    client, monkeypatch, status, legacy_body, expected_code
):
    from backend.services.legacy_task_commands import CommandResult

    enterprise = _enterprise_user(f"errors-{status}")
    _live_task(enterprise, f"task-error-{status}", "awaiting_review")
    _login(client, f"errors-{status}")
    with app.app_context():
        response = app.make_response((legacy_body, status))
    monkeypatch.setattr(
        "backend.services.legacy_task_commands.cancel_task",
        lambda task_id: CommandResult(response),
    )

    result = client.post(f"/api/v1/tasks/task-error-{status}/cancel")

    assert result.status_code == status
    error = result.get_json()["error"]
    assert set(error) == {"code", "message", "retryable", "phase", "details"}
    assert error["code"] == expected_code
    assert error["phase"] == "feature_review"
    assert error["retryable"] is False
    if status == 500:
        assert error["message"] == "Internal server error"
        assert "secret" not in result.get_data(as_text=True)
    else:
        expected_message = legacy_body["error"]
        if isinstance(expected_message, dict):
            expected_message = expected_message["message"]
        assert error["message"] == expected_message
