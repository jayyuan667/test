# Library Delete Missing Feature Table Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复删除知识库记录时因旧 `drawing_features` 表不存在导致 `DELETE /api/library/records/<id>` 返回 500 的问题。

**Architecture:** 当前结构化字段已合并到各个 `vectors_*` 表，`drawing_features` / `drawing_features_<library>` 是遗留表，可能不存在。删除记录时必须以当前 library scope 为准删除主 vector 表记录；遗留 feature 表只在存在时清理，不存在时不能阻断删除流程。

**Tech Stack:** Python 3.11.15、Flask、SQLite、pytest、GitNexus。

## Global Constraints

- 必须先写失败测试，再改生产代码。
- 必须在修改 `_delete_record` 前运行 GitNexus impact：`node .gitnexus/run.cjs impact _delete_record --direction upstream`。
- 如果 impact 显示 HIGH 或 CRITICAL，暂停并报告；当前预期是 LOW。
- 只允许修改：
  - `backend/api/library.py`
  - `backend/test_library_storage_init.py`
  - 可选实施报告：`docs/superpowers/reports/2026-06-21-library-delete-missing-feature-table-fix.md`
- 不允许修改前端、不允许改数据库 schema、不允许恢复创建 `drawing_features` 旧表。
- 不允许把运行产物目录提交，例如 `backups/`、`uploads/`、`output/`、`db_data/`、`.env`。
- 提交前必须运行 `node .gitnexus/run.cjs detect_changes`。

---

## Root Cause

线上错误：

```text
DELETE /api/library/records/3?library_key=lib_20260620233713 HTTP/1.1" 500
sqlite3.OperationalError: no such table: drawing_features
```

当前 `backend/api/library.py` 的 `_delete_record()` 在删除任意库记录时执行：

```python
cursor.execute("DELETE FROM drawing_features WHERE drawing_id = ?", (prefix,))
```

但 `backend/library_scope.py` 中 `ensure_feature_table()` 已是 no-op：

```python
def ensure_feature_table(table_name: str):
    # Structured filter columns are now part of the vector table.
    # This function is kept as a no-op so existing callers don't break.
    pass
```

因此旧表不存在是合法状态。删除逻辑必须兼容旧表缺失。

---

## File Structure

```text
backend/api/library.py
  _delete_record(record_id: int, library_key: str = "")
  修复点：删除当前 scope vector 表记录后，只有当 scope feature_table 存在时才清理遗留 feature 表。

backend/test_library_storage_init.py
  新增回归测试：没有 drawing_features 旧表时，删除私有库记录不抛 OperationalError，且主 vector 表记录被删除。

docs/superpowers/reports/2026-06-21-library-delete-missing-feature-table-fix.md
  可选：实施报告，记录 impact、测试、detect_changes 输出。
```

---

### Task 1: Add failing regression test

**Files:**
- Modify: `backend/test_library_storage_init.py`

**Interfaces:**
- Consumes: `library_scope.initialize_library_storage()`
- Consumes: `library_scope.ensure_scope(library_key, library_name)`
- Consumes: `library_api._delete_record(record_id, library_key)`
- Produces: Test `test_delete_record_tolerates_missing_legacy_feature_table`

- [ ] **Step 1: Confirm impact before editing production symbol**

Run:

```bash
node .gitnexus/run.cjs impact _delete_record --direction upstream
```

Expected:

```text
risk: LOW
direct caller: delete_library_record
```

If risk is HIGH or CRITICAL, stop and report before continuing.

- [ ] **Step 2: Add failing test**

In `backend/test_library_storage_init.py`, add this test immediately after `test_empty_library_browse_returns_zero_results`:

```python
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
```

- [ ] **Step 3: Run test and verify RED**

Run:

```bash
uv run pytest backend/test_library_storage_init.py::test_delete_record_tolerates_missing_legacy_feature_table -q
```

Expected failure:

```text
sqlite3.OperationalError: no such table: drawing_features
```

If the test passes before production code changes, the test is not proving the bug; stop and inspect the local code state.

---

### Task 2: Fix `_delete_record` with scope-aware legacy table cleanup

**Files:**
- Modify: `backend/api/library.py`

**Interfaces:**
- Consumes: `_scope_from_key(library_key)` returning `scope["vector_table"]` and `scope["feature_table"]`
- Produces: `_delete_record(record_id, library_key)` that deletes from `vector_table`, and only deletes from `feature_table` when the table exists

- [ ] **Step 1: Replace hard-coded legacy table delete**

In `backend/api/library.py`, update `_delete_record()` from this shape:

```python
def _delete_record(record_id: int, library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]
    existing = _fetch_record_by_id(record_id, library_key=library_key)
    if not existing:
        return None

    prefix = existing.get("prefix", "")
    source_task_id = existing.get("source_task_id", "")
    preview_task_id = existing.get("preview_task_id", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {vector_table} WHERE id = ?", (record_id,))
        if prefix:
            cursor.execute("DELETE FROM drawing_features WHERE drawing_id = ?", (prefix,))
        conn.commit()
    finally:
        conn.close()
```

to this:

```python
def _delete_record(record_id: int, library_key: str = ""):
    scope = _scope_from_key(library_key)
    vector_table = scope["vector_table"]
    feature_table = scope.get("feature_table") or ""
    existing = _fetch_record_by_id(record_id, library_key=library_key)
    if not existing:
        return None

    prefix = existing.get("prefix", "")
    source_task_id = existing.get("source_task_id", "")
    preview_task_id = existing.get("preview_task_id", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {vector_table} WHERE id = ?", (record_id,))
        if prefix and feature_table:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (feature_table,))
            if cursor.fetchone():
                cursor.execute(f"DELETE FROM {feature_table} WHERE drawing_id = ?", (prefix,))
        conn.commit()
    finally:
        conn.close()
```

Do not add `CREATE TABLE drawing_features`. The correct behavior is to tolerate the missing legacy table.

- [ ] **Step 2: Run target test and verify GREEN**

Run:

```bash
uv run pytest backend/test_library_storage_init.py::test_delete_record_tolerates_missing_legacy_feature_table -q
```

Expected:

```text
1 passed
```

- [ ] **Step 3: Run related backend tests**

Run:

```bash
uv run pytest backend/test_library_storage_init.py -q
```

Expected:

```text
9 passed
```

Run:

```bash
uv run pytest backend/test_kb_import_formats.py backend/test_library_storage_init.py -q
```

Expected:

```text
24 passed
```

- [ ] **Step 4: Run GitNexus change detection**

Run:

```bash
node .gitnexus/run.cjs detect_changes
```

Expected:

- Changed symbol includes `_delete_record`.
- Affected flows include `Delete_library_record ...`.
- Existing unrelated working-tree changes may still make global risk HIGH; report whether HIGH comes from unrelated files.

- [ ] **Step 5: Ensure runtime artifacts are not staged**

Run:

```bash
git status --short
```

Confirm none of these are staged:

```text
backups/
uploads/
output/
db_data/
.env
```

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/api/library.py backend/test_library_storage_init.py
git commit -m "fix: tolerate missing legacy feature table on library delete"
```

Expected: commit contains only the production fix and its regression test.

---

### Task 3: Optional implementation report

**Files:**
- Create: `docs/superpowers/reports/2026-06-21-library-delete-missing-feature-table-fix.md`

**Interfaces:**
- Consumes: Test and GitNexus outputs from Task 1-2
- Produces: Review-ready report for acceptance

- [ ] **Step 1: Create report**

Create `docs/superpowers/reports/2026-06-21-library-delete-missing-feature-table-fix.md`:

```markdown
# Library Delete Missing Feature Table Fix Report

## Root Cause

`_delete_record()` hard-coded deletion from legacy table `drawing_features`.
Current storage design keeps structured fields in `vectors_*` tables, and
`ensure_feature_table()` is a no-op, so `drawing_features` may not exist.

## Fix

- Use current scope's `feature_table`.
- Check `sqlite_master` before deleting from the legacy feature table.
- Always delete the main record from the current scope's `vector_table`.

## Files Changed

- `backend/api/library.py`
- `backend/test_library_storage_init.py`

## Verification

```text
node .gitnexus/run.cjs impact _delete_record --direction upstream
<paste output>

uv run pytest backend/test_library_storage_init.py::test_delete_record_tolerates_missing_legacy_feature_table -q
<paste RED and GREEN outputs, or describe RED then paste GREEN>

uv run pytest backend/test_library_storage_init.py -q
<paste output>

uv run pytest backend/test_kb_import_formats.py backend/test_library_storage_init.py -q
<paste output>

node .gitnexus/run.cjs detect_changes
<paste output>
```

## Scope Confirmation

- Frontend changed: no
- Database schema changed: no
- Legacy `drawing_features` table recreated: no
- Runtime data committed: no
```

- [ ] **Step 2: Commit report**

Run:

```bash
git add docs/superpowers/reports/2026-06-21-library-delete-missing-feature-table-fix.md
git commit -m "docs: report library delete feature table fix"
```

Expected: report commit contains only the report.

---

## Acceptance Checklist for Reviewer

- [ ] Failing test was observed before implementation.
- [ ] `_delete_record` no longer references hard-coded `drawing_features`.
- [ ] `_delete_record` uses `scope.get("feature_table")`.
- [ ] Legacy feature table cleanup is conditional on table existence.
- [ ] Main record is deleted from the active scope's `vector_table`.
- [ ] `uv run pytest backend/test_library_storage_init.py -q` passes.
- [ ] `uv run pytest backend/test_kb_import_formats.py backend/test_library_storage_init.py -q` passes.
- [ ] `node .gitnexus/run.cjs detect_changes` output is included in handoff.
- [ ] No runtime artifacts are staged or committed.

---

## Explicit Non-Goals

- Do not rebuild or migrate the whole library schema.
- Do not reintroduce `drawing_features` table creation.
- Do not change `/api/library/records` frontend behavior.
- Do not alter import ZIP matching or vector retrieval behavior.
- Do not touch deployment scripts.

