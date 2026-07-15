# Task 5 Report: Typed frontend workflow module

## Status

Complete. Added the typed v1 workflow contract, reducer, HTTP/SSE client, reconnecting controller, mock adapter, and focused tests without modifying `GeneratePage`.

## TDD evidence

- Reducer RED: `npm run test:workflow` exited 1 because `reducer.ts` did not exist.
- Reducer GREEN: 2 tests passed for stale-sequence identity and operation upsert replacement.
- Client/controller/mock RED: `npm run test:workflow` exited 1 because `api.ts`, `controller.ts`, and `mock.ts` did not exist; the reducer tests remained green.
- First implementation run identified unsupported TypeScript parameter-property syntax under Node strip-only mode; explicit fields fixed that runner compatibility issue.
- Final focused suite covers v1/Bearer requests, structured 403 errors, shared 401 handling, resumable authenticated SSE, controller cleanup/reconnect, mock confidence parity, sequence idempotence, operation upsert, and snapshot revision ordering.

## Contract and security decisions

- HTTP requests use `Authorization: Bearer <token>`.
- Native `EventSource` cannot set request headers, so SSE uses the backend's existing `?token=` fallback together with `after=<lastSeq>`. The module does not log URLs, tokens, request headers, or errors containing credentials.
- The controller owns the live connection, closes the failed instance, and reconnects using reducer state `lastSeq`.
- Mock legacy-derived features use `confidence: null`; no synthetic confidence is generated.

## Verification

- `npm run test:workflow`: 9 passed, 0 failed (Node reports the repository's module-type warning).
- `npx eslint src/features/drawing-workflow`: exit 0, no errors or warnings.
- `git diff --check`: exit 0.

## Concerns

- Query-string SSE authentication is required by the current backend/native EventSource combination but is less secure than header auth because URLs can be exposed by surrounding infrastructure. A future backend-issued short-lived stream ticket or cookie-only same-origin transport would reduce exposure.
- An additional `npx tsc --noEmit` check reports TS5097 for the `.ts` import suffixes required by the configured Node test command because `allowImportingTsExtensions` is not enabled. The prescribed Task 5 test and lint gates pass; changing shared package/tsconfig files was explicitly outside this task's allowed scope.

## Rejection corrections (2026-07-15)

The preceding SSE and TypeScript concerns are superseded by this correction.

### RED evidence

- Production type check reproduced TS5097 plus the incomplete `DrawingWorkflowClient` test cast.
- Transport/reducer RED: 4 failures proved the default native EventSource dependency, missing feature merge, uncleared completion error, and lost cancelled terminal state.
- Controller RED: 3 failures proved cross-task event contamination, terminal reconnect scheduling, and absent backoff delays.
- Normalizer RED: the new contract suite failed because no runtime normalization boundary existed.
- SSE parser RED: a named frame with `id: 7` and `event: phase_progress` incorrectly retained conflicting JSON `seq/type` values.

### GREEN changes

- Default streaming now uses `fetch` plus `ReadableStream` and Bearer auth. It parses SSE comments, retry, id, event, multiline data, ignores malformed JSON, preserves structured HTTP errors, invokes the 401 hook, and aborts idempotently without logging credentials or URLs.
- An injectable `StreamTransport` keeps deterministic transport tests without weakening the secure default.
- Runtime snapshot/event normalizers make nullable wire collections and numbers safe, reject invalid envelope identities, and preserve absent confidence as `null`.
- Controller start now cancels prior timers/streams, resets per-task state, isolates async generations and task IDs, seals all terminal states, and uses capped exponential backoff with injectable scheduler/randomness.
- Reducer now upserts `feature_ready`, clears snapshot errors on completion, and preserves cancelled terminal state.
- `allowImportingTsExtensions` is enabled alongside the existing `noEmit`, resolving the configured Node test imports without changing runtime output.

### Final verification

- `npm run test:workflow`: 21 passed, 0 failed; the existing package module-type warning remains informational.
- `npx eslint src/features/drawing-workflow`: exit 0.
- `npx tsc --noEmit --pretty false`: exit 0.
- `npm run build`: exit 0; Next.js production build and static generation completed.
- `git diff --check`: exit 0.

### Remaining concern

- The Node test runner reports `MODULE_TYPELESS_PACKAGE_JSON` because the shared package is not declared ESM. Adding `type: module` could affect unrelated application tooling, so this correction leaves the harmless warning in place; all requested gates pass.

## Stream and wire-contract re-review corrections

### RED

- Byte-split SSE tests lost the EOF frame when CR/LF delimiters were split across chunks.
- Canonical `task_failed.payload.status="cancelled"` produced `failed`.
- Invalid enum/range fixtures leaked negative revision/duration, invalid source kinds/statuses, out-of-range confidence, and a `snapshot: null` payload key.
- Typed HTTP status tests showed stream disconnects did not expose 403 to the controller.

### GREEN

- Replaced delimiter search with an incremental line parser that preserves a trailing CR between reads, handles CRLF/LF/CR, multiline data and comments, and flushes the final frame at EOF. The test exercises every possible byte split in a mixed-delimiter stream plus one-byte chunks.
- `StreamDisconnect` now carries typed `status`, `WorkflowError`, retryability, and optional server `retryMs`. HTTP 401 still calls the unauthorized hook once; 401/403/nonretryable failures dispatch `error_received` and permanently close that controller stream. Only retryable/transport disconnects schedule reconnects.
- Valid SSE `retry:` updates the controller's exponential base, capped by `maxReconnectDelay`.
- Normalizers now membership-check all contract enums and range-check finite progress, confidence, revision, page count, duration, page and bbox numbers. Invalid nested snapshots are omitted rather than assigned null.
- Reducer accepts canonical `payload.status="cancelled"` while retaining compatibility with `payload.state`.

### Verification

- `npm run test:workflow`: 27 passed, 0 failed.
- `npx eslint src/features/drawing-workflow`: exit 0.
- `npx tsc --noEmit --pretty false`: exit 0.
- `npm run build`: exit 0.
- `git diff --check`: exit 0.
