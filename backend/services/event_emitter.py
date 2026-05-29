# -*- coding: utf-8 -*-
"""Event emitter for SSE real-time progress updates."""

import threading
import sys
from datetime import datetime
from typing import Dict, Any, Callable
import logging

sys.stdout.reconfigure(encoding="utf-8")


logger = logging.getLogger(__name__)


def create_event_emitter(
    task_id: str, event_data: Dict, event_locks: Dict
) -> Callable[[str, Dict[str, Any]], None]:
    """Create an event emitter function for a specific task.

    Args:
        task_id: The task ID
        event_data: Shared event data dictionary
        event_locks: Shared locks dictionary

    Returns:
        Function that emits events to the SSE stream
    """

    def emit_event(event_type: str, data: Dict[str, Any]) -> None:
        if task_id not in event_data:
            return
        with event_locks.get(task_id, threading.Lock()):
            event_data[task_id].append(
                {
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    return emit_event


def emit_step_start(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    step: int,
    name: str,
    message: str = None,
) -> None:
    """Emit a step_start event."""
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    data = {"step": step, "name": name}
    if message:
        data["message"] = message
    emit_event("step_start", data)


def emit_step_complete(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    step: int,
    name: str,
    result: str = None,
) -> None:
    """Emit a step_complete event."""
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    data = {"step": step, "name": name}
    if result:
        data["result"] = result
    emit_event("step_complete", data)


def emit_complete(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    message: str = "Processing complete!",
) -> None:
    """Emit a complete event."""
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    emit_event("complete", {"message": message})


def emit_error(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    message: str,
) -> None:
    """Emit an error event."""
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    emit_event("error", {"message": message})


def emit_image_ready(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    page: int,
    total: int,
    image_path: str,
) -> None:
    """Emit an image_ready event when a page image is generated."""
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    emit_event(
        "image_ready",
        {
            "page": page,
            "total": total,
            "image_path": image_path,
            "message": f"第 {page}/{total} 页图片已生成",
        },
    )


def emit_log(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    step: int,
    message: str,
    level: str = "info",
) -> None:
    """Emit a log event for real-time log streaming."""
    # Normalise "warn" to "warning" for consistent SSE replay
    normalized_level = "warning" if (level or "").strip().lower() == "warn" else (level or "info").strip().lower()
    log_message = f"[{task_id}] step {step}: {message}"
    if normalized_level == "error":
        logger.error(log_message)
    elif normalized_level == "warning":
        logger.warning(log_message)
    else:
        logger.info(log_message)
    print(log_message)
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    emit_event(
        "log",
        {
            "step": step,
            "message": message,
            "level": normalized_level,
        },
    )
    # Persist to SQLite for SSE replay after memory state loss
    try:
        from backend.task_store import save_event
        save_event(task_id, "log", {
            "step": step,
            "message": message,
            "level": normalized_level,
        })
    except Exception:
        pass  # Persistence is best-effort; never block the pipeline


def emit_custom(
    task_id: str,
    event_data: Dict,
    event_locks: Dict,
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Emit a custom SSE event type."""
    emit_event = create_event_emitter(task_id, event_data, event_locks)
    emit_event(event_type, data)
