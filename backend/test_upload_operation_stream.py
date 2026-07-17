from backend.api.upload import _operation_event_from_enriched_row


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
