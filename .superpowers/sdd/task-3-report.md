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
- The v1 stream performs three bounded 50 ms grace reads after observing terminal status. If no persisted terminal arrives, it synthesizes one at `max(persisted id)+1`; reconnect cursors and subsequently persisted terminal rows suppress duplication.

## Critical/Important Review Fix RED

- Event/snapshot expansion command initially failed collection because `V1_EVENT_TYPES` did not exist.
- Snapshot-only RED: `2 failed, 3 passed`; both failures showed `build_task_dict()` discarded persisted `updated_at`.
- Terminal reconnect RED: `1 failed`; when a persisted terminal later claimed the prior synthetic sequence, reconnect incorrectly synthesized a second terminal.

## Critical/Important Review Fix GREEN

- Added legal-type adaptation for real legacy types and unknown types; raw process chunks are `phase_progress`, while only structured operations with a stable ID become `operation_upserted`.
- Added bounded terminal drain, stable synthesis, duplicate stored-terminal suppression, status-before-save coverage, and reconnect idempotence.
- Added route authentication/isolation, query/header cursor, malformed JSON, heartbeat, real emitter persistence, route-level legacy/v1 smoke, strict sequence/envelope, and full persisted snapshot coverage.
- Preserved `updated_at` in the authoritative `build_task_dict()` reconstruction path.
- Final command: `/Users/caojiayuan/Projects/work/test/.venv/bin/python -m pytest backend/test_tasks_api_v1.py backend/test_task_events_v1.py backend/test_sse_events.py backend/test_data_isolation.py -q`
  - `44 passed, 1 warning in 7.42s`.
