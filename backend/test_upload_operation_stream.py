import inspect

from backend.api.upload import _finalize_processing, _operation_event_from_enriched_row


def test_operation_event_from_enriched_row_matches_v1_shape():
    operation = _operation_event_from_enriched_row(
        "task-1",
        ["0010", "车", "粗车外圆", "卧式车床 CW61100", "2h"],
        0,
    )

    assert operation == {
        "id": "op-0010-0",
        "code": "0010",
        "trade": "车",
        "content": "粗车外圆",
        "equipment": ["卧式车床 CW61100"],
        "duration_minutes": 120,
        "parameters": [],
        "note": None,
        "status": "streaming",
    }


def test_operation_event_can_include_feature_evidence():
    operation = _operation_event_from_enriched_row(
        "task-1",
        ["0020", "车", "粗车外圆", "卧式车床 CW61100", "2h"],
        1,
        evidence_features=[
            {
                "id": "feature-dia-1",
                "label": "外圆",
                "value": "Φ146±0.05",
                "source": {"page": 1, "evidence_text": "Φ146±0.05"},
                "confidence": 0.92,
            }
        ],
    )

    assert operation["evidence_features"] == [
        {
            "id": "feature-dia-1",
            "label": "外圆",
            "value": "Φ146±0.05",
            "source": {"page": 1, "evidence_text": "Φ146±0.05"},
            "confidence": 0.92,
        }
    ]


def test_finalize_processing_marks_completed_after_result_is_saved():
    source = inspect.getsource(_finalize_processing)

    assert source.index("save_result(task_id, result)") < source.index('task["status"] = "completed"')
    assert source.index('task["status"] = "completed"') < source.index("emit_complete(")
