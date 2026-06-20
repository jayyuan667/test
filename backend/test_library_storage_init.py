import sqlite3

from backend import library_scope
from backend.api import library as library_api


REQUIRED_TABLES = {
    "kb_library_scopes",
    "vectors_v2",
    "kb_import_batches",
    "kb_import_items",
}


def _use_temp_database(monkeypatch, tmp_path):
    db_path = str(tmp_path / "library.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(library_api, "DB_PATH", db_path)
    return db_path


def test_initialize_library_storage_creates_required_tables(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)

    library_scope.initialize_library_storage()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert REQUIRED_TABLES <= tables


def test_initialize_library_storage_is_idempotent_and_preserves_records(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO vectors_v2 (prefix, content, real) VALUES (?, ?, ?)",
            ("TEST-001", "[]", 1),
        )
        conn.commit()

    library_scope.initialize_library_storage()

    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM vectors_v2 WHERE prefix = ?",
            ("TEST-001",),
        ).fetchone()[0]
    assert count == 1


def test_empty_library_browse_returns_zero_results(monkeypatch, tmp_path):
    _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()

    unlock = library_scope.browse_unlock_status()
    records = library_api._list_records(page=1, page_size=3)

    assert unlock == {"can_browse": False, "imported_batches": 0}
    assert records["total"] == 0
    assert records["items"] == []


def test_upsert_record_uses_feature_report_text_as_vector_fallback(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()

    calls = []

    class FakeVector:
        def tobytes(self):
            return b"vector-bytes"

    def fake_create_query_vector(text):
        calls.append(text)
        return FakeVector()

    monkeypatch.setattr(library_api, "create_query_vector", fake_create_query_vector)
    monkeypatch.setattr(library_api, "extract_structured_features", lambda text: {})

    draft = {
        "prefix": "D125A-181200A003",
        "content": "0010\t车\t车外圆",
        "process_summary": "0010 车 车外圆",
        "feature_report_text": "【零件名称】D125A-181200A003\n【技术要求】调质处理",
        "process_list": [{"code": "0010", "trade": "车", "content": "车外圆"}],
    }

    library_api._upsert_record(draft, replace=True, library_key="")

    assert calls == ["【零件名称】D125A-181200A003\n【技术要求】调质处理"]
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT context, key_features, vector_content, feature_report_text, vector FROM vectors_v2 WHERE prefix = ?",
            ("D125A-181200A003",),
        ).fetchone()

    assert row[0] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[1] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[2] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[3] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[4] == b"vector-bytes"


def test_retrieval_check_skips_without_embedding_key(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="【零件名称】D125A-181200A003",
        library_key="",
    )

    assert result == {
        "status": "skipped",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "EMBEDDING_API_KEY not configured",
    }


def test_retrieval_check_reports_matching_saved_prefix(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "fake-key")

    def fake_query(text, top_k, min_similarity, library_key):
        assert text == "【零件名称】D125A-181200A003"
        assert top_k == 5
        assert min_similarity == 0.0
        assert library_key == "private_demo"
        return [
            {"drawing_id": "OTHER", "similarity": 0.51},
            {"drawing_id": "D125A-181200A003", "similarity": 0.83},
        ]

    monkeypatch.setattr(library_api, "query_by_vector_similarity", fake_query)

    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="【零件名称】D125A-181200A003",
        library_key="private_demo",
    )

    assert result == {
        "status": "ok",
        "searchable": True,
        "matched_prefix": "D125A-181200A003",
        "similarity": 0.83,
        "reason": "",
    }


def test_retrieval_check_reports_no_match(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "fake-key")
    monkeypatch.setattr(
        library_api,
        "query_by_vector_similarity",
        lambda text, top_k, min_similarity, library_key: [{"drawing_id": "OTHER", "similarity": 0.51}],
    )

    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="【零件名称】D125A-181200A003",
        library_key="",
    )

    assert result == {
        "status": "failed",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "saved prefix not returned by retrieval self-check",
    }
