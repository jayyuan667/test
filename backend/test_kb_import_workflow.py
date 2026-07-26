import sqlite3


def test_vector_table_has_workflow_run_id(monkeypatch, tmp_path):
    from backend import library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)

    library_scope.ensure_vector_table("vectors_private_test")
    library_scope.ensure_import_tracking_tables()

    conn = sqlite3.connect(db_path)
    try:
        vector_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(vectors_private_test)"
            ).fetchall()
        }
        batch_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(kb_import_batches)"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "workflow_run_id" in vector_columns
    assert "workflow_run_id" in batch_columns


def test_upsert_record_persists_workflow_run_id(monkeypatch, tmp_path):
    from backend import library_scope
    from backend.api import library as library_api

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(library_api, "DB_PATH", db_path)
    monkeypatch.setattr(
        library_api, "create_query_vector", lambda _text: None
    )

    scope = library_scope.ensure_scope(
        "wf-lib",
        "Workflow Lib",
        scope_type="private",
        enterprise_id=6,
    )
    draft = library_api._build_draft(
        "Y1", "Y1.txt", "zip", "【图号】Y1", ["0010@车@车端面"]
    )
    draft["enterprise_id"] = 6
    draft["workflow_run_id"] = "wf_zip_import_test"

    library_api._upsert_record(
        draft, replace=False, library_key=scope["library_key"]
    )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT prefix, enterprise_id, workflow_run_id "
            f"FROM {scope['vector_table']} WHERE prefix = ?",
            ("Y1",),
        ).fetchone()
    finally:
        conn.close()

    assert row == ("Y1", 6, "wf_zip_import_test")


# ── Task 3: Permission, validation, rollback ──────────────────────────────


def test_permission_rejects_enterprise_admin_public_write(monkeypatch, tmp_path):
    from backend import kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    library_scope.initialize_library_storage()

    scope, error = kb_import_workflow.resolve_zip_import_permission(
        library_mode="public",
        library_name="",
        library_key="public",
        enterprise_id=6,
        is_super_admin=False,
        batch_id="kb_test",
    )

    assert scope is None
    assert error[1] == 403
    assert "公共工艺库" in error[0]["error"]


def test_permission_rejects_super_admin_new_private_without_enterprise(
    monkeypatch, tmp_path,
):
    from backend import kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    library_scope.initialize_library_storage()

    # super_admin with enterprise_id=None tries to create a NEW private scope
    scope, error = kb_import_workflow.resolve_zip_import_permission(
        library_mode="private_empty",
        library_name="orphan_scope",
        library_key="",  # no existing key → new scope
        enterprise_id=None,
        is_super_admin=True,
        batch_id="kb_test",
    )

    assert scope is None
    assert error[1] == 403
    assert "指定目标企业" in error[0]["error"]


def test_permission_allows_super_admin_existing_private(
    monkeypatch, tmp_path,
):
    from backend import kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    library_scope.initialize_library_storage()

    # Create an existing private scope owned by enterprise 6
    library_scope.ensure_scope(
        "existing_private",
        "Existing Private",
        scope_type="private",
        enterprise_id=6,
    )

    # super_admin tries to write to that EXISTING scope — allowed
    scope, error = kb_import_workflow.resolve_zip_import_permission(
        library_mode="private_empty",
        library_name="",
        library_key="existing_private",
        enterprise_id=None,
        is_super_admin=True,
        batch_id="kb_test",
    )

    assert error is None
    assert scope is not None
    assert scope["library_key"] == "existing_private"


def test_validation_fails_when_visible_count_mismatches(
    monkeypatch, tmp_path,
):
    from backend import kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)

    scope = library_scope.ensure_scope(
        "wf-lib", "Workflow Lib", scope_type="private", enterprise_id=6
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO {scope['vector_table']} "
            f"(prefix, enterprise_id, workflow_run_id, real) "
            f"VALUES (?, ?, ?, ?)",
            ("Y1", 7, "wf_bad", 1),
        )
        conn.commit()
    finally:
        conn.close()

    report = {
        "batch_id": "kb_bad",
        "enterprise_id": 6,
        "target_library": scope,
        "summary": {"imported_count": 1, "matched_pairs": 1},
        "matched_pairs": [{"status": "imported"}],
        "workflow_run_id": "wf_bad",
    }

    validation = kb_import_workflow.validate_zip_import_result(
        report, enterprise_id=6, is_super_admin=False
    )

    assert validation["status"] == "failed"
    assert validation["error_code"] == "visibility_mismatch"
    assert validation["visible_count"] == 0  # enterprise_id=6 visible = 0
    assert validation["inserted_count"] == 1  # wf_bad has 1 row


def test_rollback_deletes_only_current_workflow(monkeypatch, tmp_path):
    from backend import kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)

    scope = library_scope.ensure_scope(
        "wf-lib", "Workflow Lib", scope_type="private", enterprise_id=6
    )
    library_scope.ensure_import_tracking_tables()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO {scope['vector_table']} "
            f"(prefix, enterprise_id, workflow_run_id, real) "
            f"VALUES (?, ?, ?, ?)",
            ("Y1", 6, "wf_current", 1),
        )
        conn.execute(
            f"INSERT INTO {scope['vector_table']} "
            f"(prefix, enterprise_id, workflow_run_id, real) "
            f"VALUES (?, ?, ?, ?)",
            ("Y2", 6, "wf_other", 1),
        )
        conn.commit()
    finally:
        conn.close()

    report = {
        "target_library": scope,
        "enterprise_id": 6,
        "batch_id": "kb_current",
    }
    rollback = kb_import_workflow.rollback_zip_import(
        report, workflow_run_id="wf_current"
    )

    conn = sqlite3.connect(db_path)
    try:
        prefixes = [
            row[0]
            for row in conn.execute(
                f"SELECT prefix FROM {scope['vector_table']} ORDER BY prefix"
            ).fetchall()
        ]
    finally:
        conn.close()

    assert rollback["status"] == "completed"
    assert rollback["deleted_records"] == 1
    assert prefixes == ["Y2"]


def test_rollback_restores_replaced_records(monkeypatch, tmp_path):
    """P0-1: replace-mode rollback must restore old records via snapshots."""
    from backend import kb_import_workflow, library_scope, workflow_harness

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)

    scope = library_scope.ensure_scope(
        "wf-lib", "Workflow Lib", scope_type="private", enterprise_id=6
    )
    library_scope.ensure_import_tracking_tables()

    # Insert old record
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO {scope['vector_table']} "
            f"(prefix, enterprise_id, workflow_run_id, real, context) "
            f"VALUES (?, ?, ?, ?, ?)",
            ("Y1", 6, "wf_old", 1, "old source text"),
        )
        conn.commit()
    finally:
        conn.close()

    # Save snapshot of old record BEFORE replace
    workflow_harness.save_rollback_snapshot(
        "wf_current", scope["vector_table"], "Y1",
        {
            "prefix": "Y1",
            "enterprise_id": 6,
            "workflow_run_id": "wf_old",
            "real": 1,
            "context": "old source text",
        },
    )

    # Simulate INSERT OR REPLACE overwriting old record
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {scope['vector_table']} "
            f"(prefix, enterprise_id, workflow_run_id, real, context) "
            f"VALUES (?, ?, ?, ?, ?)",
            ("Y1", 6, "wf_current", 1, "new source text"),
        )
        conn.commit()
    finally:
        conn.close()

    # Rollback
    report = {
        "target_library": scope,
        "enterprise_id": 6,
        "batch_id": "kb_current",
    }
    rollback = kb_import_workflow.rollback_zip_import(
        report, workflow_run_id="wf_current"
    )

    assert rollback["status"] == "completed"
    assert rollback["restored_snapshots"] == 1

    # Old record is back
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT prefix, context, workflow_run_id "
            f"FROM {scope['vector_table']} WHERE prefix = ?",
            ("Y1",),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "Y1"
    assert row[1] == "old source text"


def test_rollback_safe_never_raises(monkeypatch, tmp_path):
    """P1-5: rollback_zip_import_safe must return status dict even on error."""
    from backend import kb_import_workflow

    # Pass a report with no vector_table — inner rollback returns skipped,
    # but the safe wrapper should still work.
    result = kb_import_workflow.rollback_zip_import_safe(
        {"target_library": {}, "batch_id": "x"}, workflow_run_id="wf_x"
    )
    assert result["attempted"] is False
    assert result["status"] == "skipped"


def test_validate_cached_result_passes_on_valid_cache(
    monkeypatch, tmp_path,
):
    from backend import (
        kb_import_workflow,
        library_scope,
        workflow_harness,
    )

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)

    library_scope.initialize_library_storage()
    library_scope.ensure_scope(
        "my_lib", "My Lib", scope_type="private", enterprise_id=6
    )

    cache_key = kb_import_workflow.build_zip_cache_key(
        zip_hash="abc123",
        enterprise_id=6,
        library_key="my_lib",
        conflict_mode="replace",
    )

    run = workflow_harness.create_workflow_run(
        "zip_import",
        enterprise_id=6,
        user_id=1,
        library_key="my_lib",
        cache_key=cache_key,
    )
    workflow_harness.finish_workflow_run(run["run_id"], "completed")

    validation = kb_import_workflow.validate_cached_result(
        cached_report={},
        cached_workflow_run_id=run["run_id"],
        zip_hash="abc123",
        enterprise_id=6,
        is_super_admin=False,
        library_key="my_lib",
        conflict_mode="replace",
    )

    assert validation["status"] == "passed"
    assert validation["cached"] is True


def test_validate_cached_result_fails_on_enterprise_mismatch(
    monkeypatch, tmp_path,
):
    from backend import (
        kb_import_workflow,
        library_scope,
        workflow_harness,
    )

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)

    library_scope.initialize_library_storage()

    run = workflow_harness.create_workflow_run(
        "zip_import", enterprise_id=6, user_id=1, library_key="public"
    )
    workflow_harness.finish_workflow_run(run["run_id"], "completed")

    # Request with a different enterprise_id
    validation = kb_import_workflow.validate_cached_result(
        cached_report={},
        cached_workflow_run_id=run["run_id"],
        zip_hash="abc",
        enterprise_id=99,  # different!
        is_super_admin=False,
        library_key="public",
        conflict_mode="replace",
    )

    assert validation["status"] == "failed"
    assert validation["error_code"] == "cache_enterprise_mismatch"


def test_replace_rollback_restores_vector_and_raw_content(monkeypatch, tmp_path):
    """P0-1 integration: failed replace rollback must restore old vector + content."""
    from backend import kb_import_workflow, library_scope, workflow_harness

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)

    scope = library_scope.ensure_scope(
        "wf-lib",
        "Workflow Lib",
        scope_type="private",
        enterprise_id=6,
    )
    library_scope.ensure_import_tracking_tables()
    vector_table = scope["vector_table"]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO {vector_table} "
            "(prefix, vector, content, context, enterprise_id, workflow_run_id, real) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Y1", b"old-vector", '["0010@车@旧"]', "old context", 6, "wf_old", 1),
        )
        conn.commit()
    finally:
        conn.close()

    assert workflow_harness.snapshot_existing_record("wf_current", vector_table, "Y1") is True

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {vector_table} "
            "(prefix, vector, content, context, enterprise_id, workflow_run_id, real) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Y1", b"new-vector", '["0010@车@新"]', "new context", 6, "wf_current", 1),
        )
        conn.commit()
    finally:
        conn.close()

    rollback = kb_import_workflow.rollback_zip_import(
        {"target_library": scope, "enterprise_id": 6, "batch_id": "kb_current"},
        workflow_run_id="wf_current",
    )

    assert rollback["status"] == "completed"
    assert rollback["restored_snapshots"] == 1

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT prefix, vector, content, context, enterprise_id, workflow_run_id "
            f"FROM {vector_table} WHERE prefix = ?",
            ("Y1",),
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        "Y1",
        b"old-vector",
        '["0010@车@旧"]',
        "old context",
        6,
        "wf_old",
    )


def test_rollback_safe_reports_restore_failure(monkeypatch, tmp_path):
    """P1-5: restore failure must bubble to rollback_failed, not completed."""
    from backend import kb_import_workflow, library_scope, workflow_harness

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    monkeypatch.setattr(workflow_harness, "DB_PATH", db_path)

    scope = library_scope.ensure_scope(
        "wf-lib",
        "Workflow Lib",
        scope_type="private",
        enterprise_id=6,
    )

    def boom(_workflow_run_id):
        raise RuntimeError("restore failed on purpose")

    monkeypatch.setattr(kb_import_workflow, "restore_rollback_snapshots", boom)

    result = kb_import_workflow.rollback_zip_import_safe(
        {"target_library": scope, "enterprise_id": 6, "batch_id": "kb_current"},
        workflow_run_id="wf_current",
    )

    assert result["attempted"] is True
    assert result["status"] == "rollback_failed"
    assert "restore failed on purpose" in result["error"]


def test_permission_rejects_super_admin_existing_orphan_private_scope(
    monkeypatch,
    tmp_path,
):
    """super_admin must not write to an existing private scope with enterprise_id=NULL."""
    from backend import kb_import_workflow, library_scope

    db_path = str(tmp_path / "vectors.db")
    monkeypatch.setattr(library_scope, "DB_PATH", db_path)
    monkeypatch.setattr(kb_import_workflow, "DB_PATH", db_path)
    library_scope.initialize_library_storage()

    library_scope.ensure_scope(
        "orphan_private",
        "Orphan Private",
        scope_type="private",
        enterprise_id=None,
    )

    scope, error = kb_import_workflow.resolve_zip_import_permission(
        library_mode="private_empty",
        library_name="",
        library_key="orphan_private",
        enterprise_id=None,
        is_super_admin=True,
        batch_id="kb_test",
    )

    assert scope is None
    assert error[1] == 403
    assert "归属未知" in error[0]["error"]
