# Auth Entry Mimo Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the unauthenticated entry flow as a MiMo-like minimal home state that transitions into an in-page auth surface when the user clicks `进入系统`.

**Architecture:** Replace the current split-screen auth entry with a single scene component that owns a `home/auth` UI state and a `login/register` form state. Reuse existing auth business logic and form validation paths while moving the visual shell, transitions, and state-trigger interaction into a new auth entry surface.

**Tech Stack:** React, TypeScript, Tailwind utility classes, project CSS in `src/index.css`, Playwright, GSAP, existing auth/toast contexts

## Global Constraints

- Keep existing login/register business logic intact.
- Default first screen must be sparse, MiMo-like, and must not show the login card immediately.
- `进入系统` acts as a state trigger, not a route jump.
- `home -> auth -> home` must feel like one scene changing state.
- Reduced motion must be supported.

---

### Task 1: Lock the new entry-state behavior with failing UI tests

**Files:**
- Modify: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: current unauthenticated app at `/`
- Produces: Playwright expectations for `home` state, auth trigger, and auth surface appearance

- [ ] **Step 1: Add a failing test for the default home state**

```ts
test('starts in minimal home state before auth is opened', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'DiMo' })).toBeVisible()
  await expect(page.getByRole('button', { name: '进入系统' })).toBeVisible()
  await expect(page.getByLabel('用户名')).not.toBeVisible()
})
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd frontend-react && npm exec -- playwright test tests/auth-ui.spec.ts -g "starts in minimal home state before auth is opened" --project=chromium`

Expected: FAIL because the current page renders the login form immediately and does not show the new minimal home state.

- [ ] **Step 3: Add a failing test for the auth transition**

```ts
test('opens auth surface when enter button is clicked', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '进入系统' }).click()

  await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
  await expect(page.getByLabel('用户名')).toBeVisible()
  await expect(page.getByRole('button', { name: '返回首页' })).toBeVisible()
})
```

- [ ] **Step 4: Run the test and verify it fails**

Run: `cd frontend-react && npm exec -- playwright test tests/auth-ui.spec.ts -g "opens auth surface when enter button is clicked" --project=chromium`

Expected: FAIL because there is no `进入系统` trigger and no in-scene auth transition.

### Task 2: Rebuild the unauthenticated entry shell around home/auth state

**Files:**
- Modify: `frontend-react/src/App.tsx`
- Create: `frontend-react/src/components/auth/AuthEntryScene.tsx`
- Modify: `frontend-react/src/components/auth/AuthShell.tsx`
- Modify: `frontend-react/src/components/auth/AuthVisualStage.tsx`
- Modify: `frontend-react/src/pages/LoginPage.tsx`
- Modify: `frontend-react/src/pages/RegisterPage.tsx`
- Modify: `frontend-react/src/index.css`

**Interfaces:**
- Consumes: `useAuth`, `useToast`, existing login/register submit behavior
- Produces: `AuthEntryScene` with `view: 'login' | 'register'`, `phase: 'home' | 'auth'`, and trigger handlers for opening/closing auth

- [ ] **Step 1: Route unauthenticated users through a single scene component**

Implement a single auth entry wrapper in `App.tsx`:

```tsx
if (!isAuthenticated) {
  return (
    <>
      <AuthEntryScene />
      <ToastStack toasts={toasts} />
    </>
  )
}
```

- [ ] **Step 2: Implement `AuthEntryScene` state ownership**

Create `AuthEntryScene.tsx` with:

```tsx
const [phase, setPhase] = useState<'home' | 'auth'>('home')
const [view, setView] = useState<'login' | 'register'>('login')
```

and handlers:

```tsx
const openLogin = () => {
  setView('login')
  setPhase('auth')
}

const openRegister = () => {
  setView('register')
  setPhase('auth')
}

const returnHome = () => setPhase('home')
```

- [ ] **Step 3: Keep form logic in page components, but pass shell state in**

Update `LoginPage` and `RegisterPage` props so they can render inside the shared scene:

```ts
interface LoginPageProps {
  onNavigate: (page: 'register') => void
  onReturnHome: () => void
  phase: 'home' | 'auth'
}
```

Use the same shape for `RegisterPage`, replacing `register`/`login` as needed.

- [ ] **Step 4: Replace the old split auth shell with a unified entry shell**

Update `AuthShell` to accept:

```ts
interface AuthShellProps {
  mode: 'login' | 'register'
  phase: 'home' | 'auth'
  onOpenAuth: () => void
  onReturnHome: () => void
  title: string
  subtitle: string
  footer: ReactNode
  children: ReactNode
}
```

The shell must always render:
- top nav
- left headline block
- right globe/stage visual
- top-right `进入系统` trigger

and only reveal the auth panel when `phase === 'auth'`.

- [ ] **Step 5: Rework the stage visual to support fade-back behavior**

Keep `AuthVisualStage`, but make it a restrained globe/orbit visual that can dim when auth opens:

```tsx
<AuthVisualStage mode={mode} phase={phase} />
```

Add `phase` prop:

```ts
export function AuthVisualStage({ mode, phase }: { mode: 'login' | 'register'; phase: 'home' | 'auth' })
```

- [ ] **Step 6: Rebuild CSS around a sparse MiMo-like shell**

Replace the old `.auth-shell` two-column split with a light, sparse scene:
- top nav
- oversized headline
- right visual anchor
- hidden/revealed auth surface

Use CSS classes that explicitly model state:

```css
.auth-entry-shell {}
.auth-entry-shell[data-phase='home'] {}
.auth-entry-shell[data-phase='auth'] {}
.auth-entry-visual {}
.auth-entry-panel {}
.auth-entry-panel.is-open {}
```

- [ ] **Step 7: Add smooth state transitions with reduced-motion fallback**

Use CSS transitions or GSAP only for:
- visual fade/scale down
- auth panel fade/translate in
- close/back transition

Do not animate layout-heavy properties.

### Task 3: Verify state transitions and auth path behavior

**Files:**
- Modify: `frontend-react/tests/auth-ui.spec.ts`
- Modify: `frontend-react/tests/auth.spec.ts`

**Interfaces:**
- Consumes: final unauthenticated auth-entry scene
- Produces: regression coverage for login/register entry and close/open transitions

- [ ] **Step 1: Update auth UI tests to match the new shell**

Cover:
- home state visible by default
- auth opens from `进入系统`
- register can be opened from auth layer
- returning home hides fields again

- [ ] **Step 2: Update auth flow tests to open auth before filling fields**

Replace direct immediate form assumptions with:

```ts
await page.goto('/')
await page.getByRole('button', { name: '进入系统' }).click()
await page.getByLabel('用户名').fill(username)
```

- [ ] **Step 3: Run targeted Playwright suites**

Run:

```bash
cd frontend-react && npm exec -- playwright test tests/auth-ui.spec.ts --project=chromium
cd frontend-react && npm exec -- playwright test tests/auth.spec.ts --project=chromium
```

Expected: PASS

- [ ] **Step 4: Run GitNexus diff impact check**

Run:

```bash
node .gitnexus/run.cjs detect_changes
```

Expected: changed symbols limited to auth entry pages/components and related CSS.
