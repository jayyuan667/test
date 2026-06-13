# GeneratePage 四项修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复工艺生成页的 4 个问题：Ctrl+滚轮缩放被浏览器劫持、标注页面功能缺失、审阅字段丢失、流式输出闪烁且不自动滚动。

**Architecture:** 在现有 React 18 前端上做增量修复。缩放改用原生事件绑定；标注增强通过新建弹窗和侧栏组件；审阅修复改白名单过滤；流式修复 GSAP 动画范围并添加 auto-scroll。

**Tech Stack:** React 18, TypeScript, GSAP, Tailwind CSS, localStorage

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/components/annotate/AnnotationPanel.tsx` | 修改 | 原生 wheel 事件、拖拽平移、自定义标签管理 |
| `frontend/src/components/annotate/AnnotationToolbar.tsx` | 修改 | "+"按钮、使用 LABEL_DISPLAY_NAMES |
| `frontend/src/components/annotate/AddLabelModal.tsx` | 新建 | 添加自定义标注类型弹窗 |
| `frontend/src/components/annotate/LabelTree.tsx` | 修改 | 分类折叠/展开 |
| `frontend/src/types/annotate.ts` | 修改 | 扩展 BUILT_IN_LABELS 到 10 种 |
| `frontend/src/index.css` | 修改 | 拖拽 cursor 样式 |
| `frontend/src/utils/featureParser.ts` | 修改 | NOISE_LABELS → HIDDEN_LABELS |
| `frontend/src/components/generate/ProcessPanel.tsx` | 修改 | GSAP 仅新行动画 + auto-scroll |
| `frontend/src/pages/GeneratePage.tsx` | 修改 | 使用 LABEL_DISPLAY_NAMES 消除重复 |

---

### Task 1: 修复 Ctrl+滚轮缩放 — 原生事件绑定

**Files:**
- Modify: `frontend/src/components/annotate/AnnotationPanel.tsx:254-289`

- [ ] **Step 1: 将 onWheel 合成事件改为原生 addEventListener**

在 `AnnotationPanel.tsx` 中，移除 scroll 容器上的 `onWheel={handleWheel}`，改为在 useEffect 中用原生 `addEventListener` 绑定，设置 `{ passive: false }`。

首先，将 `handleWheel` 从 `useCallback` 改为普通函数（因为它将被 useEffect 中的闭包引用）：

```tsx
// 删除 lines 254-289 的 handleWheel useCallback
// 替换为以下代码：

const handleWheelRef = useRef<(e: WheelEvent) => void>(() => {})

useEffect(() => {
  handleWheelRef.current = (e: WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()

    const scroll = scrollRef.current
    const img = imgRef.current
    if (!scroll || !img?.naturalWidth) return

    const oldZoom = zoomRef.current
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
    const newZoom = Math.min(Math.max(oldZoom * factor, 0.05), 8)

    const scrollRect = scroll.getBoundingClientRect()
    const desiredX = e.clientX - scrollRect.left
    const desiredY = e.clientY - scrollRect.top

    const imgRect = img.getBoundingClientRect()
    const sxOld = imgRect.width / img.naturalWidth
    const pxNat = (e.clientX - imgRect.left) / sxOld
    const pyNat = (e.clientY - imgRect.top) / (imgRect.height / img.naturalHeight)

    setZoom(newZoom)

    requestAnimationFrame(() => {
      const newImg = imgRef.current
      if (!newImg) return
      const newImgRect = newImg.getBoundingClientRect()
      const sxNew = newImgRect.width / img.naturalWidth
      scroll.scrollLeft = Math.max(0,
        (newImgRect.left - scrollRect.left) + scroll.scrollLeft + pxNat * sxNew - desiredX)
      scroll.scrollTop = Math.max(0,
        (newImgRect.top - scrollRect.top) + scroll.scrollTop + pyNat * sxNew - desiredY)
    })
  }
}, [])  // 无依赖，通过 zoomRef 读取最新 zoom

useEffect(() => {
  const el = scrollRef.current
  if (!el) return
  const handler = (e: WheelEvent) => handleWheelRef.current(e)
  el.addEventListener('wheel', handler, { passive: false })
  return () => el.removeEventListener('wheel', handler)
}, [])
```

同时添加 `zoomRef` 保持同步（在 line 35 附近）：

```tsx
const [zoom, setZoom] = useState(1)
const zoomRef = useRef(zoom)
useEffect(() => { zoomRef.current = zoom }, [zoom])
```

- [ ] **Step 2: 移除 fitToViewport 的 100% 限制**

修改 `handleZoomFit`（当前 lines 247-251）：

```tsx
const handleZoomFit = useCallback(() => {
  const scroll = scrollRef.current
  const img = imgRef.current
  if (!scroll || !img?.naturalWidth) return
  const fitW = (scroll.clientWidth - 32) / img.naturalWidth
  const fitH = (scroll.clientHeight - 32) / img.naturalHeight
  setZoom(Math.min(fitW, fitH))  // 移除 Math.min(..., 1)
}, [])
```

- [ ] **Step 3: 移除 scroll 容器上的 onWheel 属性**

在 JSX 中找到 scroll 容器 div（约 line 352），移除 `onWheel={handleWheel}` 属性。原生事件已在 useEffect 中绑定。

- [ ] **Step 4: 验证**

运行 `npx tsc --noEmit` 确认无类型错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx
git commit -m "fix(annotate): Ctrl+wheel zoom uses native passive:false event"
```

---

### Task 2: 添加拖拽平移

**Files:**
- Modify: `frontend/src/components/annotate/AnnotationPanel.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 添加 pan 状态和 refs**

在 `AnnotationPanel.tsx` 的 state 声明区域（约 line 35 之后）添加：

```tsx
const [isPanning, setIsPanning] = useState(false)
const panStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })
const isDrawingRef = useRef(false)
```

- [ ] **Step 2: 添加 pan 鼠标处理函数**

在 handleWheel 相关代码之后添加：

```tsx
const handlePanStart = useCallback((e: React.MouseEvent) => {
  // 只在非绘图模式、非 Ctrl 键时启动拖拽
  if (e.button !== 0) return
  const scroll = scrollRef.current
  if (!scroll) return

  setIsPanning(true)
  panStartRef.current = {
    x: e.clientX,
    y: e.clientY,
    scrollLeft: scroll.scrollLeft,
    scrollTop: scroll.scrollTop,
  }
  e.preventDefault()
}, [])

const handlePanMove = useCallback((e: React.MouseEvent) => {
  if (!isPanning) return
  const scroll = scrollRef.current
  if (!scroll) return

  const dx = e.clientX - panStartRef.current.x
  const dy = e.clientY - panStartRef.current.y
  scroll.scrollLeft = panStartRef.current.scrollLeft - dx
  scroll.scrollTop = panStartRef.current.scrollTop - dy
}, [isPanning])

const handlePanEnd = useCallback(() => {
  setIsPanning(false)
}, [])
```

- [ ] **Step 3: 在 scroll 容器上绑定 pan 事件**

修改 scroll 容器 div（约 line 352），添加 onMouseDown/onMouseMove/onMouseUp：

```tsx
<div
  ref={scrollRef}
  className={`overflow-auto anno-grid-bg flex-1 min-h-0 ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
  onMouseDown={handlePanStart}
  onMouseMove={handlePanMove}
  onMouseUp={handlePanEnd}
  onMouseLeave={handlePanEnd}
>
```

- [ ] **Step 4: 防止 pan 与绘图冲突**

修改现有的 `handleMouseDown`（line 138），在绘图开始时阻止 pan：

```tsx
const handleMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
  if (e.button !== 0) return
  isDrawingRef.current = true  // 添加这行
  // ... 现有绘图逻辑
}
```

修改 `handleMouseUp`（约 line 180），在绘图结束时重置：

```tsx
const handleMouseUp = () => {
  isDrawingRef.current = false  // 添加这行
  // ... 现有绘图逻辑
}
```

修改 `handlePanStart`，添加绘图检查：

```tsx
const handlePanStart = useCallback((e: React.MouseEvent) => {
  if (e.button !== 0 || isDrawingRef.current) return
  // ... 现有逻辑
}, [])
```

- [ ] **Step 5: 添加 cursor CSS 样式**

在 `index.css` 的 anno 相关样式区域（约 line 309 之后）添加：

```css
.cursor-grab { cursor: grab; }
.cursor-grabbing { cursor: grabbing; }
```

- [ ] **Step 6: Ctrl 按下时显示 zoom-in cursor**

在 scroll 容器 div 上添加动态 cursor class：

```tsx
className={`overflow-auto anno-grid-bg flex-1 min-h-0 ${
  isPanning ? 'cursor-grabbing' : 'cursor-grab'
}`}
```

注意：SVG 内部的 cursor 由 `.anno-svg` CSS 控制为 `crosshair`，绘图时覆盖 pan cursor 是正确行为。

- [ ] **Step 7: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx frontend/src/index.css
git commit -m "feat(annotate): add drag-to-pan on annotation canvas"
```

---

### Task 3: 扩展标注类型到 10 种 + 统一显示名

**Files:**
- Modify: `frontend/src/types/annotate.ts:25-37`
- Modify: `frontend/src/components/annotate/AnnotationToolbar.tsx:46-48`
- Modify: `frontend/src/pages/GeneratePage.tsx:372-374`

- [ ] **Step 1: 扩展 BUILT_IN_LABELS 到 10 种**

修改 `frontend/src/types/annotate.ts`，将 `BUILT_IN_LABELS` 从 3 种扩展到 10 种，同步更新 `LABEL_DISPLAY_NAMES`：

```typescript
export const BUILT_IN_LABELS: AnnotationLabel[] = [
  { name: 'threaded_hole',    color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'rivet_hole',       color: '#ec4899', borderStyle: 'solid', isCustom: false },
  { name: 'pin_hole',         color: '#14b8a6', borderStyle: 'solid', isCustom: false },
  { name: 'through_hole',     color: '#3b82f6', borderStyle: 'solid', isCustom: false },
  { name: 'countersunk_hole', color: '#f97316', borderStyle: '6,3',   isCustom: false },
  { name: 'thread_through',   color: '#8b5cf6', borderStyle: '6,3',   isCustom: false },
  { name: 'chamfer',          color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'emboss',           color: '#10b981', borderStyle: 'solid', isCustom: false },
  { name: 'flanged_hole',     color: '#06b6d4', borderStyle: 'solid', isCustom: false },
  { name: 'deep_draw',        color: '#ef4444', borderStyle: 'solid', isCustom: false },
]

export const LABEL_DISPLAY_NAMES: Record<string, string> = {
  threaded_hole: '螺纹孔',
  rivet_hole: '铆钉孔',
  pin_hole: '销钉孔',
  through_hole: '过孔',
  countersunk_hole: '沉头孔',
  thread_through: '螺纹过孔',
  chamfer: '倒角',
  emboss: '压印',
  flanged_hole: '翻边孔',
  deep_draw: '拉深',
}
```

- [ ] **Step 2: 修复 AnnotationToolbar.tsx 使用 LABEL_DISPLAY_NAMES**

修改 `AnnotationToolbar.tsx`：

1. 添加 import：`import { LABEL_DISPLAY_NAMES } from '../../types/annotate'`
2. 替换 lines 46-48 的硬编码三元表达式为：

```tsx
{LABEL_DISPLAY_NAMES[label.name] || label.name}
```

- [ ] **Step 3: 修复 GeneratePage.tsx 使用 LABEL_DISPLAY_NAMES**

修改 `GeneratePage.tsx`：

1. 添加 import：`import { LABEL_DISPLAY_NAMES } from '../types/annotate'`
2. 替换 lines 372-374 的本地 `summaryLabels` 为：

```tsx
const summaryLabels = LABEL_DISPLAY_NAMES
```

或直接在 line 375 使用 `LABEL_DISPLAY_NAMES` 替代 `summaryLabels`。

- [ ] **Step 4: 验证**

运行 `npx tsc --noEmit`。确认 AnnotationPanel.tsx 和 LabelTree.tsx 中已有的 `LABEL_DISPLAY_NAMES` 引用仍然正常。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/annotate.ts frontend/src/components/annotate/AnnotationToolbar.tsx frontend/src/pages/GeneratePage.tsx
git commit -m "feat(annotate): expand to 10 built-in label types + unify display names"
```

---

### Task 4: 自定义添加标注类型 — 弹窗组件

**Files:**
- Create: `frontend/src/components/annotate/AddLabelModal.tsx`

- [ ] **Step 1: 创建 AddLabelModal 组件**

```tsx
import { useState } from 'react'
import { AnnotationLabel, CUSTOM_LABEL_COLORS } from '../../types/annotate'

interface Props {
  onAdd: (label: AnnotationLabel) => void
  onClose: () => void
  existingNames: string[]
}

const PRESET_COLORS = [
  '#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4',
  '#ef4444', '#10b981', '#3b82f6', '#f59e0b', '#6366f1',
  '#84cc16', '#a855f7',
]

export default function AddLabelModal({ onAdd, onClose, existingNames }: Props) {
  const [name, setName] = useState('')
  const [color, setColor] = useState(PRESET_COLORS[0])
  const [error, setError] = useState('')

  const handleSubmit = () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('请输入类型名称')
      return
    }
    if (existingNames.includes(trimmed)) {
      setError('该类型名称已存在')
      return
    }
    onAdd({
      name: trimmed,
      color,
      borderStyle: 'solid',
      isCustom: true,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center bg-black/40"
         onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-[360px] p-5"
           onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-slate-800 mb-4">添加标注类型</h3>

        <label className="block text-xs text-slate-500 mb-1">类型名称</label>
        <input
          type="text"
          value={name}
          onChange={e => { setName(e.target.value); setError('') }}
          placeholder="如：特殊孔"
          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg
                     focus:outline-none focus:ring-2 focus:ring-indigo-300 mb-1"
          autoFocus
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
        />
        {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
        <div className="mb-4" />

        <label className="block text-xs text-slate-500 mb-2">颜色</label>
        <div className="flex flex-wrap gap-2 mb-4">
          {PRESET_COLORS.map(c => (
            <button
              key={c}
              onClick={() => setColor(c)}
              className={`w-7 h-7 rounded-full border-2 transition-all ${
                color === c ? 'border-slate-800 scale-110' : 'border-transparent'
              }`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg">
            取消
          </button>
          <button onClick={handleSubmit}
                  className="px-3 py-1.5 text-xs text-white bg-indigo-500 hover:bg-indigo-600 rounded-lg">
            确认添加
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/annotate/AddLabelModal.tsx
git commit -m "feat(annotate): add AddLabelModal component for custom label types"
```

---

### Task 5: 集成自定义标签 — AnnotationPanel + Toolbar

**Files:**
- Modify: `frontend/src/components/annotate/AnnotationPanel.tsx:26`
- Modify: `frontend/src/components/annotate/AnnotationToolbar.tsx:29-51`

- [ ] **Step 1: 在 AnnotationPanel 中管理自定义标签状态**

在 `AnnotationPanel.tsx` 中添加自定义标签的 state 和 localStorage 持久化（约 line 26 附近）：

```tsx
const [customLabels, setCustomLabels] = useState<AnnotationLabel[]>(() => {
  try {
    const saved = localStorage.getItem('annotation-custom-labels')
    return saved ? JSON.parse(saved) : []
  } catch { return [] }
})
const [showAddModal, setShowAddModal] = useState(false)

useEffect(() => {
  localStorage.setItem('annotation-custom-labels', JSON.stringify(customLabels))
}, [customLabels])

const allLabels = [...BUILT_IN_LABELS, ...customLabels]

const handleAddLabel = (label: AnnotationLabel) => {
  setCustomLabels(prev => [...prev, label])
}

const handleDeleteLabel = (name: string) => {
  setCustomLabels(prev => prev.filter(l => l.name !== name))
  // 如果当前选中的是被删除的标签，切换到第一个
  if (activeLabel === name) {
    setActiveLabel(allLabels[0]?.name || '')
  }
}
```

- [ ] **Step 2: 向 AnnotationToolbar 传递新 props**

修改 AnnotationToolbar 的 Props 接口和渲染：

```tsx
interface Props {
  // ...existing props
  onAddLabel?: () => void
  onDeleteLabel?: (name: string) => void
  canDeleteLabel?: (name: string) => boolean
}
```

在 label 按钮区域末尾（line 51 之后、separator 之前）添加"+"按钮：

```tsx
{onAddLabel && (
  <button
    onClick={onAddLabel}
    className="px-2 py-1 rounded-lg text-[11px] font-semibold border border-dashed
               border-slate-300 text-slate-400 hover:border-indigo-400 hover:text-indigo-500
               transition-all duration-150"
    title="添加标注类型"
  >
    +
  </button>
)}
```

- [ ] **Step 3: 在 AnnotationPanel 中传递新 props 给 Toolbar**

找到 AnnotationToolbar 的渲染位置，添加新 props：

```tsx
<AnnotationToolbar
  // ...existing props
  onAddLabel={() => setShowAddModal(true)}
  onDeleteLabel={handleDeleteLabel}
  canDeleteLabel={(name) => !BUILT_IN_LABELS.some(l => l.name === name)}
/>
```

- [ ] **Step 4: 渲染 AddLabelModal**

在 AnnotationPanel 的 return 末尾添加条件渲染：

```tsx
{showAddModal && (
  <AddLabelModal
    onAdd={handleAddLabel}
    onClose={() => setShowAddModal(false)}
    existingNames={allLabels.map(l => l.name)}
  />
)}
```

- [ ] **Step 5: 添加 import**

```tsx
import AddLabelModal from './AddLabelModal'
```

- [ ] **Step 6: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx frontend/src/components/annotate/AnnotationToolbar.tsx
git commit -m "feat(annotate): integrate custom label creation with toolbar + button"
```

---

### Task 6: 右侧栏拖拽宽度 + 折叠/展开

**Files:**
- Modify: `frontend/src/components/annotate/AnnotationPanel.tsx:479-500`

- [ ] **Step 1: 添加侧栏宽度和折叠状态**

在 AnnotationPanel 的 state 区域添加：

```tsx
const [sidebarWidth, setSidebarWidth] = useState(() => {
  try {
    const saved = localStorage.getItem('annotation-sidebar-width')
    return saved ? Number(saved) : 220
  } catch { return 220 }
})
const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
const isResizingRef = useRef(false)

useEffect(() => {
  localStorage.setItem('annotation-sidebar-width', String(sidebarWidth))
}, [sidebarWidth])
```

- [ ] **Step 2: 添加拖拽处理函数**

```tsx
const handleSidebarResizeStart = useCallback((e: React.MouseEvent) => {
  e.preventDefault()
  isResizingRef.current = true

  const onMove = (ev: MouseEvent) => {
    if (!isResizingRef.current) return
    // 计算从右侧边缘到鼠标的位置
    const container = scrollRef.current?.parentElement
    if (!container) return
    const containerRect = container.getBoundingClientRect()
    const newWidth = Math.min(500, Math.max(200, containerRect.right - ev.clientX))
    setSidebarWidth(newWidth)
  }

  const onUp = () => {
    isResizingRef.current = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}, [])
```

- [ ] **Step 3: 修改侧栏 JSX**

替换现有的侧栏代码（约 lines 479-500）为：

```tsx
{sidebarCollapsed ? (
  <button
    onClick={() => setSidebarCollapsed(false)}
    className="w-6 flex-shrink-0 flex items-center justify-center bg-slate-50
               border-l border-slate-200 hover:bg-slate-100 text-slate-400"
    title="展开侧栏"
  >
    ‹
  </button>
) : (
  <div
    className="flex-shrink-0 flex flex-col border-l border-slate-200 bg-slate-50 relative"
    style={{ width: sidebarWidth }}
  >
    {/* 拖拽手柄 */}
    <div
      className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-indigo-300 z-10"
      onMouseDown={handleSidebarResizeStart}
    />

    {/* 标题栏 */}
    <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200">
      <span className="text-xs font-semibold text-slate-600">标注列表</span>
      <button
        onClick={() => setSidebarCollapsed(true)}
        className="text-slate-400 hover:text-slate-600 text-xs"
        title="折叠侧栏"
      >
        ›
      </button>
    </div>

    {/* 标注树 */}
    <div className="flex-1 overflow-y-auto p-2">
      <LabelTree
        shapes={shapes}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onDelete={handleDeleteShape}
      />
    </div>
  </div>
)}
```

- [ ] **Step 4: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx
git commit -m "feat(annotate): resizable + collapsible right sidebar"
```

---

### Task 7: 标注分类折叠/展开

**Files:**
- Modify: `frontend/src/components/annotate/LabelTree.tsx`

- [ ] **Step 1: 添加折叠状态管理**

在 `LabelTree.tsx` 中添加折叠状态（使用 localStorage 持久化）：

```tsx
const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(() => {
  try {
    const saved = localStorage.getItem('annotation-collapsed-groups')
    return saved ? new Set(JSON.parse(saved)) : new Set()
  } catch { return new Set() }
})

useEffect(() => {
  localStorage.setItem('annotation-collapsed-groups',
    JSON.stringify(Array.from(collapsedGroups)))
}, [collapsedGroups])

const toggleGroup = (label: string) => {
  setCollapsedGroups(prev => {
    const next = new Set(prev)
    if (next.has(label)) next.delete(label)
    else next.add(label)
    return next
  })
}
```

- [ ] **Step 2: 修改分组标题行可点击**

找到 LabelTree 中渲染分组标题的代码（约 line 73 附近），添加 onClick 切换和折叠箭头：

```tsx
<div
  className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-slate-100 rounded"
  onClick={() => toggleGroup(label)}
>
  <span className={`text-[10px] text-slate-400 transition-transform ${
    collapsedGroups.has(label) ? '' : 'rotate-90'
  }`}>▶</span>
  {/* 颜色指示 + 类型名 + 数量 badge */}
  <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full"
        style={{ backgroundColor: color }} />
  <span className="text-xs font-medium text-slate-700 flex-1">
    {LABEL_DISPLAY_NAMES[label] || label}
  </span>
  <span className="text-[10px] text-slate-400 bg-slate-200 px-1.5 rounded-full">
    {shapes.length}
  </span>
</div>
```

- [ ] **Step 3: 条件渲染子列表**

将该分组下的标注列表用 `collapsedGroups.has(label)` 条件包裹：

```tsx
{!collapsedGroups.has(label) && (
  <div className="ml-5">
    {/* 现有的子标注列表渲染 */}
  </div>
)}
```

- [ ] **Step 4: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/annotate/LabelTree.tsx
git commit -m "feat(annotate): collapsible label groups in sidebar tree"
```

---

### Task 8: 修复审阅字段丢失 — 白名单过滤

**Files:**
- Modify: `frontend/src/utils/featureParser.ts:6-11`

- [ ] **Step 1: 将 NOISE_LABELS 改为 HIDDEN_LABELS**

修改 `featureParser.ts` lines 6-11：

```typescript
// 之前
const NOISE_LABELS = new Set([
  '报告名称', '页数', '图号', '图号保留', '零件名称', '毛坯类型',
])
const isNoise = (label: string) =>
  NOISE_LABELS.has(label) || /^第\d+页摘要$/.test(label)

// 之后
const HIDDEN_LABELS = new Set([
  '报告名称', '页数',
])
const isHidden = (label: string) =>
  HIDDEN_LABELS.has(label) || /^第\d+页摘要$/.test(label)
```

- [ ] **Step 2: 更新 parseReviewFields 中的调用**

将 `isNoise(label)` 改为 `isHidden(label)`（line 28 附近）：

```typescript
if (isHidden(label)) continue  // 原为 isNoise
```

- [ ] **Step 3: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/featureParser.ts
git commit -m "fix(review): switch from blacklist to whitelist for field filtering"
```

---

### Task 9: 修复流式闪烁 — GSAP 仅作用于新行

**Files:**
- Modify: `frontend/src/components/generate/ProcessPanel.tsx:199-210`

- [ ] **Step 1: 添加 animatedCountRef**

在 ProcessPanel 的 ref 声明区域（约 line 65 之后）添加：

```tsx
const animatedCountRef = useRef(0)
```

- [ ] **Step 2: 修改 GSAP 动画 useEffect**

替换 lines 199-210 的现有 GSAP 动画代码：

```tsx
useEffect(() => {
  if (!tableRef.current) return
  const rows = tableRef.current.querySelectorAll('tbody tr')
  if (rows.length <= animatedCountRef.current) return

  // 只选择新增的行
  const newRows = Array.from(rows).slice(animatedCountRef.current)
  if (newRows.length === 0) return

  gsap.fromTo(newRows,
    { opacity: 0, y: 10 },
    { opacity: 1, y: 0, duration: 0.3, stagger: 0.04, ease: 'power2.out' }
  )
  animatedCountRef.current = rows.length
}, [finalRows, displayedRows])
```

- [ ] **Step 3: 重置计数器**

在组件的 reset 逻辑中（当 result 或 streamingChunks 变为 null 时），重置计数器：

```tsx
// 在现有的 reset useEffect 中添加
animatedCountRef.current = 0
```

找到现有的 reset useEffect（约 lines 87-95），在其中添加这行。

- [ ] **Step 4: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/generate/ProcessPanel.tsx
git commit -m "fix(process): GSAP animation only applies to newly added rows"
```

---

### Task 10: 添加流式自动滚动

**Files:**
- Modify: `frontend/src/components/generate/ProcessPanel.tsx:268`

- [ ] **Step 1: 添加滚动相关 refs**

在 ProcessPanel 的 ref 声明区域添加：

```tsx
const userScrolledRef = useRef(false)
```

- [ ] **Step 2: 添加 scrollToBottom 函数**

在 `kickTyping` 函数附近添加：

```tsx
const scrollToBottom = useCallback(() => {
  if (userScrolledRef.current) return
  const el = tableRef.current
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}, [])
```

- [ ] **Step 3: 添加 scroll 事件监听**

添加一个 useEffect 来监听滚动事件，检测用户是否手动滚动：

```tsx
useEffect(() => {
  const el = tableRef.current
  if (!el) return

  const handleScroll = () => {
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    if (atBottom) userScrolledRef.current = false
  }

  el.addEventListener('scroll', handleScroll, { passive: true })
  return () => el.removeEventListener('scroll', handleScroll)
}, [])

// 重置 userScrolled 状态（新流式开始时）
useEffect(() => {
  if (streamingChunks) {
    userScrolledRef.current = false
  }
}, [streamingChunks])
```

- [ ] **Step 4: 在打字机完成一行后调用 scrollToBottom**

找到 `typeRow` 函数中一行打字完成的位置（约 line 143，`setDisplayedRows(prev => [...prev, row])` 之后），添加：

```tsx
setDisplayedRows(prev => [...prev, row])
setTimeout(scrollToBottom, 50)  // 等 DOM 更新后滚动
```

- [ ] **Step 5: 在 typing row 输入字符时也滚动**

找到 `typeField` 函数中设置 typingText 的位置（约 line 120），在 setTimeout 回调中添加：

```tsx
setTypingText(text.slice(0, i + 1))
scrollToBottom()
```

- [ ] **Step 6: 在 scroll 容器上添加 onScroll 标记用户手动滚动**

修改 scroll 容器 div（line 268），添加 onScroll：

```tsx
<div
  ref={tableRef}
  className="flex-1 min-h-0 rounded-2xl border border-slate-200 overflow-y-auto overflow-x-hidden bg-white"
  onScroll={() => {
    const el = tableRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    userScrolledRef.current = !atBottom
  }}
>
```

- [ ] **Step 7: 验证**

运行 `npx tsc --noEmit`。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/generate/ProcessPanel.tsx
git commit -m "fix(process): add auto-scroll to bottom during streaming output"
```

---

### Task 11: 最终验证 + 提交

- [ ] **Step 1: TypeScript 编译检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：0 errors

- [ ] **Step 2: Vite 构建检查**

```bash
cd frontend && npx vite build
```

预期：构建成功，无错误

- [ ] **Step 3: 功能验证清单**

手动验证以下功能：
- [ ] Ctrl+滚轮仅缩放图片，不影响工具栏和侧栏
- [ ] 拖拽图片可平移
- [ ] 点击"+"弹窗添加自定义标注类型
- [ ] 右侧栏可拖拽调整宽度
- [ ] 右侧栏可折叠/展开
- [ ] 标注分类可折叠/展开
- [ ] 审阅面板显示零件名称、毛坯类型、图号
- [ ] 流式输出已有行不闪烁
- [ ] 流式输出自动滚动到底部
