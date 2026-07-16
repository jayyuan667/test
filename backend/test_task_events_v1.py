import json
import os
import tempfile
import threading

import pytest
from werkzeug.security import generate_password_hash

from backend import auth_store, task_store
from backend.app import app
from backend.services.event_emitter import emit_complete, emit_custom, emit_image_ready, emit_log
from backend.services.task_event_stream import (
    V1_EVENT_TYPES,
    ensure_canonical_terminal_event,
    normalize_event,
    pack_v1_sse,
    stream_v1_events,
)


@pytest.fixture
def dbs(monkeypatch):
    auth_fd, auth_path = tempfile.mkstemp(suffix=".db")
    task_fd, task_path = tempfile.mkstemp(suffix=".db")
    os.close(auth_fd)
    os.close(task_fd)
    monkeypatch.setattr(auth_store, "DB_FILE", auth_path)
    monkeypatch.setattr(task_store, "DB_FILE", task_path)
    auth_store.init_auth_db()
    task_store.init_db()
    owner = auth_store.create_enterprise("owner")
    outsider = auth_store.create_enterprise("outsider")
    for name, enterprise in (("owner", owner), ("outsider", outsider)):
        auth_store.create_user(
            name, generate_password_hash("secret"), enterprise_id=enterprise["id"]
        )
    task_store.insert_task("task-events", pdf_name="drawing.pdf", enterprise_id=owner["id"])
    app.config["TESTING"] = True
    yield {"owner": owner, "outsider": outsider}
    os.unlink(auth_path)
    os.unlink(task_path)


def _login(client, username="owner"):
    assert client.post(
        "/api/auth/login", json={"username": username, "password": "secret"}
    ).status_code == 200


def _sse_events(body):
    return [
        json.loads(block.split("data: ", 1)[1])
        for block in body.split("\n\n")
        if "data: " in block
    ]


def _memory_terminal_ensure(rows):
    def ensure(_task_id, status):
        for row in rows:
            if row["type"] in {"complete", "error"}:
                return row
        row = {
            "id": max((item["id"] for item in rows), default=0) + 1,
            "type": "error" if status in {"error", "failed", "cancelled"} else "complete",
            "data": json.dumps({"canonical": True}),
        }
        rows.append(row)
        return row
    return ensure


def test_events_route_requires_login_and_hides_other_enterprise(dbs):
    with app.test_client() as client:
        assert client.get("/api/v1/tasks/task-events/events").status_code == 401
        _login(client, "outsider")
        assert client.get("/api/v1/tasks/task-events/events").status_code == 404


@pytest.mark.parametrize(
    ("legacy_type", "v1_type"),
    [
        ("step_start", "phase_started"),
        ("step_complete", "phase_completed"),
        ("image_ready", "feature_ready"),
        ("log", "phase_progress"),
        ("yolo_progress", "phase_progress"),
        ("preview_updated", "feature_ready"),
        ("review_required", "phase_progress"),
        ("annotation_required", "phase_progress"),
        ("unexpected_plugin_event", "phase_progress"),
    ],
)
def test_all_legacy_types_adapt_to_approved_v1_types(legacy_type, v1_type):
    normalized = normalize_event("task", {"id": 1, "type": legacy_type, "data": "{}"})
    assert normalized["type"] == v1_type
    assert normalized["type"] in V1_EVENT_TYPES
    assert normalized["phase"] in {"upload", "drawing_analysis", "annotation", "feature_review", "process_generation", "export", "done"}
    assert isinstance(normalized["progress"], (int, float))
    assert 0 <= normalized["progress"] <= 100
    if legacy_type not in {"step_start", "step_complete"}:
        assert normalized["payload"]["legacy_type"] == legacy_type


def test_sparse_real_events_still_have_non_nullable_canonical_positions():
    expected = {
        "image_ready": ("drawing_analysis", 35),
        "preview_updated": ("annotation", 45),
        "log": ("drawing_analysis", 5),
        "yolo_progress": ("drawing_analysis", 30),
        "unexpected_plugin_event": ("drawing_analysis", 0),
    }
    for index, (legacy_type, position) in enumerate(expected.items(), start=1):
        event = normalize_event("task", {"id": index, "type": legacy_type, "data": "{}"})
        assert (event["phase"], event["progress"]) == position


def test_process_stream_chunk_is_progress_not_operation():
    event = normalize_event(
        "task", {"id": 2, "type": "process_stream", "data": json.dumps({"chunk": "10 | 车削"})}
    )
    assert event["type"] == "phase_progress"
    assert event["payload"]["legacy_type"] == "process_stream"
    assert event["payload"]["process_chunk"] == "10 | 车削"


def test_process_stream_does_not_fabricate_operation_from_identifier_only():
    event = normalize_event(
        "task", {"id": 3, "type": "process_stream", "data": json.dumps({"operation": {"id": "op-empty"}})}
    )
    assert event["type"] == "phase_progress"
    assert "operation" not in event["payload"]
    assert event["payload"]["legacy_type"] == "process_stream"


def test_payload_normalization_does_not_mutate_input_dict():
    payload = {"phase": "drawing_analysis"}
    normalize_event("task", {"id": 1, "type": "log", "data": payload, "message": "hello"})
    assert payload == {"phase": "drawing_analysis"}


def test_real_legacy_event_sequence_derives_monotonic_canonical_progress():
    rows = [
        {"id": 1, "type": "step_start", "data": json.dumps({"step": 1, "name": "图纸解析"})},
        {"id": 2, "type": "log", "data": json.dumps({"step": 1, "message": "第 1/1 页已转换"})},
        {"id": 3, "type": "step_complete", "data": json.dumps({"step": 1, "name": "图纸解析"})},
        {"id": 4, "type": "annotation_required", "data": json.dumps({"pages": 1})},
        {"id": 5, "type": "review_required", "data": json.dumps({"feature_text": "M115×3-6g"})},
        {"id": 6, "type": "process_stream", "data": json.dumps({"chunk": "0010 | 下料"})},
        {"id": 7, "type": "complete", "data": json.dumps({"message": "处理完成"})},
    ]
    events = [normalize_event("task-real", row) for row in rows]

    assert [event["phase"] for event in events] == [
        "drawing_analysis", "drawing_analysis", "drawing_analysis", "annotation",
        "feature_review", "process_generation", "done",
    ]
    assert [event["progress"] for event in events] == [5, 5, 20, 45, 60, 75, 100]


def test_failed_event_preserves_structured_error_and_checkpoint():
    event = normalize_event("task", {
        "id": 9, "type": "error", "data": json.dumps({
            "message": "VLM timeout", "retryable": True, "phase": "drawing_analysis",
            "progress": 38, "checkpoint": "page-2",
        }),
    })

    assert event["type"] == "task_failed"
    assert event["phase"] == "drawing_analysis"
    assert event["progress"] == 38
    assert event["payload"]["checkpoint"] == "page-2"
    assert event["payload"]["error"] == {
        "code": "TASK_FAILED", "message": "VLM timeout", "retryable": True,
        "phase": "drawing_analysis", "details": {"checkpoint": "page-2"},
    }


def test_pack_v1_sse_has_full_envelope():
    event = normalize_event(
        "task-1",
        {"id": 7, "type": "complete", "data": "{}", "created_at": "2026-07-15T10:00:00"},
    )
    chunk = pack_v1_sse(event)
    assert chunk.startswith("id: 7\nevent: task_completed\ndata: ")
    assert set(json.loads(chunk.split("data: ", 1)[1])) == {
        "schema_version", "seq", "task_id", "type", "phase", "progress", "timestamp", "payload"
    }


def test_terminal_status_without_stored_terminal_ensures_canonical_once():
    rows = [{"id": 4, "type": "log", "data": "{}"}]
    chunks = list(stream_v1_events("task", 0, lambda _id, since_id=0: [r for r in rows if r["id"] > since_id], lambda _id: {"status": "completed"}, sleep_fn=lambda _: None, ensure_terminal_fn=_memory_terminal_ensure(rows)))
    assert sum("event: task_completed" in chunk for chunk in chunks) == 1
    assert any("id: 5" in chunk for chunk in chunks)


def test_stored_terminal_is_emitted_once_without_synthesis():
    rows = [
        {"id": 4, "type": "log", "data": "{}"},
        {"id": 5, "type": "complete", "data": "{}"},
        {"id": 6, "type": "complete", "data": "{}"},
    ]
    chunks = list(stream_v1_events("task", 0, lambda _id, since_id=0: [r for r in rows if r["id"] > since_id], lambda _id: {"status": "completed"}, sleep_fn=lambda _: None))
    assert sum("event: task_completed" in chunk for chunk in chunks) == 1


def test_duplicate_db_terminals_emit_earliest_once_and_not_on_reconnect():
    rows = [
        {"id": 5, "type": "complete", "data": "{}"},
        {"id": 6, "type": "complete", "data": "{}"},
    ]
    get_events = lambda _id, since_id=0: [row for row in rows if row["id"] > since_id]
    first = list(stream_v1_events("task", 0, get_events, lambda _id: {"status": "completed"}, sleep_fn=lambda _: None))
    reconnect = list(stream_v1_events("task", 5, get_events, lambda _id: {"status": "completed"}, sleep_fn=lambda _: None))
    assert sum("event: task_completed" in chunk for chunk in first) == 1
    assert any("id: 5" in chunk for chunk in first)
    assert sum("event: task_completed" in chunk for chunk in reconnect) == 0


def test_terminal_status_before_save_is_drained_during_grace_read():
    calls = 0
    rows = [{"id": 1, "type": "log", "data": "{}"}]

    def get_events(_task_id, since_id=0):
        nonlocal calls
        calls += 1
        if calls == 3:
            rows.append({"id": 2, "type": "complete", "data": "{}"})
        return [row for row in rows if row["id"] > since_id]

    chunks = list(stream_v1_events("task", 0, get_events, lambda _id: {"status": "completed"}, sleep_fn=lambda _: None))
    assert sum("event: task_completed" in chunk for chunk in chunks) == 1
    assert any("id: 2" in chunk for chunk in chunks)


def test_reconnect_after_synthetic_terminal_does_not_duplicate():
    rows = [{"id": 4, "type": "log", "data": "{}"}]
    get_events = lambda _id, since_id=0: [r for r in rows if r["id"] > since_id]
    ensure = _memory_terminal_ensure(rows)
    first = list(stream_v1_events("task", 0, get_events, lambda _id: {"status": "completed"}, sleep_fn=lambda _: None, ensure_terminal_fn=ensure))
    second = list(stream_v1_events("task", 5, get_events, lambda _id: {"status": "completed"}, sleep_fn=lambda _: None, ensure_terminal_fn=ensure))
    assert sum("event: task_completed" in chunk for chunk in first) == 1
    assert sum("event: task_completed" in chunk for chunk in second) == 0


def test_reconnect_does_not_duplicate_when_stored_terminal_claims_synthetic_seq():
    rows = [
        {"id": 4, "type": "log", "data": "{}"},
        {"id": 5, "type": "complete", "data": "{}"},
    ]
    chunks = list(stream_v1_events(
        "task", 5,
        lambda _id, since_id=0: [row for row in rows if row["id"] > since_id],
        lambda _id: {"status": "completed"},
        sleep_fn=lambda _: None,
    ))
    assert sum("event: task_completed" in chunk for chunk in chunks) == 0


def test_canonical_terminal_persists_and_suppresses_later_terminal_on_reconnect(dbs):
    task_store.save_event("task-events", "log", {"message": "before"})
    task_store.update_task_status("task-events", "completed", 100)
    with app.test_client() as client:
        _login(client)
        first = _sse_events(client.get("/api/v1/tasks/task-events/events").get_data(as_text=True))
    terminal = next(event for event in first if event["type"] == "task_completed")
    task_store.save_event("task-events", "log", {"message": "after"})
    task_store.save_event("task-events", "complete", {"message": "late real terminal"})
    with app.test_client() as client:
        _login(client)
        replay = _sse_events(client.get(
            f"/api/v1/tasks/task-events/events?after={terminal['seq']}"
        ).get_data(as_text=True))
    assert sum(event["type"] in {"task_completed", "task_failed"} for event in replay) == 0
    assert [event["payload"].get("message") for event in replay] == ["after"]
    stored = task_store.get_events("task-events")
    assert stored[terminal["seq"] - 1]["type"] == "complete"


def test_concurrent_canonical_terminal_ensure_inserts_once(dbs):
    task_store.update_task_status("task-events", "completed", 100)
    barrier = threading.Barrier(3)
    results = []

    def ensure():
        barrier.wait()
        results.append(ensure_canonical_terminal_event("task-events", "completed"))

    threads = [threading.Thread(target=ensure) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    terminal_rows = [row for row in task_store.get_events("task-events") if row["type"] in {"complete", "error"}]
    assert len(terminal_rows) == 1
    assert {result["id"] for result in results} == {terminal_rows[0]["id"]}


def test_real_emitter_db_chain_normalizes_legal_increasing_events(dbs):
    memory = {"task-events": []}
    locks = {"task-events": threading.Lock()}
    emit_image_ready("task-events", memory, locks, 1, 1, "/tmp/page.png")
    emit_log("task-events", memory, locks, 1, "working")
    emit_custom("task-events", memory, locks, "process_stream", {"chunk": "10 | 车削"})
    emit_complete("task-events", memory, locks)
    rows = task_store.get_events("task-events")
    normalized = [normalize_event("task-events", row) for row in rows]
    assert [event["seq"] for event in normalized] == sorted({event["seq"] for event in normalized})
    assert all(event["type"] in V1_EVENT_TYPES for event in normalized)
    assert normalized[2]["type"] == "phase_progress"
    assert normalized[-1]["type"] == "task_completed"


def test_real_legacy_chain_replays_through_v1_route(dbs):
    memory = {"task-events": []}
    locks = {"task-events": threading.Lock()}
    emit_log("task-events", memory, locks, 1, "working")
    emit_custom("task-events", memory, locks, "annotation_required", {"pages": 1})
    emit_complete("task-events", memory, locks)
    task_store.update_task_status("task-events", "completed", 100)
    with app.test_client() as client:
        _login(client)
        response = client.get("/api/v1/tasks/task-events/events")
        events = _sse_events(response.get_data(as_text=True))
    assert response.status_code == 200
    assert [event["seq"] for event in events] == sorted(event["seq"] for event in events)
    assert all(event["type"] in V1_EVENT_TYPES for event in events)
    assert sum(event["type"] in {"task_completed", "task_failed"} for event in events) == 1


def test_legacy_events_route_still_responds(dbs):
    task_store.update_task_status("task-events", "completed", 100)
    with app.test_client() as client:
        _login(client)
        response = client.get("/api/events/task-events")
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"


def test_route_supports_query_and_last_event_id_and_malformed_json(dbs):
    task_store.save_event("task-events", "log", {"message": "one"})
    task_store.save_event("task-events", "log", {"message": "two"})
    with task_store._conn() as connection:
        connection.execute("INSERT INTO task_events (task_id, event_type, data) VALUES (?,?,?)", ("task-events", "log", "{bad"))
    task_store.save_event("task-events", "complete", {})
    task_store.update_task_status("task-events", "completed", 100)
    with app.test_client() as client:
        _login(client)
        query_events = _sse_events(client.get("/api/v1/tasks/task-events/events?after=2").get_data(as_text=True))
        header_events = _sse_events(client.get("/api/v1/tasks/task-events/events", headers={"Last-Event-ID": "2"}).get_data(as_text=True))
    assert [event["seq"] for event in query_events] == [3, 4]
    assert [event["seq"] for event in header_events] == [3, 4]
    assert query_events[0]["payload"]["raw"] == "{bad"
    assert sum(event["type"].startswith("task_") for event in query_events) == 1


def test_generator_emits_heartbeat_while_active():
    calls = 0
    def get_task(_task_id):
        nonlocal calls
        calls += 1
        return {"status": "processing" if calls <= 10 else "completed"}
    rows = []
    chunks = list(stream_v1_events("task", 0, lambda _id, since_id=0: [row for row in rows if row["id"] > since_id], get_task, sleep_fn=lambda _: None, ensure_terminal_fn=_memory_terminal_ensure(rows)))
    assert ": heartbeat\n\n" in chunks
