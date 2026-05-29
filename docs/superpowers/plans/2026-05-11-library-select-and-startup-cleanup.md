# Library Select & Startup Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Replace the static "入库方式" dropdown with a dynamic list of existing libraries + a "新建" option. (2) On backend restart, mark stale tasks as cancelled and clear the process-generation page's visual state.

**Architecture:** Feature 2 (startup cleanup) is pure backend + a tiny frontend startup hook and has zero dependencies. Feature 1 (library select) adds a backend guard in `kb_import.py` and replaces the HTML/JS of the import target card. Implement in order: Task 1 → 2 → 3 (Feature 2), then Task 4 → 5 → 6 (Feature 1).

**Tech Stack:** Python/Flask, SQLite, vanilla JS (no bundler), HTML, CSS in `updated_front/css/industrial-console.css`.

---

## File Map

| File | Change |
|------|--------|
| `backend/task_store.py` | Add `cancel_stale_tasks()` |
| `backend/app.py` | Call `cancel_stale_tasks()` on startup; generate `STARTUP_TOKEN`; add `/api/startup_token` route |
| `backend/api/kb_import.py` | Add "existing library → resolve_scope" path before `ensure_scope` |
| `updated_front/css/industrial-console.css` | Add `.zip-library-list`, `.zip-library-option` radio-card styles |
| `updated_front/demo-industrial-console.html` | Replace `#zipLibraryModeSelect` + `#zipLibraryNameInput` with `#zipLibraryList` + `#zipNewLibraryForm` |
| `updated_front/js/demo-industrial-console.js` | Add `checkStartupToken()`, `loadZipLibraryList()`, `renderZipLibraryList()`, `currentZipLibraryTarget()`; update submit logic |

---

## Task 1 — `cancel_stale_tasks()` in task_store.py

**Files:**
- Modify: `backend/task_store.py`

- [ ] **Step 1: Locate the insertion point**

  Open `backend/task_store.py`. After the `count_tasks()` function (around line 157), add the new function. The existing `update_task_status()` is at line 84.

- [ ] **Step 2: Add `cancel_stale_tasks()`**

  Insert after `count_tasks()`:

  ```python
  def cancel_stale_tasks() -> int:
      """Mark tasks interrupted by a backend restart as cancelled.

      Tasks stuck in pending/processing were left by a previous process that
      no longer exists. They will never complete, so cancel them immediately.
      Returns the number of rows updated.
      """
      now = datetime.now().isoformat()
      with _conn() as c:
          c.execute(
              "UPDATE tasks SET status='cancelled', updated_at=? WHERE status IN ('pending','processing')",
              (now,),
          )
          return c.execute("SELECT changes()").fetchone()[0]
  ```

- [ ] **Step 3: Verify by running a quick smoke check**

  ```powershell
  cd F:\Work_Dir\new_3dversion\my_working
  python -c "
  from backend.task_store import init_db, insert_task, cancel_stale_tasks, get_task
  init_db()
  insert_task('test_stale_001', pdf_name='test.pdf')
  n = cancel_stale_tasks()
  t = get_task('test_stale_001')
  print('cancelled count:', n)
  print('task status:', t['status'])
  assert t['status'] == 'cancelled', f'Expected cancelled, got {t[\"status\"]}'
  print('PASS')
  "
  ```

  Expected output:
  ```
  cancelled count: 1
  task status: cancelled
  PASS
  ```

- [ ] **Step 4: Commit**

  ```powershell
  git add backend/task_store.py
  git commit -m "feat: add cancel_stale_tasks() to mark orphaned tasks on restart"
  ```

---

## Task 2 — Startup cleanup + `/api/startup_token` route in app.py

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: Add imports at the top of app.py**

  Find the line `import json` (around line 18). Add `import uuid` on the next line:

  ```python
  import json
  import uuid
  ```

- [ ] **Step 2: Import and call `cancel_stale_tasks` + generate token**

  Find the block that starts with `tasks = {}` (around line 116). Replace those three lines:

  ```python
  # Before:
  tasks = {}
  event_data = {}
  event_locks = {}
  ```

  With:

  ```python
  tasks = {}
  event_data = {}
  event_locks = {}

  # Startup cleanup: mark tasks interrupted by previous process as cancelled
  try:
      from .task_store import init_db, cancel_stale_tasks as _cancel_stale
  except ImportError:
      from backend.task_store import init_db, cancel_stale_tasks as _cancel_stale
  init_db()
  _stale_count = _cancel_stale()
  if _stale_count:
      logger.info("Startup: cancelled %d stale tasks from previous session", _stale_count)

  STARTUP_TOKEN = uuid.uuid4().hex
  ```

- [ ] **Step 3: Add the `/api/startup_token` route**

  Find the existing `@app.route("/dev/export-modal")` route (around line 61). Add the new route just before it:

  ```python
  @app.route("/api/startup_token")
  def startup_token_route():
      return jsonify({"token": STARTUP_TOKEN})
  ```

  Also ensure `jsonify` is imported — check that `from flask import Flask, Response, request, send_from_directory` already includes it. If not, add `jsonify` to that import. (Check line 22 of app.py — add `jsonify` to the Flask import if missing.)

- [ ] **Step 4: Verify the route works**

  Start the backend:
  ```powershell
  python backend/app.py
  ```

  In another terminal:
  ```powershell
  curl http://localhost:5000/api/startup_token
  ```

  Expected: `{"token":"<32-char-hex-string>"}` — different hex on each restart.

- [ ] **Step 5: Commit**

  ```powershell
  git add backend/app.py
  git commit -m "feat: startup cleanup — cancel stale tasks, expose startup_token endpoint"
  ```

---

## Task 3 — Frontend: startup token detection + process page reset

**Files:**
- Modify: `updated_front/js/demo-industrial-console.js`

- [ ] **Step 1: Find the DOMContentLoaded entry point**

  Search for `sampleZipDownloadBtn.addEventListener` — this is near the bottom (around line 3797) inside the main `addEventListener('click', ...)` or similar block. Find the very beginning of the main JS execution scope — look for the top-level immediately-invoked function or the first `const` declarations (around line 200–250).

  Find where the page initializes after DOM ready. Look for the line that references `zipResetBtn` or `zipRunBtn` setup (around line 3797). The startup check should run at the very top of the init sequence.

- [ ] **Step 2: Add `checkStartupToken` function**

  Find the `function resetGenerateWorkspace()` definition (around line 2981). Add the following function just before it:

  ```javascript
  async function checkStartupToken() {
    const STORAGE_KEY = '__prt_startup_token__';
    try {
      const res = await fetch(`${window.__API_BASE__ || '/api'}/startup_token`);
      if (!res.ok) return;
      const { token } = await res.json();
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored !== token) {
        localStorage.setItem(STORAGE_KEY, token);
        if (stored !== null) {
          // Only reset if this is not the very first load ever
          resetGenerateWorkspace();
        }
      }
    } catch (_) {
      // Backend not reachable yet — skip, no reset needed
    }
  }
  ```

  Note: `stored !== null` guard ensures we don't reset on the very first page load (before any token was stored). Only resets when token changes (i.e., backend restarted).

- [ ] **Step 3: Call `checkStartupToken` during page init**

  Find the line where `sampleZipDownloadBtn` event listener is registered (around line 3797). Just before it, add:

  ```javascript
  // Detect backend restart and clear stale visual state
  checkStartupToken();
  ```

- [ ] **Step 4: Manual test**

  1. Start backend, open page, upload a PRT — let it show results in the process panel.
  2. Stop backend (`Ctrl+C`), restart it.
  3. Refresh the browser page.
  4. The process panel should reset to the empty "等待上传 PRT" state (not show the previous task's results).
  5. Also verify: open History tab — previous completed tasks are still listed there.

- [ ] **Step 5: Commit**

  ```powershell
  git add "updated_front/js/demo-industrial-console.js"
  git commit -m "feat: detect backend restart via startup_token, reset process page on restart"
  ```

---

## Task 4 — Backend: existing-library guard in `kb_import.py`

**Files:**
- Modify: `backend/api/kb_import.py`

- [ ] **Step 1: Locate the scope-resolution block**

  In `backend/api/kb_import.py`, inside `import_zip_knowledge()` (around line 546), find:

  ```python
  normalized_mode = library_mode if library_mode in {"private_seed_public", "private_empty", "public"} else "private_seed_public"
  if normalized_mode == "public":
      target_scope = resolve_scope(PUBLIC_LIBRARY_KEY)
  else:
      proposed_key = sanitize_identifier(library_key or library_name or f"user_{batch_id}")
  ```

- [ ] **Step 2: Insert the existing-library path**

  Replace the entire `if / else` block with:

  ```python
  normalized_mode = library_mode if library_mode in {"private_seed_public", "private_empty", "public"} else "private_seed_public"
  if normalized_mode == "public":
      target_scope = resolve_scope(PUBLIC_LIBRARY_KEY)
  elif library_key and (existing_scope := resolve_scope(library_key)):
      # User selected an existing private library — use it directly to avoid
      # overwriting library_name in the scope registry via INSERT OR REPLACE.
      target_scope = existing_scope
      mark_scope_batch(target_scope["library_key"], batch_id)
  else:
      proposed_key = sanitize_identifier(library_key or library_name or f"user_{batch_id}")
      proposed_name = (library_name or proposed_key).strip() or proposed_key
      target_scope = ensure_scope(
          proposed_key,
          proposed_name,
          scope_type="private",
          seed_public=normalized_mode == "private_seed_public",
          last_batch_id=batch_id,
      )
  ```

  `resolve_scope` and `mark_scope_batch` are already imported at line 22 of this file.

- [ ] **Step 3: Verify via smoke test**

  ```powershell
  cd F:\Work_Dir\new_3dversion\my_working
  python -c "
  import sys; sys.path.insert(0, '.')
  from backend.library_scope import ensure_scope, resolve_scope, list_scopes
  # Create a test scope
  scope = ensure_scope('test_existing_lib', '测试已有库', scope_type='private', seed_public=False)
  print('Created:', scope['library_name'])
  # Verify resolve_scope finds it
  found = resolve_scope('test_existing_lib')
  assert found is not None, 'resolve_scope returned None'
  assert found['library_name'] == '测试已有库', f'Name wrong: {found[\"library_name\"]}'
  print('PASS: existing library found correctly')
  "
  ```

  Expected:
  ```
  Created: 测试已有库
  PASS: existing library found correctly
  ```

- [ ] **Step 4: Commit**

  ```powershell
  git add backend/api/kb_import.py
  git commit -m "feat: use resolve_scope for existing libraries in import_zip to preserve library name"
  ```

---

## Task 5 — HTML: replace static select with dynamic library list

**Files:**
- Modify: `updated_front/demo-industrial-console.html`
- Modify: `updated_front/css/industrial-console.css`

- [ ] **Step 1: Add CSS for radio-card list**

  Open `updated_front/css/industrial-console.css`. At the end of the file, add:

  ```css
  /* ── ZIP import library selector ─────────────────────────── */
  .zip-library-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }

  .zip-library-option {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid var(--border, #2a3040);
    border-radius: 8px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    user-select: none;
  }

  .zip-library-option:hover {
    border-color: var(--accent, #4a90e2);
    background: rgba(74, 144, 226, 0.06);
  }

  .zip-library-option input[type="radio"] {
    accent-color: var(--accent, #4a90e2);
    width: 16px;
    height: 16px;
    flex-shrink: 0;
  }

  .zip-library-option-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary, #e8eaf0);
  }

  .zip-library-option-meta {
    font-size: 12px;
    color: var(--text-muted, #7a8499);
    margin-top: 1px;
  }

  .zip-library-option.is-new .zip-library-option-title {
    color: var(--accent, #4a90e2);
  }

  .zip-library-option.is-loading {
    opacity: 0.5;
    cursor: default;
  }

  #zipNewLibraryForm {
    padding: 8px 0 0 26px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  #zipNewLibraryForm label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-muted, #7a8499);
    cursor: pointer;
  }
  ```

- [ ] **Step 2: Replace the static select in HTML**

  Find the "入库目标" hero-card block in `demo-industrial-console.html` (around line 422–441). Replace the two `filter-group` divs (the `<select id="zipLibraryModeSelect">` block and the `<input id="zipLibraryNameInput">` block) with the new structure:

  ```html
  <!-- REMOVE these two filter-group blocks: -->
  <!--
  <div class="filter-group" style="margin-bottom:12px;">
    <label>入库方式</label>
    <select id="zipLibraryModeSelect" class="filter-select">...</select>
  </div>
  <div class="filter-group" style="margin-bottom:12px;">
    <label>我的工艺库名称</label>
    <input id="zipLibraryNameInput" ... />
  </div>
  -->

  <!-- ADD this instead: -->
  <div class="filter-group" style="margin-bottom:8px;">
    <label>选择目标库</label>
  </div>
  <div id="zipLibraryList" class="zip-library-list">
    <label class="zip-library-option is-loading">
      <input type="radio" name="zipLibraryTarget" disabled />
      <div>
        <div class="zip-library-option-title">加载中...</div>
      </div>
    </label>
  </div>
  <div id="zipNewLibraryForm" style="display:none;">
    <input id="zipLibraryNameInput" class="filter-input" placeholder="例如：张三-液压项目库" value="我的工艺库" />
    <label>
      <input type="checkbox" id="zipSeedPublicCheckbox" checked />
      复制公共工艺库基线（推荐）
    </label>
  </div>
  ```

- [ ] **Step 3: Verify HTML renders**

  Start backend, open `http://localhost:5000/dev/demo-industrial-console` in browser, navigate to "工艺入库" tab. The "选择目标库" label should appear with a "加载中..." placeholder (JS not wired yet — that's the next task).

- [ ] **Step 4: Commit**

  ```powershell
  git add "updated_front/demo-industrial-console.html" "updated_front/css/industrial-console.css"
  git commit -m "feat: replace static library dropdown with dynamic radio-card list (HTML + CSS)"
  ```

---

## Task 6 — JS: `loadZipLibraryList`, `renderZipLibraryList`, updated submit logic

**Files:**
- Modify: `updated_front/js/demo-industrial-console.js`

- [ ] **Step 1: Add element references**

  Find the block where `zipLibraryModeSelect` and `zipLibraryNameInput` are assigned (around line 242):

  ```javascript
  const zipLibraryModeSelect = document.getElementById('zipLibraryModeSelect');
  ```

  Replace those two lines with:

  ```javascript
  const zipLibraryModeSelect = document.getElementById('zipLibraryModeSelect'); // may be null (removed in new HTML)
  const zipLibraryNameInput = document.getElementById('zipLibraryNameInput');
  const zipLibraryList = document.getElementById('zipLibraryList');
  const zipNewLibraryForm = document.getElementById('zipNewLibraryForm');
  const zipSeedPublicCheckbox = document.getElementById('zipSeedPublicCheckbox');
  ```

  If `zipLibraryNameInput` was already declared elsewhere, find and keep only one declaration.

- [ ] **Step 2: Add `renderZipLibraryList` function**

  Find `function currentZipLibraryMode()` (around line 554). Just before it, add:

  ```javascript
  function renderZipLibraryList(scopes) {
    if (!zipLibraryList) return;
    const items = Array.isArray(scopes) ? scopes : [];
    const html = items.map((scope) => {
      const meta = scope.scope_type === 'public' ? '公共库' : '私有库';
      const count = scope.record_count != null ? `· ${scope.record_count}条` : '';
      return `
        <label class="zip-library-option" data-key="${escapeHtml(scope.library_key)}">
          <input type="radio" name="zipLibraryTarget" value="${escapeHtml(scope.library_key)}" />
          <div>
            <div class="zip-library-option-title">${escapeHtml(scope.library_name || scope.library_key)}</div>
            <div class="zip-library-option-meta">${meta} ${count}</div>
          </div>
        </label>`;
    }).join('');

    const newOption = `
      <label class="zip-library-option is-new" data-key="__new__">
        <input type="radio" name="zipLibraryTarget" value="__new__" />
        <div>
          <div class="zip-library-option-title">+ 新建工艺库</div>
          <div class="zip-library-option-meta">创建新的私有库</div>
        </div>
      </label>`;

    zipLibraryList.innerHTML = html + newOption;

    // Default selection: first item, or "__new__" if no scopes
    const firstRadio = zipLibraryList.querySelector('input[type="radio"]');
    if (firstRadio) firstRadio.checked = true;

    // Wire up change events
    zipLibraryList.querySelectorAll('input[type="radio"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        updateZipNewLibraryFormVisibility();
        updateZipActiveLibraryChip();
      });
    });

    updateZipNewLibraryFormVisibility();
    updateZipActiveLibraryChip();
  }

  function updateZipNewLibraryFormVisibility() {
    if (!zipNewLibraryForm) return;
    const checked = zipLibraryList?.querySelector('input[type="radio"]:checked');
    zipNewLibraryForm.style.display = checked?.value === '__new__' ? 'flex' : 'none';
  }

  function updateZipActiveLibraryChip() {
    if (!zipActiveLibraryChip) return;
    const checked = zipLibraryList?.querySelector('input[type="radio"]:checked');
    if (!checked) { zipActiveLibraryChip.textContent = '当前目标：未选择'; return; }
    if (checked.value === '__new__') {
      const name = (zipLibraryNameInput?.value || '').trim() || '新工艺库';
      zipActiveLibraryChip.textContent = `当前目标：${name}（新建）`;
    } else {
      const label = checked.closest('.zip-library-option')?.querySelector('.zip-library-option-title')?.textContent || checked.value;
      zipActiveLibraryChip.textContent = `当前目标：${label}`;
    }
  }
  ```

- [ ] **Step 3: Add `loadZipLibraryList` function**

  Directly after `renderZipLibraryList`, add:

  ```javascript
  async function loadZipLibraryList() {
    if (!zipLibraryList) return;
    try {
      const data = await apiFetch('/library/scopes');
      const scopes = data?.items || [];
      renderZipLibraryList(scopes);
    } catch (_) {
      // Fallback: render just the "新建" option so the page is not broken
      renderZipLibraryList([]);
    }
  }
  ```

- [ ] **Step 4: Add `currentZipLibraryTarget` function**

  Replace the existing `currentZipLibraryMode()` and `currentZipLibraryName()` functions with:

  ```javascript
  function currentZipLibraryTarget() {
    // Returns {mode, name, key} for the currently selected import target.
    const checked = zipLibraryList?.querySelector('input[type="radio"]:checked');
    if (!checked || checked.value === '__new__') {
      // New library
      const seed = zipSeedPublicCheckbox?.checked !== false;
      const name = (zipLibraryNameInput?.value || '').trim() || '我的工艺库';
      return { mode: seed ? 'private_seed_public' : 'private_empty', name, key: '' };
    }
    // Existing library
    return { mode: 'private_empty', name: '', key: checked.value };
  }

  function currentZipLibraryMode() {
    return currentZipLibraryTarget().mode;
  }

  function currentZipLibraryName() {
    return currentZipLibraryTarget().name;
  }
  ```

- [ ] **Step 5: Update submit form to include `library_key`**

  Find the ZIP submit block (around line 2662):

  ```javascript
  form.append('library_mode', currentZipLibraryMode());
  form.append('library_name', currentZipLibraryName());
  ```

  Replace with:

  ```javascript
  const zipTarget = currentZipLibraryTarget();
  form.append('library_mode', zipTarget.mode);
  form.append('library_name', zipTarget.name);
  if (zipTarget.key) form.append('library_key', zipTarget.key);
  ```

- [ ] **Step 6: Call `loadZipLibraryList` on init and on tab switch**

  Find where the "工艺入库" tab is activated. Search for `page-zip` in the JS (the tab navigation logic). Find the handler that shows `page-zip` and add `loadZipLibraryList()` there. Also call it once on page init near `checkStartupToken()`:

  ```javascript
  checkStartupToken();
  loadZipLibraryList();
  ```

  Also find `updateZipLibraryModeUI()` calls and add `loadZipLibraryList()` after ZIP import success (after the `markSessionZipUnlocked` call around line 2674):

  ```javascript
  markSessionZipUnlocked(report.target_library.library_key);
  loadZipLibraryList(); // refresh so newly created library appears
  ```

- [ ] **Step 7: Wire `zipLibraryNameInput` change to chip update**

  Find where `zipLibraryNameInput` has a change/input handler (search for `zipLibraryNameInput.addEventListener` or `updateZipLibraryModeUI`). Add or update:

  ```javascript
  if (zipLibraryNameInput) {
    zipLibraryNameInput.addEventListener('input', updateZipActiveLibraryChip);
  }
  ```

- [ ] **Step 8: Manual test**

  1. Navigate to "工艺入库" tab.
  2. Verify the library list loads from `/api/library/scopes` (check network tab).
  3. If no libraries exist yet: only "+ 新建工艺库" is shown; `#zipNewLibraryForm` is visible.
  4. Import a ZIP → creates a library → switch away and back to tab → new library appears in list.
  5. Select existing library → form hidden → import → data goes into that library (check DB or browse page).
  6. Verify `#zipActiveLibraryChip` updates when switching selections.

- [ ] **Step 9: Commit**

  ```powershell
  git add "updated_front/js/demo-industrial-console.js"
  git commit -m "feat: dynamic library selector for ZIP import — loads existing libs, supports new-lib creation"
  ```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `cancel_stale_tasks()` in task_store | Task 1 |
| Startup call + STARTUP_TOKEN + `/api/startup_token` | Task 2 |
| Frontend: `checkStartupToken()` + `resetGenerateWorkspace()` on restart | Task 3 |
| Backend: existing library → `resolve_scope` path | Task 4 |
| HTML: replace static select with `#zipLibraryList` | Task 5 |
| CSS: radio-card styles | Task 5 |
| JS: render scopes, submit with `library_key`, update chip | Task 6 |
| Fallback if API fails | Task 6 Step 3 (renders empty → only 新建 shown) |
| Refresh list after import | Task 6 Step 6 |
| `stored !== null` guard on first load | Task 3 Step 2 |

**Placeholder scan:** No TBDs or TODOs. All code blocks are complete.

**Type consistency:**
- `currentZipLibraryTarget()` returns `{mode, name, key}` — consumed in Task 6 Step 5 as `zipTarget.mode`, `zipTarget.name`, `zipTarget.key` ✓
- `renderZipLibraryList(scopes)` takes `scope[]` from `data.items` ✓
- `cancel_stale_tasks()` returns `int` — consumed in app.py as `_stale_count` ✓
- `STARTUP_TOKEN` used in route handler in same file ✓
