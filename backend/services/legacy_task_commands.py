"""Transitional seam around request-context legacy task handlers.

The legacy workflow currently exposes its command behavior as Flask view
functions.  This adapter is the only v1 dependency on those handlers: it skips
their outer ``login_required`` wrapper (v1 already authenticated the request),
preserves inner wrappers such as upload quota enforcement, and normalizes every
legal Flask return shape to ``CommandResult``.  Delete this module when the
legacy views are replaced by request-independent workflow services.
"""

from dataclasses import dataclass
from typing import Any, Callable

from flask import Response, current_app


@dataclass(frozen=True)
class CommandResult:
    """Stable result returned by every transitional legacy command."""

    response: Response

    @property
    def status_code(self) -> int:
        return self.response.status_code

    def json(self) -> dict:
        return self.response.get_json(silent=True) or {}


def invoke_request_handler(
    handler: Callable[..., Any], *args: Any, unwrap_login: bool = True
) -> CommandResult:
    """Invoke one legacy view and normalize Response/tuple/body return values.

    Exactly one wrapper is removed.  Using ``inspect.unwrap`` here would also
    remove upload's inner quota wrapper, changing a protected behavior.
    """
    target = getattr(handler, "__wrapped__", handler) if unwrap_login else handler
    try:
        raw = target(*args)
        return CommandResult(current_app.make_response(raw))
    except Exception:
        current_app.logger.exception("Legacy task command failed")
        return CommandResult(current_app.make_response(({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            }
        }, 500)))


def create_task() -> CommandResult:
    from ..api.upload import upload_drawing

    return invoke_request_handler(upload_drawing)


def finalize_annotations(task_id: str) -> CommandResult:
    from ..api.annotations import finalize_annotations as legacy_finalize

    return invoke_request_handler(legacy_finalize, task_id)


def review_task(task_id: str) -> CommandResult:
    from ..api.upload import review_visual_features

    return invoke_request_handler(review_visual_features, task_id)


def cancel_task(task_id: str) -> CommandResult:
    from ..api.upload import cancel_task_route

    return invoke_request_handler(cancel_task_route, task_id)


def export_task(task_id: str) -> CommandResult:
    from ..api.export import export_result

    return invoke_request_handler(export_result, task_id)
