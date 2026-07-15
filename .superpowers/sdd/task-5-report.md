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
