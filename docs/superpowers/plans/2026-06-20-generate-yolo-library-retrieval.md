# Generate YOLO Review and Library Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Generate page review order and YOLO skip flow, make process-page library commits vector-searchable immediately after save, and show drawing thumbnails in database record cards.

**Architecture:** Keep the existing task state machine and annotation finalize endpoint. The frontend only changes tab rendering order, annotation-page button state, and commit draft fields; the backend centralizes searchable text fallback inside `backend/api/library.py` and performs a non-blocking retrieval self-check after commit.

**Tech Stack:** React 18 + TypeScript + Vite, Playwright, Flask, SQLite, pytest, GitNexus.

## Global Constraints

- Do not refactor the backend task state machine.
- Do not add a new YOLO annotation format.
- Do not change the process generation algorithm.
- Do not require all pre-existing backend failures to be fixed in this change.
- Do not add a frontend capability status panel.
- Node engine is `>=20 <21`; npm engine is `>=10`.
- Before editing any symbol, run `node .gitnexus/run.cjs impact <symbol> --direction upstream` and report direct callers, affected processes, and risk.
- Before committing, run `node .gitnexus/run.cjs detect-changes --scope compare --base-ref main`.

---

## Spec Review

The spec is implementable as written. It correctly avoids state-machine changes and reuses `finalizeAnnotation(taskId)` for both “skip YOLO review” and “finish annotation” continuation.

One implementation detail to preserve: `query_by_vector_similarity()` returns result prefixes as `drawing_id`, not `prefix`, so the retrieval self-check must compare `match["drawing_id"]` to the saved `prefix`.

## GitNexus Pre-Edit Impact Summary

These checks were run after refreshing the stale index with `node .gitnexus/run.cjs analyze`.

| Symbol | Direct callers | Affected processes | Risk |
| --- | ---: | ---: | --- |
| `GeneratePage` | 1 (`App`) | 1 (`App`) | LOW |
| `ProcessPanel` | 1 (`GeneratePage`) | 1 (`App`) | LOW |
| `_upsert_record` | 1 (`commit_library_record`) | 1 (`commit_library_record`) | LOW |
| `DbPage` | 1 (`App`) | 1 (`App`) | LOW |

No HIGH or CRITICAL risk was reported.

## Files

- Modify: `frontend-react/src/api/client.ts`
  - Add `source_text`, `vector_text`, `RetrievalCheck`, and the full `/library/commit` response type.
- Modify: `frontend-react/src/components/generate/ProcessPanel.tsx`
  - Populate `source_text` and `vector_text` from confirmed feature text.
  - Forward the commit response to the page-level success toast.
- Modify: `frontend-react/src/components/generate/CommitToLibraryModal.tsx`
  - Display the retrieval self-check result after commit.
  - Keep the modal open when the retrieval check fails or is skipped so the user can read the status.
- Modify: `frontend-react/src/pages/GeneratePage.tsx`
  - Render tabs as `YOLO审阅 → 特征审阅 → 工艺规程`.
  - Change annotation buttons to `开始标注 / 跳过 YOLO 审阅` before visiting the annotation overlay and `继续标注 / 完成标注 → 下一步` after visiting.
- Modify: `frontend-react/src/pages/DbPage.tsx`
  - Add list-card thumbnail preview and a reusable placeholder.
  - Open the existing snapshot modal when thumbnail is clicked.
- Modify: `backend/api/library.py`
  - Import `query_by_vector_similarity`.
  - Add centralized searchable text normalization.
  - Use the same text for vector, `context`, `key_features_text`, and `vector_content` fallback.
  - Return `retrieval_check` from `/api/library/commit`.
- Modify: `backend/test_library_storage_init.py`
  - Add backend tests for vector fallback and retrieval check behavior.
- Modify: `frontend-react/tests/upload-flow.spec.ts`
  - Update YOLO button-flow assertions and tab order assertions.
- Create: `frontend-react/tests/db-preview.spec.ts`
  - Add thumbnail/snapshot modal coverage using mocked API responses.

---

### Task 1: Backend commit uses searchable feature text and returns retrieval check

**Files:**
- Modify: `backend/api/library.py`
- Test: `backend/test_library_storage_init.py`

**Interfaces:**
- Consumes: `query_by_vector_similarity(text: str, top_k: int, min_similarity: float, library_key: str | None) -> list[dict]`
- Produces:
  - `_normalise_searchable_text(draft: dict) -> tuple[str, str]`
  - `_build_retrieval_check(prefix: str, vector_text: str, library_key: str) -> dict`
  - `/api/library/commit` response includes `retrieval_check`

- [ ] **Step 1: Run impact for backend symbols**

Run:

```bash
node .gitnexus/run.cjs impact _upsert_record --direction upstream
node .gitnexus/run.cjs impact commit_library_record --direction upstream
```

Expected:

```text
risk: LOW
direct caller of _upsert_record: commit_library_record
affected process: commit_library_record
```

- [ ] **Step 2: Write failing backend tests**

Append this code to `backend/test_library_storage_init.py`:

```python
def test_upsert_record_uses_feature_report_text_as_vector_fallback(monkeypatch, tmp_path):
    db_path = _use_temp_database(monkeypatch, tmp_path)
    library_scope.initialize_library_storage()

    calls = []

    class FakeVector:
        def tobytes(self):
            return b"vector-bytes"

    def fake_create_query_vector(text):
        calls.append(text)
        return FakeVector()

    monkeypatch.setattr(library_api, "create_query_vector", fake_create_query_vector)
    monkeypatch.setattr(library_api, "extract_structured_features", lambda text: {})

    draft = {
        "prefix": "D125A-181200A003",
        "content": "0010\t车\t车外圆",
        "process_summary": "0010 车 车外圆",
        "feature_report_text": "【零件名称】D125A-181200A003\n【技术要求】调质处理",
        "process_list": [{"code": "0010", "trade": "车", "content": "车外圆"}],
    }

    library_api._upsert_record(draft, replace=True, library_key="")

    assert calls == ["【零件名称】D125A-181200A003\n【技术要求】调质处理"]
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT context, key_features, vector_content, feature_report_text, vector FROM vectors_v2 WHERE prefix = ?",
            ("D125A-181200A003",),
        ).fetchone()

    assert row[0] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[1] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[2] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[3] == "【零件名称】D125A-181200A003\n【技术要求】调质处理"
    assert row[4] == b"vector-bytes"


def test_retrieval_check_skips_without_embedding_key(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="【零件名称】D125A-181200A003",
        library_key="",
    )

    assert result == {
        "status": "skipped",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "EMBEDDING_API_KEY not configured",
    }


def test_retrieval_check_reports_matching_saved_prefix(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "fake-key")

    def fake_query(text, top_k, min_similarity, library_key):
        assert text == "【零件名称】D125A-181200A003"
        assert top_k == 5
        assert min_similarity == 0.0
        assert library_key == "private_demo"
        return [
            {"drawing_id": "OTHER", "similarity": 0.51},
            {"drawing_id": "D125A-181200A003", "similarity": 0.83},
        ]

    monkeypatch.setattr(library_api, "query_by_vector_similarity", fake_query)

    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="【零件名称】D125A-181200A003",
        library_key="private_demo",
    )

    assert result == {
        "status": "ok",
        "searchable": True,
        "matched_prefix": "D125A-181200A003",
        "similarity": 0.83,
        "reason": "",
    }


def test_retrieval_check_reports_no_match(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "fake-key")
    monkeypatch.setattr(
        library_api,
        "query_by_vector_similarity",
        lambda text, top_k, min_similarity, library_key: [{"drawing_id": "OTHER", "similarity": 0.51}],
    )

    result = library_api._build_retrieval_check(
        prefix="D125A-181200A003",
        vector_text="【零件名称】D125A-181200A003",
        library_key="",
    )

    assert result == {
        "status": "failed",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "saved prefix not returned by retrieval self-check",
    }
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest backend/test_library_storage_init.py -q
```

Expected:

```text
FAILED backend/test_library_storage_init.py::test_upsert_record_uses_feature_report_text_as_vector_fallback
FAILED backend/test_library_storage_init.py::test_retrieval_check_skips_without_embedding_key
FAILED backend/test_library_storage_init.py::test_retrieval_check_reports_matching_saved_prefix
FAILED backend/test_library_storage_init.py::test_retrieval_check_reports_no_match
```

- [ ] **Step 4: Import vector self-check function**

In `backend/api/library.py`, replace the `from ..vector_map_rag import (...)` block with:

```python
from ..vector_map_rag import (
    DB_PATH,
    create_query_vector,
    extract_all_features,
    extract_key_features_text,
    extract_structured_features,
    invalidate_index_cache,
    query_by_fused_text,
    query_by_vector_similarity,
)
```

- [ ] **Step 5: Add searchable text and retrieval-check helpers**

Insert this code immediately before `_upsert_record()` in `backend/api/library.py`:

```python
def _normalise_searchable_text(draft: dict) -> tuple[str, str]:
    """Return source_text and vector_text for storage and retrieval."""
    source_text = (
        draft.get("source_text")
        or draft.get("feature_report_text")
        or draft.get("context")
        or draft.get("key_features_text")
        or draft.get("vector_content")
        or ""
    )
    source_text = str(source_text or "").strip()
    vector_text = str(draft.get("vector_text") or source_text or "").strip()
    return source_text, vector_text


def _build_retrieval_check(prefix: str, vector_text: str, library_key: str = ""):
    normalized_prefix = str(prefix or "").strip().upper()
    text = str(vector_text or "").strip()
    if not text:
        return {
            "status": "skipped",
            "searchable": False,
            "matched_prefix": "",
            "similarity": 0,
            "reason": "vector_text is empty",
        }
    if not os.getenv("EMBEDDING_API_KEY", ""):
        return {
            "status": "skipped",
            "searchable": False,
            "matched_prefix": "",
            "similarity": 0,
            "reason": "EMBEDDING_API_KEY not configured",
        }

    try:
        matches = query_by_vector_similarity(
            text,
            top_k=5,
            min_similarity=0.0,
            library_key=library_key or None,
        )
    except Exception as exc:
        logger.warning("[Library] retrieval self-check failed prefix=%s: %s", normalized_prefix, exc)
        return {
            "status": "failed",
            "searchable": False,
            "matched_prefix": "",
            "similarity": 0,
            "reason": str(exc) or "retrieval self-check failed",
        }

    for match in matches or []:
        matched_prefix = str(match.get("drawing_id") or match.get("prefix") or "").strip().upper()
        if matched_prefix == normalized_prefix:
            return {
                "status": "ok",
                "searchable": True,
                "matched_prefix": normalized_prefix,
                "similarity": float(match.get("similarity") or 0),
                "reason": "",
            }

    return {
        "status": "failed",
        "searchable": False,
        "matched_prefix": "",
        "similarity": 0,
        "reason": "saved prefix not returned by retrieval self-check",
    }
```

- [ ] **Step 6: Replace searchable text handling in `_upsert_record()`**

In `_upsert_record()`, replace this block:

```python
    vector = create_query_vector(draft.get("vector_text") or draft.get("source_text") or "")
    vector_blob = vector.tobytes() if vector is not None else None
    prefix = draft["prefix"].strip().upper()
    process_list = draft.get("process_list", [])
    content = json.dumps(process_list, ensure_ascii=False)
    context = draft.get("context") or draft.get("source_text") or ""
    key_features_text = draft.get("key_features_text") or draft.get("vector_text") or draft.get("source_text") or ""
```

with:

```python
    source_text, vector_text = _normalise_searchable_text(draft)
    vector = create_query_vector(vector_text)
    vector_blob = vector.tobytes() if vector is not None else None
    prefix = draft["prefix"].strip().upper()
    process_list = draft.get("process_list", [])
    content = json.dumps(process_list, ensure_ascii=False)
    context = draft.get("context") or source_text
    key_features_text = draft.get("key_features_text") or vector_text or source_text
```

In the same function, replace:

```python
    feature_report_text = (draft.get("feature_report_text") or "").strip()
```

with:

```python
    feature_report_text = (draft.get("feature_report_text") or source_text).strip()
```

In the same function, replace:

```python
    vector_content = structured.get("vector_index", draft.get("vector_text") or key_features_text) if isinstance(structured, dict) else (draft.get("vector_text") or key_features_text)
```

with:

```python
    vector_content = structured.get("vector_index", vector_text or key_features_text) if isinstance(structured, dict) else (vector_text or key_features_text)
```

At the end of `_upsert_record()`, replace:

```python
    invalidate_index_cache()
```

with:

```python
    invalidate_index_cache(library_key or None)
    return {"prefix": prefix, "source_text": source_text, "vector_text": vector_text}
```

- [ ] **Step 7: Return `retrieval_check` from `/library/commit`**

In `commit_library_record()`, replace:

```python
    _upsert_record(draft, replace=replace, library_key=library_key)
    logger.info("[Library] commit finished prefix=%s replaced=%s", draft.get("prefix"), replace)

    fresh = _fetch_existing_record(draft["prefix"], library_key=library_key)
```

with:

```python
    saved_meta = _upsert_record(draft, replace=replace, library_key=library_key)
    retrieval_check = _build_retrieval_check(
        saved_meta["prefix"],
        saved_meta["vector_text"],
        library_key=library_key,
    )
    logger.info(
        "[Library] commit finished prefix=%s replaced=%s retrieval_status=%s",
        draft.get("prefix"),
        replace,
        retrieval_check.get("status"),
    )

    fresh = _fetch_existing_record(draft["prefix"], library_key=library_key)
```

Then add `"retrieval_check": retrieval_check,` to the response object:

```python
        {
            "message": "Library record saved",
            "draft": draft,
            "existing": existing,
            "saved": fresh,
            "replaced": bool(existing) and replace,
            "active_scope": _scope_from_key(library_key),
            "retrieval_check": retrieval_check,
        }
```

- [ ] **Step 8: Run backend tests**

Run:

```bash
uv run pytest backend/test_library_storage_init.py -q
```

Expected:

```text
7 passed
```

- [ ] **Step 9: Commit backend retrieval changes**

Run:

```bash
git add backend/api/library.py backend/test_library_storage_init.py
git commit -m "fix: make library commits vector searchable"
```

---

### Task 2: Frontend commit draft sends `source_text` and `vector_text`

**Files:**
- Modify: `frontend-react/src/api/client.ts`
- Modify: `frontend-react/src/components/generate/ProcessPanel.tsx`
- Modify: `frontend-react/src/components/generate/CommitToLibraryModal.tsx`

**Interfaces:**
- Consumes: backend `/api/library/commit` response `retrieval_check`
- Produces:
  - `CommitDraft.source_text: string`
  - `CommitDraft.vector_text: string`
  - `CommitLibraryResponse.retrieval_check`
  - `CommitToLibraryModal.onSuccess(message: string): void`

- [ ] **Step 1: Run impact for frontend commit symbols**

Run:

```bash
node .gitnexus/run.cjs impact ProcessPanel --direction upstream
node .gitnexus/run.cjs impact CommitToLibraryModal --direction upstream
```

Expected:

```text
risk: LOW
direct caller of ProcessPanel: GeneratePage
direct caller of CommitToLibraryModal: ProcessPanel
```

- [ ] **Step 2: Update API types**

In `frontend-react/src/api/client.ts`, replace the `CommitDraft` interface and `commitToLibrary()` return type with:

```ts
export interface CommitDraft {
  prefix: string
  content: string
  process_summary: string
  feature_report_text: string
  source_text: string
  vector_text: string
  preview_image_urls: string[]
  source_type: string
  source_task_id: string
  process_list: { code: string; trade: string; content: string }[]
  tech_requirement: string
  product_type: string
}

export interface RetrievalCheck {
  status: 'ok' | 'failed' | 'skipped'
  searchable: boolean
  matched_prefix: string
  similarity: number
  reason: string
}

export interface CommitLibraryResponse {
  message: string
  record_id?: number
  retrieval_check?: RetrievalCheck
}

export async function commitToLibrary(params: {
  draft: CommitDraft
  action: 'replace' | 'keep'
  library_key: string
}): Promise<CommitLibraryResponse> {
  return request<CommitLibraryResponse>('/library/commit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}
```

- [ ] **Step 3: Update `ProcessPanel` props and draft**

In `frontend-react/src/components/generate/ProcessPanel.tsx`, replace the props interface and function signature with:

```ts
interface Props {
  result: TaskResult | null
  taskId: string | null
  runToken: number
  streamingChunks: string
  reviewText?: string
  onTypewriterComplete?: (rowCount: number) => void
  onRowsChange?: (rows: ProcessRow[]) => void
  onTypewriterProgress?: (info: TypewriterProgress) => void
  onCommitSuccess?: (message: string) => void
}

export function ProcessPanel({ result, taskId, runToken, streamingChunks, reviewText, onTypewriterComplete, onRowsChange, onTypewriterProgress, onCommitSuccess }: Props) {
```

Inside the `commitDraft` `useMemo()`, replace:

```ts
    const featureText = reviewText || result?.feature_report_text || ''
    const featSrc = featureText
```

with:

```ts
    const featureText = reviewText || result?.feature_report_text || result?.feature_report || ''
    const searchableFeatureText = featureText.trim()
    const featSrc = searchableFeatureText
```

In the returned draft object, replace:

```ts
      feature_report_text: featureText,
      preview_image_urls: result?.preview_image_urls || result?.preview_images || [],
```

with:

```ts
      feature_report_text: featureText,
      source_text: searchableFeatureText,
      vector_text: searchableFeatureText,
      preview_image_urls: result?.preview_image_urls || result?.preview_images || [],
```

Replace the modal render block at the bottom with:

```tsx
      {showCommitModal && (
        <CommitToLibraryModal
          draft={commitDraft}
          onClose={() => setShowCommitModal(false)}
          onSuccess={(message) => {
            onCommitSuccess?.(message)
            setShowCommitModal(false)
          }}
        />
      )}
```

- [ ] **Step 4: Pass page toast callback from `GeneratePage`**

In `frontend-react/src/pages/GeneratePage.tsx`, update the `ProcessPanel` usage by adding `onCommitSuccess={onSuccess}`:

```tsx
                  <ProcessPanel
                    result={result}
                    taskId={taskId}
                    runToken={runToken}
                    streamingChunks={streamingChunks}
                    reviewText={reviewText}
                    onTypewriterComplete={(rowCount) => {
                      setProgress(100)
                      setPhaseHint(`工艺生成完成，共 ${rowCount} 道工序`)
                    }}
                    onTypewriterProgress={handleTypewriterProgress}
                    onRowsChange={setEditedRows}
                    onCommitSuccess={onSuccess}
                  />
```

- [ ] **Step 5: Show retrieval check result in commit modal**

In `frontend-react/src/components/generate/CommitToLibraryModal.tsx`, replace the import with:

```ts
import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { getLibraryScopes, commitToLibrary, type LibraryScope, type CommitDraft, type RetrievalCheck } from '../../api/client'
```

Replace the `Props` interface with:

```ts
interface Props {
  draft: CommitDraft
  onClose: () => void
  onSuccess: (message: string) => void
}
```

After the existing `error` state, add:

```ts
  const [retrievalCheck, setRetrievalCheck] = useState<RetrievalCheck | null>(null)
```

Replace `handleCommit` with:

```ts
  const handleCommit = async () => {
    if (!selectedKey) return
    setCommitting(true)
    setError(null)
    setRetrievalCheck(null)
    try {
      const response = await commitToLibrary({ draft, action: 'replace', library_key: selectedKey })
      const check = response.retrieval_check || null
      setRetrievalCheck(check)
      if (!check || check.status === 'ok') {
        onSuccess(check ? `入库成功，检索自测通过，相似度 ${check.similarity.toFixed(2)}` : '入库成功')
        onClose()
        return
      }
      if (check.status === 'skipped') {
        setError(`入库成功，检索自测跳过：${check.reason}`)
        return
      }
      setError(`入库成功，检索自测失败：${check.reason}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '入库失败')
    } finally {
      setCommitting(false)
    }
  }
```

In the modal body, immediately after the error rendering branch and before the scopes list branch, add this rendering block:

```tsx
          ) : retrievalCheck ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left">
              <div className="text-[13px] font-bold text-amber-700">
                {retrievalCheck.status === 'skipped' ? '入库成功，检索自测已跳过' : '入库成功，检索自测未命中'}
              </div>
              <div className="text-[12px] text-amber-700 mt-1">
                {retrievalCheck.reason || '请检查向量服务配置后重新检索。'}
              </div>
              <button className="btn btn-secondary !text-[12px] !mt-3" onClick={onClose}>关闭</button>
            </div>
```

This changes the body conditional from:

```tsx
          ) : scopes.length === 0 ? (
```

to:

```tsx
          ) : retrievalCheck ? (
            ...
          ) : scopes.length === 0 ? (
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
npm --prefix frontend-react run build
```

Expected:

```text
✓ built in ...
```

- [ ] **Step 7: Commit frontend commit-draft changes**

Run:

```bash
git add frontend-react/src/api/client.ts frontend-react/src/components/generate/ProcessPanel.tsx frontend-react/src/components/generate/CommitToLibraryModal.tsx frontend-react/src/pages/GeneratePage.tsx
git commit -m "fix: send searchable text when committing process records"
```

---

### Task 3: Generate page YOLO tab order and skip button state

**Files:**
- Modify: `frontend-react/src/pages/GeneratePage.tsx`
- Modify: `frontend-react/tests/upload-flow.spec.ts`

**Interfaces:**
- Consumes: existing `finalizeAnnotation(taskId)` API
- Produces:
  - Initial annotation actions: `开始标注`, `跳过 YOLO 审阅`
  - After annotation overlay visit: `继续标注`, `完成标注 → 下一步`

- [ ] **Step 1: Run impact for `GeneratePage`**

Run:

```bash
node .gitnexus/run.cjs impact GeneratePage --direction upstream
```

Expected:

```text
risk: LOW
direct caller: App
affected process: App
```

- [ ] **Step 2: Update Playwright expectations**

In `frontend-react/tests/upload-flow.spec.ts`, replace the helper comment and finalize click in `goToReviewState()`:

```ts
  // Now "完成标注 → 继续" is enabled (annotateVisited = true)
  await page.locator('button:has-text("完成标注")').click()
```

with:

```ts
  // Now "完成标注 → 下一步" is enabled (annotateVisited = true)
  await page.locator('button:has-text("完成标注 → 下一步")').click()
```

Replace the test `上传后 SSE 推送 annotation_required → 显示 YOLO 标注界面` with:

```ts
  test('上传后 SSE 推送 annotation_required → 显示 YOLO 标注界面和跳过入口', async ({ page }) => {
    await uploadAndWaitAnnotation(page)
    await expect(page.locator('button:has-text("开始标注")')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('button:has-text("跳过 YOLO 审阅")')).toBeVisible()
    await expect(page.locator('button:has-text("完成标注")')).not.toBeVisible()
  })
```

Replace the test `YOLO 标注界面：开始标注 → 退出 → 完成标注 → 自动跳转特征审阅` with:

```ts
  test('YOLO 标注界面：开始标注 → 退出 → 完成标注 → 自动跳转特征审阅', async ({ page }) => {
    await uploadAndWaitAnnotation(page)

    await expect(page.locator('button:has-text("跳过 YOLO 审阅")')).toBeVisible()
    await expect(page.locator('button:has-text("完成标注")')).not.toBeVisible()

    await page.locator('button:has-text("开始标注")').click()
    await expect(page.locator('.fixed.inset-0')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('text=标注工具')).toBeVisible()

    await page.locator('button:has-text("退出标注")').click()
    await expect(page.locator('.fixed.inset-0')).not.toBeVisible({ timeout: 5000 })

    await expect(page.locator('button:has-text("继续标注")')).toBeVisible()
    const finalizeBtn = page.locator('button:has-text("完成标注 → 下一步")')
    await expect(finalizeBtn).toBeEnabled({ timeout: 3000 })
    await expect(page.locator('button:has-text("跳过 YOLO 审阅")')).not.toBeVisible()

    await finalizeBtn.click()

    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    await expect(reviewTab).toHaveClass(/text-orange/, { timeout: 5000 })
  })
```

Add this test after it:

```ts
  test('YOLO 标注界面：可直接跳过 YOLO 审阅进入特征审阅', async ({ page }) => {
    await uploadAndWaitAnnotation(page)

    await page.locator('button:has-text("跳过 YOLO 审阅")').click()

    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    await expect(reviewTab).toHaveClass(/text-orange/, { timeout: 5000 })
  })
```

Replace the `Tab 切换：YOLO ↔ 审阅 ↔ 工艺规程` test with:

```ts
  test('Tab 顺序：YOLO审阅 → 特征审阅 → 工艺规程', async ({ page }) => {
    await uploadAndWaitAnnotation(page)

    const tabs = page.locator('button').filter({ hasText: /YOLO审阅|特征审阅|工艺规程/ })
    await expect(tabs.nth(0)).toHaveText('YOLO审阅')
    await expect(tabs.nth(1)).toHaveText('特征审阅')
    await expect(tabs.nth(2)).toHaveText('工艺规程')

    const yoloTab = page.locator('button', { hasText: 'YOLO审阅' }).first()
    const reviewTab = page.locator('button', { hasText: '特征审阅' }).first()
    const processTab = page.locator('button', { hasText: '工艺规程' }).first()

    await expect(yoloTab).toHaveClass(/text-orange/)

    await reviewTab.click()
    await expect(reviewTab).toHaveClass(/text-orange/)

    await processTab.click()
    await expect(processTab).toHaveClass(/text-orange/)

    await yoloTab.click()
    await expect(yoloTab).toHaveClass(/text-orange/)
  })
```

- [ ] **Step 3: Run frontend flow test to verify failure**

Run:

```bash
cd frontend-react
npx playwright test tests/upload-flow.spec.ts --grep "YOLO|Tab"
```

Expected:

```text
failed
```

- [ ] **Step 4: Change tab rendering order**

In `frontend-react/src/pages/GeneratePage.tsx`, replace the current tab bar button rendering block:

```tsx
          {([
            { id: 'review' as ActiveTab, label: '特征审阅' },
            { id: 'process' as ActiveTab, label: '工艺规程' },
          ]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-2.5 text-[12px] font-semibold transition-all duration-200 border-b-2
                ${activeTab === tab.id
                  ? 'text-orange-600 border-orange-500'
                  : 'text-slate-400 border-transparent hover:text-slate-600'}
              `}
            >
              {tab.label}
            </button>
          ))}
          {showAnnotationTab && (
            <button
              onClick={() => setActiveTab('annotation')}
              className={`px-4 py-2.5 text-[12px] font-semibold transition-all duration-200 border-b-2 ${
                activeTab === 'annotation'
                  ? 'text-orange-600 border-orange-500'
                  : 'text-slate-400 border-transparent hover:text-slate-600'
              }`}
            >
              YOLO审阅
            </button>
          )}
```

with:

```tsx
          {([
            ...(showAnnotationTab ? [{ id: 'annotation' as ActiveTab, label: 'YOLO审阅' }] : []),
            { id: 'review' as ActiveTab, label: '特征审阅' },
            { id: 'process' as ActiveTab, label: '工艺规程' },
          ]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-2.5 text-[12px] font-semibold transition-all duration-200 border-b-2
                ${activeTab === tab.id
                  ? 'text-orange-600 border-orange-500'
                  : 'text-slate-400 border-transparent hover:text-slate-600'}
              `}
            >
              {tab.label}
            </button>
          ))}
```

- [ ] **Step 5: Change annotation button state**

In `frontend-react/src/pages/GeneratePage.tsx`, replace the annotation action block:

```tsx
                    <div className="flex items-center gap-3 mt-2">
                      <button className="btn btn-primary !text-[12px]" onClick={handleOpenAnnotate}>
                        开始标注
                      </button>
                      <button
                        className="btn btn-secondary !text-[12px]"
                        disabled={!annotateVisited}
                        onClick={handleFinalizeAnnotation}
                        title={!annotateVisited ? '请先完成标注' : ''}
                      >
                        完成标注 → 继续
                      </button>
                    </div>
                    {!annotateVisited && (
                      <p className="text-[10px] text-slate-300">需先完成至少一次标注后才能继续</p>
                    )}
```

with:

```tsx
                    <div className="flex items-center gap-3 mt-2">
                      <button className="btn btn-primary !text-[12px]" onClick={handleOpenAnnotate}>
                        {annotateVisited ? '继续标注' : '开始标注'}
                      </button>
                      <button
                        className={`btn !text-[12px] ${annotateVisited ? 'btn-secondary' : 'btn-ghost'}`}
                        disabled={!taskId}
                        onClick={handleFinalizeAnnotation}
                        title={!taskId ? '任务 ID 缺失，无法继续' : ''}
                      >
                        {annotateVisited ? '完成标注 → 下一步' : '跳过 YOLO 审阅'}
                      </button>
                    </div>
                    {!annotateVisited && (
                      <p className="text-[10px] text-slate-300">可先审阅预标注；也可跳过，直接使用当前 YOLO 预标注继续。</p>
                    )}
```

- [ ] **Step 6: Run focused Playwright tests**

Run:

```bash
cd frontend-react
npx playwright test tests/upload-flow.spec.ts --grep "YOLO|Tab"
```

Expected:

```text
passed
```

- [ ] **Step 7: Run frontend build**

Run:

```bash
npm --prefix frontend-react run build
```

Expected:

```text
✓ built in ...
```

- [ ] **Step 8: Commit YOLO UI changes**

Run:

```bash
git add frontend-react/src/pages/GeneratePage.tsx frontend-react/tests/upload-flow.spec.ts
git commit -m "fix: reorder yolo review flow"
```

---

### Task 4: Database list thumbnail preview

**Files:**
- Modify: `frontend-react/src/pages/DbPage.tsx`
- Create: `frontend-react/tests/db-preview.spec.ts`

**Interfaces:**
- Consumes: `LibraryRecord.preview_image_urls`, `LibraryRecord.preview_task_id`, `getAssetUrl()`, existing `handleViewSnapshot(record)`
- Produces: thumbnail button in each list card; placeholder for records without preview images

- [ ] **Step 1: Run impact for `DbPage`**

Run:

```bash
node .gitnexus/run.cjs impact DbPage --direction upstream
```

Expected:

```text
risk: LOW
direct caller: App
affected process: App
```

- [ ] **Step 2: Add mocked Playwright test**

Create `frontend-react/tests/db-preview.spec.ts` with:

```ts
import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/library/scopes', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{ library_key: 'public', library_name: '公共工艺库', scope_type: 'public', record_count: 2 }],
        can_browse_db: true,
        active_scope: 'public',
      }),
    })
  })

  await page.route('**/api/library/records?**', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 1,
            prefix: 'D125A-181200A003',
            product_type: '轴类',
            process_summary: '0010 车 车外圆',
            context: '',
            tech_requirement: '',
            created_at: '2026-06-20T00:00:00',
            process_count: 1,
            content: '[]',
            process_list: [{ code: '0010', trade: '车', content: '车外圆' }],
            trades: ['车'],
            source_type: 'web_upload',
            source_task_id: 'task-1',
            preview_task_id: 'task-1',
            preview_total_pages: 1,
            preview_image_urls: ['/api/result/task-1/asset/page-1.png'],
            feature_report_text: '【零件名称】D125A-181200A003',
            feature_report_path: '',
            feature_report_json: {},
            real: 1,
          },
          {
            id: 2,
            prefix: 'NO-PREVIEW',
            product_type: '未知',
            process_summary: '',
            context: '',
            tech_requirement: '',
            created_at: '2026-06-20T00:00:00',
            process_count: 0,
            content: '[]',
            process_list: [],
            trades: [],
            source_type: 'web_upload',
            source_task_id: '',
            preview_task_id: '',
            preview_total_pages: 0,
            preview_image_urls: [],
            feature_report_text: '',
            feature_report_path: '',
            feature_report_json: {},
            real: 1,
          },
        ],
        page: 1,
        page_size: 3,
        total: 2,
        total_pages: 1,
        product_types: ['轴类'],
        active_scope: { library_key: 'public', library_name: '公共工艺库', scope_type: 'public' },
      }),
    })
  })

  await page.route('**/api/library/records/1?**', async route => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        prefix: 'D125A-181200A003',
        product_type: '轴类',
        process_summary: '0010 车 车外圆',
        context: '',
        tech_requirement: '',
        created_at: '2026-06-20T00:00:00',
        process_count: 1,
        content: '[]',
        process_list: [{ code: '0010', trade: '车', content: '车外圆' }],
        trades: ['车'],
        source_type: 'web_upload',
        source_task_id: 'task-1',
        preview_task_id: 'task-1',
        preview_total_pages: 1,
        preview_image_urls: ['/api/result/task-1/asset/page-1.png'],
        feature_report_text: '【零件名称】D125A-181200A003',
        feature_report_path: '',
        feature_report_json: {},
        real: 1,
      }),
    })
  })
})

test('database list shows thumbnail and opens snapshot modal', async ({ page }) => {
  await page.goto('/')
  await page.locator('button:has-text("数据库")').click()

  const thumbnail = page.locator('button[aria-label="查看 D125A-181200A003 图纸快照"]')
  await expect(thumbnail).toBeVisible()
  await expect(thumbnail.locator('img')).toHaveAttribute('src', '/api/result/task-1/asset/page-1.png')

  await thumbnail.click()

  await expect(page.locator('text=库记录快照')).toBeVisible()
  await expect(page.locator('img[alt="快照"]')).toHaveAttribute('src', '/api/result/task-1/asset/page-1.png')
})

test('database list shows placeholder when preview images are missing', async ({ page }) => {
  await page.goto('/')
  await page.locator('button:has-text("数据库")').click()

  const placeholder = page.locator('button[aria-label="NO-PREVIEW 暂无图纸快照"]')
  await expect(placeholder).toBeVisible()
  await expect(placeholder.locator('text=暂无预览')).toBeVisible()
})
```

- [ ] **Step 3: Run mocked test to verify failure**

Run:

```bash
cd frontend-react
npx playwright test tests/db-preview.spec.ts
```

Expected:

```text
failed
```

- [ ] **Step 4: Add thumbnail helpers in `DbPage`**

In `frontend-react/src/pages/DbPage.tsx`, after `handleViewSnapshot`, add:

```tsx
  const getPreviewUrls = (record: LibraryRecord) => {
    const taskId = record.preview_task_id || record.source_task_id
    return normalizeAssetUrls(record.preview_image_urls, taskId, getAssetUrl)
  }

  const renderPreviewThumb = (record: LibraryRecord) => {
    const urls = getPreviewUrls(record)
    const firstUrl = urls[0]
    if (!firstUrl) {
      return (
        <button
          type="button"
          aria-label={`${record.prefix || '记录'} 暂无图纸快照`}
          className="w-20 h-20 shrink-0 rounded-xl border border-dashed border-slate-200 bg-slate-50 text-slate-300 flex flex-col items-center justify-center cursor-default"
          onClick={e => e.stopPropagation()}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M8 12h8" />
            <path d="M12 8v8" />
          </svg>
          <span className="text-[10px] mt-1">暂无预览</span>
        </button>
      )
    }
    return (
      <button
        type="button"
        aria-label={`查看 ${record.prefix || '记录'} 图纸快照`}
        className="w-20 h-20 shrink-0 rounded-xl border border-slate-200 bg-slate-50 overflow-hidden group/thumb"
        onClick={e => {
          e.stopPropagation()
          handleSelectRecord(record)
          handleViewSnapshot(record)
        }}
      >
        <img
          src={firstUrl}
          alt={`${record.prefix || '记录'} 图纸缩略图`}
          className="w-full h-full object-cover transition-transform duration-200 group-hover/thumb:scale-105"
          onError={e => {
            const img = e.currentTarget
            img.style.display = 'none'
            const parent = img.parentElement
            if (parent) parent.setAttribute('aria-label', `${record.prefix || '记录'} 暂无图纸快照`)
          }}
        />
      </button>
    )
  }
```

- [ ] **Step 5: Insert thumbnail into record cards**

In `frontend-react/src/pages/DbPage.tsx`, inside the `records.map()` card, replace the card body content:

```tsx
                    <div className="flex items-start justify-between mb-1.5">
                      <div className="min-w-0 flex items-center gap-2">
                        <div className="text-[14px] font-bold text-slate-800 truncate" dangerouslySetInnerHTML={{ __html: highlightText(r.prefix || '未命名', query) }} />
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${st.cls}`}>{st.label}</span>
                      </div>
                      <span className="chip shrink-0 ml-2 !text-[10px]">{r.process_count || 0} 工序</span>
                    </div>
                    <div className="text-[11px] text-slate-500 mb-1.5">
                      <span dangerouslySetInnerHTML={{ __html: highlightText(r.product_type || '未分类', query) }} />
                      {' · '}
                      <span>{src}</span>
                      {' · '}
                      <span>工序 {r.process_count || 0} 条</span>
                    </div>
                    {r.process_summary && (
                      <div className="text-[12px] text-slate-500 line-clamp-2 leading-relaxed mb-1.5" dangerouslySetInnerHTML={{ __html: highlightText(r.process_summary, query) }} />
                    )}
                    <div className="flex gap-1.5 flex-wrap">
                      {r.trades?.slice(0, 3).map(t => (
                        <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100">{t}</span>
                      ))}
                    </div>
```

with:

```tsx
                    <div className="flex items-start gap-3">
                      {renderPreviewThumb(r)}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between mb-1.5">
                          <div className="min-w-0 flex items-center gap-2">
                            <div className="text-[14px] font-bold text-slate-800 truncate" dangerouslySetInnerHTML={{ __html: highlightText(r.prefix || '未命名', query) }} />
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${st.cls}`}>{st.label}</span>
                          </div>
                          <span className="chip shrink-0 ml-2 !text-[10px]">{r.process_count || 0} 工序</span>
                        </div>
                        <div className="text-[11px] text-slate-500 mb-1.5">
                          <span dangerouslySetInnerHTML={{ __html: highlightText(r.product_type || '未分类', query) }} />
                          {' · '}
                          <span>{src}</span>
                          {' · '}
                          <span>工序 {r.process_count || 0} 条</span>
                        </div>
                        {r.process_summary && (
                          <div className="text-[12px] text-slate-500 line-clamp-2 leading-relaxed mb-1.5" dangerouslySetInnerHTML={{ __html: highlightText(r.process_summary, query) }} />
                        )}
                        <div className="flex gap-1.5 flex-wrap">
                          {r.trades?.slice(0, 3).map(t => (
                            <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100">{t}</span>
                          ))}
                        </div>
                      </div>
                    </div>
```

- [ ] **Step 6: Run database preview test**

Run:

```bash
cd frontend-react
npx playwright test tests/db-preview.spec.ts
```

Expected:

```text
passed
```

- [ ] **Step 7: Run frontend build**

Run:

```bash
npm --prefix frontend-react run build
```

Expected:

```text
✓ built in ...
```

- [ ] **Step 8: Commit database preview changes**

Run:

```bash
git add frontend-react/src/pages/DbPage.tsx frontend-react/tests/db-preview.spec.ts
git commit -m "feat: show library record thumbnails"
```

---

### Task 5: Final regression, GitNexus change detection, and acceptance

**Files:**
- No new implementation files.
- Validate all files changed by Tasks 1-4.

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: verified branch ready for review.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
uv run pytest backend/test_library_storage_init.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run frontend build**

Run:

```bash
npm --prefix frontend-react run build
```

Expected:

```text
✓ built in ...
```

- [ ] **Step 3: Run focused Playwright coverage**

Run:

```bash
cd frontend-react
npx playwright test tests/upload-flow.spec.ts --grep "YOLO|Tab"
npx playwright test tests/db-preview.spec.ts
```

Expected:

```text
passed
```

- [ ] **Step 4: Run GitNexus change detection**

Run:

```bash
node .gitnexus/run.cjs detect-changes --scope compare --base-ref main
```

Expected:

```text
Changed symbols include GeneratePage, ProcessPanel, CommitToLibraryModal, DbPage, _upsert_record, commit_library_record.
Affected flows match Generate page review flow and library commit flow.
No unexpected high-risk flow appears.
```

- [ ] **Step 5: Manual acceptance checklist**

Run the app, upload a drawing that reaches YOLO review, then verify:

```text
1. Tabs render in this order when YOLO is visible: YOLO审阅 → 特征审阅 → 工艺规程.
2. Before opening annotation overlay, YOLO page shows: 开始标注 + 跳过 YOLO 审阅.
3. Clicking 跳过 YOLO 审阅 calls finalize and advances to 特征审阅.
4. After opening and closing annotation overlay, YOLO page shows: 继续标注 + 完成标注 → 下一步.
5. From 工艺规程, clicking 入库 sends source_text/vector_text equal to the confirmed feature text.
6. /api/library/commit response includes retrieval_check.
7. Database list card shows the first preview image when preview_image_urls is present.
8. Database list card shows 暂无预览 placeholder when preview_image_urls is empty.
9. Clicking a thumbnail opens the existing 库记录快照 modal.
```

- [ ] **Step 6: Final commit if any validation-only fixes were needed**

If Task 5 required fixes, commit them:

```bash
git add frontend-react backend
git commit -m "test: cover yolo review and library retrieval"
```

If no files changed during Task 5, do not create a commit.

## Self-Review

- Spec coverage:
  - Tab order is covered by Task 3.
  - YOLO button state is covered by Task 3.
  - Skip YOLO review reuses `finalizeAnnotation(taskId)` in Task 3.
  - Process-page commit sends `source_text` and `vector_text` in Task 2.
  - Backend vector fallback and self-check are covered by Task 1.
  - Database list thumbnails are covered by Task 4.
  - Tests and acceptance are covered by Tasks 1, 3, 4, and 5.
- Placeholder scan:
  - No placeholder markers or deferred-work wording are present.
- Type consistency:
  - `RetrievalCheck` matches backend response keys: `status`, `searchable`, `matched_prefix`, `similarity`, `reason`.
  - `CommitDraft.source_text` and `CommitDraft.vector_text` are produced by `ProcessPanel` and consumed by backend `_normalise_searchable_text()`.
  - `query_by_vector_similarity()` result comparison uses `drawing_id`, with `prefix` as a defensive fallback.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-20-generate-yolo-library-retrieval.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
