import io
import json
import os
import tempfile
import zipfile

import pytest

from backend.app import app
from backend import auth_store


@pytest.fixture(autouse=True)
def isolated_auth_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_kb_import_auth_")
    os.close(fd)
    monkeypatch.setattr(auth_store, "DB_FILE", path)
    auth_store.init_auth_db()
    yield
    try:
        os.unlink(path)
    except OSError:
        pass


def _zip_with_files(count: int) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for idx in range(count):
            archive.writestr(f"file_{idx}.txt", "0010 sample")
    buffer.seek(0)
    return buffer


def test_import_zip_rejects_archives_smaller_than_production_minimum(monkeypatch):
    called = False

    def fake_import_zip_knowledge(*args, **kwargs):
        nonlocal called
        called = True
        return {"ok": True}

    from backend.api import kb_import

    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)

    app.config["TESTING"] = True
    client = app.test_client()
    login_response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_response.status_code == 200

    response = client.post(
        "/api/kb/import_zip",
        data={"zip_file": (_zip_with_files(9), "tiny.zip")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "至少需要 10 个文件" in response.get_json()["error"]
    assert called is False


def test_demo_fast_zip_import_reuses_cached_report_when_enabled(monkeypatch, tmp_path):
    from backend.api import kb_import

    calls = []

    def fake_import_zip_knowledge(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "batch_id": "kb_first",
            "zip_name": args[1],
            "conflict_mode": kwargs.get("conflict_mode"),
            "library_mode": kwargs.get("library_mode"),
            "summary": {
                "total_files": 10,
                "prt_count": 0,
                "pdf_count": 0,
                "image_count": 0,
                "xlsx_count": 10,
                "matched_pairs": 5,
                "imported_count": 5,
                "skipped_count": 0,
                "error_count": 0,
            },
            "matched_pairs": [],
            "unmatched_pdfs": [],
            "unmatched_xlsx": [],
            "unmatched_prts": [],
            "unmatched_images": [],
            "errors": [],
            "created_at": "2026-06-26T12:00:00",
        }

    monkeypatch.setenv("DEMO_FAST_ZIP_IMPORT", "1")
    monkeypatch.setattr(kb_import, "OUTPUT_FOLDER", str(tmp_path / "output"))
    monkeypatch.setattr(kb_import, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)

    app.config["TESTING"] = True
    client = app.test_client()
    login_response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_response.status_code == 200

    first = client.post(
        "/api/kb/import_zip",
        data={"zip_file": (_zip_with_files(10), "demo.zip"), "library_key": "public"},
        content_type="multipart/form-data",
    )
    second = client.post(
        "/api/kb/import_zip",
        data={"zip_file": (_zip_with_files(10), "demo.zip"), "library_key": "public"},
        content_type="multipart/form-data",
    )

    assert first.status_code == 200
    assert first.get_json().get("cached") is not True
    assert second.status_code == 200
    second_body = second.get_json()
    assert second_body["cached"] is True
    assert second_body["summary"]["matched_pairs"] == 5
    assert second_body["message"] == "检测到相同知识包，已复用历史入库结果"
    assert len(calls) == 1


def test_demo_fast_zip_import_does_not_cache_when_disabled(monkeypatch, tmp_path):
    from backend.api import kb_import

    calls = []

    def fake_import_zip_knowledge(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "batch_id": f"kb_{len(calls)}",
            "zip_name": args[1],
            "conflict_mode": kwargs.get("conflict_mode"),
            "library_mode": kwargs.get("library_mode"),
            "summary": {"total_files": 10, "matched_pairs": len(calls), "imported_count": len(calls), "skipped_count": 0, "error_count": 0},
            "matched_pairs": [],
            "unmatched_pdfs": [],
            "unmatched_xlsx": [],
            "unmatched_prts": [],
            "unmatched_images": [],
            "errors": [],
            "created_at": "2026-06-26T12:00:00",
        }

    monkeypatch.delenv("DEMO_FAST_ZIP_IMPORT", raising=False)
    monkeypatch.setattr(kb_import, "OUTPUT_FOLDER", str(tmp_path / "output"))
    monkeypatch.setattr(kb_import, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)

    app.config["TESTING"] = True
    client = app.test_client()
    login_response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_response.status_code == 200

    for _ in range(2):
        response = client.post(
            "/api/kb/import_zip",
            data={"zip_file": (_zip_with_files(10), "demo.zip"), "library_key": "public"},
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        assert response.get_json().get("cached") is not True

    assert len(calls) == 2
