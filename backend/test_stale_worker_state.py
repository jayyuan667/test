"""
SSE lifecycle tests: ensure cancelled tasks close event streams.

Run: .venv/bin/pytest backend/test_stale_worker_state.py -v
"""

import json
import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from backend.app import app
from backend import auth_store


@pytest.fixture(autouse=True)
def setup_auth(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_sse_")
    os.close(fd)
    monkeypatch.setattr(auth_store, "DB_FILE", path)
    auth_store.init_auth_db()

    yield

    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login(client):
    auth_store.create_user("tester", generate_password_hash("password123"), "super_admin")
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "tester", "password": "password123"}),
        content_type="application/json",
    )
    return json.loads(resp.data)


def test_events_closes_for_cancelled_in_memory(client):
    """In-memory task with cancelled status must close SSE with error event."""
    _login(client)

    task_id = "cancelled-inmem-task"

    # Access the in-memory tasks dict from events module
    from backend.api import events as events_mod

    events_mod.tasks[task_id] = {
        "task_id": task_id,
        "pdf_name": "test.pdf",
        "status": "cancelled",
        "progress": 40,
    }
    events_mod.event_data[task_id] = []
    events_mod.event_locks[task_id] = None

    resp = client.get(f"/api/events/{task_id}", buffered=False)

    chunks = []
    try:
        for _ in range(10):
            chunk = resp.response.__next__()
            chunks.append(chunk.decode("utf-8"))
            if any("event: error" in c or "cancelled" in c.lower() for c in chunks):
                break
    finally:
        try:
            resp.close()
        except Exception:
            pass

    stream = "".join(chunks)
    assert resp.status_code == 200
    assert "cancelled" in stream.lower(), f"Expected cancelled in stream, got: {stream[:300]}"


def test_terminal_statuses_include_cancelled():
    """TERMINAL_STATUSES must include cancelled."""
    from backend.api.events import TERMINAL_STATUSES
    assert "cancelled" in TERMINAL_STATUSES
    assert "completed" in TERMINAL_STATUSES
    assert "error" in TERMINAL_STATUSES
