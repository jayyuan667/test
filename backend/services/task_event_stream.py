"""Adapters for persisted task events and the FORGE v1 SSE contract."""

import json
import time

from backend.domain.task_contract import SCHEMA_VERSION


V1_EVENT_TYPES = frozenset({
    "phase_started",
    "phase_progress",
    "feature_ready",
    "operation_upserted",
    "phase_completed",
    "task_completed",
    "task_failed",
    "heartbeat",
})

DIRECT_TYPE_MAP = {
    "step_start": "phase_started",
    "step_complete": "phase_completed",
    "complete": "task_completed",
    "error": "task_failed",
    "image_ready": "feature_ready",
    "preview_updated": "feature_ready",
    "log": "phase_progress",
    "yolo_progress": "phase_progress",
    "review_required": "phase_progress",
    "annotation_required": "phase_progress",
}

TERMINAL_TYPES = frozenset({"task_completed", "task_failed"})
TERMINAL_STATES = frozenset({"completed", "error", "failed", "cancelled"})
TERMINAL_GRACE_READS = 3
VALID_PHASES = frozenset({"upload", "drawing_analysis", "annotation", "feature_review", "process_generation", "export", "done"})
LEGACY_TRANSITIONS = {
    "annotation_required": ("annotation", 45),
    "review_required": ("feature_review", 60),
    "process_stream": ("process_generation", 75),
    "complete": ("done", 100),
}
LEGACY_DEFAULT_POSITIONS = {
    "step_start": ("drawing_analysis", 5),
    "step_complete": ("drawing_analysis", 20),
    "image_ready": ("drawing_analysis", 35),
    "preview_updated": ("annotation", 45),
    "log": ("drawing_analysis", 5),
    "yolo_progress": ("drawing_analysis", 30),
}
V1_DEFAULT_POSITIONS = {
    "phase_started": ("upload", 0),
    "phase_progress": ("drawing_analysis", 0),
    "feature_ready": ("drawing_analysis", 35),
    "operation_upserted": ("process_generation", 75),
    "phase_completed": ("drawing_analysis", 20),
    "task_completed": ("done", 100),
    "task_failed": ("drawing_analysis", 0),
}


def _canonical_position(legacy_type, payload):
    phase = payload.get("phase") if payload.get("phase") in VALID_PHASES else None
    progress = payload.get("progress")
    if not isinstance(progress, (int, float)) or isinstance(progress, bool) or not 0 <= progress <= 100:
        progress = None
    transition = LEGACY_TRANSITIONS.get(legacy_type)
    if transition:
        phase, progress = phase or transition[0], progress if progress is not None else transition[1]
    step = payload.get("step")
    if isinstance(step, int) and legacy_type in {"step_start", "step_complete", "log", "yolo_progress"}:
        phase = phase or "drawing_analysis"
        if progress is None:
            progress = min(95, max(5, step * 20 - (0 if legacy_type == "step_complete" else 15)))
    if legacy_type == "error":
        phase, progress = phase or "drawing_analysis", progress if progress is not None else 0
    default_phase, default_progress = LEGACY_DEFAULT_POSITIONS.get(
        legacy_type, V1_DEFAULT_POSITIONS.get(legacy_type, ("drawing_analysis", 0))
    )
    phase = phase or default_phase
    progress = progress if progress is not None else default_progress
    return phase, progress


def _structured_failure(payload, phase):
    if isinstance(payload.get("error"), dict):
        return payload["error"]
    details = {"checkpoint": payload["checkpoint"]} if payload.get("checkpoint") is not None else {}
    return {"code": payload.get("code") or "TASK_FAILED", "message": payload.get("message") or "Task failed", "retryable": payload.get("retryable") is True, "phase": phase, "details": details}


def _payload(event):
    data = event.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {"raw": data}
    elif isinstance(data, dict):
        data = dict(data)
    else:
        data = {}
    if event.get("message") is not None and "message" not in data:
        data["message"] = event["message"]
    return data


def _adapt_type(legacy_type, payload):
    if legacy_type == "process_stream":
        operation = payload.get("operation")
        if isinstance(operation, dict) and operation.get("id") and operation.get("code") and operation.get("content"):
            payload["operation"] = dict(operation)
            return "operation_upserted"
        payload.pop("operation", None)
        if "chunk" in payload:
            payload["process_chunk"] = payload.pop("chunk")
        payload["legacy_type"] = legacy_type
        return "phase_progress"
    if legacy_type in V1_EVENT_TYPES:
        return legacy_type
    adapted = DIRECT_TYPE_MAP.get(legacy_type, "phase_progress")
    if legacy_type not in {"step_start", "step_complete", "complete", "error"}:
        payload["legacy_type"] = legacy_type
    return adapted


def normalize_event(task_id, event):
    """Convert one SQLite task_events row to the stable v1 event shape."""
    payload = _payload(event)
    legacy_type = event.get("type")
    event_type = _adapt_type(legacy_type, payload)
    phase, progress = _canonical_position(legacy_type, payload)
    if event_type == "task_failed":
        payload["error"] = _structured_failure(payload, phase)
    return {
        "schema_version": SCHEMA_VERSION,
        "seq": int(event["id"]),
        "task_id": task_id,
        "type": event_type,
        "phase": phase,
        "progress": progress,
        "timestamp": event.get("created_at"),
        "payload": payload,
    }


def pack_v1_sse(event):
    """Serialize a normalized event with an SSE resume identifier."""
    return (
        f"id: {event['seq']}\n"
        f"event: {event['type']}\n"
        f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    )


def ensure_canonical_terminal_event(task_id, status):
    """Atomically return or create the task's earliest persisted terminal row."""
    from backend import task_store

    with task_store._conn() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """SELECT id, event_type, step, message, data, created_at
               FROM task_events
               WHERE task_id=? AND event_type IN ('complete', 'error')
               ORDER BY id LIMIT 1""",
            (task_id,),
        ).fetchone()
        if row is None:
            event_type = "error" if status in {"error", "failed", "cancelled"} else "complete"
            payload = json.dumps(
                {"canonical": True, "status": status}, ensure_ascii=False
            )
            cursor = connection.execute(
                "INSERT INTO task_events (task_id, event_type, data) VALUES (?, ?, ?)",
                (task_id, event_type, payload),
            )
            row = connection.execute(
                """SELECT id, event_type, step, message, data, created_at
                   FROM task_events WHERE id=?""",
                (cursor.lastrowid,),
            ).fetchone()
    return {
        "id": row[0], "type": row[1], "step": row[2], "message": row[3],
        "data": row[4], "created_at": row[5],
    }


def stream_v1_events(
    task_id,
    after,
    get_events_fn,
    get_task_fn,
    sleep_fn=time.sleep,
    ensure_terminal_fn=ensure_canonical_terminal_event,
):
    """Replay unseen rows and deliver exactly one stable terminal event."""
    yield "retry: 1500\n\n"
    yield ": connected\n\n"
    cursor = after
    persisted_max = 0
    terminal_emitted = False
    terminal_persisted = False
    earliest_terminal_id = None

    def drain(rows):
        nonlocal cursor, persisted_max, terminal_emitted, terminal_persisted, earliest_terminal_id
        chunks = []
        for row in rows:
            row_id = int(row["id"])
            persisted_max = max(persisted_max, row_id)
            normalized = normalize_event(task_id, row)
            if normalized["type"] in TERMINAL_TYPES:
                terminal_persisted = True
                if earliest_terminal_id is None:
                    earliest_terminal_id = row_id
                elif row_id != earliest_terminal_id:
                    cursor = max(cursor, row_id)
                    continue
            if row_id <= cursor:
                continue
            cursor = row_id
            if normalized["type"] in TERMINAL_TYPES:
                if terminal_emitted:
                    continue
                terminal_emitted = True
            chunks.append(pack_v1_sse(normalized))
        return chunks

    # Read from zero once so a synthesized terminal always uses max(DB id)+1,
    # including after reconnect when the client cursor is already ahead.
    for chunk in drain(get_events_fn(task_id, since_id=0)):
        yield chunk
    if terminal_persisted:
        return

    idle_ticks = 0
    while True:
        task = get_task_fn(task_id)
        if task is None:
            return
        if task.get("status") in TERMINAL_STATES:
            for _ in range(TERMINAL_GRACE_READS):
                sleep_fn(0.05)
                for chunk in drain(get_events_fn(task_id, since_id=persisted_max)):
                    yield chunk
                if terminal_persisted:
                    return
            canonical = ensure_terminal_fn(task_id, task.get("status"))
            for chunk in drain([canonical]):
                yield chunk
            return

        sleep_fn(0.5)
        rows = get_events_fn(task_id, since_id=persisted_max)
        chunks = drain(rows)
        for chunk in chunks:
            yield chunk
        if terminal_emitted:
            return
        if chunks:
            idle_ticks = 0
        else:
            idle_ticks += 1
            if idle_ticks >= 10:
                yield ": heartbeat\n\n"
                idle_ticks = 0
