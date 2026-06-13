# GeneratePage 七项增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 GeneratePage 的 7 项问题：标注栏序号、退出保存、缩放上限、图纸预览缩放、添加工序、工种编辑、入库按钮。

**Architecture:** 前端 React 18 + TailwindCSS，后端已有 `/api/library/commit` 和 `/api/library/scopes` API。修改集中在 6 个现有文件 + 1 个新文件。

**Tech Stack:** React 18, TypeScript, TailwindCSS, GSAP, Vite

---

## File Structure

| 文件 | 职责 |
|------|------|
| `frontend/src/components/annotate/LabelTree.tsx` | 标注侧栏分组列表 — 添加序号显示 |
| `frontend/src/components/annotate/AnnotationPanel.tsx` | 标注主面板 — 关闭时立即保存 |
| `frontend/src/components/generate/UploadPanel.tsx` | 图纸内嵌预览 — 添加 Ctrl+滚轮缩放 + 拖拽平移 |
| `frontend/src/components/generate/FullscreenPreview.tsx` | 全屏预览 — 改为 Ctrl+滚轮触发 |
| `frontend/src/components/generate/ProcessPanel.tsx` | 工艺表格 — 添加行、工种编辑、入库按钮 |
| `frontend/src/components/generate/CommitToLibraryModal.tsx` | **新建** — 选库入库弹窗 |
| `frontend/src/api/client.ts` | API 层 — 添加 commitToLibrary |

---

### Task 1: 右侧标注栏序号

**Files:**
- Modify: `frontend/src/components/annotate/LabelTree.tsx:86-116`

- [ ] **Step 1: 修改子项渲染，添加序号**

在 `LabelTree.tsx` 中，`items.map` 已经按 label 分组，组内索引即序号。修改子项 span 显示 `displayName + seq`：

```tsx
// LabelTree.tsx — 修改 items.map 回调，添加 idx 参数
{!collapsedGroups.has(label) && items.map((shape, idx) => (
  <div
    key={shape.id}
    className={`
      flex items-center gap-2 pl-7 pr-2 py-1 rounded-lg cursor-pointer transition-all duration-100
      ${selectedId === shape.id ? 'bg-flame-50/80' : 'hover:bg-slate-50/60'}
    `}
    onClick={() => onSelect(shape.id)}
  >
    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: getLabelColor(shape.label) }} />

    {editingId === shape.id ? (
      <input
        autoFocus
        value={editValue}
        onChange={e => setEditValue(e.target.value)}
        onBlur={() => commitRename(shape.id)}
        onKeyDown={e => {
          if (e.key === 'Enter') commitRename(shape.id)
          if (e.key === 'Escape') setEditingId(null)
        }}
        className="flex-1 min-w-0 text-[11px] px-1.5 py-0.5 rounded border border-flame-300 bg-white outline-none"
        onClick={e => e.stopPropagation()}
      />
    ) : (
      <span
        className="flex-1 min-w-0 text-[11px] text-slate-700 truncate"
        onDoubleClick={e => { e.stopPropagation(); startRename(shape) }}
      >
        {LABEL_DISPLAY_NAMES[shape.label] || shape.label} {idx + 1}
      </span>
    )}

    <button
      onClick={e => { e.stopPropagation(); onDelete(shape.id) }}
      className="shrink-0 w-5 h-5 flex items-center justify-center rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors text-[13px]"
    >×</button>
  </div>
))}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd F:\Work_Dir\2D-v && npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/annotate/LabelTree.tsx
git commit -m "feat(annotate): 右侧标注栏显示分组内序号"
```

---

### Task 2: 退出标注页立即保存

**Files:**
- Modify: `frontend/src/components/annotate/AnnotationPanel.tsx` — 添加 `onClose` prop + 立即保存逻辑
- Modify: `frontend/src/pages/GeneratePage.tsx:102-104` — 传递 `onClose` 回调

- [ ] **Step 1: 修改 AnnotationPanel，添加 onClose prop**

在 `AnnotationPanel.tsx` 的 Props 接口中添加 `onClose?` 回调：

```tsx
// AnnotationPanel.tsx — Props 接口
interface Props {
  taskId: string
  previewImages: string[]
  getAssetUrl: (filename: string) => string
  onClose?: () => void
}
```

在组件内部，添加一个 `handleClose` 函数，在关闭前立即保存：

```tsx
// AnnotationPanel.tsx — 在组件内部添加
const handleClose = useCallback(async () => {
  // 立即保存当前页标注（不等防抖）
  if (currentPage && currentPage.shapes.length > 0) {
    try {
      await saveAnnotation(taskId, {
        page: pageNumber,
        shapes: currentPage.shapes.map(s => ({
          label: s.label,
          points: [[s.x, s.y], [s.x + s.width, s.y + s.height]],
          shape_type: 'rectangle',
        })),
        imageWidth: currentPage.imageWidth,
        imageHeight: currentPage.imageHeight,
        imagePath: previewImages[pageNumber - 1] || `page_${pageNumber}.png`,
      })
    } catch { /* save failed, still close */ }
  }
  onClose?.()
}, [taskId, currentPage, pageNumber, previewImages, onClose])
```

注意：`saveAnnotation` 的 import 已在文件中存在（line 8）。

- [ ] **Step 2: 修改 GeneratePage，传递 onClose**

```tsx
// GeneratePage.tsx — 修改 handleCloseAnnotate
const handleCloseAnnotate = useCallback(() => {
  setAnnotateOpen(false)
}, [])
```

这段不需要改，因为关闭逻辑在 AnnotationPanel 内部处理。但需要给 AnnotationPanel 传递 `onClose` prop：

```tsx
// GeneratePage.tsx — AnnotationPanel 使用处（约 line 539）
<AnnotationPanel
  taskId={taskId}
  previewImages={previewUrls.map(u => {
    const idx = u.indexOf('/asset/')
    return idx >= 0 ? u.slice(idx + 7) : u.split('/').pop() || u
  })}
  getAssetUrl={(filename) => getAssetUrl(taskId, filename)}
  onClose={handleCloseAnnotate}
/>
```

同时需要修改退出标注按钮，改为调用 AnnotationPanel 的 handleClose 而不是直接关闭：

由于退出按钮在 GeneratePage 中（line 530-535），而 AnnotationPanel 的 handleClose 需要在内部调用，有两种方案：
- **方案 A**：将退出按钮移入 AnnotationPanel 内部（较复杂）
- **方案 B**：AnnotationPanel 通过 `onClose` prop 暴露关闭方法，GeneratePage 调用

采用方案 B：AnnotationPanel 通过 `useImperativeHandle` 暴露 `handleClose`，或者更简单地，在 GeneratePage 中直接用 `onClose` 回调：

实际上最简单的方案是：在 GeneratePage 的退出按钮 onClick 中，不直接 unmount，而是先触发保存。但 AnnotationPanel 的数据在内部。

**最终方案**：给 AnnotationPanel 添加 `onClose` prop，退出按钮改为触发 AnnotationPanel 的内部关闭逻辑。通过 `useImperativeHandle` 暴露：

```tsx
// AnnotationPanel.tsx — 修改导出方式
import { useCallback, useRef, useState, useEffect, useImperativeHandle, forwardRef } from 'react'

export interface AnnotationPanelHandle {
  saveAndClose: () => Promise<void>
}

export const AnnotationPanel = forwardRef<AnnotationPanelHandle, Props>(
  function AnnotationPanel({ taskId, previewImages, getAssetUrl, onClose }, ref) {
    // ... existing code ...

    const handleSaveAndClose = useCallback(async () => {
      if (currentPage && currentPage.shapes.length > 0) {
        try {
          await saveAnnotation(taskId, {
            page: pageNumber,
            shapes: currentPage.shapes.map(s => ({
              label: s.label,
              points: [[s.x, s.y], [s.x + s.width, s.y + s.height]],
              shape_type: 'rectangle',
            })),
            imageWidth: currentPage.imageWidth,
            imageHeight: currentPage.imageHeight,
            imagePath: previewImages[pageNumber - 1] || `page_${pageNumber}.png`,
          })
        } catch { /* save failed, still close */ }
      }
      onClose?.()
    }, [taskId, currentPage, pageNumber, previewImages, onClose])

    useImperativeHandle(ref, () => ({
      saveAndClose: handleSaveAndClose,
    }), [handleSaveAndClose])

    // ... rest of component ...
  }
)
```

- [ ] **Step 3: 修改 GeneratePage 使用 ref**

```tsx
// GeneratePage.tsx
import { AnnotationPanel, type AnnotationPanelHandle } from '../components/annotate/AnnotationPanel'

// 添加 ref
const annotationRef = useRef<AnnotationPanelHandle>(null)

// 修改 handleCloseAnnotate
const handleCloseAnnotate = useCallback(async () => {
  await annotationRef.current?.saveAndClose()
  setAnnotateOpen(false)
}, [])

// 修改 AnnotationPanel 使用
<AnnotationPanel
  ref={annotationRef}
  taskId={taskId}
  previewImages={...}
  getAssetUrl={...}
  onClose={() => setAnnotateOpen(false)}
/>
```

- [ ] **Step 4: 验证 TypeScript 编译**

```bash
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx frontend/src/pages/GeneratePage.tsx
git commit -m "feat(annotate): 退出标注页时立即保存数据"
```

---

### Task 3: Ctrl+滚轮缩放上限排查

**Files:**
- Modify: `frontend/src/components/annotate/AnnotationPanel.tsx` — 根据排查结果修复

- [ ] **Step 1: 启动开发服务器，测试缩放行为**

```bash
cd F:\Work_Dir\2D-v\frontend && npm run dev
```

打开标注页，Ctrl+滚轮放大，观察是否在某个百分比卡住。

- [ ] **Step 2: 检查 fitToViewport 和初始值**

读取 `AnnotationPanel.tsx` 中 `handleZoomFit` 和初始 zoom 设置逻辑。如果 fitToViewport 设置了较低的初始值（如 0.5），则放大到 800% 时实际倍数是 0.5 × 8 = 4x，可能不够。

修复：移除 `Math.min(..., 1)` 对 fitToViewport 结果的限制（如果存在），或提高最大缩放倍数。

- [ ] **Step 3: 检查图片 CSS 限制**

检查 `<img>` 标签是否有 `max-width: 100%` 或其他 CSS 限制导致放大后图片不跟随。在 AnnotationPanel 中，图片应使用 `width/height` 基于 zoom 计算，而非 `max-width`。

- [ ] **Step 4: 修复并验证**

根据排查结果修改代码，然后：
```bash
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx
git commit -m "fix(annotate): 修复 Ctrl+滚轮缩放上限问题"
```

---

### Task 4: UploadPanel 添加 Ctrl+滚轮缩放 + 拖拽平移

**Files:**
- Modify: `frontend/src/components/generate/UploadPanel.tsx:66-117`

- [ ] **Step 1: 添加缩放和平移状态**

在 `UploadPanel` 的 `hasImages` 分支中，添加原生 wheel 事件监听和拖拽平移逻辑：

```tsx
// UploadPanel.tsx — 在 hasImages 分支的 return 之前添加
const scrollRef = useRef<HTMLDivElement>(null)
const zoomRef = useRef(zoom)
const [isPanning, setIsPanning] = useState(false)
const panStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })

// Sync zoomRef
useEffect(() => { zoomRef.current = zoom }, [zoom])

// Native wheel listener for Ctrl+zoom with cursor anchor
useEffect(() => {
  const el = scrollRef.current
  if (!el) return
  const handler = (e: WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    const oldZoom = zoomRef.current
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
    const newZoom = Math.min(Math.max(oldZoom * factor, 0.1), 10)

    const rect = el.getBoundingClientRect()
    const cursorX = e.clientX - rect.left + el.scrollLeft
    const cursorY = e.clientY - rect.top + el.scrollTop
    const ratio = newZoom / oldZoom

    requestAnimationFrame(() => {
      setZoom(newZoom)
      el.scrollLeft = Math.max(0, cursorX * ratio - (e.clientX - rect.left))
      el.scrollTop = Math.max(0, cursorY * ratio - (e.clientY - rect.top))
    })
  }
  el.addEventListener('wheel', handler, { passive: false })
  return () => el.removeEventListener('wheel', handler)
}, [])

// Pan handlers
const handlePanStart = useCallback((e: React.MouseEvent) => {
  if (e.button !== 0) return
  const el = scrollRef.current
  if (!el) return
  setIsPanning(true)
  panStartRef.current = {
    x: e.clientX,
    y: e.clientY,
    scrollLeft: el.scrollLeft,
    scrollTop: el.scrollTop,
  }
}, [])

const handlePanMove = useCallback((e: React.MouseEvent) => {
  if (!isPanning) return
  const el = scrollRef.current
  if (!el) return
  const dx = e.clientX - panStartRef.current.x
  const dy = e.clientY - panStartRef.current.y
  el.scrollLeft = panStartRef.current.scrollLeft - dx
  el.scrollTop = panStartRef.current.scrollTop - dy
}, [isPanning])

const handlePanEnd = useCallback(() => {
  setIsPanning(false)
}, [])
```

- [ ] **Step 2: 修改图片容器，绑定事件和 ref**

替换原来的 image stage div：

```tsx
{/* Image stage */}
<div
  ref={scrollRef}
  className={`flex-1 min-h-0 mx-4 mb-4 rounded-2xl border border-slate-200 overflow-auto flex items-center justify-center ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
  style={{ background: 'linear-gradient(135deg, #fafbfc 0%, #f8fafc 100%)' }}
  onMouseDown={handlePanStart}
  onMouseMove={handlePanMove}
  onMouseUp={handlePanEnd}
  onMouseLeave={handlePanEnd}
>
  <img
    ref={imageRef}
    src={previewUrls[pageIdx]}
    alt={`第 ${pageIdx + 1} 页`}
    className="block object-contain rounded-xl transition-none select-none"
    draggable={false}
    style={{
      width: `${zoom * 100}%`,
      height: 'auto',
      minHeight: '100%',
      boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
    }}
  />
</div>
```

- [ ] **Step 3: 修改工具栏缩放按钮，使用乘法**

```tsx
<button className="btn btn-ghost !px-2 !py-1.5 text-[11px]" onClick={() => setZoom(z => Math.max(0.1, z / 1.25))}>−</button>
// ...
<button className="btn btn-ghost !px-2 !py-1.5 text-[11px]" onClick={() => setZoom(z => Math.min(10, z * 1.25))}>+</button>
```

- [ ] **Step 4: 验证 TypeScript 编译**

```bash
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/generate/UploadPanel.tsx
git commit -m "feat(preview): 图纸预览支持 Ctrl+滚轮缩放和拖拽平移"
```

---

### Task 5: FullscreenPreview 改为 Ctrl+滚轮触发

**Files:**
- Modify: `frontend/src/components/generate/FullscreenPreview.tsx:29-33,85-91`

- [ ] **Step 1: 修改 handleWheel，添加 ctrlKey 检查和乘法缩放**

```tsx
// FullscreenPreview.tsx — 替换 handleWheel
const stageRef = useRef<HTMLDivElement>(null)
const zoomRef = useRef(zoom)

useEffect(() => { zoomRef.current = zoom }, [zoom])

useEffect(() => {
  const el = stageRef.current
  if (!el) return
  const handler = (e: WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    const oldZoom = zoomRef.current
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
    const newZoom = Math.min(Math.max(oldZoom * factor, 0.1), 10)

    const rect = el.getBoundingClientRect()
    const cursorX = e.clientX - rect.left + el.scrollLeft
    const cursorY = e.clientY - rect.top + el.scrollTop
    const ratio = newZoom / oldZoom

    requestAnimationFrame(() => {
      setZoom(newZoom)
      el.scrollLeft = Math.max(0, cursorX * ratio - (e.clientX - rect.left))
      el.scrollTop = Math.max(0, cursorY * ratio - (e.clientY - rect.top))
    })
  }
  el.addEventListener('wheel', handler, { passive: false })
  return () => el.removeEventListener('wheel', handler)
}, [])
```

- [ ] **Step 2: 修改 stage div，移除 onWheel，添加 overflow-auto**

```tsx
{/* Stage */}
<div
  ref={stageRef}
  className="flex-1 overflow-auto flex items-center justify-center"
  style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)' }}
>
  <img
    src={urls[index]}
    alt={`Page ${index + 1}`}
    className="block object-contain transition-none select-none"
    draggable={false}
    style={{
      width: `${zoom * 100}%`,
      height: 'auto',
      minHeight: '100%',
    }}
  />
</div>
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/generate/FullscreenPreview.tsx
git commit -m "feat(preview): 全屏预览改为 Ctrl+滚轮触发缩放"
```

---

### Task 6: ProcessPanel 添加新工序 + 工种可编辑

**Files:**
- Modify: `frontend/src/components/generate/ProcessPanel.tsx`

- [ ] **Step 1: 添加编辑状态和行管理函数**

在 ProcessPanel 组件内部（`const tableRef` 之后）添加：

```tsx
// Editable state for final rows
const [editRows, setEditRows] = useState<ProcessRow[]>([])
const [hoveredRow, setHoveredRow] = useState<number | null>(null)

// Sync editRows with finalRows when result changes
useEffect(() => {
  if (finalRows.length > 0) {
    setEditRows(finalRows)
  }
}, [finalRows])

// Renumber rows (step 10)
const renumberRows = useCallback((rows: ProcessRow[]) => {
  return rows.map((row, i) => ({ ...row, code: String((i + 1) * 10) }))
}, [])

// Add row at bottom
const handleAddRow = useCallback(() => {
  setEditRows(prev => {
    const newRows = [...prev, { code: '', trade: '', content: '' }]
    return renumberRows(newRows)
  })
}, [renumberRows])

// Insert row after index
const handleInsertRow = useCallback((afterIdx: number) => {
  setEditRows(prev => {
    const newRows = [...prev]
    newRows.splice(afterIdx + 1, 0, { code: '', trade: '', content: '' })
    return renumberRows(newRows)
  })
}, [renumberRows])

// Delete row
const handleDeleteRow = useCallback((idx: number) => {
  setEditRows(prev => {
    const newRows = prev.filter((_, i) => i !== idx)
    return renumberRows(newRows)
  })
}, [renumberRows])

// Cell edit handler
const handleCellEdit = useCallback((idx: number, field: 'trade' | 'content', value: string) => {
  setEditRows(prev => {
    const newRows = [...prev]
    newRows[idx] = { ...newRows[idx], [field]: value }
    return newRows
  })
}, [])
```

- [ ] **Step 2: 修改行渲染逻辑，使用 editRows**

将 `const rows = hasFinalResult ? finalRows : displayedRows` 替换为：

```tsx
const rows = hasFinalResult ? editRows : displayedRows
```

- [ ] **Step 3: 修改 tbody 中的行渲染，添加工种编辑 + 插入/删除按钮**

```tsx
<tbody>
  {rows.map((row, i) => (
    <tr
      key={i}
      className="group relative"
      onMouseEnter={() => setHoveredRow(i)}
      onMouseLeave={() => setHoveredRow(null)}
    >
      <td className="text-center font-mono text-[15px] font-bold text-flame-600 bg-gradient-to-r from-flame-50/50 to-orange-50/30">
        {row.code}
      </td>
      <td>
        {hasFinalResult ? (
          <span
            contentEditable
            suppressContentEditableWarning
            onBlur={(e) => handleCellEdit(i, 'trade', e.currentTarget.textContent || '')}
            className="cell-editable block"
          >
            {row.trade}
          </span>
        ) : row.trade ? (
          <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${tradeBadgeClass(row.trade)}`}>
            {row.trade}
          </span>
        ) : null}
      </td>
      <td>
        {hasFinalResult ? (
          <span
            contentEditable
            suppressContentEditableWarning
            onBlur={(e) => handleCellEdit(i, 'content', e.currentTarget.textContent || '')}
            className="cell-editable block"
          >
            {row.content}
          </span>
        ) : (
          <span
            contentEditable
            suppressContentEditableWarning
            className="cell-editable block"
          >
            {row.content}
          </span>
        )}
      </td>
      {/* Insert + Delete buttons (final result only) */}
      {hasFinalResult && (
        <td className="w-16 text-right opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="flex items-center gap-1 justify-end">
            <button
              onClick={() => handleInsertRow(i)}
              className="w-6 h-6 flex items-center justify-center rounded text-slate-400 hover:text-blue-500 hover:bg-blue-50 text-[14px]"
              title="在下方插入"
            >+</button>
            <button
              onClick={() => handleDeleteRow(i)}
              className="w-6 h-6 flex items-center justify-center rounded text-slate-400 hover:text-red-500 hover:bg-red-50 text-[13px]"
              title="删除此行"
            >×</button>
          </div>
        </td>
      )}
    </tr>
  ))}
  {/* Typing row — unchanged */}
  {showTyping && (
    <tr className="tw-typing-row">
      {/* ... existing typing row code unchanged ... */}
    </tr>
  )}
</tbody>
```

- [ ] **Step 4: 修改 colgroup，添加操作列**

```tsx
<colgroup>
  <col style={{ width: 80 }} />
  <col style={{ width: 90 }} />
  <col />
  {hasFinalResult && <col style={{ width: 64 }} />}
</colgroup>
<thead>
  <tr>
    <th className="text-center">工序号</th>
    <th>工种</th>
    <th>工序名称及内容</th>
    {hasFinalResult && <th></th>}
  </tr>
</thead>
```

- [ ] **Step 5: 在表格下方添加"+ 添加工序"按钮**

```tsx
{/* Add row button — final result only */}
{hasFinalResult && (
  <div className="shrink-0 pt-2">
    <button
      onClick={handleAddRow}
      className="w-full py-2 rounded-xl border-2 border-dashed border-slate-200 text-[13px] font-medium text-slate-400 hover:text-flame-500 hover:border-flame-300 hover:bg-flame-50/30 transition-colors"
    >
      + 添加工序
    </button>
  </div>
)}
```

- [ ] **Step 6: 验证 TypeScript 编译**

```bash
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/generate/ProcessPanel.tsx
git commit -m "feat(process): 支持添加/插入/删除工序行，工种字段可编辑"
```

---

### Task 7: 入库按钮 + 选库弹窗

**Files:**
- Create: `frontend/src/components/generate/CommitToLibraryModal.tsx`
- Modify: `frontend/src/api/client.ts` — 添加 commitToLibrary API
- Modify: `frontend/src/components/generate/ProcessPanel.tsx` — 添加入库按钮

- [ ] **Step 1: 在 client.ts 添加 commitToLibrary API**

在 `deleteLibraryScope` 函数之后添加：

```typescript
// client.ts — 在 deleteLibraryScope 之后添加

export interface CommitDraft {
  prefix: string
  content: string
  process_summary: string
  feature_report: string
}

export async function commitToLibrary(params: {
  draft: CommitDraft
  action: 'replace' | 'keep'
  library_key: string
}): Promise<{ message: string; record_id?: number }> {
  return request('/library/commit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}
```

- [ ] **Step 2: 创建 CommitToLibraryModal 组件**

```tsx
// frontend/src/components/generate/CommitToLibraryModal.tsx
import { useState, useEffect } from 'react'
import { getLibraryScopes, commitToLibrary, type LibraryScope, type CommitDraft } from '../../api/client'

interface Props {
  draft: CommitDraft
  onClose: () => void
  onSuccess: () => void
}

export function CommitToLibraryModal({ draft, onClose, onSuccess }: Props) {
  const [scopes, setScopes] = useState<LibraryScope[]>([])
  const [loading, setLoading] = useState(true)
  const [committing, setCommitting] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getLibraryScopes()
      .then(res => {
        setScopes(res.items)
        if (res.items.length > 0) setSelectedKey(res.items[0].library_key)
      })
      .catch(err => setError(err instanceof Error ? err.message : '获取库列表失败'))
      .finally(() => setLoading(false))
  }, [])

  const handleCommit = async () => {
    if (!selectedKey) return
    setCommitting(true)
    setError(null)
    try {
      await commitToLibrary({ draft, action: 'replace', library_key: selectedKey })
      onSuccess()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '入库失败')
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.4)' }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-white rounded-2xl shadow-2xl w-[420px] max-h-[80vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-5 pb-3 border-b border-slate-100">
          <h3 className="text-[16px] font-bold text-slate-800">选择入库目标</h3>
          <p className="text-[12px] text-slate-400 mt-1">将当前工艺规程保存到知识库</p>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400 text-[13px]">
              <span className="w-4 h-4 border-2 border-slate-200 border-t-flame-500 rounded-full animate-spin mr-2" />
              加载中...
            </div>
          ) : error ? (
            <div className="text-red-500 text-[13px] text-center py-4">{error}</div>
          ) : scopes.length === 0 ? (
            <div className="text-slate-400 text-[13px] text-center py-8">暂无可用知识库</div>
          ) : (
            <div className="flex flex-col gap-2">
              {scopes.map(scope => (
                <button
                  key={scope.library_key}
                  onClick={() => setSelectedKey(scope.library_key)}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors ${
                    selectedKey === scope.library_key
                      ? 'border-flame-400 bg-flame-50/50'
                      : 'border-slate-100 hover:border-slate-200 bg-white'
                  }`}
                >
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    selectedKey === scope.library_key ? 'border-flame-500' : 'border-slate-300'
                  }`}>
                    {selectedKey === scope.library_key && <div className="w-2 h-2 rounded-full bg-flame-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-slate-700">{scope.library_name}</div>
                    <div className="text-[11px] text-slate-400">
                      {scope.scope_type === 'public' ? '公共库' : '私有库'}
                      {scope.record_count != null && ` · ${scope.record_count} 条记录`}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3">
          <button onClick={onClose} className="btn btn-ghost !text-[12px]">取消</button>
          <button
            onClick={handleCommit}
            disabled={!selectedKey || committing}
            className="btn btn-primary !text-[12px] !px-5"
          >
            {committing ? '入库中...' : '确认入库'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 在 ProcessPanel 中添加入库按钮和弹窗状态**

```tsx
// ProcessPanel.tsx — 添加 import 和 state
import { CommitToLibraryModal } from './CommitToLibraryModal'
import type { CommitDraft } from '../../api/client'

// 在组件内部添加
const [showCommitModal, setShowCommitModal] = useState(false)

// Build draft from current rows
const commitDraft: CommitDraft = useMemo(() => {
  const rows = editRows.length > 0 ? editRows : finalRows
  const content = rows.map(r => `${r.code}\t${r.trade}\t${r.content}`).join('\n')
  const processSummary = rows.map(r => `${r.code} ${r.trade} ${r.content}`).join('; ')
  return {
    prefix: '',
    content,
    process_summary: processSummary,
    feature_report: '',
  }
}, [editRows, finalRows])
```

- [ ] **Step 4: 在"+ 添加工序"按钮下方添加入库按钮**

```tsx
{/* Action buttons — final result only */}
{hasFinalResult && (
  <div className="shrink-0 pt-2 flex gap-2">
    <button
      onClick={handleAddRow}
      className="flex-1 py-2 rounded-xl border-2 border-dashed border-slate-200 text-[13px] font-medium text-slate-400 hover:text-flame-500 hover:border-flame-300 hover:bg-flame-50/30 transition-colors"
    >
      + 添加工序
    </button>
    <button
      onClick={() => setShowCommitModal(true)}
      className="px-5 py-2 rounded-xl bg-gradient-to-r from-flame-500 to-orange-500 text-white text-[13px] font-semibold shadow-sm hover:shadow-md transition-shadow"
    >
      入库
    </button>
  </div>
)}

{/* Commit modal */}
{showCommitModal && (
  <CommitToLibraryModal
    draft={commitDraft}
    onClose={() => setShowCommitModal(false)}
    onSuccess={() => {/* toast or feedback */}}
  />
)}
```

- [ ] **Step 5: 验证 TypeScript 编译**

```bash
npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/generate/CommitToLibraryModal.tsx frontend/src/api/client.ts frontend/src/components/generate/ProcessPanel.tsx
git commit -m "feat(process): 添加入库按钮和选库弹窗"
```

---

### Task 8: 最终验证

- [ ] **Step 1: TypeScript 编译检查**

```bash
cd F:\Work_Dir\2D-v && npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 2: Vite 构建**

```bash
cd F:\Work_Dir\2D-v\frontend && npx vite build
```

Expected: 构建成功，无错误

- [ ] **Step 3: 最终 Commit（如有遗漏）**

```bash
git status
```

检查是否有未提交的修改。
