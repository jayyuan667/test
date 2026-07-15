# FORGE v1 Workflow Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build backwards-compatible `/api/v1/tasks/*` contracts and a typed frontend workflow, then prove the real `test.png` upload-to-export path without changing protected model behavior.

**Architecture:** Existing VLM/LLM/RAG/OCR/YOLO/FreeCAD modules remain behind a normalization seam. Backend modules convert persisted legacy results and events into versioned objects. The frontend consumes those objects through one adapter and a pure idempotent reducer; legacy routes remain available for rollback.

**Tech Stack:** Python 3.11, Flask, SQLite, pytest, Next.js 16, React 19, TypeScript, Node test runner, Playwright.

## Global Constraints

- Preserve existing `/api/*` responses and protected core behavior.
- Never fabricate confidence, equipment, duration, evidence, or feature values.
- SQLite is authoritative for status and event sequence.
- New page code may not add direct `fetch`, `EventSource`, Markdown domain parsing, or polling.
- Do not modify `.env`, keys, databases, uploads, or outputs.
- Rebuild only after a failing characterization test proves it is safer than adaptation.
- Acceptance fixture: `/Users/caojiayuan/Documents/测试包/drawing/test.png`.

---

### Task 1: Verification baseline

**Files:** Modify `eslint.config.mjs`, `package.json`.

**Interfaces:** Produces `npm run lint:src` and `npm run test:workflow` for later tasks.

- [ ] **Step 1: Record baseline.** Run `npm run lint > /tmp/forge-lint-before.txt 2>&1; test $? -ne 0`, `npm run build`, and `.venv/bin/python -m pytest backend/test_sse_events.py backend/test_data_isolation.py -q`. Expected: historical lint failure is recorded; build and backend results are known before edits.
- [ ] **Step 2: Prove scope failure.** Run `npx eslint . 2>&1 | tee /tmp/forge-eslint-scope.txt` followed by `! rg '/\.venv/|/output/|/test-results/' /tmp/forge-eslint-scope.txt`. Expected: FAIL because `.venv` appears.
- [ ] **Step 3: Add ignores.** Add `.venv/**`, `output/**`, `uploads/**`, `test-results/**`, `playwright-report/**`, and `backend/**/__pycache__/**` to `globalIgnores`.
- [ ] **Step 4: Add scripts.** Add `"lint:src": "eslint src e2e"` and `"test:workflow": "node --test --experimental-strip-types src/features/drawing-workflow/*.test.ts"`.
- [ ] **Step 5: Verify.** Re-run the scope assertion and `npm run build`. Expected: runtime paths disappear and build exits 0; unrelated historical source errors remain honestly reported.
- [ ] **Step 6: Commit.** Run `git add eslint.config.mjs package.json package-lock.json && git commit -m "chore: establish frontend verification scope"`.

---

### Task 2: Backend v1 snapshot contract

**Files:** Create `backend/domain/__init__.py`, `backend/domain/task_contract.py`, `backend/services/task_snapshot.py`, `backend/test_task_contract_v1.py`.

**Interfaces:** Produces `build_task_snapshot(task_id: str, task: dict, result: dict | None = None) -> dict`.

- [ ] **Step 1: Write failing row tests.** Test a five-column row `['0050','车工','粗车外圆','CW61100','90min']` and assert `trade='车工'`, `content='粗车外圆'`, `equipment=['CW61100']`, `duration_minutes=90`. Test a three-column row and assert empty equipment plus null duration.
- [ ] **Step 2: Verify RED.** Run `.venv/bin/python -m pytest backend/test_task_contract_v1.py -q`. Expected: import failure for the missing module.
- [ ] **Step 3: Implement minimal helpers.** Define `SCHEMA_VERSION='1.0'`, a duration parser that strips `min` and returns integer or `None`, and exact positional mapping. IDs use `op-{code}-{index}`.
- [ ] **Step 4: Verify GREEN.** Re-run the test. Expected: 2 passed.
- [ ] **Step 5: Write failing feature tests.** For `【螺纹与螺孔】M115×3-6g`, assert kind `thread`, confidence `None`, source method `legacy_text`. For structured JSON containing confidence `0.91`, page `1`, bbox `[10,20,30,40]`, assert all values are preserved.
- [ ] **Step 6: Verify RED and implement.** Run the focused test, implement structured-first normalization and a legacy bracket parser that preserves text but never invents confidence, then re-run. Expected: 4 passed.
- [ ] **Step 7: Add state test.** With status `processing` and progress `100`, assert state remains `processing`, phase is `drawing_analysis`, and schema is `1.0`. Implement an explicit state-to-phase map.
- [ ] **Step 8: Verify regressions.** Run `.venv/bin/python -m pytest backend/test_task_contract_v1.py backend/test_history_task_store.py -q`.
- [ ] **Step 9: Commit.** Run `git add backend/domain backend/services/task_snapshot.py backend/test_task_contract_v1.py && git commit -m "feat: normalize v1 drawing task snapshots"`.

---

### Task 3: Isolated snapshot API and resumable events

**Files:** Create `backend/api/v1/__init__.py`, `backend/api/v1/tasks.py`, `backend/services/task_event_stream.py`, `backend/test_tasks_api_v1.py`, `backend/test_task_events_v1.py`; modify `backend/api/__init__.py`.

**Interfaces:** Produces `GET /api/v1/tasks/<id>`, `GET /api/v1/tasks/<id>/events?after=N`, `normalize_event()`, and `pack_v1_sse()`.

- [ ] **Step 1: Write failing route tests.** Using temporary auth/task DBs, assert unauthenticated access returns 401, an owned task returns schema `1.0`, and another enterprise's task returns 404.
- [ ] **Step 2: Verify RED.** Run `.venv/bin/python -m pytest backend/test_tasks_api_v1.py -q`. Expected: route 404.
- [ ] **Step 3: Implement snapshot route.** Apply `login_required`, call `assert_task_access`, load `build_task_dict`, return 404 when absent, and return `build_task_snapshot`. Register blueprint at `/api/v1`.
- [ ] **Step 4: Verify isolation.** Run `.venv/bin/python -m pytest backend/test_tasks_api_v1.py backend/test_data_isolation.py -q`.
- [ ] **Step 5: Write failing event tests.** Normalize DB event ID 7 and assert `seq=7`; serialize it and assert the chunk starts with `id: 7`, then `event:` and JSON `data:`. Insert IDs 1,2,3 and assert `after=2` emits only 3.
- [ ] **Step 6: Verify RED and implement.** Map `step_start→phase_started`, `step_complete→phase_completed`, `process_stream→operation_upserted`, `complete→task_completed`, `error→task_failed`. Emit `retry: 1500`, heartbeat comments, and only `id > after`.
- [ ] **Step 7: Verify old and new streams.** Run `.venv/bin/python -m pytest backend/test_task_events_v1.py backend/test_sse_events.py -q`.
- [ ] **Step 8: Commit.** Run `git add backend/api/v1 backend/api/__init__.py backend/services/task_event_stream.py backend/test_tasks_api_v1.py backend/test_task_events_v1.py && git commit -m "feat: expose resumable v1 task reads"`.

---

### Task 4: v1 commands through existing workflow behavior

**Files:** Modify `backend/api/v1/tasks.py`, `backend/test_tasks_api_v1.py`; modify `backend/api/upload.py`, `backend/api/annotations.py`, or `backend/api/export.py` only when a failing characterization test requires extraction.

**Interfaces:** Produces v1 upload, annotation-finalize, review, cancel, and export commands. Successful JSON commands return an updated snapshot; no route calls another local route over HTTP.

- [ ] **Step 1: Write failing upload test.** Post an in-memory PNG to `/api/v1/tasks`, patch only the expensive pipeline launcher, and assert 202 plus an initial snapshot containing the original file name.
- [ ] **Step 2: Verify RED.** Run `.venv/bin/python -m pytest backend/test_tasks_api_v1.py -q -k upload`. Expected: 404 or 405.
- [ ] **Step 3: Extract only if required.** First characterize the old upload response. If request handling cannot be reused, extract `create_drawing_task(file_storage, enterprise_id: int | None, library_key: str = 'public') -> str`; both routes call it. Do not change pipeline selection, prompts, model calls, or transitions.
- [ ] **Step 4: Implement and verify upload.** Run `.venv/bin/python -m pytest backend/test_tasks_api_v1.py backend/test_upload_capability_gate.py -q`.
- [ ] **Step 5: Repeat RED/GREEN for commands.** Add one failing test each for `/annotations/finalize`, `/review`, `/cancel`, and `/export`; delegate to existing workflow functions. Errors use `error.code`, `message`, `retryable`, `phase`, and `details` exactly.
- [ ] **Step 6: Run protected regressions.** Run `.venv/bin/python -m pytest backend/test_tasks_api_v1.py backend/test_annotation_finalize_restore.py backend/test_upload_capability_gate.py backend/test_data_isolation.py backend/test_history_task_store.py -q`.
- [ ] **Step 7: Commit changed files only.** Stage the v1 files and any old file actually refactored, then commit `feat: route v1 commands through existing workflow`.

---

### Task 5: Typed frontend workflow module

**Files:** Create `src/features/drawing-workflow/types.ts`, `reducer.ts`, `reducer.test.ts`, `api.ts`, `api.test.ts`, `controller.ts`, `controller.test.ts`, `mock.ts`.

**Interfaces:** Produces `DrawingWorkflowClient`, `reduceWorkflowState`, and `createDrawingWorkflowController`.

- [ ] **Step 1: Write failing sequence test.** Using `node:test`, create state with `lastSeq=8`, apply an event with `seq=8`, and assert reducer returns the same object.
- [ ] **Step 2: Write failing upsert test.** Apply two `operation_upserted` events with ID `op-1`; assert one row exists and the second payload replaces its content.
- [ ] **Step 3: Verify RED.** Run `npm run test:workflow`. Expected: missing `types.ts` or `reducer.ts`.
- [ ] **Step 4: Implement exact types and minimal reducer.** `WorkflowState` contains `snapshot`, `operationsById`, `operationOrder`, `lastSeq`, `connection`, and `error`. Implement sequence rejection, progress, operation upsert, terminal completion/failure, and higher-revision snapshot replacement only.
- [ ] **Step 5: Verify GREEN.** Run `npm run test:workflow`.
- [ ] **Step 6: Write failing client tests.** Inject `fetchImpl`, `eventSourceFactory`, `apiBase`, and `getToken`. Assert v1 URLs, Bearer auth, preserved 403 metadata, and reconnect URL `after=<lastSeq>`.
- [ ] **Step 7: Implement the client interface.** Define `upload(file)`, `getSnapshot(taskId)`, `connect(taskId, after, onEvent)`, `finalizeAnnotations`, `submitReview`, `cancel`, and `exportUrl`. Controller owns cleanup and reconnect; reducer alone changes state.
- [ ] **Step 8: Add Mock parity test.** Assert Mock returns the same `TaskSnapshot` shape and uses `confidence=null` when no real confidence source exists.
- [ ] **Step 9: Verify and commit.** Run `npm run test:workflow` and `npx eslint src/features/drawing-workflow`; expect all pass and zero lint errors. Commit as `feat: add typed drawing workflow client`.

---

### Task 6: GeneratePage migration and real vertical acceptance

**Files:** Modify `src/components/pages/GeneratePage.tsx`, `src/services/index.ts`, `src/services/types.ts`; create `e2e/v1-workflow.spec.ts`, `docs/verification/2026-07-15-v1-workflow.md`.

**Interfaces:** Consumes workflow controller state. Produces the current UI backed by v1 and reproducible acceptance evidence.

- [ ] **Step 1: Write failing controller flow test.** With an in-memory client, execute upload, feature-ready, review, operation-upsert, and completion. Assert exact feature, operation, progress, and completion state without Markdown parsing.
- [ ] **Step 2: Verify RED, add minimal selectors, verify GREEN.** Run `npm run test:workflow` before and after implementation.
- [ ] **Step 3: Wire rollback flag.** Use `const useWorkflowV1 = process.env.NEXT_PUBLIC_USE_WORKFLOW_V1 !== 'false'`. The v1 branch renders snapshot fields directly; null confidence displays `未提供` and shows source method/page.
- [ ] **Step 4: Remove page-owned v1 transport.** The v1 branch contains no direct `fetch`, `new EventSource`, Markdown feature parsing, or polling. Legacy fallback remains through its adapter rather than inline duplication.
- [ ] **Step 5: Write failing real E2E.** Log in, upload the exact `test.png`, observe a real phase, confirm review, wait for a structured operation, reload and resume the same task, then download an export. Do not mock network or use a synthetic PDF.
- [ ] **Step 6: Verify RED.** Run `PW_TEST_HTML_REPORT_OPEN=never npx playwright test --config=e2e/playwright.prod.config.ts e2e/v1-workflow.spec.ts --reporter=line`. Failure must be the first unimplemented v1 assertion, not login or missing fixture.
- [ ] **Step 7: Fix gaps through lower-level RED/GREEN tests.** Do not weaken E2E assertions. Save sanitized snapshot JSON, SSE transcript, screenshots, and export under `/tmp/forge-v1-evidence/`; never store keys or tokens.
- [ ] **Step 8: Run backend gate.** Run `.venv/bin/python -m pytest backend/test_task_contract_v1.py backend/test_task_events_v1.py backend/test_tasks_api_v1.py backend/test_sse_events.py backend/test_annotation_finalize_restore.py backend/test_upload_capability_gate.py backend/test_data_isolation.py -q`.
- [ ] **Step 9: Run frontend gate.** Run `npm run test:workflow`, focused ESLint over touched frontend files, `npm run build`, then the real Playwright test. Every command must exit 0.
- [ ] **Step 10: Verify legacy compatibility.** Run `curl -fsS http://localhost:5390/api/health` and `.venv/bin/python -m pytest backend/test_runtime_smoke.py backend/test_sse_events.py -q`.
- [ ] **Step 11: Document and commit.** Record task ID, timestamps, commands, results, explicit null fields, and evidence paths in the verification document. Commit source/tests/document only; do not add `/tmp`, exports, drawings, DBs, `.env`, or tokens.

---

## Plan Self-Review

- Contract, isolation, resumable events, commands, typed frontend state, rollback, protected regressions, and real E2E all have test-first tasks.
- Backend and frontend share the approved `TaskSnapshot`, `Feature`, `ProcessOperation`, and `TaskEvent` fields.
- Complete three-column redesign and reuse-first workflow remain outside this cycle.
- Targeted rebuild is allowed only after a failing characterization test and may not alter model semantics.
- Rollback remains available through old routes and `NEXT_PUBLIC_USE_WORKFLOW_V1=false`.
