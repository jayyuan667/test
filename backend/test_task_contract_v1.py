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


def test_real_process_flow_data_maps_to_structured_operations():
    snapshot = build_task_snapshot(
        "task-real",
        {},
        {"process_flow": {"data": [["0010", "料", "下料棒料", "", ""]]}},
    )
    assert snapshot["process_operations"][0]["code"] == "0010"
    assert snapshot["process_operations"][0]["content"] == "下料棒料"


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
    assert feature["source"]["page"] is None
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


def test_snapshot_always_has_the_complete_v1_top_level_shape():
    snapshot = build_task_snapshot("task-shape", {})

    assert set(snapshot) == {
        "schema_version",
        "task",
        "drawing",
        "features",
        "review",
        "process_operations",
        "reuse_candidates",
        "capabilities",
    }


def test_legacy_error_status_normalizes_without_key_error():
    snapshot = build_task_snapshot(
        "task-error",
        {"status": "error", "error": "vision failed"},
    )

    assert snapshot["task"]["state"] == "failed"
    assert snapshot["task"]["phase"] == "drawing_analysis"
    assert snapshot["task"]["error"] == "vision failed"


def test_nested_task_result_is_used_when_result_argument_is_omitted():
    snapshot = build_task_snapshot(
        "task-nested-result",
        {"result": {"feature_text": "【螺纹与螺孔】M20×2-6g"}},
    )

    assert snapshot["features"][0]["label"] == "M20×2-6g"


def test_explicit_result_argument_wins_over_nested_task_result():
    snapshot = build_task_snapshot(
        "task-explicit-result",
        {"result": {"feature_text": "【螺纹与螺孔】M20×2-6g"}},
        {"feature_text": "【螺纹与螺孔】M30×3-6g"},
    )

    assert snapshot["features"][0]["label"] == "M30×3-6g"


def test_structured_feature_is_normalized_to_complete_v1_shape():
    snapshot = build_task_snapshot(
        "task-feature-shape",
        {},
        {
            "features": [
                {
                    "kind": "length",
                    "label": "25",
                    "source": {"bbox": [1, 2, 3, 4]},
                }
            ]
        },
    )

    feature = snapshot["features"][0]
    assert set(feature) == {
        "id",
        "kind",
        "label",
        "value",
        "unit",
        "tolerance",
        "source",
        "confidence",
        "review_status",
        "missing_reason",
    }
    assert feature["id"] == "feature-structured-0"
    assert feature["value"] is None
    assert feature["unit"] is None
    assert feature["tolerance"] == {"upper": None, "lower": None, "text": None}
    assert feature["source"] == {
        "method": None,
        "page": None,
        "bbox": [1, 2, 3, 4],
        "evidence_text": None,
    }
    assert feature["confidence"] is None
    assert feature["review_status"] == "unreviewed"
    assert feature["missing_reason"] is None
