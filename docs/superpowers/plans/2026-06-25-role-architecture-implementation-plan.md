# Role Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the React frontend with the approved role architecture so `user`, `enterprise_admin`, and `super_admin` each see the right navigation, copy, controls, and page scope without inventing new backend contracts.

**Architecture:** Keep the existing auth model and page topology intact, then layer role-specific presentation rules on top: shared role/scope vocabulary, split admin semantics, business-page action gating, and light-touch copy refinement on stable pages. Reuse the current `AuthContext`, `authRequest()` API helpers, library scope APIs, and state-driven page routing; avoid router changes and avoid any backend schema expansion in this phase.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 3, Vite, existing auth/admin/library APIs, Playwright tests.

## Global Constraints

- Frontend route model stays `useState`-driven; do not introduce `react-router`.
- Existing auth model remains authoritative: `user` still includes both `未分配企业` and `已分配企业` states.
- `未分配企业` users must not gain business capability; they may only see `个人中心` plus locked/limited entry states where needed.
- Current scope mapping is fixed for this phase: `个人 = private library`, `平台 = public library`.
- `企业` scope is presentation-only in this phase; do not invent a new backend `scope_type`, table, or API contract.
- `enterprise_admin` copy must avoid platform-language such as `平台`, `全部企业`, `跨企业治理`.
- `super_admin` copy must clearly use platform-governance language where relevant.
- Role-specific changes on `工艺生成` and `历史记录` must stay light; do not redesign their main workflows.
- Motion changes must stay subtle: page fade/up, tab transitions, scope transitions, short action feedback only.
- Preserve the unified API response contract `{success: true, data: ...}` / `{success: false, error: ...}` and existing `authRequest<T>()` usage.

---

## File Structure

- `frontend-react/src/App.tsx`
  - Keep page mounting/routing structure stable.
  - Add role-aware fallback for restricted pages if the current page becomes invalid for the user.
- `frontend-react/src/components/layout/Sidebar.tsx`
  - Tighten nav visibility and per-role subcopy.
- `frontend-react/src/types/auth.ts`
  - Keep user/admin types aligned with current auth payload; no new backend-only fields.
- `frontend-react/src/pages/admin/AdminPage.tsx`
  - Split page title, intro copy, and visible tab semantics by role.
- `frontend-react/src/pages/admin/EnterpriseTab.tsx`
  - Keep platform-only enterprise governance language and actions.
- `frontend-react/src/pages/admin/UsersTab.tsx`
  - Distinguish enterprise-operator behavior from platform-operator behavior in labels, filters, and editable fields.
- `frontend-react/src/pages/admin/QuotaTab.tsx`
  - Show enterprise-local wording for enterprise admins and platform wording for super admins.
- `frontend-react/src/pages/DbPage.tsx`
  - Apply role-aware scope naming, locked states, and action gating over existing `public/private` data.
- `frontend-react/src/pages/ZipPage.tsx`
  - Constrain target-library choices and copy by role without changing import APIs.
- `frontend-react/src/pages/ProfilePage.tsx`
  - Strengthen role/enterprise/authorization messaging.
- `frontend-react/src/pages/GeneratePage.tsx`
  - Add only light auxiliary role context around retrieval/commit impact.
- `frontend-react/src/pages/HistoryPage.tsx`
  - Keep the page stable; add only light filters/copy if already supported locally.
- `frontend-react/tests/auth-ui.spec.ts`
  - Extend role-aware navigation and admin-shell coverage.
- `frontend-react/tests/db-preview.spec.ts`
  - Extend library browsing / restricted-state coverage.
- `frontend-react/tests/zip-to-db-flow.spec.ts`
  - Extend role-aware ingest target behavior coverage.

## Task 1: Codify Role Guards And Shared Vocabulary

**Files:**
- Modify: `frontend-react/src/App.tsx`
- Modify: `frontend-react/src/components/layout/Sidebar.tsx`
- Modify: `frontend-react/src/types/auth.ts`
- Test: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `useAuth()` current `user`, existing `PageId`, existing nav items.
- Produces: stable role guard behavior for page routing and nav rendering; shared UI understanding of `未分配企业 user`.

- [ ] **Step 1: Write the failing navigation test**

```ts
test('unassigned user only gets profile and limited entry states', async ({ page }) => {
  // Seed auth as role=user with enterprise_id=null
  // Expect sidebar to hide admin and disable business access paths.
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts --grep "unassigned user only gets profile"`
Expected: FAIL because the current shell still renders business pages as generally available.

- [ ] **Step 3: Implement minimal routing and nav guard changes**

```tsx
const isUnassignedUser = user?.role === 'user' && user.enterprise_id == null

useEffect(() => {
  if (isUnassignedUser && page !== 'profile') {
    setPage('profile')
  }
}, [isUnassignedUser, page])
```

```tsx
const visibleItems = NAV_ITEMS.filter(item => {
  if (item.roles && !item.roles.includes(userRole || '')) return false
  if (isUnassignedUser && item.id !== 'profile') return false
  return true
})
```

- [ ] **Step 4: Add role-aware nav subcopy**

```tsx
{ id: 'admin', title: '管理后台', sub: userRole === 'super_admin' ? '平台治理与配额总览' : '企业成员与授权管理' }
```

- [ ] **Step 5: Run the focused test and typecheck**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts --grep "unassigned user only gets profile"`
Expected: PASS

Run: `cd frontend-react && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend-react/src/App.tsx frontend-react/src/components/layout/Sidebar.tsx frontend-react/src/types/auth.ts frontend-react/tests/auth-ui.spec.ts
git commit -m "feat: add role-aware shell guards"
```

## Task 2: Split Admin Console Semantics By Role

**Files:**
- Modify: `frontend-react/src/pages/admin/AdminPage.tsx`
- Modify: `frontend-react/src/pages/admin/EnterpriseTab.tsx`
- Modify: `frontend-react/src/pages/admin/UsersTab.tsx`
- Modify: `frontend-react/src/pages/admin/QuotaTab.tsx`
- Test: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `useAuth().user.role`, `getEnterprises()`, `getAdminUsers()`, `getAdminQuotas()`.
- Produces: `super_admin` sees platform-governance framing; `enterprise_admin` sees enterprise-operations framing with no platform language leakage.

- [ ] **Step 1: Write failing admin-role tests**

```ts
test('enterprise admin sees enterprise console wording only', async ({ page }) => {
  // Expect no "平台管理" / "全部企业" wording.
})

test('super admin sees enterprise governance tab', async ({ page }) => {
  // Expect enterprise management tab and platform summary wording.
})
```

- [ ] **Step 2: Run test to verify current wording fails**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts --grep "console wording|enterprise governance tab"`
Expected: FAIL because `AdminPage` currently hardcodes `系统管理` and generic tabs for both roles.

- [ ] **Step 3: Split admin shell header and tab intro**

```tsx
const isSuperAdmin = user?.role === 'super_admin'
const title = isSuperAdmin ? '平台管理' : '企业运营台'
const intro = isSuperAdmin
  ? '管理企业、用户与平台配额。'
  : '管理本企业成员、配额与授权状态。'
```

- [ ] **Step 4: Tighten enterprise-admin tab language and action set**

```tsx
// EnterpriseTab
if (!isSuperAdmin) return null

// UsersTab
const filterLabel = isSuperAdmin ? '企业筛选' : '成员列表'
const canEditEnterprise = isSuperAdmin
```

```tsx
// QuotaTab
const summaryTitle = isSuperAdmin ? '平台配额概览' : '本企业配额概览'
```

- [ ] **Step 5: Re-run focused admin tests**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts --grep "console wording|enterprise governance tab"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend-react/src/pages/admin/AdminPage.tsx frontend-react/src/pages/admin/EnterpriseTab.tsx frontend-react/src/pages/admin/UsersTab.tsx frontend-react/src/pages/admin/QuotaTab.tsx frontend-react/tests/auth-ui.spec.ts
git commit -m "feat: split admin console semantics by role"
```

## Task 3: Re-scope Knowledge Library Browsing

**Files:**
- Modify: `frontend-react/src/pages/DbPage.tsx`
- Modify: `frontend-react/src/api/client.ts`
- Test: `frontend-react/tests/db-preview.spec.ts`

**Interfaces:**
- Consumes: `getLibraryScopes()`, `getLibraryRecords()`, active auth user.
- Produces: role-aware labels and action gating over existing `public/private` scopes without backend contract changes.

- [ ] **Step 1: Write failing browsing tests**

```ts
test('super admin can distinguish platform library from personal library', async ({ page }) => {
  // Expect public/private labels rendered as 平台/个人 in UI copy.
})

test('enterprise admin does not see platform governance copy in db page', async ({ page }) => {
  // Expect enterprise copy and no platform governance verbs.
})
```

- [ ] **Step 2: Run test to verify current copy fails**

Run: `cd frontend-react && npx playwright test tests/db-preview.spec.ts`
Expected: FAIL on copy/assertion mismatch.

- [ ] **Step 3: Add UI-only scope label mapping**

```ts
const uiScopeLabel = scope.scope_type === 'public'
  ? '平台工艺库'
  : '我的工艺库'
```

```tsx
const allowDeleteScope = activeScope?.scope_type !== 'public' && user?.role !== 'user'
```

- [ ] **Step 4: Add unassigned-user lock state and enterprise-admin copy**

```tsx
if (user?.role === 'user' && user.enterprise_id == null) {
  return <LockShell onNavigate={onNavigate} />
}
```

```tsx
const bannerCopy = user?.role === 'super_admin'
  ? '查看平台与个人工艺记录。'
  : user?.role === 'enterprise_admin'
    ? '查看企业复用相关记录与个人工艺库。'
    : '查询、复用与回看我的工艺记录。'
```

- [ ] **Step 5: Run focused browse tests**

Run: `cd frontend-react && npx playwright test tests/db-preview.spec.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend-react/src/pages/DbPage.tsx frontend-react/src/api/client.ts frontend-react/tests/db-preview.spec.ts
git commit -m "feat: rescope library browsing by role"
```

## Task 4: Re-scope ZIP Import Targets Without New Backend Scope Types

**Files:**
- Modify: `frontend-react/src/pages/ZipPage.tsx`
- Modify: `frontend-react/src/api/client.ts`
- Test: `frontend-react/tests/zip-to-db-flow.spec.ts`

**Interfaces:**
- Consumes: `getLibraryScopes()`, existing ZIP import request shape `{ library_mode, library_name, library_key }`.
- Produces: role-aware target selection where `personal=private`, `platform=public`, and enterprise range is copy/state only for now.

- [ ] **Step 1: Write failing ZIP target tests**

```ts
test('regular assigned user defaults to personal library target', async ({ page }) => {
  // Expect no platform-first target.
})

test('super admin can still choose public baseline target', async ({ page }) => {
  // Expect public option visible.
})
```

- [ ] **Step 2: Run tests to verify current target behavior fails**

Run: `cd frontend-react && npx playwright test tests/zip-to-db-flow.spec.ts`
Expected: FAIL because current target selection is scope-list driven with generic `公共库/私有库` wording.

- [ ] **Step 3: Filter and relabel targets by role**

```tsx
const visibleScopes = scopes.filter(scope => {
  if (user?.role === 'super_admin') return true
  return scope.scope_type !== 'public'
})
```

```tsx
const targetLabel = scope.scope_type === 'public'
  ? '平台基线库'
  : '我的工艺库'
```

- [ ] **Step 4: Add enterprise-admin explanatory copy without API expansion**

```tsx
const helperText = user?.role === 'enterprise_admin'
  ? '本阶段企业范围仅做界面引导；真实入库仍写入你当前可用的个人工艺库。'
  : '默认推荐先写入我的工艺库，确认后再决定共享。'
```

- [ ] **Step 5: Re-run ZIP tests and build**

Run: `cd frontend-react && npx playwright test tests/zip-to-db-flow.spec.ts`
Expected: PASS

Run: `cd frontend-react && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend-react/src/pages/ZipPage.tsx frontend-react/src/api/client.ts frontend-react/tests/zip-to-db-flow.spec.ts
git commit -m "feat: constrain zip import targets by role"
```

## Task 5: Light-Touch Role Cues On Profile, Generate, And History

**Files:**
- Modify: `frontend-react/src/pages/ProfilePage.tsx`
- Modify: `frontend-react/src/pages/GeneratePage.tsx`
- Modify: `frontend-react/src/pages/HistoryPage.tsx`
- Test: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `useAuth().user`, current retrieval scope state, current history list UI.
- Produces: stronger self-service context in profile, light retrieval-impact messaging in generate, and stable/no-governance history copy.

- [ ] **Step 1: Write failing page-copy tests**

```ts
test('profile highlights enterprise assignment and authorization state', async ({ page }) => {
  // Expect explicit enterprise/authorization wording.
})

test('history remains execution-focused for all roles', async ({ page }) => {
  // Expect no governance panel language.
})
```

- [ ] **Step 2: Run tests to verify current copy is insufficient**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts --grep "profile highlights|history remains"`
Expected: FAIL

- [ ] **Step 3: Strengthen profile role messaging**

```tsx
const statusHint = user.role === 'enterprise_admin'
  ? '你当前负责本企业运营治理。'
  : user.role === 'super_admin'
    ? '你当前拥有平台治理权限。'
    : user.enterprise_id == null
      ? '当前账号尚未分配企业，业务能力受限。'
      : '当前账号可执行工艺业务任务。'
```

- [ ] **Step 4: Add only auxiliary cues to generate/history**

```tsx
const retrievalHint = user?.role === 'super_admin'
  ? '当前可切换平台基线检索。'
  : user?.role === 'enterprise_admin'
    ? '优先关注企业复用影响与入库去向。'
    : '优先关注结果、建议与下一步动作。'
```

```tsx
const historyTitle = '历史记录'
const historySubtitle = '查看历史输出、快照与工艺回看，不承载治理操作。'
```

- [ ] **Step 5: Run focused tests**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts --grep "profile highlights|history remains"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend-react/src/pages/ProfilePage.tsx frontend-react/src/pages/GeneratePage.tsx frontend-react/src/pages/HistoryPage.tsx frontend-react/tests/auth-ui.spec.ts
git commit -m "feat: add light role cues to stable pages"
```

## Task 6: Regression Sweep And Documentation Sync

**Files:**
- Modify: `docs/superpowers/HANDOFF-user-auth-system.md`
- Modify: `docs/superpowers/specs/2026-06-25-role-architecture-design.md`
- Test: `frontend-react/tests/auth-ui.spec.ts`
- Test: `frontend-react/tests/db-preview.spec.ts`
- Test: `frontend-react/tests/zip-to-db-flow.spec.ts`

**Interfaces:**
- Consumes: completed UI behavior from Tasks 1-5.
- Produces: updated handoff notes and regression evidence for role architecture rollout.

- [ ] **Step 1: Update docs to reflect final constraints**

```md
- `user` 继续区分未分配企业 / 已分配企业
- 当前范围映射：个人=private，平台=public
- 企业范围仍为前端表达层，不新增后端 scope 契约
```

- [ ] **Step 2: Run targeted regression suite**

Run: `cd frontend-react && npx playwright test tests/auth-ui.spec.ts tests/db-preview.spec.ts tests/zip-to-db-flow.spec.ts`
Expected: PASS

- [ ] **Step 3: Run full frontend verification**

Run: `cd frontend-react && npm run build`
Expected: PASS

- [ ] **Step 4: Optional backend sanity if UI touches request shapes**

Run: `pytest backend/test_auth_store.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/HANDOFF-user-auth-system.md docs/superpowers/specs/2026-06-25-role-architecture-design.md frontend-react/tests/auth-ui.spec.ts frontend-react/tests/db-preview.spec.ts frontend-react/tests/zip-to-db-flow.spec.ts
git commit -m "docs: sync role architecture rollout constraints"
```

## Self-Review

- Spec coverage:
  - Admin split: Tasks 1-2
  - Knowledge browse scoping: Task 3
  - ZIP ingest scoping: Task 4
  - Profile unification: Task 5
  - Generate/history light cuts: Task 5
  - Motion/copy constraints: Tasks 2-5
- Placeholder scan:
  - No `TODO`/`TBD` markers remain.
  - `企业` scope explicitly constrained to presentation-only.
- Type consistency:
  - Plan only relies on existing `User`, `AdminUser`, `QuotaInfo`, `LibraryScope`, and current API helper signatures.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-role-architecture-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
