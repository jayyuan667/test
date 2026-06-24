# Task 2 Report: Shared Auth Shell and Login Screen

## Status

DONE_WITH_CONCERNS

## Scope Completed

- Created `frontend-react/src/components/auth/AuthShell.tsx`
- Created `frontend-react/src/components/auth/AuthVisualStage.tsx`
- Migrated `frontend-react/src/pages/LoginPage.tsx` into the shared auth shell
- Added auth-shell/stage styling to `frontend-react/src/index.css`
- Updated `frontend-react/tests/auth-ui.spec.ts` for the new login subtitle and tightened two existing locators that became ambiguous once the brief’s footer copy was added

## Blast Radius / Impact Analysis

Pre-edit GitNexus impact check:

```bash
node .gitnexus/run.cjs impact LoginPage --direction upstream
```

Result:

- Target: `LoginPage`
- Risk: `LOW`
- Direct upstream caller: `AppShell`
- Affected processes: `App → UseAuth`, `App → UseToast`

This matched the task guidance to keep the change in the unauthenticated view layer and avoid auth logic/request-flow edits.

## TDD Evidence

### RED

Added the required subtitle assertion:

```ts
await expect(page.getByText('进入图纸检视台，继续你的工艺流程。')).toBeVisible()
```

Initial focused run showed the suite was not yet configured correctly from repo root, then with the frontend server running the focused spec failed against the old UI before implementation:

```bash
npm exec -- playwright test tests/auth-ui.spec.ts --config=playwright.config.ts --project=chromium --grep "shows login screen"
```

Observed failures during RED:

- Missing new auth-shell content before implementation
- Existing test locators became too broad once the required footer copy and password toggle were present

### GREEN

After implementing the shell, stage, login migration, and CSS, the focused test passed:

```bash
npm exec -- playwright test tests/auth-ui.spec.ts --config=playwright.config.ts --project=chromium --grep "shows login screen"
```

Result:

- `1 passed (1.2s)`

## Verification

Build verification:

```bash
npm run build
```

Result:

- Build succeeded

Broader auth UI verification:

```bash
npm exec -- playwright test tests/auth-ui.spec.ts --config=playwright.config.ts --project=chromium
```

Result:

- `shows login screen with auth stage and form panel`: PASS
- `keeps form as priority on narrow screens`: PASS
- `switches from login to register without losing themed shell`: FAIL

Failure reason:

- `RegisterPage` still renders the pre-redesign standalone card and does not include `auth-visual-stage`
- `RegisterPage.tsx` was outside the write scope for this task, so I did not change it

## GitNexus Change Check

Pre-commit staged check:

```bash
node .gitnexus/run.cjs detect_changes --scope staged
```

Result:

- Changes: `5 files, 1 symbol`
- Risk: `medium`
- Changed symbol: `LoginPage`
- Affected flows: `App → UseAuth`, `App → UseToast`

## Commit

- `f7e716e feat: add themed auth shell for login`

## Concerns

- The full `auth-ui.spec.ts` file is still not green because the register screen has not been migrated to the shared auth shell yet.
- The task brief’s stated write scope excluded `frontend-react/src/pages/RegisterPage.tsx`, so I left that failure untouched and reported it explicitly.

---

## Follow-up Fixes (Reviewer Round)

### Scope

- Kept changes inside the existing Task 2 files only
- Did not modify `RegisterPage.tsx`

### Fixes Applied

1. Reduced palette drift in `frontend-react/src/index.css`
   - Reworked the auth shell background to use the existing `--navy-*`, `--bg-page`, and `--flame-glow` tokens
   - Replaced the visibly separate raw blue accents in the stage with the existing navy system
   - Kept the auth panel and stage aligned with the existing slate/navy/flame palette rather than introducing a parallel color language

2. Restored accessibility-oriented selectors in `frontend-react/tests/auth-ui.spec.ts`
   - Replaced `#username` and `#password` checks with `getByLabel(..., { exact: true })`
   - Kept the stricter brand assertion for `.auth-kicker`, since the footer still contains the same product text and would make plain text matching ambiguous

### Verification

Focused auth UI checks:

```bash
npm exec -- playwright test tests/auth-ui.spec.ts --config=playwright.config.ts --project=chromium --grep "shows login screen|keeps form as priority"
```

Output:

```text
Running 2 tests using 1 worker
✓  1 [chromium] › tests/auth-ui.spec.ts:14:3 › auth ui redesign › shows login screen with auth stage and form panel (4.1s)
✓  2 [chromium] › tests/auth-ui.spec.ts:36:3 › auth ui redesign › keeps form as priority on narrow screens (882ms)

2 passed (5.7s)
```

Build verification:

```bash
npm run build
```

Output:

```text
vite v6.4.3 building for production...
transforming...
✓ 65 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.41 kB │ gzip:   0.30 kB
dist/assets/index-eW9z6qsz.css   56.31 kB │ gzip:  11.50 kB
dist/assets/index-CJH2TMbX.js   439.85 kB │ gzip: 128.61 kB
✓ built in 1.07s
```
