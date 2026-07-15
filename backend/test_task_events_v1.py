import json
import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from backend import auth_store, task_store
from backend.app import app
from backend.services.task_event_stream import normalize_event, pack_v1_sse


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
    enterprise = auth_store.create_enterprise("events")
    auth_store.create_user(
        "events-user",
        generate_password_hash("secret"),
        enterprise_id=enterprise["id"],
    )
    task_store.insert_task("task-events", pdf_name="drawing.pdf", enterprise_id=enterprise["id"])
    response = app.test_client().post(
        "/api/auth/login", json={"username": "events-user", "password": "secret"}
    )
    assert response.status_code == 200
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        test_client.post(
            "/api/auth/login", json={"username": "events-user", "password": "secret"}
        )
        yield test_client
    os.unlink(auth_path)
    os.unlink(task_path)


def test_normalize_event_uses_database_id_as_sequence():
    event = normalize_event(
        "task-1",
        {"id": 7, "type": "step_start", "step": 2, "message": "分析", "data": None,
         "created_at": "2026-07-15T10:00:00"},
    )

    assert event["seq"] == 7
    assert event["type"] == "phase_started"
    assert event["schema_version"] == "1.0"


def test_pack_v1_sse_includes_id_event_and_json_data():
    event = normalize_event(
        "task-1", {"id": 7, "type": "complete", "data": json.dumps({"progress": 100})}
    )

    chunk = pack_v1_sse(event)

    assert chunk.startswith("id: 7\nevent: task_completed\ndata: ")
    assert json.loads(chunk.split("data: ", 1)[1]) == event


def test_events_route_replays_only_ids_after_cursor(client):
    task_store.save_event("task-events", "step_start", {"phase": "drawing_analysis"})
    task_store.save_event("task-events", "step_complete", {"phase": "drawing_analysis"})
    task_store.save_event("task-events", "process_stream", {"operation": {"id": "op-1"}})
    task_store.update_task_status("task-events", "completed", 100)

    response = client.get("/api/v1/tasks/task-events/events?after=2")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "retry: 1500" in body
    assert "id: 1\n" not in body
    assert "id: 2\n" not in body
    assert body.count("id: 3\n") == 1
    assert "event: operation_upserted" in body
