# Task 5 Report: Structured Process Workstation and Page Composition

## Scope

- Added the structured `ProcessWorkspace` with semantic desktop table and labeled narrow-screen rows.
- Replaced the validation-card page with the four-step fused workstation.
- Reused the v1 workflow controller for upload, recovery, SSE state, commands, authenticated preview assets, and export URL ownership.
- Added ordered multi-page preview loading with task/snapshot epoch guards and per-source pending-request deduplication.
- Added backward inspection (`reachedStep`, `selectedStep`, `followLatest`) without replaying completed commands.
- Extended feature review with an explicit read-only historical mode.

## RED

The first tests failed because:

1. `ProcessWorkspace.tsx` did not exist.
2. `GeneratePage.tsx` loaded only the first preview URL and had no `Promise.all` multi-page path.
3. `GeneratePage.tsx` had no four-step reached/view/follow-latest composition.
4. The old page exposed the technical `connection · seq` status.

## GREEN

- Process rows render only structured operation fields. Missing trade, equipment, duration, and source/notes are explicit and never inferred.
- Real task phase and bounded progress remain visible while process operations stream in.
- Preview components receive object URLs only; they never fetch or own persistence.
- All preview source URLs are passed to `controller.loadPreview` in source order. A task/revision/source signature plus load epoch prevents stale state publication; pending deduplication prevents overlapping snapshot refreshes from revoking a newer URL for the same page.
- Explicit backend states take precedence in step mapping: an annotation snapshot containing features remains on step 02, and `process_generation` reaches step 04 before the first operation arrives.
- Selecting an earlier step disables follow-latest. Starting upload/finalize/review restores it. Historical feature steps do not render an owning command.
- Static architecture guards reject direct fetch, EventSource, polling, Markdown parsing, and query-token transport in `GeneratePage`.

## Verification

- `npm run test:workflow`: 45 passed.
- `npx -y tsx --test src/components/workflow/*.test.ts src/components/workflow/*.test.tsx`: 18 passed.
- `npx eslint src/components/pages/GeneratePage.tsx src/components/workflow`: passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed (Next.js 16.2.10 production build).

The plan's raw `node --test --experimental-strip-types ...*.tsx` command is not executable on the installed Node 26.3.0 (and was reproduced on Node 22.23.1) because native type stripping does not register the `.tsx` extension. The transient `tsx` runner was used for the same test files without changing project dependencies.

## Self-review

- No legacy transport or state logic was copied.
- No unrelated dirty files were staged.
- CSS remains scoped beneath `.forge-workflow` except the existing drawing dialog portal selectors.
- Export remains delegated to `controller.exportUrl`; the workstation component only invokes a callback.
- The v1 operation schema has no dedicated source field. The UI therefore labels the final column `依据 / 备注`, renders the real `note` when present, and otherwise says `来源未提供`.
