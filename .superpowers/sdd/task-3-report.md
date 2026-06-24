# Task 3 Report: Port the Shared Shell to Registration and Mobile Behavior

## Scope

- Task brief read from `.superpowers/sdd/task-3-brief.md`
- Owned write scope respected:
  - `frontend-react/src/pages/RegisterPage.tsx`
  - `frontend-react/src/index.css`
  - `frontend-react/tests/auth-ui.spec.ts`

## Blast Radius Assessment

- Requested baseline: medium-high risk
- Manual dependency check performed because GitNexus `impact` / `detect_changes` tools were not available in this session
- Direct render path:
  - `frontend-react/src/App.tsx` renders `RegisterPage` from the unauthenticated auth-page switch
- Shared styling surface:
  - `frontend-react/src/index.css` auth shell classes are shared with login
- Practical risk:
  - Changes affect register presentation, auth cross-page consistency, and mobile auth layout
  - Auth APIs, submission flow, and login contract were left unchanged

## TDD Evidence

### RED

1. Added the required assertions to `frontend-react/tests/auth-ui.spec.ts`:
   - register subtitle visible
   - `.auth-shell` visible on register
   - mobile `auth-visual-stage` `min-height` equals `220px`

2. First command from the brief was not a valid Playwright invocation in this environment because `npm exec` consumed the flags incorrectly and produced an invalid `page.goto('/')` run. I corrected the harness invocation and captured the intended failing behavior with:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --project=chromium --grep "switches from login to register form|keeps form as priority on narrow screens"
```

3. RED result:
   - `switches from login to register form` failed because text `注册后可申请企业授权并继续工艺入库与生成流程。` was missing
   - `keeps form as priority on narrow screens` failed because `.auth-stage` `min-height` was `260px`, not `220px`

### GREEN

1. Implemented the minimal production changes:
   - Migrated `RegisterPage` to `AuthShell`
   - Set register title/subtitle/footer to the exact brief values
   - Preserved existing register validation, toggles, submit flow, and navigation behavior
   - Updated shared auth CSS mobile rules to the brief values

2. Targeted GREEN verification:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --project=chromium --grep "keeps form as priority on narrow screens"
```

- Result: pass

3. Required full auth UI verification:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --project=chromium
```

- Result: `3 passed (13.9s)`

## Change Summary

- `frontend-react/src/pages/RegisterPage.tsx`
  - Replaced legacy standalone card layout with shared `AuthShell`
  - Kept all field structure and behavior functionally identical
  - Updated footer branding to match the shared auth shell contract

- `frontend-react/src/index.css`
  - Set `.auth-stage` `min-height: 320px`
  - Set `.auth-stage` `border-radius: 28px`
  - Changed mobile breakpoint to `900px`
  - On mobile:
    - `.auth-shell` uses one column
    - `.auth-stage-wrap` moves before the panel and uses `min-height: 220px`
    - `.auth-panel-wrap` aligns to top with `padding-top: 20px`
    - `.auth-panel` expands to full width
    - `.auth-stage` uses `min-height: 220px`

- `frontend-react/tests/auth-ui.spec.ts`
  - Restored register parity assertions
  - Added mobile CSS assertion for the visual stage

## Diff Verification

- Verified the code diff was limited to the three owned files before commit using:

```bash
git diff -- frontend-react/src/pages/RegisterPage.tsx frontend-react/src/index.css frontend-react/tests/auth-ui.spec.ts
git status --short frontend-react/src/pages/RegisterPage.tsx frontend-react/src/index.css frontend-react/tests/auth-ui.spec.ts
```

- GitNexus `detect_changes()` was not available in this session, so I used manual diff verification instead.

## Commit

- `ef0e92f feat: align register page with auth shell`

## Concerns

- One intermediate targeted Playwright run hit a transient `page.goto('/')` timeout while the local dev server was otherwise healthy; the isolated rerun passed, and the required full auth-ui spec passed afterward.

## Follow-up Fixes

Reviewer feedback identified two real issues in the Task 3 mobile behavior.

### Issue 1: Mobile auth layout still let the stage dominate the first viewport

- Root cause:
  - The mobile breakpoint moved the visual stage above the form, but it only changed `min-height`
  - Desktop `height: calc(100dvh - 168px)` and large stage/copy spacing still made the stage occupy most of the first screen
- Fix:
  - Kept the stage as a compact atmosphere header on narrow screens
  - Reduced mobile stage height to `136px`
  - Tightened stage copy spacing and stage text size
  - Reduced mobile panel padding so the form enters the first viewport much earlier

### Issue 2: Mobile test asserted a style token instead of the user-visible behavior

- Root cause:
  - The prior assertion only checked `min-height: 220px`
  - That would not catch regressions where the visual stage still consumed the first viewport and pushed the form below the fold
- Fix:
  - Replaced the CSS-only assertion with DOM-rect checks
  - The mobile test now verifies:
    - stage height stays compressed
    - stage bottom stays in the upper part of the viewport
    - form panel begins within the first viewport
    - username field also lands within the first viewport

## Focused Verification Evidence

### RED

Command:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --project=chromium --grep "keeps form as priority on narrow screens"
```

Output:

```text
Running 1 test using 1 worker

(node:3117) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)
  ✘  1 [chromium] › tests/auth-ui.spec.ts:38:3 › auth ui redesign › keeps form as priority on narrow screens (3.9s)


  1) [chromium] › tests/auth-ui.spec.ts:38:3 › auth ui redesign › keeps form as priority on narrow screens

    Error: expect(received).toBeLessThan(expected)

    Expected: < 180
    Received:   676

      57 |     expect(usernameBox).not.toBeNull()
      58 |
    > 59 |     expect(stageBox!.height).toBeLessThan(180)
         |                              ^
      60 |     expect(panelBox!.top).toBeLessThan(260)
      61 |     expect(usernameBox!.top).toBeLessThan(420)
      62 |   })

  1 failed
    [chromium] › tests/auth-ui.spec.ts:38:3 › auth ui redesign › keeps form as priority on narrow screens
```

### GREEN

Command:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --project=chromium --grep "switches from login to register form|keeps form as priority on narrow screens"
```

Output:

```text
Running 2 tests using 1 worker

(node:3202) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)
  ✓  1 [chromium] › tests/auth-ui.spec.ts:27:3 › auth ui redesign › switches from login to register form (8.0s)
  ✓  2 [chromium] › tests/auth-ui.spec.ts:38:3 › auth ui redesign › keeps form as priority on narrow screens (6.2s)

  2 passed (14.7s)
```
