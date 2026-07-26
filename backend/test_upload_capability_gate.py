import io


def test_pdf_upload_is_rejected_before_task_creation(monkeypatch):
    from backend.api import upload as upload_api
    from backend.app import app

    monkeypatch.setattr(
        upload_api,
        "inspect_pdf_capability",
        lambda: {"available": False, "provider": None, "reason": "请执行 uv sync"},
    )
    client = app.test_client()
    response = client.post(
        "/api/upload_drawing",
        data={"file": (io.BytesIO(b"%PDF-1.4"), "drawing.pdf")},
        content_type="multipart/form-data",
    )
    body = response.get_json()
    assert response.status_code == 422
    assert body["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert upload_api.tasks == {}
