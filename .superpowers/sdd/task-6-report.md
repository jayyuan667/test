# Task 6 Report: GeneratePage migration and real acceptance

## Status

Complete. `GeneratePage` defaults to the v1 workflow controller and keeps the prior page behind `NEXT_PUBLIC_USE_WORKFLOW_V1=false`. The v1 page contains no direct fetch, EventSource construction, Markdown feature parsing, or polling loop.

## Implementation

- Preserved the original untracked page byte-for-byte in `/tmp/forge-task6-baseline/` before moving it to `LegacyGeneratePage`.
- Added controller-owned upload, annotation, review, cancel, export, event-driven snapshot recovery, and complete flow coverage.
- Rendered canonical feature/source/confidence and process-operation fields directly.
- Persisted the active task ID for reload/resume.
- Fixed browser fetch receiver binding, monotonic real snapshot revisions, and real `process_flow.data` adaptation.
- Added a real Playwright workflow using the exact required PNG and PDF download.

## Verification

- Backend gate: 78 passed, exit 0 (one pre-existing background-thread warning).
- Workflow tests: 38 passed, exit 0, including asset-boundary, evidence-QA, and legacy-characterization gates.
- Focused ESLint: exit 0.
- Production build: exit 0.
- Real Playwright: 1 passed in 2.1m, task `af54cfa7-599e-4fd4-9df7-6b9d9f32f191`; both JSON artifacts passed the post-write sensitive-content scan.
- Legacy health/SSE: health OK; SSE 2 passed. The combined runtime-smoke command remains blocked at collection by the missing user-owned `scripts.runtime_smoke` module and is not reported as passing.
- Evidence and field-level details: `docs/verification/2026-07-15-v1-workflow.md` and `/tmp/forge-v1-evidence/`.

## Concerns

- The prescribed backend gate emits a warning from a background PRT batch thread because Onshape credentials are absent and test cleanup races the thread. All 78 tests pass; Task 6 did not alter that protected PRT path.
- XLSX export requires pandas, which is absent from the active environment. The verified UI export is PDF and succeeds with the real task.
- The workflow Node runner retains its existing `MODULE_TYPELESS_PACKAGE_JSON` informational warning.

## Rejection correction

- Added authenticated preview loading through the workflow client/controller, object-URL ownership/cleanup, visible drawing preview, and source/page links. The page still owns no transport.
- Initial controller state now uses snapshot revision as `lastSeq`; the first stream connects with `after=revision` and does not replay accepted events.
- Finalize, review, and cancel commands capture generation/task identity; late responses after task switch or dispose are ignored.
- Real E2E now supports environment overrides and asserts non-initial progress, visible preview, exact null-confidence display, meaningful linked source, positive feature/operation counts, completed/done/100, same-task reload with preserved row count, sanitized parsed events, final snapshot, and PDF filename/MIME/size/magic.
- Removed the Task 6-added `scripts` runtime-smoke implementation. The missing user-owned `scripts.runtime_smoke` dependency is documented as a legacy smoke limitation rather than absorbed.
- `LegacyGeneratePage` is an immutable transitional fallback. Its provenance, original hash, and deletion criteria are documented in the verification record.
- The legacy removal gate is executable: 14 days, at least 100 real tasks, 99.5% critical-path success, no more than 0.5% error-budget consumption, zero attributable P0/P1 incidents, product and engineering owner approval, and a successful rollback drill within 15 minutes. A workflow characterization test pins the reviewed legacy hash.
- Asset loading now rejects cross-origin, wrong-task, malformed-path, traversal, query, and fragment targets before token access or fetch. Evidence sanitization covers both final snapshot and events, recursively removes secret fields, redacts URLs/home paths, and runs an explicit QA assertion before writes.
