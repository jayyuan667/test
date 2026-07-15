"""Adapters for persisted task events and the FORGE v1 SSE contract."""

import json
import time

from backend.domain.task_contract import SCHEMA_VERSION


EVENT_TYPE_MAP = {
    "step_start": "phase_started",
    "step_complete": "phase_completed",
    "process_stream": "operation_upserted",
    "complete": "task_completed",
    "error": "task_failed",
}


def _payload(event):
    data = event.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {"raw": data}
    if not isinstance(data, dict):
        data = {}
    if event.get("message") is not None and "message" not in data:
        data["message"] = event["message"]
    return data


def normalize_event(task_id, event):
    """Convert one SQLite task_events row to the stable v1 event shape."""
    payload = _payload(event)
    return {
        "schema_version": SCHEMA_VERSION,
        "seq": event["id"],
        "task_id": task_id,
        "type": EVENT_TYPE_MAP.get(event.get("type"), event.get("type")),
        "phase": payload.get("phase"),
        "progress": payload.get("progress"),
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


def stream_v1_events(task_id, after, get_events_fn, get_task_fn, sleep_fn=time.sleep):
    """Replay unseen events, then poll until the task reaches a terminal state."""
    yield "retry: 1500\n\n"
    yield ": connected\n\n"
    cursor = after
    idle_ticks = 0
    while True:
        events = get_events_fn(task_id, since_id=cursor)
        for event in events:
            normalized = normalize_event(task_id, event)
            yield pack_v1_sse(normalized)
            cursor = max(cursor, normalized["seq"])
        if events:
            idle_ticks = 0
        else:
            idle_ticks += 1
            if idle_ticks >= 10:
                yield ": heartbeat\n\n"
                idle_ticks = 0

        task = get_task_fn(task_id)
        if task is None or task.get("status") in {"completed", "error", "failed", "cancelled"}:
            break
        sleep_fn(0.5)
