from backend.services.task_snapshot import build_task_snapshot


def test_five_column_process_row_maps_by_position():
    snapshot = build_task_snapshot(
        "task-1",
        {},
        {"process_operations": [["0050", "车工", "粗车外圆", "CW61100", "90min"]]},
    )

    operation = snapshot["process_operations"][0]
    assert operation["trade"] == "车工"
    assert operation["content"] == "粗车外圆"
    assert operation["equipment"] == ["CW61100"]
    assert operation["duration_minutes"] == 90


def test_three_column_process_row_has_no_equipment_or_duration():
    snapshot = build_task_snapshot(
        "task-2",
        {},
        {"process_operations": [["0060", "钳工", "去毛刺"]]},
    )

    operation = snapshot["process_operations"][0]
    assert operation["equipment"] == []
    assert operation["duration_minutes"] is None


def test_legacy_bracket_feature_is_thread_without_invented_confidence():
    snapshot = build_task_snapshot(
        "task-3",
        {},
        {"feature_text": "【螺纹与螺孔】M115×3-6g"},
    )

    feature = snapshot["features"][0]
    assert feature["kind"] == "thread"
    assert feature["label"] == "M115×3-6g"
    assert feature["confidence"] is None
    assert feature["source"]["method"] == "legacy_text"
    assert feature["source"]["evidence_text"] == "【螺纹与螺孔】M115×3-6g"


def test_structured_feature_preserves_confidence_page_and_bbox():
    snapshot = build_task_snapshot(
        "task-4",
        {},
        {
            "features": [
                {
                    "id": "feature-thread-1",
                    "kind": "thread",
                    "label": "M115×3-6g",
                    "confidence": 0.91,
                    "source": {
                        "method": "vlm",
                        "page": 1,
                        "bbox": [10, 20, 30, 40],
                    },
                }
            ]
        },
    )

    feature = snapshot["features"][0]
    assert feature["confidence"] == 0.91
    assert feature["source"]["page"] == 1
    assert feature["source"]["bbox"] == [10, 20, 30, 40]


def test_processing_state_is_not_inferred_from_full_progress():
    snapshot = build_task_snapshot(
        "task-5",
        {"status": "processing", "progress": 100},
    )

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["task"]["state"] == "processing"
    assert snapshot["task"]["phase"] == "drawing_analysis"
