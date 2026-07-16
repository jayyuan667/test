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


def _is_fence_text(value):
    return isinstance(value, str) and value.strip().strip("`").lower() in {"", "markdown"}


def _parse_process_rows_from_raw(raw_text):
    if not isinstance(raw_text, str):
        return []

    rows = []
    normalized_text = raw_text.replace("ENDD$$", " ")
    for line in normalized_text.strip().splitlines():
        current = line.strip()
        if (
            not current
            or current.startswith(("#", "|", "---", "==="))
            or _is_fence_text(current)
        ):
            continue
        content = current[2:].strip() if current.startswith(("- ", "* ")) else current
        match = re.match(r"^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$", content)
        if not match:
            continue

        code, description = match.groups()
        trade = None
        trade_match = re.search(r"[（(]\s*工种\s*[：:]\s*([^）)]+)\s*[）)]\s*$", description)
        if trade_match:
            trade = trade_match.group(1).strip()
            description = description[:trade_match.start()].strip()
        rows.append([code, trade, description, "", ""])
    return rows


def _rows_need_raw_reparse(rows):
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) > 2 and _is_fence_text(row[2]):
            return True
        if isinstance(row, dict) and _is_fence_text(row.get("content")):
            return True
    return False


def _normalize_operation(row, index):
    if isinstance(row, (list, tuple)):
        code = row[0] if row else ""
        if len(row) == 2:
            trade = None
            content = row[1]
            equipment = []
            duration = None
        else:
            trade = row[1] if len(row) > 1 else None
            content = row[2] if len(row) > 2 else ""
            equipment = [row[3]] if len(row) > 3 and row[3] else []
            duration = row[4] if len(row) > 4 else None
        identifier, parameters, note, status = None, [], None, "complete"
    else:
        getter = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
        code, trade, content = getter("code", ""), getter("trade"), getter("content", "")
        equipment = getter("equipment", [])
        if isinstance(equipment, str):
            equipment = [equipment] if equipment else []
        elif not isinstance(equipment, list):
            equipment = []
        duration = getter("duration_minutes", getter("duration"))
        identifier, parameters = getter("id"), getter("parameters", [])
        note, status = getter("note"), getter("status", "complete")
    duration_minutes = duration if isinstance(duration, int) and not isinstance(duration, bool) else _duration_minutes(duration)
    return {
        "id": identifier or f"op-{code}-{index}",
        "code": code,
        "trade": trade,
        "content": content,
        "equipment": equipment,
        "duration_minutes": duration_minutes,
        "parameters": parameters if isinstance(parameters, list) else [],
        "note": note,
        "status": status if status in {"draft", "streaming", "complete", "modified"} else "complete",
    }


def _normalize_task_error(state, phase, value):
    if state == "completed" or value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        return {
            "code": "TASK_FAILED",
            "message": value,
            "retryable": False,
            "phase": phase,
            "details": {},
        }
    return value


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


def _clean_feature_label(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip().lstrip("：:;；,，").strip())


def _feature_identity(value):
    label = _clean_feature_label(value).lower()
    label = re.sub(r"\s+", "", label)
    label = label.replace("φ", "Φ").replace("ϕ", "Φ")
    return label


def _dedupe_features(features):
    seen = set()
    deduped = []
    for feature in features:
        label = _clean_feature_label(feature.get("label"))
        value = _clean_feature_label(feature.get("value"))
        key = _feature_identity(value or label)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append({**feature, "label": label, "value": value or None})
    return deduped


def _structured_features(result):
    features = result.get("features")
    if not isinstance(features, list):
        return None
    return _dedupe_features([
        _normalize_structured_feature(feature, index)
        for index, feature in enumerate(features)
        if isinstance(feature, dict)
    ])


NON_FEATURE_CATEGORIES = {"报告名称", "页数", "第1页摘要", "摘要"}
EMPTY_FEATURE_VALUES = {"", "无", "无。", "无；无", "无;无"}


def _clean_legacy_feature_value(label):
    cleaned = _clean_feature_label(label)
    parts = [_clean_feature_label(part) for part in re.split(r"[;；]", cleaned)]
    seen = set()
    values = []
    for part in parts:
        if part in EMPTY_FEATURE_VALUES or re.fullmatch(r"\d+(\.\d+)?", part):
            continue
        key = _feature_identity(part)
        if key in seen:
            continue
        seen.add(key)
        values.append(part)
    return "；".join(values)


def _legacy_feature_kind(category, value):
    if category == "螺纹与螺孔" or re.search(r"\bM\d+[×xX]", value):
        return "thread"
    return "unknown"


def _legacy_features(text):
    if not isinstance(text, str):
        return []
    features = []
    for match in re.finditer(r"【([^】]+)】([^\r\n]+)", text):
        category, label = match.groups()
        if category in NON_FEATURE_CATEGORIES:
            continue
        evidence = match.group(0)
        value = _clean_legacy_feature_value(label)
        if not value:
            continue
        features.append(
            {
                "id": f"feature-legacy-{len(features)}",
                "kind": _legacy_feature_kind(category, value),
                "label": value,
                "value": value,
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
    return _dedupe_features(features)


def build_task_snapshot(task_id: str, task: dict, result: dict | None = None) -> dict:
    if result is None:
        result = task.get("result") or {}
    rows = result.get("process_operations")
    if not isinstance(rows, list):
        process_flow = result.get("process_flow")
        rows = process_flow.get("data", []) if isinstance(process_flow, dict) else []
    process_flow = result.get("process_flow")
    if isinstance(process_flow, dict) and _rows_need_raw_reparse(rows):
        reparsed_rows = _parse_process_rows_from_raw(process_flow.get("raw"))
        if reparsed_rows:
            rows = reparsed_rows
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
            "error": _normalize_task_error(state, phase, task.get("error")),
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
