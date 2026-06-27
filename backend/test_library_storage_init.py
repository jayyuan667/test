import sqlite3

from flask import Flask, g

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
    app = Flask(__name__)
    with app.test_request_context("/api/library/records?library_key=public"):
        g.current_user = {"role": "user", "enterprise_id": 1}
        records = library_api._list_records(page=1, page_size=3)

    assert unlock == {"can_browse": False, "imported_batches": 0}
    assert records["total"] == 0
    assert records["items"] == []


def test_delete_record_tolerates_missing_legacy_feature_table(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()
    scope = library_scope.ensure_scope("private_demo", "Private Demo")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"INSERT INTO {scope['vector_table']} (prefix, content, real) VALUES (?, ?, ?)",
            ("Y5", "[]", 1),
        )
        record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drawing_features'"
        ).fetchone() is None
        conn.commit()

    deleted = library_api._delete_record(record_id, library_key="private_demo")

    assert deleted["prefix"] == "Y5"
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            f"SELECT COUNT(*) FROM {scope['vector_table']} WHERE id = ?",
            (record_id,),
        ).fetchone()[0]
    assert count == 0


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


def test_retrieval_check_skips_with_empty_vector_text(monkeypatch):
    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="",
        library_key="",
    )

    assert result == {
        "status": "skipped",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "vector_text is empty",
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


def test_vector_table_migration_adds_retrieval_check_columns(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()

    with sqlite3.connect(db_path) as conn:
        conn.execute("ALTER TABLE vectors_v2 RENAME TO vectors_legacy")
        conn.execute(
            """
            CREATE TABLE vectors_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prefix TEXT UNIQUE,
                vector BLOB,
                content TEXT,
                real INTEGER DEFAULT 1
            )
            """
        )
        conn.commit()

        library_api._migrate_vector_table(conn.cursor(), "vectors_v2")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(vectors_v2)")}

    assert {
        "retrieval_check_status",
        "retrieval_check_similarity",
        "retrieval_check_matched_prefix",
        "retrieval_check_reason",
        "retrieval_checked_at",
    } <= columns


def test_records_return_persisted_retrieval_check(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()
    library_api._ensure_provenance_columns()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO vectors_v2 (
                prefix, content, real, retrieval_check_status,
                retrieval_check_similarity, retrieval_check_matched_prefix,
                retrieval_check_reason, retrieval_checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("D125", "[]", 1, "ok", 0.83, "D125", "", "2026-06-26T12:00:00"),
        )
        record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    detail = library_api._fetch_record_by_id(record_id)
    app = Flask(__name__)
    with app.test_request_context("/api/library/records?library_key=public"):
        g.current_user = {"role": "user", "enterprise_id": 1}
        listed = library_api._list_records(page=1, page_size=10)

    expected = {
        "status": "ok",
        "similarity": 0.83,
        "matched_prefix": "D125",
        "reason": "",
        "checked_at": "2026-06-26T12:00:00",
    }
    assert detail["retrieval_check"] == expected
    assert listed["items"][0]["retrieval_check"] == expected


def test_commit_persists_retrieval_check(monkeypatch, tmp_path):
    _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()

    class FakeVector:
        def tobytes(self):
            return b"vector-bytes"

    monkeypatch.setattr(library_api, "create_query_vector", lambda text: FakeVector())
    monkeypatch.setattr(library_api, "extract_structured_features", lambda text: {})
    monkeypatch.setattr(
        library_api,
        "_build_retrieval_check",
        lambda prefix, vector_text, library_key="": {
            "status": "ok",
            "searchable": True,
            "matched_prefix": prefix,
            "similarity": 0.91,
            "reason": "",
        },
    )

    app = Flask(__name__)
    with app.test_request_context(
        "/api/library/commit",
        method="POST",
        json={
            "action": "replace",
            "draft": {
                "prefix": "D126",
                "feature_report_text": "【零件名称】D126",
                "process_list": [{"code": "0010", "trade": "车", "content": "车外圆"}],
            },
        },
    ):
        g.current_user = {"role": "user", "enterprise_id": 1}
        response = library_api.commit_library_record.__wrapped__()

    body = response.get_json()

    assert body["retrieval_check"]["similarity"] == 0.91
    assert body["saved"]["retrieval_check"]["status"] == "ok"
    assert body["saved"]["retrieval_check"]["similarity"] == 0.91
