# Task 4 Report: v1 workflow commands

## Outcome

- Added authenticated v1 upload, annotation-finalize, review, cancel, and export routes.
- Upload returns HTTP 202 with the initial v1 snapshot and original drawing name.
- Successful JSON workflow commands return the current v1 snapshot.
- Export preserves the existing binary GET/POST export behavior, including edited POST rows.
- Legacy command errors are adapted to the exact v1 fields: `code`, `message`, `retryable`, `phase`, and `details`.
- Existing workflow Python entry points are invoked directly; no local HTTP callback was introduced.
- No legacy route file, protected pipeline, model, prompt, or state-transition implementation was changed.

## TDD evidence

- Upload RED: `1 failed, 5 deselected`; expected 404 for missing `POST /api/v1/tasks`.
- Command RED: `4 failed, 6 deselected`; all four missing command routes returned 404.
- GREEN: `backend/test_tasks_api_v1.py`: `10 passed`, then `11 passed` after exact error-envelope coverage.
- The repository `.venv` has no pytest (`No module named pytest`). As in Tasks 2 and 3, tests used the existing `/Users/caojiayuan/Projects/work/test/.venv/bin/python` environment. No dependency was installed.

## Verification

- `backend/test_tasks_api_v1.py backend/test_annotation_finalize_restore.py backend/test_data_isolation.py backend/test_history_task_store.py`: `28 passed, 1 warning`.
- `py_compile` passed for both changed Python files.
- `git diff --check` passed.
- Protected suite including `backend/test_upload_capability_gate.py`: `28 passed, 1 failed, 1 warning`.

## Concerns

- `backend/test_upload_capability_gate.py::test_pdf_upload_is_rejected_before_task_creation` is a pre-existing baseline mismatch: it makes an unauthenticated request to the legacy `/api/upload_drawing`, which is protected by `login_required`, and therefore receives 401 before the PDF capability gate; the test expects 422. It also fails when run alone. Task 4 did not weaken legacy authentication to satisfy it.
- The existing data-isolation suite emits its known background-thread warning because Onshape credentials are absent and batch cleanup races the fixture (`KeyError` after the credential error).
- v1 routes directly invoke decorated legacy Python handlers. This deliberately preserves authentication, quota, persistence, workflow selection, export override, and transition behavior without absorbing the untracked legacy files into this commit.

## Changed files

- `backend/api/v1/tasks.py`
- `backend/test_tasks_api_v1.py`
- `.superpowers/sdd/task-4-report.md`

## Quality review correction

The first implementation directly invoked decorated legacy views and manually
interpreted only common two-tuple returns. Quality review rejected that coupling.
The correction adds `backend/services/legacy_task_commands.py`, the single,
explicitly transitional seam around request-context legacy handlers. It removes
only the outer `login_required` wrapper, retains upload quota enforcement,
normalizes all Flask return forms with `current_app.make_response`, catches and
sanitizes internal exceptions, and exposes a stable `CommandResult`. The v1
route no longer imports or invokes legacy handlers directly.

### Correction RED

- Focused suite: `7 failed, 15 passed`.
- Failures proved the missing adapter, unsupported bare serializer response,
  and absent 400/403/409/500 adapter contract.

### Correction GREEN

- Focused Task 4 suite: `22 passed`.
- Task 4 plus protected regressions except the known capability baseline:
  `39 passed, 1 known warning`.
- Full requested suite: `39 passed, 1 failed, 1 known warning`; the sole failure
  remains the pre-existing unauthenticated capability-gate mismatch documented
  above.
- Added coverage for single wrapper invocation, Response/two-tuple/three-tuple
  normalization, real POST export row forwarding with only the serializer
  boundary mocked, command-specific cross-enterprise non-mutation, exact safe
  400/403/409 envelopes, and sanitized 500 responses.
