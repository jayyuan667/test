import inspect

from backend.api.upload import (
    _feature_evidence_from_task,
    _finalize_processing,
    _match_operation_evidence,
    _operation_event_from_enriched_row,
)


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


def test_feature_evidence_falls_back_to_report_text_when_pages_are_empty():
    features = _feature_evidence_from_task({
        "feature_report_json": {
            "report_text": "【材料】45钢\n【关键尺寸】Φ146±0.05；总长1471.8±0.1\n【螺纹与螺孔】M115×3-6g"
        }
    })

    assert [feature["value"] for feature in features] == [
        "45钢",
        "Φ146±0.05",
        "总长1471.8±0.1",
        "M115×3-6g",
    ]


def test_operation_evidence_matches_turning_content_to_key_dimension():
    features = _feature_evidence_from_task({
        "feature_report_json": {
            "report_text": "【材料】45钢\n【关键尺寸】Φ146±0.05；总长1471.8±0.1\n【螺纹与螺孔】M115×3-6g"
        }
    })

    evidence = _match_operation_evidence("粗车外圆，留精加工余量", features)

    assert evidence
    assert evidence[0]["value"] == "Φ146±0.05"


def test_finalize_processing_marks_completed_after_result_is_saved():
    source = inspect.getsource(_finalize_processing)

    assert source.index("save_result(task_id, result)") < source.index('task["status"] = "completed"')
    assert source.index('task["status"] = "completed"') < source.index("emit_complete(")
