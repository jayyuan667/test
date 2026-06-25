# Task 2 Report: Split Admin Console Semantics By Role

## Status

DONE_WITH_CONCERNS

## Scope Completed

- Updated `frontend-react/src/pages/admin/AdminPage.tsx` to split admin-console title, intro copy, and visible tabs by `user.role`
- Updated `frontend-react/src/pages/admin/EnterpriseTab.tsx` so non-super-admin access returns `null`
- Updated `frontend-react/src/pages/admin/UsersTab.tsx` to show `企业筛选` only for super admins, `成员列表` for enterprise admins, and to stop sending enterprise reassignment updates for enterprise-admin edits
- Updated `frontend-react/src/pages/admin/QuotaTab.tsx` to show role-specific summary framing: `平台配额概览` vs `本企业配额概览`
- Added focused Playwright coverage in `frontend-react/tests/auth-ui.spec.ts` for enterprise-admin wording isolation and super-admin governance visibility

## Requirements Mapping

- Enterprise admin sees `企业运营台`
- Enterprise admin sees intro `管理本企业成员、配额与授权状态。`
- Enterprise admin does not see the enterprise-governance tab
- Enterprise admin does not see platform-governance wording such as `平台管理`, `全部企业`, `跨企业治理`
- Super admin keeps `企业管理` tab visibility
- Super admin sees `平台管理` and `平台配额概览`

## Blast Radius / Impact Analysis

Pre-edit GitNexus impact checks:

```bash
cd frontend-react
npx gitnexus impact AdminPage --direction upstream
npx gitnexus impact EnterpriseTab --direction upstream
npx gitnexus impact UsersTab --direction upstream
npx gitnexus impact QuotaTab --direction upstream
```

Results:

- `AdminPage`: risk `LOW`, 1 direct caller (`AppLayout`), 1 affected process group
- `EnterpriseTab`: risk `LOW`, direct caller `AdminPage`
- `UsersTab`: risk `LOW`, direct caller `AdminPage`
- `QuotaTab`: risk `LOW`, direct caller `AdminPage`

This matched the task boundary: admin-console-only wording and visibility changes, no backend capability expansion.

## TDD Evidence

### RED

Added these focused tests first in `frontend-react/tests/auth-ui.spec.ts`:

- `enterprise admin sees enterprise console wording only`
- `super admin sees enterprise governance tab`

Then ran:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --grep "console wording|enterprise governance tab"
```

Observed failures before implementation:

- enterprise-admin test failed because `企业运营台` did not exist
- super-admin test was still exercising the old generic admin framing

### GREEN

After implementing the admin-shell and tab wording split, reran the same focused command:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --grep "console wording|enterprise governance tab"
```

Result:

- `2 passed (5.2s)`

## GitNexus Change Check

Pre-commit staged check:

```bash
git add frontend-react/src/pages/admin/AdminPage.tsx \
        frontend-react/src/pages/admin/EnterpriseTab.tsx \
        frontend-react/src/pages/admin/UsersTab.tsx \
        frontend-react/src/pages/admin/QuotaTab.tsx \
        frontend-react/tests/auth-ui.spec.ts
cd frontend-react
npx gitnexus detect_changes --scope staged
```

Result:

- Changes: `5 files, 9 symbols`
- Affected processes: `6`
- Risk level: `high`
- Changed symbols: `AdminPage`, `tabs`, `EnterpriseTab`, `fetchEnterprises`, `QuotaTab`, `fetchQuotas`, `UsersTab`, `fetchData`, `saveEditing`

Affected execution flows reported by GitNexus:

- `AdminPage → Request`
- `UsersTab → Request`
- `EnterpriseTab → Request`
- `HandleToggleActive → Request`
- `AdminPage → UseToast`
- `AdminPage → UseAuth`

The high staged-risk rating came from touching several admin symbols at once, but the changed files remained within the requested task-owned admin surface.

## Verification

Focused verification run:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --grep "console wording|enterprise governance tab"
```

Output summary:

```text
Running 2 tests using 1 worker
✓ enterprise admin sees enterprise console wording only
✓ super admin sees enterprise governance tab
2 passed (5.2s)
```

## Commit

- `781c24f feat: split admin console semantics by role`

## Concerns

- The workspace still contains many unrelated uncommitted changes outside this task, including files explicitly excluded from my write scope. I left them untouched.
- Several task-owned files already contained uncommitted visual/style edits before this task. I preserved and worked with those edits rather than reverting them, so the task commit is scoped to the five requested files but is not a pristine isolation from all earlier local changes inside those same files.

---

## Reviewer Follow-up Fixes

### Fixes Applied

- Updated `frontend-react/src/pages/admin/AdminPage.tsx` so `activeTab` is corrected to the first visible tab whenever role-driven tab visibility makes the current tab invalid
- Updated `frontend-react/tests/auth-ui.spec.ts` so `mockAuthSession` accepts `User` rather than only `typeof UNASSIGNED_USER`
- Extended enterprise-admin coverage to assert:
  - `本企业配额概览` appears on the quota tab
  - enterprise-admin quota save sends only `{ quota_total: ... }`
  - enterprise-admin status toggle sends only `{ is_active: ... }`
  - neither enterprise-admin request includes `enterprise_id`

### Verification

Focused Playwright rerun:

```bash
cd frontend-react
npx playwright test tests/auth-ui.spec.ts --grep "console wording|enterprise governance tab|enterprise admin saves user changes"
```

Exact output summary:

```text
Running 3 tests using 1 worker
✓  1 [chromium] › tests/auth-ui.spec.ts:248:3 › admin console role wording › enterprise admin sees enterprise console wording only (2.9s)
✓  2 [chromium] › tests/auth-ui.spec.ts:268:3 › admin console role wording › super admin sees enterprise governance tab (942ms)
✓  3 [chromium] › tests/auth-ui.spec.ts:281:3 › admin console role wording › enterprise admin saves user changes without enterprise reassignment payload (1.5s)

3 passed (5.9s)
```
