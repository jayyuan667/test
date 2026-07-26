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


def _setup_workflow_mocks(monkeypatch, tmp_path):
    """Point workflow_harness and kb_import_workflow at tmp_path DB."""
    from backend import workflow_harness, kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    library_scope.initialize_library_storage()
    return db_path


def test_import_zip_rejects_archives_smaller_than_production_minimum(
    monkeypatch,
):
    called = False

    def fake_import_zip_knowledge(*args, **kwargs):
        nonlocal called
        called = True
        return {"ok": True}

    from backend.api import kb_import

    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)

    app.config["TESTING"] = True
    client = app.test_client()
    login_response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/kb/import_zip",
        data={"zip_file": (_zip_with_files(9), "tiny.zip")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "至少需要 10 个文件" in response.get_json()["error"]
    assert called is False


def test_demo_fast_zip_import_reuses_cached_report_when_enabled(
    monkeypatch, tmp_path,
):
    from backend.api import kb_import

    calls = []
    db_path = _setup_workflow_mocks(monkeypatch, tmp_path)

    def fake_import_zip_knowledge(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "batch_id": "kb_first",
            "zip_name": args[1],
            "conflict_mode": kwargs.get("conflict_mode"),
            "library_mode": kwargs.get("library_mode"),
            "enterprise_id": kwargs.get("enterprise_id"),
            "workflow_run_id": kwargs.get("workflow_run_id"),
            "target_library": {
                "library_key": "public",
                "scope_type": "public",
                "vector_table": "vectors_v2",
            },
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

    # Mock validation so the route always passes post-import checks
    monkeypatch.setattr(
        kb_import, "validate_zip_import_result",
        lambda report, **kw: {
            "status": "passed",
            "visible_count": report.get("summary", {}).get("imported_count", 0),
            "inserted_count": report.get("summary", {}).get("imported_count", 0),
            "expected_count": report.get("summary", {}).get("imported_count", 0),
            "orphan_count": 0,
        },
    )

    app.config["TESTING"] = True
    client = app.test_client()
    login_response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert login_response.status_code == 200

    first = client.post(
        "/api/kb/import_zip",
        data={
            "zip_file": (_zip_with_files(10), "demo.zip"),
            "library_key": "public",
        },
        content_type="multipart/form-data",
    )
    second = client.post(
        "/api/kb/import_zip",
        data={
            "zip_file": (_zip_with_files(10), "demo.zip"),
            "library_key": "public",
        },
        content_type="multipart/form-data",
    )

    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body.get("cached") is not True
    assert first_body.get("workflow_run_id", "").startswith("wf_zip_import_")
    assert first_body.get("validation", {}).get("status") == "passed"

    assert second.status_code == 200
    second_body = second.get_json()
    assert second_body["cached"] is True
    assert second_body["summary"]["matched_pairs"] == 5
    assert "复用" in second_body.get("message", "")
    assert second_body.get("validation", {}).get("cached") is True
    assert second_body.get("workflow_run_id", "").startswith("wf_zip_import_")

    assert len(calls) == 1  # second request hits cache


def test_demo_fast_zip_import_does_not_cache_when_disabled(
    monkeypatch, tmp_path,
):
    from backend.api import kb_import

    calls = []
    _setup_workflow_mocks(monkeypatch, tmp_path)

    def fake_import_zip_knowledge(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "batch_id": f"kb_{len(calls)}",
            "zip_name": args[1],
            "conflict_mode": kwargs.get("conflict_mode"),
            "library_mode": kwargs.get("library_mode"),
            "enterprise_id": kwargs.get("enterprise_id"),
            "workflow_run_id": kwargs.get("workflow_run_id"),
            "target_library": {
                "library_key": "public",
                "scope_type": "public",
                "vector_table": "vectors_v2",
            },
            "summary": {
                "total_files": 10,
                "matched_pairs": len(calls),
                "imported_count": len(calls),
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

    monkeypatch.delenv("DEMO_FAST_ZIP_IMPORT", raising=False)
    monkeypatch.setattr(kb_import, "OUTPUT_FOLDER", str(tmp_path / "output"))
    monkeypatch.setattr(kb_import, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)
    monkeypatch.setattr(
        kb_import, "validate_zip_import_result",
        lambda report, **kw: {
            "status": "passed",
            "visible_count": report.get("summary", {}).get("imported_count", 0),
            "inserted_count": report.get("summary", {}).get("imported_count", 0),
            "expected_count": report.get("summary", {}).get("imported_count", 0),
            "orphan_count": 0,
        },
    )

    app.config["TESTING"] = True
    client = app.test_client()
    login_response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert login_response.status_code == 200

    for _ in range(2):
        response = client.post(
            "/api/kb/import_zip",
            data={
                "zip_file": (_zip_with_files(10), "demo.zip"),
                "library_key": "public",
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        assert response.get_json().get("cached") is not True
        assert response.get_json().get("workflow_run_id", "").startswith(
            "wf_zip_import_"
        )

    assert len(calls) == 2


def test_zip_import_success_includes_workflow_validation(
    monkeypatch, tmp_path,
):
    from backend.api import kb_import

    _setup_workflow_mocks(monkeypatch, tmp_path)

    def fake_import_zip_knowledge(*args, **kwargs):
        return {
            "batch_id": "kb_success",
            "zip_name": "demo.zip",
            "conflict_mode": kwargs.get("conflict_mode"),
            "library_mode": kwargs.get("library_mode"),
            "enterprise_id": kwargs.get("enterprise_id"),
            "workflow_run_id": kwargs.get("workflow_run_id"),
            "target_library": {
                "library_key": "public",
                "scope_type": "public",
                "vector_table": "vectors_v2",
            },
            "summary": {
                "total_files": 10,
                "matched_pairs": 0,
                "imported_count": 0,
                "skipped_count": 0,
                "error_count": 0,
            },
            "matched_pairs": [],
            "unmatched_pdfs": [],
            "unmatched_xlsx": [],
            "unmatched_prts": [],
            "unmatched_images": [],
            "errors": [],
            "created_at": "2026-06-28T00:00:00",
        }

    monkeypatch.setattr(kb_import, "OUTPUT_FOLDER", str(tmp_path / "output"))
    monkeypatch.setattr(kb_import, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)

    app.config["TESTING"] = True
    client = app.test_client()
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        ).status_code
        == 200
    )

    response = client.post(
        "/api/kb/import_zip",
        data={
            "zip_file": (_zip_with_files(10), "demo.zip"),
            "library_key": "public",
            "library_mode": "public",
        },
        content_type="multipart/form-data",
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["workflow_run_id"].startswith("wf_zip_import_")
    assert body["validation"]["status"] == "passed"


def test_zip_import_validation_failure_rolls_back(monkeypatch, tmp_path):
    from backend.api import kb_import

    _setup_workflow_mocks(monkeypatch, tmp_path)

    def fake_import_zip_knowledge(*args, **kwargs):
        return {
            "batch_id": "kb_bad",
            "zip_name": "demo.zip",
            "conflict_mode": kwargs.get("conflict_mode"),
            "library_mode": kwargs.get("library_mode"),
            "enterprise_id": kwargs.get("enterprise_id"),
            "workflow_run_id": kwargs.get("workflow_run_id"),
            "target_library": {
                "library_key": "public",
                "scope_type": "public",
                "vector_table": "vectors_v2",
            },
            "summary": {
                "total_files": 10,
                "matched_pairs": 1,
                "imported_count": 1,
                "skipped_count": 0,
                "error_count": 0,
            },
            "matched_pairs": [{"status": "imported"}],
            "unmatched_pdfs": [],
            "unmatched_xlsx": [],
            "unmatched_prts": [],
            "unmatched_images": [],
            "errors": [],
            "created_at": "2026-06-28T00:00:00",
        }

    monkeypatch.setattr(kb_import, "OUTPUT_FOLDER", str(tmp_path / "output"))
    monkeypatch.setattr(kb_import, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setattr(kb_import, "import_zip_knowledge", fake_import_zip_knowledge)

    # Force validation failure
    monkeypatch.setattr(
        kb_import,
        "validate_zip_import_result",
        lambda *args, **kwargs: {
            "status": "failed",
            "error_code": "visibility_mismatch",
            "visible_count": 0,
            "inserted_count": 1,
            "expected_count": 1,
        },
    )

    app.config["TESTING"] = True
    client = app.test_client()
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        ).status_code
        == 200
    )

    response = client.post(
        "/api/kb/import_zip",
        data={
            "zip_file": (_zip_with_files(10), "demo.zip"),
            "library_key": "public",
            "library_mode": "public",
        },
        content_type="multipart/form-data",
    )

    body = response.get_json()
    assert response.status_code == 500
    assert body["workflow_run_id"].startswith("wf_zip_import_")
    assert body["error_code"] == "visibility_mismatch"
    assert body["rollback"]["status"] == "completed"


def test_get_zip_import_run_returns_events(monkeypatch, tmp_path):
    from backend import workflow_harness

    db_path = _setup_workflow_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)

    run = workflow_harness.create_workflow_run(
        "zip_import", enterprise_id=None, user_id=1,
    )
    workflow_harness.record_workflow_event(
        run["run_id"], "received", "received", progress_hint=5,
    )
    workflow_harness.update_workflow_metadata(run["run_id"], batch_id="kb_done")
    workflow_harness.finish_workflow_run(
        run["run_id"], "completed", result={"batch_id": "kb_done"},
    )

    app.config["TESTING"] = True
    client = app.test_client()
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        ).status_code
        == 200
    )

    response = client.get(f"/api/kb/import_zip/runs/{run['run_id']}")
    body = response.get_json()

    assert response.status_code == 200
    assert body["run_id"] == run["run_id"]
    assert body["batch_id"] == "kb_done"
    assert body["status"] == "completed"
    assert body["events"][0]["stage"] == "received"
