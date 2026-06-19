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
