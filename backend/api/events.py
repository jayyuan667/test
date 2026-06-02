# -*- coding: utf-8 -*-
"""SSE events endpoint for real-time progress updates."""

import time
import json
import os
import logging
from flask import Blueprint, Response, stream_with_context
import threading

from ..config import OUTPUT_FOLDER

events_bp = Blueprint("events", __name__)
logger = logging.getLogger(__name__)

tasks = {}
event_data = {}
event_locks = {}


def set_shared_state(tasks_dict, event_data_dict, event_locks_dict):
    """Inject shared state from app.py."""
    global tasks, event_data, event_locks
    tasks = tasks_dict
    event_data = event_data_dict
    event_locks = event_locks_dict


def _sse_pack(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_response(generator):
    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return Response(stream_with_context(generator), headers=headers)


@events_bp.route("/events/<task_id>", methods=["GET"])
def stream_events(task_id):
    if task_id in tasks and tasks[task_id].get("status") in ["completed", "error"]:
        task = tasks[task_id]

        def finished_event_generator():
            yield ": connected\n\n"
            final_type = "complete" if task.get("status") == "completed" else "error"
            final_message = "Processing complete!" if final_type == "complete" else task.get("error", "Task failed")
            yield _sse_pack("sse_ready", {"task_id": task_id, "message": "SSE connected"})
            yield _sse_pack(final_type, {"message": final_message, "task_id": task_id})

        return _sse_response(finished_event_generator())

    logger.info("[SSE] client connected for task_id=%s", task_id)

    if task_id not in tasks:
        # Fallback: try task_store (SQLite)
        try:
            from ..task_store import get_task, get_events, get_result as get_db_result
            db_task = get_task(task_id)
            if db_task:
                if db_task.get("status") in ["completed", "error"]:
                    def db_finished_event_generator():
                        yield ": connected\n\n"
                        final_type = "complete" if db_task["status"] == "completed" else "error"
                        final_message = "Processing complete!" if final_type == "complete" else db_task.get("error", "Task failed")
                        yield _sse_pack("sse_ready", {"task_id": task_id, "message": "SSE connected (from DB)"})
                        yield _sse_pack(final_type, {"message": final_message, "task_id": task_id})

                    return _sse_response(db_finished_event_generator())

                def db_event_generator():
                    yield ": connected\n\n"
                    yield _sse_pack("sse_ready", {"task_id": task_id, "message": "SSE connected (from DB)"})
                    last_id = 0
                    while True:
                        events = get_events(task_id, since_id=last_id)
                        if events:
                            for evt in events:
                                data = json.loads(evt["data"]) if evt.get("data") else {}
                                yield _sse_pack(evt["type"], data)
                                last_id = max(last_id, evt["id"])
                        # Refresh task status every loop
                        current_task = get_task(task_id)
                        if current_task and current_task.get("status") in ["completed", "error"]:
                            yield _sse_pack("complete" if current_task["status"] == "completed" else "error",
                                           {"message": "Done", "task_id": task_id})
                            break
                        time.sleep(0.5)
                return _sse_response(db_event_generator())
        except ImportError:
            pass

        result_file = os.path.join(OUTPUT_FOLDER, task_id, "result.json")
        if os.path.exists(result_file):
            def completed_event_generator():
                yield ": connected\n\n"
                yield _sse_pack("complete", {"message": "Processing complete!", "task_id": task_id})

            return _sse_response(completed_event_generator())

        logger.warning("[SSE] task not found for task_id=%s", task_id)
        return Response("Task not found", status=404)

    def event_generator():
        last_index = -1
        cleanup_done = False
        idle_ticks = 0

        yield ": connected\n\n"
        yield _sse_pack("sse_ready", {"task_id": task_id, "message": "SSE connected"})

        while True:
            lock = event_locks.get(task_id)
            if lock is None:
                events = event_data.get(task_id, [])
            else:
                with lock:
                    events = list(event_data.get(task_id, []))

            if last_index < len(events) - 1:
                idle_ticks = 0
                for i in range(last_index + 1, len(events)):
                    event = events[i]
                    yield _sse_pack(event["type"], event["data"])
                    last_index = i
            else:
                idle_ticks += 1
                if idle_ticks >= 10:
                    idle_ticks = 0
                    yield ": keepalive\n\n"

            task = tasks.get(task_id, {})
            if task.get("status") in ["completed", "error"]:
                if last_index < len(events) - 1:
                    continue

                if not cleanup_done:
                    cleanup_done = True
                    logger.info("[SSE] task finished for task_id=%s status=%s", task_id, task.get("status"))
                    time.sleep(0.2)
                    final_type = "complete" if task.get("status") == "completed" else "error"
                    final_message = "Processing complete!" if final_type == "complete" else task.get("error", "Task failed")
                    yield _sse_pack(final_type, {"message": final_message, "task_id": task_id})

                    if not task.get("keep_after_complete"):
                        lock = event_locks.get(task_id)
                        if lock is None:
                            event_data.pop(task_id, None)
                            event_locks.pop(task_id, None)
                        else:
                            with lock:
                                event_data.pop(task_id, None)
                                event_locks.pop(task_id, None)
                        tasks.pop(task_id, None)
                break

            time.sleep(0.2)

        logger.info("[SSE] client disconnected for task_id=%s", task_id)

    return _sse_response(event_generator())
