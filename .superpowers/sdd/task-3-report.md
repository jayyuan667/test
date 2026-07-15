# Task 3 Report: Isolated snapshot API and resumable events

## Scope

- Added authenticated `GET /api/v1/tasks/<task_id>` snapshot reads.
- Added authenticated, enterprise-isolated `GET /api/v1/tasks/<task_id>/events` SSE reads.
- Added persisted-event normalization and v1 SSE serialization without changing the legacy stream.

## RED

- `.venv/bin/python -m pytest backend/test_tasks_api_v1.py -q`
  - Could not collect because the repository venv has no pytest; no dependency was installed.
- `/Users/caojiayuan/Projects/work/test/.venv/bin/python -m pytest backend/test_tasks_api_v1.py -q`
  - `2 failed, 1 passed`; both failures were the expected missing-route 404 behavior.
- `/Users/caojiayuan/Projects/work/test/.venv/bin/python -m pytest backend/test_task_events_v1.py -q`
  - Collection failed with the expected `ModuleNotFoundError: backend.services.task_event_stream`.

## GREEN

- Snapshot/isolation: `17 passed, 1 warning`.
- New/legacy events: `5 passed`.
- Final combined verification: `22 passed, 1 warning`.

## Tests added

- Snapshot authentication, owned-task schema version, and cross-enterprise 404 isolation.
- SQLite `id` to v1 `seq` normalization.
- SSE `id:`, `event:`, and JSON `data:` framing.
- Strict `after=N` replay filtering using SQLite `id > N`.

## Commit

- `feat: expose resumable v1 task reads` (commit hash recorded in handoff).

## Concerns

- The repository `.venv` lacks pytest, so verification used an existing Python 3.11 environment with the project dependencies; nothing was installed.
- `backend/test_data_isolation.py` passes but emits one pre-existing background-thread warning because Onshape credentials are absent and its batch cleanup races the test fixture.
- The v1 stream deliberately does not synthesize terminal events; it replays persisted terminal events, avoiding duplicate terminal delivery while keeping legacy stream behavior untouched.
