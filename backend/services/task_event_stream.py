"""Adapters for persisted task events and the FORGE v1 SSE contract."""

import json
import time
from datetime import datetime, timezone

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
        if isinstance(operation, dict) and operation.get("id"):
            payload["operation"] = dict(operation)
            return "operation_upserted"
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
    event_type = _adapt_type(event.get("type"), payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "seq": int(event["id"]),
        "task_id": task_id,
        "type": event_type,
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


def _synthetic_terminal(task_id, seq, task):
    status = task.get("status")
    failed = status in {"error", "failed", "cancelled"}
    return {
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "task_id": task_id,
        "type": "task_failed" if failed else "task_completed",
        "phase": None,
        "progress": task.get("progress"),
        "timestamp": task.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "payload": {"synthetic": True, "status": status},
    }


def stream_v1_events(task_id, after, get_events_fn, get_task_fn, sleep_fn=time.sleep):
    """Replay unseen rows and deliver exactly one stable terminal event."""
    yield "retry: 1500\n\n"
    yield ": connected\n\n"
    cursor = after
    persisted_max = 0
    terminal_emitted = False
    terminal_persisted = False

    def drain(rows):
        nonlocal cursor, persisted_max, terminal_emitted, terminal_persisted
        chunks = []
        for row in rows:
            row_id = int(row["id"])
            persisted_max = max(persisted_max, row_id)
            normalized = normalize_event(task_id, row)
            if normalized["type"] in TERMINAL_TYPES:
                terminal_persisted = True
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
            synthetic_seq = persisted_max + 1
            if synthetic_seq > after:
                yield pack_v1_sse(_synthetic_terminal(task_id, synthetic_seq, task))
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
