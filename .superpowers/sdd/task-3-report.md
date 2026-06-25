# Task 3 Report: Frontend Default Behavior Fixes

## Changes Made

### 1. DbPage.tsx — Default scope selection (line 126)
- **Before:** `setFilterScope(data.items[0].library_key)` — always selected the first scope (public library)
- **After:** Prefers the first non-public scope; falls back to `data.items[0]` if no private scope exists
- **File:** `frontend-react/src/pages/DbPage.tsx`

### 2. DbPage.tsx — Fallback text (line 911)
- **Before:** `'公共工艺库'` (public library)
- **After:** `'工艺库'` (library) — neutral fallback when no scope is active
- **File:** `frontend-react/src/pages/DbPage.tsx`

### 3. ZipPage.tsx — seedPublic default (line 30)
- **Before:** `const [seedPublic, setSeedPublic] = useState(true)`
- **After:** `const [seedPublic, setSeedPublic] = useState(false)`
- **File:** `frontend-react/src/pages/ZipPage.tsx`

## Verification

- **Build:** `npm run build` — PASS
- **Playwright tests (3):** `tests/auth-ui.spec.ts` — 3/3 PASS

## Commit

`fix: default to private scope, prevent public library data leakage`
