# Export Modal Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the export modal into the main industrial console page, adapt data format to backend's `process_flow.data` structure, source images from `creo_views/全部默认.jpg`, and match the existing industrial visual style.

**Architecture:** Inline modal div in `demo-industrial-console.html`, styled via `industrial-console.css` using existing CSS variables. JS opens modal on "导出工艺文件" click, fetches result from `/api/result/<task_id>`, fills preview table from `process_flow.data`, loads image from `/api/result/<task_id>/asset/creo_views/全部默认.jpg`. Export buttons trigger direct backend download via `/api/export/<task_id>?format=pdf|xlsx`. No jsPDF dependency.

**Tech Stack:** Vanilla HTML/CSS/JS, Flask backend (no changes needed), existing CSS variables.

---

### Task 1: Add export modal CSS

**Files:**
- Modify: `updated_front/css/industrial-console.css` — append before the final `@media` rules or end-of-file

- [ ] **Step 1: Append export modal styles to CSS**

Insert these styles at the end of `industrial-console.css` (before any existing closing):

```css
/* ── Export Modal ── */
.export-modal {
  position: fixed;
  inset: 0;
  background: rgba(16, 26, 40, 0.48);
  backdrop-filter: blur(6px);
  display: none;
  align-items: center;
  justify-content: center;
  padding: 28px;
  z-index: 50;
}

.export-modal.open {
  display: flex;
}

.export-modal-card {
  width: min(980px, 100%);
  max-height: calc(100vh - 56px);
  overflow: auto;
  border-radius: var(--radius);
  background: rgba(255,255,255,0.98);
  border: 1px solid #d7e2ef;
  box-shadow: 0 26px 60px rgba(18, 31, 48, 0.18);
  padding: 22px;
}

.export-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.export-modal-title {
  font-size: 24px;
  font-weight: 800;
  margin-bottom: 8px;
}

.export-modal-meta {
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.7;
}

/* ── Export preview layout ── */
.export-preview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.export-preview-image-shell {
  border: 1px dashed #d7e1eb;
  border-radius: 14px;
  min-height: 240px;
  background: linear-gradient(180deg, #f7fbff 0%, #eef5fc 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 12px;
}

.export-preview-image-shell img {
  display: block;
  max-width: 100%;
  max-height: 400px;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 10px;
  box-shadow: 0 14px 32px rgba(19, 33, 51, 0.14);
  background: #fff;
}

.export-preview-image-placeholder {
  color: var(--text-soft);
  font-size: 14px;
  text-align: center;
}

.export-info-block {
  border-radius: 14px;
  border: 1px solid #e0e8f0;
  background: #fff;
  padding: 14px;
}

.export-info-block h4 {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--text);
}

.export-info-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
  color: var(--text-soft);
  line-height: 1.8;
}

.export-info-row .label {
  color: var(--text-soft);
  font-weight: 500;
}

.export-info-row .value {
  color: var(--text);
  font-weight: 600;
}

/* ── Export process table ── */
.export-process-block {
  border-radius: 14px;
  border: 1px solid #e0e8f0;
  background: #fff;
  padding: 14px;
  margin-bottom: 0;
}

.export-process-block h4 {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--text);
}

.export-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.export-table th,
.export-table td {
  border: 1px solid #cfd8e3;
  padding: 8px 10px;
  vertical-align: top;
}

.export-table th {
  background: #f0f7ff;
  text-align: center;
  font-weight: 700;
  color: #35506b;
}

.export-table td.step-code {
  text-align: center;
  color: var(--accent);
  font-weight: 700;
  width: 80px;
}

.export-table td.step-content {
  color: var(--text);
}

.export-table td.empty-row {
  text-align: center;
  color: #9aa6b2;
}

.export-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
```

- [ ] **Step 2: Verify CSS is syntactically valid**

Open `industrial-console.css` in editor, confirm no unclosed braces or syntax errors at the insertion point.

- [ ] **Step 3: Commit**

```bash
git add updated_front/css/industrial-console.css
git commit -m "style: add export modal CSS using existing design variables"
```

---

### Task 2: Add export modal HTML

**Files:**
- Modify: `updated_front/demo-industrial-console.html` — insert before `<script src="js/demo-industrial-console.js"></script>` at line 777

- [ ] **Step 1: Insert modal markup**

Add this HTML block before `<script src="js/demo-industrial-console.js"></script>` (line 777):

```html
  <div class="export-modal" id="exportModal">
    <div class="export-modal-card">
      <div class="export-modal-head">
        <div>
          <div class="export-modal-title">导出工艺文件</div>
          <div class="export-modal-meta" id="exportModalMeta">加载中...</div>
        </div>
        <button class="close-button" id="exportModalCloseBtn">×</button>
      </div>

      <div class="export-preview-grid">
        <div class="export-preview-image-shell">
          <img id="exportModalImage" alt="工艺预览" style="display:none;" />
          <div class="export-preview-image-placeholder" id="exportModalImagePlaceholder">未提供图片</div>
        </div>
        <div class="export-info-block">
          <h4>图纸信息</h4>
          <div class="export-info-row" id="exportModalInfo">暂无信息</div>
        </div>
      </div>

      <div class="export-process-block">
        <h4>工艺规程</h4>
        <table class="export-table" id="exportModalTable">
          <thead>
            <tr>
              <th>工序号</th>
              <th>工序名称及内容</th>
            </tr>
          </thead>
          <tbody>
            <tr><td colspan="2" class="empty-row">暂无工艺数据</td></tr>
          </tbody>
        </table>
      </div>

      <div class="export-modal-actions">
        <button class="button secondary" id="exportCancelBtn">取消</button>
        <button class="button secondary" id="exportExcelBtn">下载 Excel</button>
        <button class="button primary" id="exportPdfBtn">下载 PDF</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 2: Check HTML for duplicate IDs**

No IDs from this block (`exportModal`, `exportModalCloseBtn`, `exportModalImage`, `exportModalImagePlaceholder`, `exportModalInfo`, `exportModalTable`, `exportCancelBtn`, `exportExcelBtn`, `exportPdfBtn`, `exportModalMeta`) should exist elsewhere in the file. Verify with search.

- [ ] **Step 3: Commit**

```bash
git add updated_front/demo-industrial-console.html
git commit -m "feat: add export modal HTML structure to main page"
```

---

### Task 3: Add export modal JS logic

**Files:**
- Modify: `updated_front/js/demo-industrial-console.js`
  - Replace `openExportEngineeringCard` function body (line ~2267)
  - Add new helper functions before the closing `})();` (before line 4875)
  - Add event listener wiring inside the IIFE's existing init/event-binding area

- [ ] **Step 1: Get DOM references for export modal elements**

Add these lines alongside the existing DOM references, near the other `document.getElementById` calls (around line 277-278 where `const dbPreviewModal` and `closeDbPreviewModal` are defined):

```js
    const exportModal = document.getElementById('exportModal');
    const exportModalCloseBtn = document.getElementById('exportModalCloseBtn');
    const exportCancelBtn = document.getElementById('exportCancelBtn');
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    const exportModalImage = document.getElementById('exportModalImage');
    const exportModalImagePlaceholder = document.getElementById('exportModalImagePlaceholder');
    const exportModalInfo = document.getElementById('exportModalInfo');
    const exportModalTable = document.getElementById('exportModalTable');
    const exportModalMeta = document.getElementById('exportModalMeta');
```

- [ ] **Step 2: Replace `openExportEngineeringCard` function body**

Replace the existing `openExportEngineeringCard` function (lines 2267-2287) with:

```js
    function openExportEngineeringCard() {
      const taskId = currentExportTaskId();
      if (!taskId) {
        if (reviewStatusBadge) {
          reviewStatusBadge.textContent = '暂无可导出任务';
          reviewStatusBadge.className = 'status-badge danger';
        }
        return;
      }
      exportModalMeta.textContent = `加载任务 ${taskId} 数据...`;
      exportModalImage.style.display = 'none';
      exportModalImagePlaceholder.style.display = 'block';
      exportModalImagePlaceholder.textContent = '加载中...';
      exportModalInfo.innerHTML = '加载中...';
      exportModalTable.querySelector('tbody').innerHTML = '<tr><td colspan="2" class="empty-row">加载中...</td></tr>';
      exportModal.classList.add('open');

      apiFetch(`/result/${encodeURIComponent(taskId)}`).then((result) => {
        if (!result) { fillExportModalFallback(taskId); return; }
        fillExportModal(taskId, result);
        cacheHistoryResult(taskId, result);
      }).catch(() => {
        fillExportModalFallback(taskId);
      });
    }
```

- [ ] **Step 3: Add `fillExportModal` function**

Insert before `openExportEngineeringCard`:

```js
    function fillExportModal(taskId, result) {
      const sourceName = result.source_name || result.pdf_name || taskId;
      const processFlow = result.process_flow || {};
      const rows = Array.isArray(processFlow.data) ? processFlow.data : [];
      const featureText = result.feature_report_text || result.expert_judgment || '';

      exportModalMeta.textContent = `任务ID：${taskId}  |  文件：${sourceName}`;

      // Info block
      let infoHtml = '';
      if (sourceName) infoHtml += `<div><span class="label">文件名称</span> <span class="value">${escapeHtml(sourceName)}</span></div>`;
      if (taskId) infoHtml += `<div><span class="label">任务ID</span> <span class="value">${escapeHtml(taskId)}</span></div>`;
      if (featureText) {
        const brief = String(featureText).length > 200 ? String(featureText).slice(0, 200) + '...' : featureText;
        infoHtml += `<div style="margin-top:6px;font-size:12px;line-height:1.6;white-space:pre-wrap;">${escapeHtml(brief)}</div>`;
      }
      exportModalInfo.innerHTML = infoHtml || '暂无信息';

      // Image from creo_views
      const imageUrl = `${API_BASE}/result/${encodeURIComponent(taskId)}/asset/creo_views/${encodeURIComponent('全部默认.jpg')}`;
      exportModalImage.src = imageUrl;
      exportModalImage.style.display = 'block';
      exportModalImagePlaceholder.style.display = 'none';
      exportModalImage.onerror = function() {
        exportModalImage.style.display = 'none';
        exportModalImagePlaceholder.style.display = 'block';
        exportModalImagePlaceholder.textContent = '未找到 creo_views/全部默认.jpg';
      };

      // Process table
      renderExportTable(rows);
    }
```

- [ ] **Step 4: Add `fillExportModalFallback` function**

```js
    function fillExportModalFallback(taskId) {
      exportModalMeta.textContent = `任务ID：${taskId}`;
      exportModalInfo.innerHTML = '<div><span class="label">任务ID</span> <span class="value">' + escapeHtml(taskId) + '</span></div>';
      exportModalImage.style.display = 'none';
      exportModalImagePlaceholder.style.display = 'block';
      exportModalImagePlaceholder.textContent = '无法加载图片';
      renderExportTable([]);
    }
```

- [ ] **Step 5: Add `renderExportTable` function**

```js
    function renderExportTable(rows) {
      const tbody = exportModalTable.querySelector('tbody');
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="2" class="empty-row">暂无工艺数据</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function(r) {
        const code = Array.isArray(r) ? String(r[0] || '').trim() : '';
        const content = Array.isArray(r) ? String(r[1] || '').trim() : String(r || '');
        return '<tr>' +
          '<td class="step-code">' + escapeHtml(code) + '</td>' +
          '<td class="step-content">' + escapeHtml(content) + '</td>' +
        '</tr>';
      }).join('');
    }
```

- [ ] **Step 6: Add `closeExportModal` function**

```js
    function closeExportModal() {
      exportModal.classList.remove('open');
      exportModalImage.removeAttribute('src');
    }
```

- [ ] **Step 7: Wire up event listeners**

Add near the other event listener registrations (e.g., near line 4163 where the click delegation for `openExportCardBtn` is):

```js
    if (exportModalCloseBtn) exportModalCloseBtn.addEventListener('click', closeExportModal);
    if (exportCancelBtn) exportCancelBtn.addEventListener('click', closeExportModal);
    if (exportModal) exportModal.addEventListener('click', function(e) { if (e.target === exportModal) closeExportModal(); });
    if (exportPdfBtn) exportPdfBtn.addEventListener('click', function() {
      const taskId = currentExportTaskId();
      if (taskId) window.open(API_BASE + '/export/' + encodeURIComponent(taskId) + '?format=pdf', '_blank');
    });
    if (exportExcelBtn) exportExcelBtn.addEventListener('click', function() {
      const taskId = currentExportTaskId();
      if (taskId) window.open(API_BASE + '/export/' + encodeURIComponent(taskId) + '?format=xlsx', '_blank');
    });
```

- [ ] **Step 8: Commit**

```bash
git add updated_front/js/demo-industrial-console.js
git commit -m "feat: wire export modal with backend data and creo_views image"
```

---

### Task 4: Remove standalone export-file-modal.html reference

**Files:**
- Modify: `backend/app.py` — remove the dev route `/dev/export-modal`
- Remove/Document: `updated_front/export-file-modal.html` — no longer integrated

- [ ] **Step 1: Remove dev route from app.py**

Delete lines 67-72 in `backend/app.py`:
```python
@app.route("/dev/export-modal")
def dev_export_modal():
    """Serve the export modal through Flask for live debugging."""
    template_path = os.path.join(BASE_DIR, "updated_front", "export-file-modal.html")
    ...
        return Response("export-file-modal.html not found", status=404, mimetype="text/plain")
```

- [ ] **Step 2: Remove standalone modal file**

```bash
git rm updated_front/export-file-modal.html
```

- [ ] **Step 3: Commit**

```bash
git add backend/app.py updated_front/export-file-modal.html
git commit -m "chore: remove standalone export modal, now embedded in main page"
```

---

### Task 5: Verify end-to-end

- [ ] **Step 1: Start Flask dev server**

```bash
python backend/app.py
```
Expected: Server starts on localhost:5000, no import errors.

- [ ] **Step 2: Open main page in browser**

Navigate to `http://localhost:5000` and verify:
- Page loads with correct CSS styling
- "导出工艺文件" button is in the process generation tab toolbar

- [ ] **Step 3: Complete a process generation task**

Upload a PRT file, wait for processing to complete. The "导出工艺文件" button should become enabled.

- [ ] **Step 4: Open export modal and verify**

Click "导出工艺文件":
- Modal opens with dark overlay and blur
- Meta line shows task ID and file name
- Image loads from `creo_views/全部默认.jpg`
- Process table shows rows from `process_flow.data`
- Info block shows file name, task ID, feature text

- [ ] **Step 5: Test export download buttons**

- Click "下载 PDF" → browser opens/downloads PDF file
- Click "下载 Excel" → browser opens/downloads Excel file
- Click "取消" or "×" or backdrop → modal closes

- [ ] **Step 6: Commit**

```bash
git commit -m "chore: final integration verification of export modal"
```
