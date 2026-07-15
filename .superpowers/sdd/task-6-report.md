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

- Backend gate: 76 passed, exit 0 (one pre-existing background-thread warning).
- Workflow tests: 30 passed, exit 0.
- Focused ESLint: exit 0.
- Production build: exit 0.
- Real Playwright: 1 passed in 2.2m, task `63a8d0d5-c36b-4d8d-8646-e76614141033`.
- Legacy health/runtime/SSE: health OK; 3 passed, exit 0.
- Evidence and field-level details: `docs/verification/2026-07-15-v1-workflow.md` and `/tmp/forge-v1-evidence/`.

## Concerns

- The prescribed backend gate emits a warning from a background PRT batch thread because Onshape credentials are absent and test cleanup races the thread. All 76 assertions pass; Task 6 did not alter that protected PRT path.
- XLSX export requires pandas, which is absent from the active environment. The verified UI export is PDF and succeeds with the real task.
- The workflow Node runner retains its existing `MODULE_TYPELESS_PACKAGE_JSON` informational warning.
