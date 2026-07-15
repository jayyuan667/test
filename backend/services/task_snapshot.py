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

STATE_ALIASES = {"error": "failed"}


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


def _normalize_structured_feature(feature, index):
    tolerance = feature.get("tolerance")
    if not isinstance(tolerance, dict):
        tolerance = {}
    source = feature.get("source")
    if not isinstance(source, dict):
        source = {}
    return {
        "id": feature.get("id", f"feature-structured-{index}"),
        "kind": feature.get("kind", "unknown"),
        "label": feature.get("label", ""),
        "value": feature.get("value"),
        "unit": feature.get("unit"),
        "tolerance": {
            "upper": tolerance.get("upper"),
            "lower": tolerance.get("lower"),
            "text": tolerance.get("text"),
        },
        "source": {
            "method": source.get("method"),
            "page": source.get("page"),
            "bbox": source.get("bbox"),
            "evidence_text": source.get("evidence_text"),
        },
        "confidence": feature.get("confidence"),
        "review_status": feature.get("review_status", "unreviewed"),
        "missing_reason": feature.get("missing_reason"),
    }


def _structured_features(result):
    features = result.get("features")
    if not isinstance(features, list):
        return None
    return [
        _normalize_structured_feature(feature, index)
        for index, feature in enumerate(features)
        if isinstance(feature, dict)
    ]


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
                    "page": None,
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
    if result is None:
        result = task.get("result") or {}
    rows = result.get("process_operations")
    if not isinstance(rows, list):
        process_flow = result.get("process_flow")
        rows = process_flow.get("data", []) if isinstance(process_flow, dict) else []
    features = _structured_features(result)
    if features is None:
        features = _legacy_features(result.get("feature_text"))
    persisted_state = task.get("state", task.get("status", "pending"))
    state = STATE_ALIASES.get(persisted_state, persisted_state)
    phase = STATE_TO_PHASE.get(state, "drawing_analysis")
    return {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "id": task_id,
            "state": state,
            "phase": phase,
            "progress": task.get("progress", 0),
            "revision": task.get("revision", 0),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "error": task.get("error"),
        },
        "drawing": {
            "name": task.get("drawing_name", task.get("pdf_name", "")),
            "source_kind": task.get("source_kind", "unknown"),
            "page_count": result.get("page_count", 1),
            "preview_urls": result.get("preview_urls", result.get("preview_image_urls", [])),
        },
        "features": features,
        "review": {
            "status": result.get("review_status", "not_ready"),
            "raw_text": result.get("feature_text"),
        },
        "process_operations": [
            _normalize_operation(row, index) for index, row in enumerate(rows)
        ],
        "reuse_candidates": result.get("reuse_candidates", []),
        "capabilities": result.get("capabilities", {}),
    }
