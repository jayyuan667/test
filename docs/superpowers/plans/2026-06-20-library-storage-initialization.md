# Library Storage Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a new or empty SQLite knowledge-base database immediately browsable without HTTP 500 errors.

**Architecture:** Add one idempotent initializer in `library_scope.py` that creates the scope registry, public vector table, and import tracking tables. Invoke it when the library API loads and keep `browse_unlock_status()` independently safe for direct callers.

**Tech Stack:** Python 3.11, SQLite, Flask, pytest.

## Global Constraints

- Do not delete, clear, or replace existing database records.
- Use `CREATE TABLE IF NOT EXISTS` for new initialization.
- Do not modify YOLO, SSE, process streaming, or frontend behavior.
- Preserve existing knowledge-base import behavior.

---

### Task 1: Initialize empty knowledge-base storage

**Files:**
- Create: `backend/test_library_storage_init.py`
- Modify: `backend/library_scope.py`
- Modify: `backend/api/library.py`

**Interfaces:**
- Produces: `ensure_import_tracking_tables() -> None`
- Produces: `initialize_library_storage() -> None`
- Preserves: `browse_unlock_status() -> {"can_browse": bool, "imported_batches": int}`

- [ ] **Step 1: Write failing empty-database tests**

Tests use a temporary SQLite path and patch both `library_scope.DB_PATH` and
`api.library.DB_PATH`. They assert initialization creates
`kb_library_scopes`, `vectors_v2`, `kb_import_batches`, and `kb_import_items`;
repeated initialization preserves a seeded row; empty browse status and
record listing return zero results.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
./.venv/bin/python -m pytest backend/test_library_storage_init.py -q
```

Expected: failure because `initialize_library_storage` does not exist.

- [ ] **Step 3: Implement idempotent initialization**

Add import tracking table creation and a composed initializer in
`backend/library_scope.py`. Update `browse_unlock_status()` to ensure its
table before querying. Replace the library API's module-level
`ensure_scope_registry()` call with `initialize_library_storage()`.

- [ ] **Step 4: Verify tests**

Run:

```bash
./.venv/bin/python -m pytest backend/test_library_storage_init.py backend/test_core.py backend/test_startup_import.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Update and verify the current database**

Run the initializer against `db_data/2d-v.db`, inspect required tables, and
call the Flask test client for `/api/library/scopes` and
`/api/library/records?page=1&page_size=3`; both must return HTTP 200.

- [ ] **Step 6: Check scope and commit**

Run `detect-changes`, `git diff --check`, and commit only the database
initialization files.
