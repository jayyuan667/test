import io
import os
import tempfile

from werkzeug.security import generate_password_hash


def test_pdf_upload_is_rejected_before_task_creation(monkeypatch):
    from backend import auth_store
    from backend.api import upload as upload_api
    from backend.app import app

    monkeypatch.setattr(
        upload_api,
        "inspect_pdf_capability",
        lambda: {"available": False, "provider": None, "reason": "请执行 uv sync"},
    )
    auth_fd, auth_path = tempfile.mkstemp(suffix=".db")
    os.close(auth_fd)
    monkeypatch.setattr(auth_store, "DB_FILE", auth_path)
    auth_store.init_auth_db()
    enterprise = auth_store.create_enterprise("capability-test")
    auth_store.create_user("capability-user", generate_password_hash("secret"), enterprise_id=enterprise["id"])
    client = app.test_client()
    assert client.post("/api/auth/login", json={"username": "capability-user", "password": "secret"}).status_code == 200
    response = client.post(
        "/api/upload_drawing",
        data={"file": (io.BytesIO(b"%PDF-1.4"), "drawing.pdf")},
        content_type="multipart/form-data",
    )
    body = response.get_json()
    assert response.status_code == 422
    assert body["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert upload_api.tasks == {}
    os.unlink(auth_path)
