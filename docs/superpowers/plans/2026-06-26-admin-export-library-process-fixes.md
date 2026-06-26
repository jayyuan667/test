# Admin Export Library Process Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reported permission-management, export, public-library snapshot, and process-row editing bugs without expanding the product architecture.

**Architecture:** Keep the existing Flask Blueprint API, React useState routing, Tailwind/CSS-variable UI, and enterprise isolation model. Extend existing endpoints and components in place, using focused helper functions where they reduce duplicated permission or row-cleaning logic. All frontend changes follow product UI rules from `PRODUCT.md`: restrained, task-focused, minimal controls, no new design system.

**Tech Stack:** Python 3.11+, Flask, sqlite3, openpyxl, Pillow, React 18, TypeScript, Tailwind CSS 3, Vite, pytest, Playwright.

## Global Constraints

- Keep API responses in the existing `{success: true, data: {...}}` / `{success: false, error: {...}}` style for auth/admin endpoints.
- Do not introduce new roles, new auth tables, react-router, shadcn, or a new design system.
- Do not add pandas; XLSX export uses `openpyxl`.
- PDF export must stay compatible with Windows and prioritize Windows Chinese fonts.
- Enterprise administrators may only claim `role=user AND enterprise_id IS NULL` users into their own enterprise.
- Super administrators retain global authority, but full-platform private data still requires an explicit scope.
- Public library records are visible when the selected scope is `public`.
- Process-row editing is primarily a frontend display/state fix; backend row cleaning is defensive only.
- Before editing any function/class/method, run `node .gitnexus/run.cjs impact <symbol> --direction upstream` and report direct callers, affected processes, and risk.
- Before any commit, run `node .gitnexus/run.cjs detect_changes --scope staged`.

---

## File Structure

- Modify `backend/api/admin.py`: add unassigned-user listing scope and enterprise-admin claim logic.
- Modify `frontend-react/src/api/client.ts`: allow `getAdminUsers()` to pass `scope=unassigned`.
- Modify `frontend-react/src/pages/admin/EnterpriseTab.tsx`: rename "续期管理员" copy to "设置/续期管理员".
- Modify `frontend-react/src/pages/admin/UsersTab.tsx`: add compact member/unassigned switch and "分配到本企业" action.
- Modify `backend/api/export.py`: replace pandas export with openpyxl and add cross-platform font candidates.
- Modify `backend/api/library.py`: allow super_admin public scope reads and add a library snapshot asset route or helper.
- Modify `frontend-react/src/pages/DbPage.tsx`: keep public scope visible for super_admin and show snapshot image failure text.
- Modify `frontend-react/src/components/generate/ProcessPanel.tsx`: preserve inserted blank rows in edit mode and clean rows before emitting/committing.
- Inspect `frontend-react/src/components/generate/CommitToLibraryModal.tsx`: do not edit it when `ProcessPanel` passes a cleaned `draft.process_list`; edit it only when inspection shows the modal re-derives rows from unclean content.
- Add/modify tests:
  - `backend/test_admin_permissions.py`
  - `backend/test_export.py`
  - `backend/test_library_snapshot.py`
  - `frontend-react/tests/admin-users.spec.ts`
  - `frontend-react/tests/data-isolation.spec.ts`
  - `frontend-react/tests/process-panel.spec.ts`

---

### Task 1: Admin Permission Semantics

**Files:**
- Modify: `backend/api/admin.py`
- Modify: `frontend-react/src/api/client.ts`
- Modify: `frontend-react/src/pages/admin/EnterpriseTab.tsx`
- Modify: `frontend-react/src/pages/admin/UsersTab.tsx`
- Test: `backend/test_admin_permissions.py`
- Test: `frontend-react/tests/admin-users.spec.ts`

**Interfaces:**
- Consumes: `auth_store.list_all_users()`, `auth_store.list_enterprise_users(enterprise_id)`, `auth_store.update_user(user_id, **kwargs)`.
- Produces: `GET /api/admin/users?scope=unassigned` for enterprise admins; `updateAdminUser(userId, { enterprise_id })` may claim an unassigned user when caller is enterprise admin.

- [ ] **Step 1: Run impact analysis**

Run:

```bash
node .gitnexus/run.cjs impact list_users --direction upstream
node .gitnexus/run.cjs impact update_user --direction upstream
```

Expected: report callers/processes before editing `backend/api/admin.py`. If risk is HIGH or CRITICAL, warn the user before continuing.

- [ ] **Step 2: Add failing backend tests**

Create `backend/test_admin_permissions.py` with tests that isolate `auth_store.DB_PATH` to a temp DB and register the admin blueprint. Use `client.session_transaction()` or a small request hook to set `g.current_user` consistently with existing auth tests in this repo; do not bypass the endpoint permission branches being tested. The key assertions:

```python
def test_enterprise_admin_can_list_unassigned_users(client, login_as, make_user):
    ent = make_enterprise("Acme")
    admin = make_user("acme_admin", role="enterprise_admin", enterprise_id=ent["id"])
    unassigned = make_user("new_user", role="user", enterprise_id=None)
    make_user("other_admin", role="enterprise_admin", enterprise_id=None)

    login_as(admin)
    res = client.get("/api/admin/users?scope=unassigned")

    assert res.status_code == 200
    usernames = [u["username"] for u in res.json["data"]["users"]]
    assert usernames == [unassigned["username"]]
```

```python
def test_enterprise_admin_can_claim_only_unassigned_user(client, login_as, make_user):
    ent = make_enterprise("Acme")
    other = make_enterprise("Other")
    admin = make_user("acme_admin", role="enterprise_admin", enterprise_id=ent["id"])
    target = make_user("new_user", role="user", enterprise_id=None)
    other_user = make_user("other_user", role="user", enterprise_id=other["id"])

    login_as(admin)
    ok_res = client.put(f"/api/admin/users/{target['id']}", json={"enterprise_id": ent["id"]})
    forbidden_res = client.put(f"/api/admin/users/{other_user['id']}", json={"enterprise_id": ent["id"]})

    assert ok_res.status_code == 200
    assert ok_res.json["data"]["user"]["enterprise_id"] == ent["id"]
    assert forbidden_res.status_code == 403
```

Run:

```bash
.venv/bin/python3 -m pytest backend/test_admin_permissions.py -q
```

Expected: fails before implementation because `scope=unassigned` and enterprise-admin claim are not supported.

- [ ] **Step 3: Implement backend list scope**

In `backend/api/admin.py`, update `list_users()` so the enterprise-admin branch handles `scope=unassigned`:

```python
scope = (request.args.get("scope") or "").strip().lower()
if user["role"] == "super_admin":
    ...
else:
    eid = user.get("enterprise_id")
    if scope == "unassigned":
        users = [
            u for u in auth_store.list_all_users()
            if u.get("role") == "user" and u.get("enterprise_id") is None
        ]
    elif not eid:
        users = []
    else:
        users = auth_store.list_enterprise_users(eid)
```

Keep the default enterprise-admin branch unchanged for member lists.

- [ ] **Step 4: Implement backend claim rule**

In `update_user()`, replace the enterprise-admin rejection block with explicit claim support:

```python
if current_user["role"] == "enterprise_admin":
    current_eid = current_user.get("enterprise_id")
    requested_eid = data.get("enterprise_id") if "enterprise_id" in data else None

    if "role" in data:
        return fail(ERR_FORBIDDEN, "无权修改角色", status=403)

    if "enterprise_id" in data:
        can_claim = (
            target.get("role") == "user"
            and target.get("enterprise_id") is None
            and requested_eid == current_eid
        )
        if not can_claim:
            return fail(ERR_FORBIDDEN, "只能分配未分配用户到本企业", status=403)
    elif target.get("enterprise_id") != current_eid:
        return fail(ERR_FORBIDDEN, "只能管理本企业用户", status=403)
```

Leave quota and active-state handling intact for own-enterprise users.

- [ ] **Step 5: Extend frontend API**

In `frontend-react/src/api/client.ts`, change:

```ts
export async function getAdminUsers(params?: number | { enterpriseId?: number; scope?: 'unassigned' }): Promise<{ users: AdminUser[] }> {
  const qs = new URLSearchParams()
  if (typeof params === 'number') qs.set('enterprise_id', String(params))
  else if (params) {
    if (params.enterpriseId) qs.set('enterprise_id', String(params.enterpriseId))
    if (params.scope) qs.set('scope', params.scope)
  }
  const query = qs.toString()
  return authRequest<{ users: AdminUser[] }>(`/admin/users${query ? `?${query}` : ''}`)
}
```

Preserve existing callers that pass a number.

- [ ] **Step 6: Update admin UI copy and controls**

In `EnterpriseTab.tsx`, replace visible copy:

```tsx
设置/续期管理员
```

In `UsersTab.tsx`, for enterprise admins add a compact two-option segmented control:

```tsx
const [userScope, setUserScope] = useState<'members' | 'unassigned'>('members')
...
getAdminUsers(isSuperAdmin ? filterEnt : userScope === 'unassigned' ? { scope: 'unassigned' } : undefined)
```

For unassigned rows, show only:

```tsx
<button
  onClick={() => claimUser(u)}
  className="theme-link-action text-xs font-medium min-h-[44px]"
>
  分配到本企业
</button>
```

`claimUser()` calls:

```ts
await updateAdminUser(user.id, { enterprise_id: currentUser.enterprise_id })
```

- [ ] **Step 7: Add Playwright coverage**

In `frontend-react/tests/admin-users.spec.ts`, add a test that mocks or seeds an enterprise-admin session, opens 管理后台, switches to 未分配用户, clicks 分配到本企业, and expects the row to leave the unassigned list.

Run:

```bash
cd frontend-react && npx playwright test tests/admin-users.spec.ts --reporter=line
```

Expected: passes after UI implementation.

- [ ] **Step 8: Verify and commit**

Run:

```bash
.venv/bin/python3 -m pytest backend/test_admin_permissions.py -q
cd frontend-react && npm run build
node ../.gitnexus/run.cjs detect_changes --scope staged
```

Expected: pytest passes, build passes, GitNexus reports only expected admin symbols and UI components. Commit:

```bash
git add backend/api/admin.py backend/test_admin_permissions.py frontend-react/src/api/client.ts frontend-react/src/pages/admin/EnterpriseTab.tsx frontend-react/src/pages/admin/UsersTab.tsx frontend-react/tests/admin-users.spec.ts
git commit -m "fix: allow enterprise admins to claim unassigned users"
```

---

### Task 2: XLSX and PDF Export Reliability

**Files:**
- Modify: `backend/api/export.py`
- Test: `backend/test_export.py`

**Interfaces:**
- Consumes: `_normalize_rows(result_data: dict) -> list[list[str]]`.
- Produces: `_excel_response(task_id: str, result_data: dict)` using openpyxl only; `_load_font(size: int)` with cross-platform CJK font candidates.

- [ ] **Step 1: Run impact analysis**

Run:

```bash
node .gitnexus/run.cjs impact _excel_response --direction upstream
node .gitnexus/run.cjs impact _load_font --direction upstream
node .gitnexus/run.cjs impact export_result --direction upstream
```

Expected: report blast radius. If risk is HIGH or CRITICAL, warn before editing.

- [ ] **Step 2: Add failing export tests**

Create `backend/test_export.py`:

```python
def test_xlsx_export_uses_openpyxl_without_pandas(monkeypatch):
    import sys
    from backend.api import export as export_api

    monkeypatch.setitem(sys.modules, "pandas", None)
    result = {
        "process_flow": {
            "data": [
                ["0010", "车", "车端面"],
                ["0020", "检", "检验尺寸"],
            ]
        }
    }

    with export_api.export_bp.test_request_context("/export/t1?format=xlsx"):
        response = export_api._excel_response("t1", result)

    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

```python
def test_font_candidates_include_windows_and_cross_platform_paths():
    from backend.api.export import FONT_CANDIDATES

    joined = "\n".join(FONT_CANDIDATES)
    assert "C:\\Windows\\Fonts\\msyh.ttc" in joined
    assert "simhei.ttf" in joined
    assert "STHeiti" in joined
    assert "NotoSansCJK" in joined or "SourceHanSansCN" in joined
```

Run:

```bash
.venv/bin/python3 -m pytest backend/test_export.py -q
```

Expected: fails before removing pandas and adding font candidates.

- [ ] **Step 3: Replace pandas XLSX path**

In `backend/api/export.py`, import openpyxl inside `_excel_response`:

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
```

Add helper:

```python
def _write_xlsx_workbook(tables: Dict[str, List[List[str]]]) -> BytesIO:
    columns = ["标签编码", "工种", "工序内容"]
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    for sheet_name, rows in tables.items():
        ws = wb.create_sheet(title=(sheet_name[:31] or "Process"))
        ws.append(columns)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="FFF7ED")
            cell.alignment = Alignment(vertical="center")
        for row in rows:
            normalized = list(row) + [""] * (len(columns) - len(row))
            ws.append(normalized[:len(columns)])
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 80
        for row_cells in ws.iter_rows():
            for cell in row_cells:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
```

Use it for both `process_flow.tables` and normalized `process_flow.data`.

- [ ] **Step 4: Add Windows-first font candidates**

Replace `FONT_CANDIDATES` with:

```python
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/source-han-sans/SourceHanSansCN-Regular.otf",
]
```

Update `_load_font()` to log a warning when no candidate exists:

```python
logger.warning("No CJK font candidate found for PDF export; falling back to PIL default font")
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
.venv/bin/python3 -m pytest backend/test_export.py -q
.venv/bin/python3 -m pytest backend/test_data_isolation.py -q
node .gitnexus/run.cjs detect_changes --scope staged
```

Expected: export tests pass, isolation tests still pass, staged scope is limited to export behavior. Commit:

```bash
git add backend/api/export.py backend/test_export.py
git commit -m "fix: make process exports reliable without pandas"
```

---

### Task 3: Public Library Visibility and Snapshot Assets

**Files:**
- Modify: `backend/api/library.py`
- Modify: `backend/api/result.py` only if the chosen implementation reuses result blueprint helpers.
- Modify: `frontend-react/src/api/client.ts` only if a new snapshot URL helper is needed.
- Modify: `frontend-react/src/pages/DbPage.tsx`
- Test: `backend/test_library_snapshot.py`
- Test: `frontend-react/tests/data-isolation.spec.ts`

**Interfaces:**
- Consumes: `get_enterprise_scope()`, `_fetch_record_by_id(record_id, library_key)`, `_list_records(...)`.
- Produces: public scope records visible to super_admin; snapshot asset access based on library-record visibility.

- [ ] **Step 1: Run impact analysis**

Run:

```bash
node .gitnexus/run.cjs impact _list_records --direction upstream
node .gitnexus/run.cjs impact list_library_records --direction upstream
node .gitnexus/run.cjs impact get_result_asset --direction upstream
```

Expected: report blast radius. Warn on HIGH or CRITICAL risk.

- [ ] **Step 2: Add failing backend tests**

Create `backend/test_library_snapshot.py`:

```python
def test_super_admin_can_list_public_scope_records(client, login_as_super_admin, seed_public_record):
    record = seed_public_record(prefix="PUB001")
    login_as_super_admin()

    res = client.get("/api/library/records?library_key=public")

    assert res.status_code == 200
    prefixes = [item["prefix"] for item in res.json["items"]]
    assert record["prefix"] in prefixes
```

```python
def test_library_snapshot_asset_requires_record_access(client, login_as_enterprise_admin, seed_library_record_with_asset):
    ent_id = 1
    record = seed_library_record_with_asset(enterprise_id=ent_id, filename="pages/page_001.png")
    login_as_enterprise_admin(enterprise_id=ent_id)

    res = client.get(f"/api/library/records/{record['id']}/asset/pages/page_001.png?library_key={record['library_key']}")

    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("image/")
```

Run:

```bash
.venv/bin/python3 -m pytest backend/test_library_snapshot.py -q
```

Expected: public scope or snapshot asset test fails before implementation.

- [ ] **Step 3: Fix super_admin public scope logic**

In `_list_records()`, resolve scope before super_admin branch and allow public scope:

```python
_scope_type_key = (scope or {}).get("scope_type", "")
if _is_super:
    _scope_param = request.args.get("scope", "")
    _filter_ent = request.args.get("enterprise_id", type=int)
    if _scope_type_key == "public":
        pass
    elif _scope_param == "all":
        pass
    elif _filter_ent is not None:
        where.append("enterprise_id = ?")
        params.append(_filter_ent)
        _ent_sql = "AND enterprise_id = ?"
        _ent_params_pt = [_filter_ent]
    else:
        where.append("1 = 0")
        _ent_sql = "AND 1 = 0"
```

- [ ] **Step 4: Add library snapshot asset route**

In `backend/api/library.py`, add a route near record endpoints:

```python
@library_bp.route("/library/records/<int:record_id>/asset/<path:filename>", methods=["GET"])
@login_required
def get_library_record_asset(record_id: int, filename: str):
    library_key = request.args.get("library_key", "")
    record = _fetch_record_by_id(record_id, library_key=library_key)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    if not _can_access_record(record):
        return jsonify({"error": "Record not found"}), 404
    preview_task_id = record.get("preview_task_id") or record.get("source_task_id") or ""
    if not preview_task_id:
        return jsonify({"error": "Asset not found"}), 404
    return _send_preview_asset(preview_task_id, filename)
```

Add helpers in the same file:

```python
def _can_access_record(record: dict) -> bool:
    ent_id, is_super = get_enterprise_scope()
    if is_super:
        return True
    if record.get("enterprise_id") is None:
        return True
    return ent_id is not None and int(record["enterprise_id"]) == ent_id
```

```python
def _send_preview_asset(task_id: str, filename: str):
    from flask import send_from_directory
    from ..config import OUTPUT_FOLDER, KB_PREVIEW_FOLDER

    safe_name = filename.replace("\\", "/")
    if safe_name.startswith("/") or ".." in safe_name.split("/"):
        return jsonify({"error": "Asset not found"}), 404
    root = os.path.join(KB_PREVIEW_FOLDER, task_id) if task_id.startswith("kb_") or task_id.startswith("library_") else os.path.join(OUTPUT_FOLDER, task_id)
    file_path = os.path.join(root, *safe_name.split("/"))
    if not os.path.isfile(file_path):
        return jsonify({"error": "Asset not found"}), 404
    return send_from_directory(root, safe_name)
```

- [ ] **Step 5: Update frontend snapshot URLs**

In `DbPage.tsx`, update `getPreviewUrls(record)` so record snapshots prefer the library-record asset route:

```ts
const getLibraryAssetUrl = (record: LibraryRecord, filename: string) => {
  const qs = filterScope ? `?library_key=${encodeURIComponent(filterScope)}` : ''
  return `/api/library/records/${record.id}/asset/${filename}${qs}`
}
```

When a stored URL is already `/api/result/...`, convert only for relative filenames. Keep absolute URLs unchanged.

Add visible error state in snapshot modal:

```tsx
const [snapshotError, setSnapshotError] = useState('')
...
onError={() => setSnapshotError('快照文件不存在或已被清理')}
```

Render the message in place of a silently hidden image.

- [ ] **Step 6: Add Playwright coverage**

In `frontend-react/tests/data-isolation.spec.ts`, add or update tests:

```ts
test('super admin can browse public library records', async ({ page }) => {
  await loginAs(page, 'admin', 'admin123')
  await page.getByRole('button', { name: /知识库|数据库/ }).click()
  await page.getByLabel('数据库范围').selectOption('public')
  await expect(page.getByText('暂无记录')).not.toBeVisible()
})
```

```ts
test('library snapshot failure shows explicit message', async ({ page }) => {
  await openRecordWithBrokenSnapshot(page)
  await page.getByRole('button', { name: /查看.*快照/ }).click()
  await expect(page.getByText('快照文件不存在或已被清理')).toBeVisible()
})
```

- [ ] **Step 7: Verify and commit**

Run:

```bash
.venv/bin/python3 -m pytest backend/test_library_snapshot.py -q
.venv/bin/python3 -m pytest backend/test_data_isolation.py -q
cd frontend-react && npx playwright test tests/data-isolation.spec.ts --reporter=line
node ../.gitnexus/run.cjs detect_changes --scope staged
```

Expected: public-library and snapshot tests pass, data isolation tests pass. Commit:

```bash
git add backend/api/library.py backend/api/result.py backend/test_library_snapshot.py frontend-react/src/api/client.ts frontend-react/src/pages/DbPage.tsx frontend-react/tests/data-isolation.spec.ts
git commit -m "fix: restore public library visibility and snapshots"
```

---

### Task 4: Process Row Editing Display and Cleaning

**Files:**
- Modify: `frontend-react/src/components/generate/ProcessPanel.tsx`
- Inspect: `frontend-react/src/components/generate/CommitToLibraryModal.tsx`; modify it only when the modal re-derives process rows from unclean text instead of receiving `draft.process_list`.
- Modify: `backend/api/library.py`
- Test: `frontend-react/tests/process-panel.spec.ts`
- Test: `backend/test_library_process_rows.py`

**Interfaces:**
- Consumes: `ProcessRow { code: string; trade: string; content: string }`.
- Produces: frontend helper `cleanProcessRows(rows: ProcessRow[]): ProcessRow[]`; backend helper `_clean_process_list(process_list: list) -> list`.

- [ ] **Step 1: Run impact analysis**

Run:

```bash
node .gitnexus/run.cjs impact ProcessPanel --direction upstream
node .gitnexus/run.cjs impact _upsert_record --direction upstream
```

Expected: report affected React flows and library write path. Warn on HIGH or CRITICAL risk.

- [ ] **Step 2: Add failing frontend test**

Create `frontend-react/tests/process-panel.spec.ts`:

```ts
test('inserting a process row shows an editable blank row and does not submit blank rows', async ({ page }) => {
  await openCompletedGenerateResult(page)
  await page.getByRole('tab', { name: '工艺规程' }).click()

  const firstInsert = page.getByTitle('在下方插入').first()
  await firstInsert.click()

  await expect(page.getByPlaceholder('工序内容')).toBeVisible()
  await page.getByPlaceholder('工序内容').fill('补充检验倒角')
  await page.getByText('入库').click()

  await expect(page.getByText('补充检验倒角')).toBeVisible()
  await expect(page.getByText(/^0030\s*$/)).not.toBeVisible()
})
```

Run:

```bash
cd frontend-react && npx playwright test tests/process-panel.spec.ts --reporter=line
```

Expected: fails before implementation because blank rows are filtered from render.

- [ ] **Step 3: Add frontend cleaning helper**

In `ProcessPanel.tsx`, add:

```ts
function cleanProcessRows(rows: ProcessRow[]): ProcessRow[] {
  return rows
    .filter(row => row.code.trim() || row.trade.trim() || row.content.trim())
    .map((row, index) => ({
      code: String((index + 1) * 10).padStart(4, '0'),
      trade: row.trade.trim(),
      content: row.content.trim(),
    }))
}
```

Update `renumberRows()` to use `padStart(4, '0')`:

```ts
return rows.map((row, i) => ({ ...row, code: String((i + 1) * 10).padStart(4, '0') }))
```

- [ ] **Step 4: Render edit rows without filtering**

Replace:

```ts
const allRows = hasFinalResult ? editRows : displayedRows
const rows = allRows.filter(r => (r.content || '').trim().length > 0 || (r.trade || '').trim().length > 0)
```

with:

```ts
const rows = hasFinalResult ? editRows : displayedRows.filter(r => r.content.trim() || r.trade.trim())
```

In edit mode, render inputs for blank rows:

```tsx
{hasFinalResult ? (
  <input
    aria-label={`第 ${i + 1} 行工序内容`}
    className="cell-editable block w-full bg-transparent outline-none"
    value={row.content}
    placeholder="工序内容"
    onChange={e => handleCellEdit(i, 'content', e.currentTarget.value)}
  />
) : (
  <span className="cell-editable block">{row.content}</span>
)}
```

Use input/select-like controls in edit mode rather than `contentEditable` for newly inserted blank rows.

- [ ] **Step 5: Clean rows before parent notification and commit draft**

Change the parent notification effect:

```ts
useEffect(() => {
  onRowsChange?.(cleanProcessRows(editRows))
}, [editRows, onRowsChange])
```

In `commitDraft`, use:

```ts
const rows = cleanProcessRows(editRows.length > 0 ? editRows : finalRows)
```

- [ ] **Step 6: Add backend defensive cleaning**

In `backend/api/library.py`, add:

```python
def _clean_process_list(process_list):
    cleaned = []
    for row in process_list or []:
        if isinstance(row, dict):
            code = str(row.get("code") or row.get("step_code") or "").strip()
            trade = str(row.get("trade") or row.get("work_type") or "").strip()
            content = str(row.get("content") or row.get("name") or row.get("description") or "").strip()
            if code or trade or content:
                cleaned.append({"code": code, "trade": trade, "content": content})
        else:
            text = str(row or "").strip()
            if text:
                cleaned.append(text)
    for index, row in enumerate(cleaned):
        if isinstance(row, dict):
            row["code"] = f"{(index + 1) * 10:04d}"
    return cleaned
```

In `_upsert_record()`, replace:

```python
process_list = draft.get("process_list", [])
```

with:

```python
process_list = _clean_process_list(draft.get("process_list", []))
```

- [ ] **Step 7: Add backend row-cleaning test**

Create `backend/test_library_process_rows.py`:

```python
def test_clean_process_list_drops_blank_dicts_and_renumbers():
    from backend.api.library import _clean_process_list

    rows = [
        {"code": "0010", "trade": "车", "content": "车端面"},
        {"code": "", "trade": "", "content": ""},
        {"code": "", "trade": "检", "content": "检验"},
    ]

    assert _clean_process_list(rows) == [
        {"code": "0010", "trade": "车", "content": "车端面"},
        {"code": "0020", "trade": "检", "content": "检验"},
    ]
```

- [ ] **Step 8: Verify and commit**

Run:

```bash
.venv/bin/python3 -m pytest backend/test_library_process_rows.py -q
cd frontend-react && npx playwright test tests/process-panel.spec.ts --reporter=line
cd frontend-react && npm run build
node ../.gitnexus/run.cjs detect_changes --scope staged
```

Expected: frontend inserted-row test passes, backend cleaning test passes, build passes. Commit:

```bash
git add frontend-react/src/components/generate/ProcessPanel.tsx frontend-react/src/components/generate/CommitToLibraryModal.tsx backend/api/library.py backend/test_library_process_rows.py frontend-react/tests/process-panel.spec.ts
git commit -m "fix: show inserted process rows and drop blanks"
```

---

### Task 5: Regression Sweep and Documentation Update

**Files:**
- Modify: `docs/superpowers/reports/2026-06-26-admin-export-library-process-fixes-delivery.md`
- Modify: `docs/superpowers/HANDOFF-user-auth-system.md` if permission behavior changed from the old handoff text.

**Interfaces:**
- Consumes: all completed tasks.
- Produces: delivery report with commands, outcomes, risk notes, and remaining limitations.

- [ ] **Step 1: Run focused backend regression**

Run:

```bash
.venv/bin/python3 -m pytest backend/test_auth_store.py backend/test_data_isolation.py backend/test_admin_permissions.py backend/test_export.py backend/test_library_snapshot.py backend/test_library_process_rows.py -q
```

Expected: all pass; any skipped test has the existing documented reason.

- [ ] **Step 2: Run frontend regression**

Run:

```bash
cd frontend-react && npm run build
cd frontend-react && npx playwright test tests/auth-ui.spec.ts tests/db-preview.spec.ts tests/zip-to-db-flow.spec.ts tests/data-isolation.spec.ts tests/admin-users.spec.ts tests/process-panel.spec.ts --reporter=line
```

Expected: build passes; Playwright tests pass or only documented data-seeding tests skip.

- [ ] **Step 3: Run GitNexus final staged detection**

Run:

```bash
node .gitnexus/run.cjs detect_changes --scope staged
```

Expected: changed symbols match the implementation scope: admin API/UI, export API, library/result asset path, process panel, and tests.

- [ ] **Step 4: Write delivery report**

Create `docs/superpowers/reports/2026-06-26-admin-export-library-process-fixes-delivery.md` with:

```markdown
# 管理权限、导出、公共库快照与工序编辑修复交付报告

> 日期：2026-06-26
> 分支：yolo-react

## 修复内容

- 超级管理员设置/续期企业管理员入口文案修正。
- 企业管理员可领取未分配普通用户到本企业。
- XLSX 导出移除 pandas 依赖，改用 openpyxl。
- PDF 导出补充 Windows/macOS/Linux 中文字体候选。
- 超级管理员可浏览公共库。
- 数据库快照图片基于库记录权限访问。
- 工序编辑插入行可见，空行不入库。

## 验证命令

在本节写入 Steps 1-3 的实际命令和结果摘要。每一行必须包含命令、通过/失败状态、测试数量或构建摘要、以及跳过项原因。

## 风险与限制

- 企业管理员只能领取未分配普通用户，不能设置企业管理员。
- 全平台私有数据仍需超级管理员显式选择范围。
- 找不到历史快照文件时显示明确空状态，不恢复已删除文件。
```

Before committing, re-open the report and confirm the 验证命令 section contains no angle-bracket tokens and no generic success claims without command output.

- [ ] **Step 5: Update handoff doc when its role constraints are stale**

If `docs/superpowers/HANDOFF-user-auth-system.md` still says enterprise admins cannot see unassigned users, update the role constraints section:

```markdown
- `enterprise_admin` 可管理本企业成员，并可领取未分配普通用户到本企业；不可查看其他企业成员，不可修改用户角色。
```

- [ ] **Step 6: Commit report**

Run:

```bash
git add docs/superpowers/reports/2026-06-26-admin-export-library-process-fixes-delivery.md docs/superpowers/HANDOFF-user-auth-system.md
node .gitnexus/run.cjs detect_changes --scope staged
git commit -m "docs: report admin export library process fixes"
```

Expected: GitNexus staged detection reports documentation-only or low-risk doc changes.

---

## Final Completion Checklist

- [ ] All task commits are present.
- [ ] Backend focused tests pass.
- [ ] Frontend build passes.
- [ ] Playwright focused tests pass or documented skips are unchanged.
- [ ] `node .gitnexus/run.cjs detect_changes --scope staged` was run before each commit.
- [ ] No unrelated dirty worktree changes were reverted or committed.
- [ ] Delivery report records actual verification output.
