# Auth UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the login and registration pages into a shared industrial-auth experience that stays aligned with the existing product UI while improving polish, hierarchy, and motion.

**Architecture:** Keep the current auth flow and `AuthProvider -> AppShell` structure intact, but extract a shared authentication shell for layout, brand framing, and the themed visual stage. Implement the new experience with existing React, Tailwind, and GSAP primitives only, with reduced-motion and mobile fallbacks built into the shared shell.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, GSAP, Playwright

## Global Constraints

- Do not change backend auth APIs, cookie handling, roles, or `AuthContext` behavior.
- Do not introduce a new brand palette; stay within existing `slate / navy / flame` tokens.
- Do not turn auth screens into a marketing page; form readability and task completion come first.
- Do not make real Rive runtime integration a prerequisite for the redesign.
- Keep motion low-frequency, low-amplitude, and provide `prefers-reduced-motion` fallback.
- Keep the redesign scoped to auth pages and minimal shared styling/components needed to support them.

---

## File Structure

- Modify: `frontend-react/src/pages/LoginPage.tsx`
  - Replace the standalone card layout with the new shared auth shell and updated login form content.
- Modify: `frontend-react/src/pages/RegisterPage.tsx`
  - Reuse the shared auth shell and align registration form structure and copy with the login page.
- Create: `frontend-react/src/components/auth/AuthShell.tsx`
  - Own the responsive two-zone layout, brand block, panel wrapper, and optional form footer slot.
- Create: `frontend-react/src/components/auth/AuthVisualStage.tsx`
  - Own the right-side themed visual stage, decorative layers, and low-cost motion hooks.
- Modify: `frontend-react/src/index.css`
  - Add auth-specific tokens and component classes that derive from the existing palette.
- Create: `frontend-react/tests/auth-ui.spec.ts`
  - Capture auth-screen layout, navigation, and reduced-motion-safe affordances using Playwright route mocking.

## Task 1: Add Auth UI Regression Coverage First

**Files:**
- Create: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `http://localhost:3200/`, current unauthenticated app shell behavior
- Produces: Playwright coverage for auth landing, login→register navigation, and mobile-safe layout expectations

- [ ] **Step 1: Write the failing test**

```ts
import { test, expect } from '@playwright/test'

test.describe('auth ui redesign', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/auth/me', async route => {
      await route.fulfill({
        contentType: 'application/json',
        status: 401,
        body: JSON.stringify({ error: '未登录' }),
      })
    })
  })

  test('shows login screen with auth stage and form panel', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible()
    await expect(page.getByText('二维工艺系统')).toBeVisible()
    await expect(page.getByText('图纸解析与工艺编制控制台')).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
    await expect(page.getByLabel('用户名')).toBeVisible()
    await expect(page.getByLabel('密码')).toBeVisible()
  })

  test('switches from login to register without losing themed shell', async ({ page }) => {
    await page.goto('/')

    await page.getByRole('button', { name: '立即注册' }).click()

    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
    await expect(page.getByLabel('确认密码')).toBeVisible()
  })

  test('keeps form as priority on narrow screens', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    const submit = page.getByRole('button', { name: '登录' })
    await expect(submit).toBeVisible()
    await expect(page.getByLabel('用户名')).toBeVisible()
    await expect(page.getByTestId('auth-visual-stage')).toBeVisible()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium`

Expected: FAIL because the current login/register pages do not render `图纸解析与工艺编制控制台` or `data-testid="auth-visual-stage"`.

- [ ] **Step 3: Commit the failing test only**

```bash
git add frontend-react/tests/auth-ui.spec.ts
git commit -m "test: add auth ui redesign coverage"
```

## Task 2: Build the Shared Auth Shell and Login Screen

**Files:**
- Create: `frontend-react/src/components/auth/AuthShell.tsx`
- Create: `frontend-react/src/components/auth/AuthVisualStage.tsx`
- Modify: `frontend-react/src/pages/LoginPage.tsx`
- Modify: `frontend-react/src/index.css`
- Test: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `LoginPage` current submit behavior (`login(username, password)`), existing `useToast`, existing palette tokens in `index.css`
- Produces:
  - `AuthShell(props: { title: string; subtitle: string; footer: ReactNode; children: ReactNode })`
  - `AuthVisualStage(props: { mode: 'login' | 'register' })`
  - CSS classes `auth-shell`, `auth-panel`, `auth-stage`, `auth-grid`, `auth-kicker`

- [ ] **Step 1: Write a failing assertion for login-specific shell copy**

Append this expectation to `shows login screen with auth stage and form panel`:

```ts
await expect(page.getByText('进入图纸检视台，继续你的工艺流程。')).toBeVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium --grep "shows login screen"`

Expected: FAIL because the new login subtitle does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `frontend-react/src/components/auth/AuthVisualStage.tsx`:

```tsx
import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

export function AuthVisualStage({ mode }: { mode: 'login' | 'register' }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const reduceMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (!rootRef.current || reduceMotion) return
    const ctx = gsap.context(() => {
      gsap.fromTo('.auth-stage-beam', { opacity: 0.45 }, { opacity: 0.7, duration: 2.2, repeat: -1, yoyo: true, ease: 'sine.inOut' })
      gsap.fromTo('.auth-stage-sheet', { y: 0 }, { y: mode === 'login' ? -6 : -4, duration: 3, repeat: -1, yoyo: true, ease: 'sine.inOut' })
      gsap.fromTo('.auth-stage-scan', { xPercent: -20, opacity: 0.18 }, { xPercent: 20, opacity: 0.3, duration: 2.6, repeat: -1, yoyo: true, ease: 'sine.inOut' })
    }, rootRef)
    return () => ctx.revert()
  }, [mode, reduceMotion])

  return (
    <div ref={rootRef} data-testid="auth-visual-stage" className="auth-stage" aria-hidden="true">
      <div className="auth-stage-beam" />
      <div className="auth-stage-grid" />
      <div className="auth-stage-sheet" />
      <div className="auth-stage-sheet auth-stage-sheet-secondary" />
      <div className="auth-stage-hud" />
      <div className="auth-stage-scan" />
    </div>
  )
}
```

Create `frontend-react/src/components/auth/AuthShell.tsx`:

```tsx
import type { ReactNode } from 'react'
import { AuthVisualStage } from './AuthVisualStage'

interface AuthShellProps {
  mode: 'login' | 'register'
  title: string
  subtitle: string
  footer: ReactNode
  children: ReactNode
}

export function AuthShell({ mode, title, subtitle, footer, children }: AuthShellProps) {
  return (
    <div className="auth-shell">
      <section className="auth-panel-wrap">
        <div className="auth-panel">
          <div className="auth-brand">
            <div className="auth-brand-mark" />
            <div>
              <p className="auth-kicker">二维工艺系统</p>
              <h1 className="auth-title">{title}</h1>
              <p className="auth-subtitle">{subtitle}</p>
            </div>
          </div>
          {children}
          <div className="auth-footer">{footer}</div>
        </div>
      </section>
      <section className="auth-stage-wrap">
        <div className="auth-stage-copy">
          <p className="auth-stage-label">图纸解析与工艺编制控制台</p>
          <p className="auth-stage-text">聚焦当前图纸，保持任务链路清晰、稳定、可追溯。</p>
        </div>
        <AuthVisualStage mode={mode} />
      </section>
    </div>
  )
}
```

Patch `frontend-react/src/pages/LoginPage.tsx` to wrap the form:

```tsx
import { AuthShell } from '../components/auth/AuthShell'

// inside return
return (
  <AuthShell
    mode="login"
    title="欢迎登录"
    subtitle="进入图纸检视台，继续你的工艺流程。"
    footer={
      <p className="text-center text-xs text-slate-400">
        &copy; {new Date().getFullYear()} 二维工艺系统
      </p>
    }
  >
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* existing fields and actions, kept functionally identical */}
    </form>
  </AuthShell>
)
```

Append auth classes to `frontend-react/src/index.css`:

```css
.auth-shell {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(380px, 1.08fr);
  background:
    radial-gradient(circle at 18% 20%, rgba(249, 115, 22, 0.08) 0%, transparent 28%),
    linear-gradient(135deg, #eff4fa 0%, #e2e8f0 45%, #dbe4ee 100%);
}

.auth-panel-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.auth-panel {
  width: min(100%, 440px);
  padding: 28px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(18px);
  box-shadow: 0 18px 60px rgba(15, 23, 42, 0.08);
}

.auth-stage-wrap {
  position: relative;
  overflow: hidden;
  background: linear-gradient(160deg, #0f1d35 0%, #0b1526 55%, #081220 100%);
}
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium --grep "shows login screen"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend-react/src/components/auth/AuthShell.tsx frontend-react/src/components/auth/AuthVisualStage.tsx frontend-react/src/pages/LoginPage.tsx frontend-react/src/index.css frontend-react/tests/auth-ui.spec.ts
git commit -m "feat: add themed auth shell for login"
```

## Task 3: Port the Shared Shell to Registration and Mobile Behavior

**Files:**
- Modify: `frontend-react/src/pages/RegisterPage.tsx`
- Modify: `frontend-react/src/index.css`
- Test: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `AuthShell`, existing `register(username, password)` behavior, current form validation and password toggles
- Produces: registration page parity with shared shell and mobile-first auth layout rules

- [ ] **Step 1: Write a failing mobile/layout test assertion**

Append these expectations:

```ts
await expect(page.getByText('注册后可申请企业授权并继续工艺入库与生成流程。')).toBeVisible()
await expect(page.locator('.auth-shell')).toBeVisible()
```

And add this style assertion inside `keeps form as priority on narrow screens`:

```ts
await expect(page.getByTestId('auth-visual-stage')).toHaveCSS('min-height', '220px')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium --grep "switches from login to register|keeps form as priority"`

Expected: FAIL because register still uses the old standalone layout and the auth stage has no mobile size rule.

- [ ] **Step 3: Write minimal implementation**

Patch `frontend-react/src/pages/RegisterPage.tsx`:

```tsx
import { AuthShell } from '../components/auth/AuthShell'

return (
  <AuthShell
    mode="register"
    title="创建账号"
    subtitle="注册后可申请企业授权并继续工艺入库与生成流程。"
    footer={
      <p className="text-center text-xs text-slate-400">
        &copy; {new Date().getFullYear()} 二维工艺系统
      </p>
    }
  >
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* existing register fields and actions, kept functionally identical */}
    </form>
  </AuthShell>
)
```

Extend `frontend-react/src/index.css`:

```css
.auth-stage {
  min-height: 320px;
  border-radius: 28px;
}

@media (max-width: 900px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .auth-stage-wrap {
    order: -1;
    min-height: 220px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .auth-panel-wrap {
    padding-top: 20px;
    align-items: flex-start;
  }

  .auth-panel {
    width: 100%;
    max-width: 100%;
  }

  .auth-stage {
    min-height: 220px;
  }
}
```

- [ ] **Step 4: Run the full auth UI spec**

Run: `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium`

Expected: PASS 3 tests

- [ ] **Step 5: Commit**

```bash
git add frontend-react/src/pages/RegisterPage.tsx frontend-react/src/index.css frontend-react/tests/auth-ui.spec.ts
git commit -m "feat: align register page with auth shell"
```

## Task 4: Polish Motion, Focus States, and Final Verification

**Files:**
- Modify: `frontend-react/src/components/auth/AuthVisualStage.tsx`
- Modify: `frontend-react/src/pages/LoginPage.tsx`
- Modify: `frontend-react/src/pages/RegisterPage.tsx`
- Modify: `frontend-react/src/index.css`
- Test: `frontend-react/tests/auth-ui.spec.ts`

**Interfaces:**
- Consumes: `usePrefersReducedMotion`, current form input state, auth shell CSS classes
- Produces: final visual polish with reduced-motion safety and consistent focus/hover states

- [ ] **Step 1: Write a failing test for focus-safe labels and shell continuity**

Add this test:

```ts
test('shows clear auth actions and field labels after switching views', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '立即注册' }).click()
  await page.getByRole('button', { name: '立即登录' }).click()

  await expect(page.getByLabel('用户名')).toBeVisible()
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
  await expect(page.getByText('图纸解析与工艺编制控制台')).toBeVisible()
})
```

- [ ] **Step 2: Run test to verify it fails if continuity regresses**

Run: `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium --grep "shows clear auth actions"`

Expected: FAIL until the final auth pages are fully wired into the shared shell and navigation text remains visible.

- [ ] **Step 3: Write minimal implementation**

Refine `frontend-react/src/components/auth/AuthVisualStage.tsx`:

```tsx
// add extra static stage details only if they do not affect behavior
<div className="auth-stage-reticle" />
<div className="auth-stage-pulse" />
```

Refine auth form wrappers in both page files:

```tsx
<form onSubmit={handleSubmit} className="space-y-5 auth-form">
```

Append CSS:

```css
.auth-form input {
  min-height: 46px;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
}

.auth-form input:focus {
  box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.12);
}

.auth-stage-copy {
  position: relative;
  z-index: 2;
  padding: 40px 40px 0;
  color: rgba(248, 250, 252, 0.92);
}

@media (prefers-reduced-motion: reduce) {
  .auth-stage,
  .auth-stage * {
    animation: none !important;
    transition: none !important;
    transform: none !important;
  }
}
```

- [ ] **Step 4: Run final verification**

Run:
- `npm --prefix frontend-react exec playwright test tests/auth-ui.spec.ts --project=chromium`
- `npm --prefix frontend-react run build`

Expected:
- Playwright: PASS 4 tests
- Build: PASS with Vite production build output

- [ ] **Step 5: Commit**

```bash
git add frontend-react/src/components/auth/AuthVisualStage.tsx frontend-react/src/pages/LoginPage.tsx frontend-react/src/pages/RegisterPage.tsx frontend-react/src/index.css frontend-react/tests/auth-ui.spec.ts
git commit -m "feat: polish auth ui motion and focus states"
```

## Self-Review

- Spec coverage:
  - Shared auth shell: Task 2
  - Themed visual stage: Task 2
  - Registration parity: Task 3
  - Mobile fallback: Task 3
  - Motion and reduced-motion: Task 4
  - No auth logic changes: preserved across all tasks
- Placeholder scan:
  - No `TODO`/`TBD`
  - Commands and file paths are explicit
- Type consistency:
  - `AuthShell` and `AuthVisualStage` signatures are defined before later tasks depend on them
  - Tests consistently target `data-testid="auth-visual-stage"`
