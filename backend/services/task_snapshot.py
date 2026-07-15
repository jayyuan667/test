"""Normalize persisted drawing-task data into the FORGE v1 snapshot contract."""

import re

from backend.domain.task_contract import SCHEMA_VERSION


STATE_TO_PHASE = {
    "pending": "upload",
    "processing": "drawing_analysis",
    "awaiting_annotation": "annotation",
    "awaiting_review": "feature_review",
    "completed": "done",
    "failed": "drawing_analysis",
    "cancelled": "done",
}


def _duration_minutes(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.endswith("min"):
        value = value[:-3].strip()
    try:
        return int(value)
    except ValueError:
        return None


def _normalize_operation(row, index):
    code = row[0]
    return {
        "id": f"op-{code}-{index}",
        "code": code,
        "trade": row[1] if len(row) > 1 else None,
        "content": row[2] if len(row) > 2 else "",
        "equipment": [row[3]] if len(row) > 3 and row[3] else [],
        "duration_minutes": _duration_minutes(row[4]) if len(row) > 4 else None,
        "parameters": [],
        "note": None,
        "status": "complete",
    }


def _structured_features(result):
    features = result.get("features")
    return features if isinstance(features, list) else None


def _legacy_features(text):
    if not isinstance(text, str):
        return []
    features = []
    for index, match in enumerate(re.finditer(r"【([^】]+)】([^\r\n]+)", text)):
        category, label = match.groups()
        evidence = match.group(0)
        features.append(
            {
                "id": f"feature-legacy-{index}",
                "kind": "thread" if category == "螺纹与螺孔" else "unknown",
                "label": label,
                "value": label,
                "unit": None,
                "tolerance": {"upper": None, "lower": None, "text": None},
                "source": {
                    "method": "legacy_text",
                    "page": 1,
                    "bbox": None,
                    "evidence_text": evidence,
                },
                "confidence": None,
                "review_status": "unreviewed",
                "missing_reason": None,
            }
        )
    return features


def build_task_snapshot(task_id: str, task: dict, result: dict | None = None) -> dict:
    result = result or {}
    rows = result.get("process_operations", [])
    features = _structured_features(result)
    if features is None:
        features = _legacy_features(result.get("feature_text"))
    state = task.get("state", task.get("status", "pending"))
    return {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "id": task_id,
            "state": state,
            "phase": STATE_TO_PHASE[state],
            "progress": task.get("progress", 0),
            "revision": task.get("revision", 0),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "error": task.get("error"),
        },
        "features": features,
        "process_operations": [
            _normalize_operation(row, index) for index, row in enumerate(rows)
        ],
    }
