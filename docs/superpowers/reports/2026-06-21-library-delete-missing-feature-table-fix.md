# Library Delete Missing Feature Table Fix Report

## Root Cause

`_delete_record()` hard-coded deletion from legacy table `drawing_features`.
Current storage design keeps structured fields in `vectors_*` tables, and
`ensure_feature_table()` is a no-op, so `drawing_features` may not exist.

## Fix

- Use current scope's `feature_table` via `scope.get("feature_table")`.
- Check `sqlite_master` before deleting from the legacy feature table.
- Always delete the main record from the current scope's `vector_table`.

## TDD Flow

1. RED: Reverted fix, ran the new test — confirmed `sqlite3.OperationalError: no such table: drawing_features`
2. GREEN: Applied fix, test passed `1 passed`

## Files Changed

- `backend/api/library.py` (fix: `_delete_record`)
- `backend/test_library_storage_init.py` (regression test)

## Verification

```text
$ node .gitnexus/run.cjs impact _delete_record --direction upstream
risk: LOW
direct caller: delete_library_record
affected processes: Delete_library_record → _load_feature_report_json,
  Delete_library_record → Ensure_scope_registry, etc. (6 total)

$ uv run pytest backend/test_library_storage_init.py::test_delete_record_tolerates_missing_legacy_feature_table -q
# RED (before fix):
FAILED — sqlite3.OperationalError: no such table: drawing_features
# GREEN (after fix):
1 passed

$ uv run pytest backend/test_library_storage_init.py -q
9 passed

$ uv run pytest backend/test_kb_import_formats.py backend/test_library_storage_init.py -q
24 passed, 5 warnings (SwigPyPacked deprecation — pre-existing, unrelated)

$ node .gitnexus/run.cjs detect_changes
# After commit: 6 files (pre-existing only), 10 symbols, risk HIGH (from
# unrelated pre-existing changes). _delete_record no longer in working diff.
```

## Scope Confirmation

- Frontend changed: **no**
- Database schema changed: **no**
- Legacy `drawing_features` table recreated: **no**
- Runtime data committed: **no**
- Deployment scripts touched: **no**
