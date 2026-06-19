# React 前端功能补齐实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对齐 H5 前端功能，补齐 React 前端缺失的标注工具、导出弹窗、配置页、批处理上传、SSE 补全、DB 锁定机制

**Architecture:** 标注工具作为 GeneratePage 第三个 Tab 内嵌，导出弹窗为共享组件，配置页为独立第 5 个页面。先搭 UI 壳子（mock 数据），用户测评后再接入后端 API。

**Tech Stack:** React 18 + TypeScript + Vite 6 + Tailwind CSS 3 + GSAP 3

**约束:** 不可修改 `updated_front/` 和 `backend/`，保持暗色玻璃态风格

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| **新增** | `src/types/annotate.ts` | 标注相关类型 |
| **新增** | `src/hooks/useDebounce.ts` | 通用 debounce hook |
| **新增** | `src/components/annotate/AnnotationPanel.tsx` | 标注工具主体 |
| **新增** | `src/components/annotate/AnnotationToolbar.tsx` | 标注工具栏 |
| **新增** | `src/components/annotate/LabelTree.tsx` | 标签树侧栏 |
| **新增** | `src/components/shared/ExportModal.tsx` | 导出弹窗 |
| **新增** | `src/pages/SettingsPage.tsx` | 配置页 |
| **修改** | `src/pages/GeneratePage.tsx` | 新增标注 Tab + 导出弹窗集成 |
| **修改** | `src/pages/ZipPage.tsx` | 多文件上传支持 |
| **修改** | `src/pages/DbPage.tsx` | 锁定机制 |
| **修改** | `src/App.tsx` | 新增 SettingsPage 路由 |
| **修改** | `src/components/layout/Sidebar.tsx` | 新增设置导航项 |
| **修改** | `src/api/client.ts` | 补全 annotation/config/batch API |
| **修改** | `src/types/index.ts` | 新增 PageId 'settings' |
| **修改** | `src/index.css` | 标注工具样式 |

---

## Task 1: 标注工具 — 类型与基础设施

**Files:**
- Create: `src/types/annotate.ts`
- Create: `src/hooks/useDebounce.ts`
- Modify: `src/index.css`
- Modify: `src/types/index.ts`

- [ ] **Step 1: 创建标注类型定义**

```typescript
// src/types/annotate.ts

export interface AnnotationShape {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
}

export interface AnnotationPage {
  pageNumber: number
  shapes: AnnotationShape[]
  imageWidth: number
  imageHeight: number
  imagePath: string
}

export interface AnnotationLabel {
  name: string
  color: string
  borderStyle: string
  isCustom: boolean
}

export const BUILT_IN_LABELS: AnnotationLabel[] = [
  { name: 'chamfer',       color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'threaded_hole', color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'circle_hole',   color: '#10b981', borderStyle: 'solid', isCustom: false },
]

export const CUSTOM_LABEL_COLORS = ['#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4']

export const LABEL_DISPLAY_NAMES: Record<string, string> = {
  chamfer: '倒角',
  threaded_hole: '螺纹孔',
  circle_hole: '圆孔',
}
```

- [ ] **Step 2: 创建 debounce hook**

```typescript
// src/hooks/useDebounce.ts

import { useEffect, useState } from 'react'

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
```

- [ ] **Step 3: 添加标注工具 CSS**

在 `src/index.css` 的 `@layer components` 块末尾（`}` 之前）添加：

```css
  /* ── Annotation Tool ── */
  .anno-canvas-wrap {
    position: relative;
    display: inline-block;
    line-height: 0;
  }
  .anno-svg {
    position: absolute;
    top: 0;
    left: 0;
    cursor: crosshair;
  }
  .anno-rect {
    fill: rgba(249, 115, 22, 0.08);
    stroke-width: 2;
    transition: fill 0.1s;
  }
  .anno-rect:hover {
    fill: rgba(249, 115, 22, 0.15);
  }
  .anno-rect.selected {
    fill: rgba(249, 115, 22, 0.18);
    stroke-dasharray: none;
    filter: drop-shadow(0 0 6px rgba(249, 115, 22, 0.4));
  }
  .anno-temp-rect {
    fill: rgba(249, 115, 22, 0.1);
    stroke: #f97316;
    stroke-width: 2;
    stroke-dasharray: 6 3;
  }
```

- [ ] **Step 4: 扩展 PageId 类型**

修改 `src/types/index.ts` 最后一行：

```typescript
// Before
export type PageId = 'generate' | 'zip' | 'history' | 'db'

// After
export type PageId = 'generate' | 'zip' | 'history' | 'db' | 'settings'
```

- [ ] **Step 5: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/annotate.ts frontend/src/hooks/useDebounce.ts frontend/src/types/index.ts frontend/src/index.css
git commit -m "feat(annotate): 标注工具类型定义、debounce hook、基础 CSS"
```

---

## Task 2: 标注工具 — AnnotationToolbar 组件

**Files:**
- Create: `src/components/annotate/AnnotationToolbar.tsx`

- [ ] **Step 1: 创建 AnnotationToolbar**

```tsx
// src/components/annotate/AnnotationToolbar.tsx

import type { AnnotationLabel } from '../../types/annotate'

interface Props {
  labels: AnnotationLabel[]
  activeLabel: string
  onLabelChange: (name: string) => void
  zoom: number
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomFit: () => void
  onZoom100: () => void
  pageNumber: number
  totalPages: number
  onPrevPage: () => void
  onNextPage: () => void
  shapeCount: number
  onExport: () => void
}

export function AnnotationToolbar({
  labels, activeLabel, onLabelChange,
  zoom, onZoomIn, onZoomOut, onZoomFit, onZoom100,
  pageNumber, totalPages, onPrevPage, onNextPage,
  shapeCount, onExport,
}: Props) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-200/60 bg-white/40 backdrop-blur-sm rounded-t-xl flex-wrap">
      {/* Label buttons */}
      <div className="flex items-center gap-1.5">
        {labels.map(label => (
          <button
            key={label.name}
            onClick={() => onLabelChange(label.name)}
            className={`
              px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all duration-150
              ${activeLabel === label.name
                ? 'text-white shadow-sm'
                : 'bg-white/60 text-slate-600 border-slate-200/60 hover:border-slate-300'}
            `}
            style={activeLabel === label.name ? {
              background: label.color,
              borderColor: label.color,
              boxShadow: `0 2px 8px ${label.color}40`,
            } : undefined}
          >
            {label.name === 'chamfer' ? '倒角' :
             label.name === 'threaded_hole' ? '螺纹孔' :
             label.name === 'circle_hole' ? '圆孔' : label.name}
          </button>
        ))}
      </div>

      <div className="w-px h-5 bg-slate-200/60" />

      {/* Zoom controls */}
      <div className="flex items-center gap-1">
        <button onClick={onZoomOut} className="btn btn-ghost !px-2 !py-1 !text-[11px]" title="缩小">−</button>
        <span className="text-[11px] font-mono text-slate-500 w-10 text-center">{Math.round(zoom * 100)}%</span>
        <button onClick={onZoomIn} className="btn btn-ghost !px-2 !py-1 !text-[11px]" title="放大">+</button>
        <button onClick={onZoomFit} className="btn btn-ghost !px-2 !py-1 !text-[11px]" title="适应窗口">适应</button>
        <button onClick={onZoom100} className="btn btn-ghost !px-2 !py-1 !text-[11px]" title="100%">1:1</button>
      </div>

      <div className="w-px h-5 bg-slate-200/60" />

      {/* Page navigation */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={onPrevPage}
          disabled={pageNumber <= 1}
          className="btn btn-ghost !px-2 !py-1 !text-[11px]"
        >‹</button>
        <span className="text-[11px] text-slate-500">{pageNumber} / {totalPages}</span>
        <button
          onClick={onNextPage}
          disabled={pageNumber >= totalPages}
          className="btn btn-ghost !px-2 !py-1 !text-[11px]"
        >›</button>
      </div>

      <div className="flex-1" />

      {/* Shape count + Export */}
      <span className="text-[11px] text-slate-400">{shapeCount} 个标注</span>
      <button onClick={onExport} className="btn btn-ghost !px-3 !py-1 !text-[11px]">
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          导出
        </span>
      </button>
    </div>
  )
}
```

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/annotate/AnnotationToolbar.tsx
git commit -m "feat(annotate): AnnotationToolbar 组件"
```

---

## Task 3: 标注工具 — LabelTree 组件

**Files:**
- Create: `src/components/annotate/LabelTree.tsx`

- [ ] **Step 1: 创建 LabelTree**

```tsx
// src/components/annotate/LabelTree.tsx

import { useState } from 'react'
import type { AnnotationShape, AnnotationLabel } from '../../types/annotate'
import { LABEL_DISPLAY_NAMES } from '../../types/annotate'

interface Props {
  shapes: AnnotationShape[]
  labels: AnnotationLabel[]
  selectedId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onRename: (id: string, newLabel: string) => void
}

export function LabelTree({ shapes, labels, selectedId, onSelect, onDelete, onRename }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const grouped = new Map<string, AnnotationShape[]>()
  for (const s of shapes) {
    const arr = grouped.get(s.label) || []
    arr.push(s)
    grouped.set(s.label, arr)
  }

  const toggleCollapse = (label: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      next.has(label) ? next.delete(label) : next.add(label)
      return next
    })
  }

  const startRename = (shape: AnnotationShape) => {
    setEditingId(shape.id)
    setEditValue(shape.label)
  }

  const commitRename = (id: string) => {
    if (editValue.trim()) onRename(id, editValue.trim())
    setEditingId(null)
  }

  const getLabelColor = (name: string) =>
    labels.find(l => l.name === name)?.color || '#94a3b8'

  if (shapes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400 text-[12px] gap-2">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 9l6 6m0-6l-6 6" />
        </svg>
        <span>暂无标注</span>
        <span className="text-[11px] text-slate-300">选择标签后在图片上绘制</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-0.5 overflow-auto p-2">
      {Array.from(grouped.entries()).map(([label, items]) => (
        <div key={label}>
          {/* Parent node */}
          <button
            onClick={() => toggleCollapse(label)}
            className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg text-[11px] font-semibold text-slate-600 hover:bg-slate-100/60 transition-colors"
          >
            <span className="text-[10px] text-slate-400 transition-transform duration-150" style={{
              transform: collapsed.has(label) ? 'rotate(-90deg)' : 'rotate(0deg)',
            }}>▼</span>
            <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: getLabelColor(label) }} />
            <span className="flex-1 text-left">{LABEL_DISPLAY_NAMES[label] || label}</span>
            <span className="text-[10px] text-slate-400">{items.length}</span>
          </button>

          {/* Children */}
          {!collapsed.has(label) && items.map(shape => (
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
                  {LABEL_DISPLAY_NAMES[shape.label] || shape.label}
                </span>
              )}

              <button
                onClick={e => { e.stopPropagation(); onDelete(shape.id) }}
                className="shrink-0 w-5 h-5 flex items-center justify-center rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors text-[13px]"
              >×</button>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/annotate/LabelTree.tsx
git commit -m "feat(annotate): LabelTree 标签树组件"
```

---

## Task 4: 标注工具 — AnnotationPanel 主体

**Files:**
- Create: `src/components/annotate/AnnotationPanel.tsx`

- [ ] **Step 1: 创建 AnnotationPanel**

```tsx
// src/components/annotate/AnnotationPanel.tsx

import { useCallback, useEffect, useRef, useState } from 'react'
import type { AnnotationShape, AnnotationLabel, AnnotationPage } from '../../types/annotate'
import { BUILT_IN_LABELS, CUSTOM_LABEL_COLORS } from '../../types/annotate'
import { useDebounce } from '../../hooks/useDebounce'
import { AnnotationToolbar } from './AnnotationToolbar'
import { LabelTree } from './LabelTree'

interface Props {
  taskId: string
  previewImages: string[]
  getAssetUrl: (filename: string) => string
}

const CUSTOM_LABELS_KEY = 'annotate.customLabels.v1'
const MIN_SHAPE_SIZE = 6

export function AnnotationPanel({ taskId, previewImages, getAssetUrl }: Props) {
  // Labels
  const [customLabels, setCustomLabels] = useState<AnnotationLabel[]>(() => {
    try {
      const raw = localStorage.getItem(CUSTOM_LABELS_KEY)
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })
  const allLabels = [...BUILT_IN_LABELS, ...customLabels]
  const [activeLabel, setActiveLabel] = useState(BUILT_IN_LABELS[0].name)

  // Pages
  const [pageNumber, setPageNumber] = useState(1)
  const [allPages, setAllPages] = useState<Record<number, AnnotationPage>>({})
  const totalPages = previewImages.length || 1

  // Zoom
  const [zoom, setZoom] = useState(1)
  const scrollRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const [imgNatural, setImgNatural] = useState({ w: 0, h: 0 })

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null)
  const [drawCurrent, setDrawCurrent] = useState<{ x: number; y: number } | null>(null)

  // Selection
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Auto-save debounce
  const currentPage = allPages[pageNumber]
  const debouncedShapes = useDebounce(currentPage?.shapes || [], 1000)

  // Current shapes helper
  const shapes = currentPage?.shapes || []

  // Load annotations on mount (mock — no API call yet)
  useEffect(() => {
    if (!allPages[pageNumber]) {
      setAllPages(prev => ({
        ...prev,
        [pageNumber]: {
          pageNumber,
          shapes: [],
          imageWidth: imgNatural.w,
          imageHeight: imgNatural.h,
          imagePath: previewImages[pageNumber - 1] || '',
        }
      }))
    }
  }, [pageNumber, previewImages, imgNatural, allPages])

  // Auto-save effect (debounced)
  useEffect(() => {
    if (debouncedShapes.length > 0 || currentPage?.shapes?.length === 0) {
      // Mock: log save. Real API call will be added later.
      console.log(`[annotate] auto-save page ${pageNumber}: ${debouncedShapes.length} shapes`)
    }
  }, [debouncedShapes, pageNumber, currentPage?.shapes?.length])

  // Image load handler
  const handleImageLoad = useCallback(() => {
    const img = imgRef.current
    if (img) {
      setImgNatural({ w: img.naturalWidth, h: img.naturalHeight })
    }
  }, [])

  // Coordinate transforms
  const toReal = useCallback((displayX: number, displayY: number) => ({
    x: displayX / zoom,
    y: displayY / zoom,
  }), [zoom])

  // Drawing handlers
  const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    setIsDrawing(true)
    setDrawStart({ x, y })
    setDrawCurrent({ x, y })
    setSelectedId(null)
  }, [])

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return
    const rect = e.currentTarget.getBoundingClientRect()
    setDrawCurrent({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    })
  }, [isDrawing])

  const handleMouseUp = useCallback(() => {
    if (!isDrawing || !drawStart || !drawCurrent) return
    setIsDrawing(false)

    const w = Math.abs(drawCurrent.x - drawStart.x)
    const h = Math.abs(drawCurrent.y - drawStart.y)
    if (w < MIN_SHAPE_SIZE || h < MIN_SHAPE_SIZE) return

    const topLeft = toReal(
      Math.min(drawStart.x, drawCurrent.x),
      Math.min(drawStart.y, drawCurrent.y),
    )
    const size = toReal(w, h)

    const newShape: AnnotationShape = {
      id: crypto.randomUUID(),
      label: activeLabel,
      x: topLeft.x,
      y: topLeft.y,
      width: size.x,
      height: size.y,
    }

    setAllPages(prev => {
      const page = prev[pageNumber] || {
        pageNumber, shapes: [], imageWidth: imgNatural.w, imageHeight: imgNatural.h, imagePath: '',
      }
      return {
        ...prev,
        [pageNumber]: { ...page, shapes: [...page.shapes, newShape] },
      }
    })

    setDrawStart(null)
    setDrawCurrent(null)
    setSelectedId(newShape.id)
  }, [isDrawing, drawStart, drawCurrent, activeLabel, pageNumber, imgNatural, toReal])

  // Shape interaction
  const handleShapeClick = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedId(id)
  }, [])

  const handleDeleteShape = useCallback((id: string) => {
    setAllPages(prev => {
      const page = prev[pageNumber]
      if (!page) return prev
      return {
        ...prev,
        [pageNumber]: { ...page, shapes: page.shapes.filter(s => s.id !== id) },
      }
    })
    if (selectedId === id) setSelectedId(null)
  }, [pageNumber, selectedId])

  const handleRenameShape = useCallback((id: string, newLabel: string) => {
    // Register as custom label if not exists
    if (!allLabels.find(l => l.name === newLabel)) {
      const newCustom: AnnotationLabel = {
        name: newLabel,
        color: CUSTOM_LABEL_COLORS[customLabels.length % CUSTOM_LABEL_COLORS.length],
        borderStyle: 'solid',
        isCustom: true,
      }
      const updated = [...customLabels, newCustom]
      setCustomLabels(updated)
      localStorage.setItem(CUSTOM_LABELS_KEY, JSON.stringify(updated))
    }

    setAllPages(prev => {
      const page = prev[pageNumber]
      if (!page) return prev
      return {
        ...prev,
        [pageNumber]: {
          ...page,
          shapes: page.shapes.map(s => s.id === id ? { ...s, label: newLabel } : s),
        },
      }
    })
  }, [allLabels, customLabels, pageNumber])

  // Zoom controls
  const handleZoomIn = useCallback(() => setZoom(z => Math.min(z + 0.2, 8)), [])
  const handleZoomOut = useCallback(() => setZoom(z => Math.max(z - 0.2, 0.05)), [])
  const handleZoom100 = useCallback(() => setZoom(1), [])
  const handleZoomFit = useCallback(() => {
    const scroll = scrollRef.current
    const img = imgRef.current
    if (!scroll || !img?.naturalWidth) return
    const fitW = (scroll.clientWidth - 32) / img.naturalWidth
    const fitH = (scroll.clientHeight - 32) / img.naturalHeight
    setZoom(Math.min(fitW, fitH, 1))
  }, [])

  // Wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!e.ctrlKey) return
    e.preventDefault()
    const delta = e.deltaY > 0 ? -0.1 : 0.1
    setZoom(z => Math.min(Math.max(z + delta, 0.05), 8))
  }, [])

  // Page navigation
  const handlePrevPage = useCallback(() => {
    if (pageNumber > 1) setPageNumber(p => p - 1)
  }, [pageNumber])
  const handleNextPage = useCallback(() => {
    if (pageNumber < totalPages) setPageNumber(p => p + 1)
  }, [pageNumber, totalPages])

  // Export (mock)
  const handleExport = useCallback(() => {
    console.log('[annotate] export requested for task', taskId)
  }, [taskId])

  // Display dimensions
  const displayW = imgNatural.w * zoom
  const displayH = imgNatural.h * zoom

  // SVG draw rect in display coords
  const drawRect = isDrawing && drawStart && drawCurrent ? {
    x: Math.min(drawStart.x, drawCurrent.x),
    y: Math.min(drawStart.y, drawCurrent.y),
    w: Math.abs(drawCurrent.x - drawStart.x),
    h: Math.abs(drawCurrent.y - drawStart.y),
  } : null

  const currentImageUrl = previewImages[pageNumber - 1]
    ? getAssetUrl(previewImages[pageNumber - 1])
    : ''

  return (
    <div className="flex flex-col h-full min-h-0">
      <AnnotationToolbar
        labels={allLabels}
        activeLabel={activeLabel}
        onLabelChange={setActiveLabel}
        zoom={zoom}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onZoomFit={handleZoomFit}
        onZoom100={handleZoom100}
        pageNumber={pageNumber}
        totalPages={totalPages}
        onPrevPage={handlePrevPage}
        onNextPage={handleNextPage}
        shapeCount={shapes.length}
        onExport={handleExport}
      />

      <div className="flex-1 min-h-0 flex">
        {/* Canvas area */}
        <div
          ref={scrollRef}
          className="flex-1 min-w-0 overflow-auto flex items-center justify-center p-4 bg-slate-50/40"
          onWheel={handleWheel}
        >
          {currentImageUrl ? (
            <div className="anno-canvas-wrap">
              <img
                ref={imgRef}
                src={currentImageUrl}
                alt={`Page ${pageNumber}`}
                style={{ width: displayW, height: displayH }}
                onLoad={handleImageLoad}
                draggable={false}
              />
              <svg
                className="anno-svg"
                width={displayW}
                height={displayH}
                viewBox={`0 0 ${imgNatural.w} ${imgNatural.h}`}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                {shapes.map(shape => {
                  const label = allLabels.find(l => l.name === shape.label)
                  const color = label?.color || '#94a3b8'
                  const isSelected = selectedId === shape.id
                  return (
                    <rect
                      key={shape.id}
                      x={shape.x}
                      y={shape.y}
                      width={shape.width}
                      height={shape.height}
                      className={`anno-rect ${isSelected ? 'selected' : ''}`}
                      stroke={color}
                      strokeDasharray={label?.borderStyle === '6,3' ? '6,3' : undefined}
                      onClick={(e) => handleShapeClick(shape.id, e)}
                    />
                  )
                })}

                {/* Temp drawing rect */}
                {drawRect && (
                  <rect
                    x={drawRect.x / zoom}
                    y={drawRect.y / zoom}
                    width={drawRect.w / zoom}
                    height={drawRect.h / zoom}
                    className="anno-temp-rect"
                  />
                )}
              </svg>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-slate-400 text-[12px]">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
              <span>等待图片加载</span>
            </div>
          )}
        </div>

        {/* Label tree sidebar */}
        <div className="w-[220px] shrink-0 border-l border-slate-200/60 bg-white/30 backdrop-blur-sm flex flex-col">
          <div className="px-3 py-2.5 border-b border-slate-200/60">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">标注列表</span>
          </div>
          <div className="flex-1 min-h-0 overflow-auto">
            <LabelTree
              shapes={shapes}
              labels={allLabels}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onDelete={handleDeleteShape}
              onRename={handleRenameShape}
            />
          </div>
          <div className="px-3 py-2 border-t border-slate-200/60">
            <p className="text-[10px] text-slate-400 leading-relaxed">
              选择标签 → 在图片上拖拽绘制矩形
              <br />双击标签名可重命名
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/annotate/AnnotationPanel.tsx
git commit -m "feat(annotate): AnnotationPanel 标注工具主体"
```

---

## Task 5: 标注工具 — 集成到 GeneratePage

**Files:**
- Modify: `src/pages/GeneratePage.tsx`

- [ ] **Step 1: 添加标注 Tab 到 GeneratePage**

修改 `src/pages/GeneratePage.tsx`：

1. 添加 import：

```typescript
import { AnnotationPanel } from '../components/annotate/AnnotationPanel'
```

2. 修改 `ActiveTab` 类型：

```typescript
// Before
type ActiveTab = 'review' | 'process'

// After
type ActiveTab = 'review' | 'process' | 'annotate'
```

3. 修改 Tab bar 中的 tabs 数组，在 `{ id: 'process' as ActiveTab, label: '工艺规程' }` 后面添加：

```typescript
{ id: 'annotate' as ActiveTab, label: '标注工具' },
```

4. 修改右侧内容区，将 `{activeTab === 'review' ? ... : ...}` 替换为三路条件：

```tsx
{activeTab === 'review' ? (
  <ReviewPanel
    reviewText={reviewText}
    onReviewTextChange={setReviewText}
    onConfirm={handleConfirmReview}
    onRerun={handleRerun}
    busy={busy}
    ocrThicknessHint={ocrThicknessHint || undefined}
  />
) : activeTab === 'annotate' ? (
  <AnnotationPanel
    taskId={taskId || ''}
    previewImages={previewUrls.map(u => {
      const parts = u.split('/')
      return parts[parts.length - 1]
    })}
    getAssetUrl={(filename) => taskId ? getAssetUrl(taskId, filename) : ''}
  />
) : (
  <ProcessPanel result={result} taskId={taskId} streamingChunks={streamingChunks} />
)}
```

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/GeneratePage.tsx
git commit -m "feat(annotate): 集成标注工具 Tab 到 GeneratePage"
```

---

## Task 6: 导出弹窗

**Files:**
- Create: `src/components/shared/ExportModal.tsx`
- Modify: `src/pages/GeneratePage.tsx`

- [ ] **Step 1: 创建 ExportModal 组件**

```tsx
// src/components/shared/ExportModal.tsx

import { useState } from 'react'
import type { TaskResult } from '../../types'

interface Props {
  taskId: string
  result: TaskResult
  onClose: () => void
}

export function ExportModal({ taskId, result, onClose }: Props) {
  const [downloading, setDownloading] = useState<string | null>(null)

  const previewUrl = result.preview_image_urls?.[0] || result.image_url || ''
  const processRows = result.process_flow?.data || []

  const handleDownload = async (format: 'pdf' | 'xlsx') => {
    try {
      setDownloading(format)
      const res = await fetch(`/api/export/${taskId}/download?format=${format}`)
      if (!res.ok) throw new Error(`Export failed: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${result.pdf_name || 'export'}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Modal card */}
      <div className="relative z-10 w-full max-w-3xl max-h-[85vh] flex flex-col card-solid overflow-hidden animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200/60 shrink-0">
          <div>
            <h2 className="text-[15px] font-bold text-slate-800">导出工艺文件</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">{result.pdf_name}</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >×</button>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-auto p-6 flex gap-5">
          {/* Preview image */}
          <div className="w-[280px] shrink-0">
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Preview"
                className="w-full rounded-xl border border-slate-200/60 object-contain bg-slate-50"
              />
            ) : (
              <div className="w-full h-[200px] rounded-xl border border-slate-200/60 bg-slate-50 flex items-center justify-center text-slate-400 text-[12px]">
                无预览图
              </div>
            )}

            {/* Info */}
            <div className="mt-3 flex flex-col gap-1.5">
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">页数</span>
                <span className="text-slate-600 font-medium">{result.total_pages || '-'}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">文件数</span>
                <span className="text-slate-600 font-medium">{result.file_count || '-'}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">模式</span>
                <span className="text-slate-600 font-medium">{result.upload_mode_label || result.upload_mode || '-'}</span>
              </div>
            </div>
          </div>

          {/* Process table preview */}
          <div className="flex-1 min-w-0">
            <h3 className="text-[12px] font-bold text-slate-500 uppercase tracking-wider mb-3">工序预览</h3>
            {processRows.length > 0 ? (
              <div className="overflow-auto max-h-[400px] rounded-xl border border-slate-200/60">
                <table className="data-table">
                  <thead>
                    <tr>
                      {(result.process_flow?.columns || ['标签编码', '工序内容']).map(col => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {processRows.map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => <td key={j}>{cell}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-slate-400 text-[12px]">
                暂无工序数据
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200/60 shrink-0">
          <button
            onClick={() => handleDownload('xlsx')}
            disabled={downloading !== null}
            className="btn btn-secondary"
          >
            {downloading === 'xlsx' ? '下载中...' : '下载 XLSX'}
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            disabled={downloading !== null}
            className="btn btn-primary"
          >
            {downloading === 'pdf' ? '下载中...' : '下载 PDF'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 在 GeneratePage 中集成导出弹窗**

修改 `src/pages/GeneratePage.tsx`：

1. 添加 import 和 state：

```typescript
import { ExportModal } from '../components/shared/ExportModal'

// 在组件内添加 state
const [showExport, setShowExport] = useState(false)
```

2. 在 ProcessPanel 的 props 区域，需要给 ProcessPanel 传递一个导出按钮触发。但 ProcessPanel 内部已有导出按钮。最简方案：在 completed 状态时，top bar 的重置按钮旁加一个"导出"按钮：

在 `{hasTask && (` 块内、重置按钮之前添加：

```tsx
{completed && result && (
  <button className="btn btn-ghost !text-[12px]" onClick={() => setShowExport(true)}>
    <span className="flex items-center gap-1.5">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      导出
    </span>
  </button>
)}
```

3. 在组件 return 的最后、`</div>` 之前添加弹窗渲染：

```tsx
{showExport && result && (
  <ExportModal taskId={taskId!} result={result} onClose={() => setShowExport(false)} />
)}
```

- [ ] **Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/shared/ExportModal.tsx frontend/src/pages/GeneratePage.tsx
git commit -m "feat(export): 导出弹窗组件及 GeneratePage 集成"
```

---

## Task 7: 配置页

**Files:**
- Create: `src/pages/SettingsPage.tsx`
- Modify: `src/App.tsx`
- Modify: `src/components/layout/Sidebar.tsx`
- Modify: `src/api/client.ts`

- [ ] **Step 1: 在 client.ts 添加配置 API**

在 `src/api/client.ts` 文件末尾添加：

```typescript
/* ── Config ── */

export interface SystemConfig {
  vision_api_key: string
  vision_api_base: string
  vision_model_id: string
  llm_api_key: string
  llm_base_url: string
  llm_model: string
  vision_mode: string
  poppler_path: string
  creo_exe: string
  creo_base_dir: string
  creo_out_dir: string
}

export async function getConfig(): Promise<SystemConfig> {
  return request<SystemConfig>('/config')
}

export async function updateConfig(payload: Partial<SystemConfig>): Promise<{ message: string }> {
  return request<{ message: string }>('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
```

- [ ] **Step 2: 创建 SettingsPage**

```tsx
// src/pages/SettingsPage.tsx

import { useCallback, useEffect, useRef, useState } from 'react'
import { getConfig, updateConfig, type SystemConfig } from '../api/client'
import gsap from 'gsap'

const CONFIG_GROUPS = [
  {
    title: '视觉模型配置',
    fields: [
      { key: 'vision_mode', label: '视觉模式', type: 'select', options: ['doubao', 'local'] },
      { key: 'vision_api_key', label: 'API Key', type: 'password' },
      { key: 'vision_api_base', label: 'API Base URL', type: 'text' },
      { key: 'vision_model_id', label: 'Model ID', type: 'text' },
    ] as const,
  },
  {
    title: 'LLM 配置',
    fields: [
      { key: 'llm_api_key', label: 'API Key', type: 'password' },
      { key: 'llm_base_url', label: 'Base URL', type: 'text' },
      { key: 'llm_model', label: 'Model', type: 'text' },
    ] as const,
  },
  {
    title: '路径配置',
    fields: [
      { key: 'poppler_path', label: 'Poppler 路径', type: 'text' },
      { key: 'creo_exe', label: 'Creo 可执行文件', type: 'text' },
      { key: 'creo_base_dir', label: 'Creo 基础目录', type: 'text' },
      { key: 'creo_out_dir', label: 'Creo 输出目录', type: 'text' },
    ] as const,
  },
]

export function SettingsPage() {
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getConfig()
      .then(c => { setConfig(c); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!loading && cardRef.current) {
      gsap.fromTo(cardRef.current,
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5, ease: 'power3.out' }
      )
    }
  }, [loading])

  const handleChange = useCallback((key: keyof SystemConfig, value: string) => {
    setConfig(prev => prev ? { ...prev, [key]: value } : prev)
  }, [])

  const handleSave = useCallback(async () => {
    if (!config) return
    setSaving(true)
    try {
      await updateConfig(config)
    } catch {
      // toast will be added in integration phase
    } finally {
      setSaving(false)
    }
  }, [config])

  const togglePassword = (key: string) => {
    setShowPasswords(prev => ({ ...prev, [key]: !prev[key] }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-[13px]">
        <div className="animate-spin w-5 h-5 border-2 border-slate-300 border-t-flame-500 rounded-full mr-3" />
        加载配置中...
      </div>
    )
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64 text-red-400 text-[13px]">
        加载配置失败
      </div>
    )
  }

  return (
    <div ref={cardRef} className="max-w-2xl">
      <div className="card-solid flex flex-col gap-6">
        {CONFIG_GROUPS.map(group => (
          <div key={group.title}>
            <h3 className="text-[13px] font-bold text-slate-700 mb-4 pb-2 border-b border-slate-200/60">
              {group.title}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {group.fields.map(field => (
                <div key={field.key} className="flex flex-col gap-1.5">
                  <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    {field.label}
                  </label>
                  {field.type === 'select' ? (
                    <select
                      value={config[field.key] || ''}
                      onChange={e => handleChange(field.key, e.target.value)}
                      className="h-10 px-3 rounded-xl border border-slate-200 bg-white text-[13px] text-slate-700 focus:border-flame-400 focus:ring-2 focus:ring-flame-100 outline-none transition-all"
                    >
                      {field.options.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <div className="relative">
                      <input
                        type={field.type === 'password' && !showPasswords[field.key] ? 'password' : 'text'}
                        value={config[field.key] || ''}
                        onChange={e => handleChange(field.key, e.target.value)}
                        className="w-full h-10 px-3 pr-10 rounded-xl border border-slate-200 bg-white text-[13px] text-slate-700 font-mono focus:border-flame-400 focus:ring-2 focus:ring-flame-100 outline-none transition-all"
                      />
                      {field.type === 'password' && (
                        <button
                          type="button"
                          onClick={() => togglePassword(field.key)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 rounded"
                        >
                          {showPasswords[field.key] ? '🙈' : '👁'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="flex justify-end pt-2 border-t border-slate-200/60">
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn-primary"
          >
            {saving ? '保存中...' : '保存配置'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 修改 App.tsx 添加 SettingsPage 路由**

1. 添加 import：

```typescript
import { SettingsPage } from './pages/SettingsPage'
```

2. 在 `PAGE_TITLES` 中添加：

```typescript
settings: { title: '系统配置', sub: '视觉模型、LLM 和路径配置' },
```

3. 在 page content 区域添加：

```tsx
{page === 'settings' && <SettingsPage />}
```

- [ ] **Step 4: 修改 Sidebar 添加设置导航项**

修改 `src/components/layout/Sidebar.tsx` 中的 `NAV_ITEMS` 数组，在 `db` 之后添加：

```typescript
{ id: 'settings', icon: '⚙', title: '系统配置', sub: '视觉模型、LLM 和路径配置' },
```

- [ ] **Step 5: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/SettingsPage.tsx frontend/src/App.tsx frontend/src/components/layout/Sidebar.tsx
git commit -m "feat(settings): 配置页 + API + 侧栏导航"
```

---

## Task 8: 批处理上传

**Files:**
- Modify: `src/api/client.ts`
- Modify: `src/pages/GeneratePage.tsx`

- [ ] **Step 1: 在 client.ts 添加批量上传 API**

在 `src/api/client.ts` 的 `uploadFile` 函数之后添加：

```typescript
export async function batchUpload(files: File[]): Promise<{
  batch_task_id: string
  file_count: number
  files: { task_id: string; pdf_name: string; prt_name: string }[]
  message: string
}> {
  const fd = new FormData()
  files.forEach(f => fd.append('files', f))
  const res = await fetch(`${BASE}/batch_upload`, { method: 'POST', body: fd })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || body.message || `Batch upload failed: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 2: 修改 GeneratePage 支持多文件**

修改 `src/pages/GeneratePage.tsx` 的 `handleUploadClick` 函数：

```typescript
const handleUploadClick = useCallback(() => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf,.png,.jpg,.jpeg,.dxf,.dwg,.prt'
  input.multiple = true
  input.onchange = () => {
    const files = input.files
    if (!files || files.length === 0) return
    if (files.length === 1) {
      handleFileSelected(files[0])
    } else {
      handleBatchSelected(Array.from(files))
    }
  }
  input.click()
}, [handleFileSelected])
```

在 `handleFileSelected` 之前添加 `handleBatchSelected` 函数：

```typescript
const handleBatchSelected = useCallback(async (files: File[]) => {
  try {
    setResult(null)
    setReviewText('')
    setStreamingChunks('')
    setPreviewUrls([])
    setProgress(0)
    setPhaseHint(`正在上传 ${files.length} 个文件...`)
    setStatus('processing')
    setFileName(files.map(f => f.name).join(', '))

    const { batch_task_id, files: uploaded } = await batchUpload(files)
    setTaskId(batch_task_id)
    setPhaseHint(`${uploaded.length} 个文件已上传，等待处理...`)

    esRef.current?.close()
    esRef.current = connectSSE(batch_task_id, {
      onStepStart(data) { setPhaseHint(String(data.message || '处理中...')) },
      onStepComplete(data) { setPhaseHint(String(data.message || '步骤完成')) },
      onLog(data) { setPhaseHint(String(data.message || '')) },
      onReviewRequired(data) {
        setReviewText(String(data.content || ''))
        setStatus('awaiting_review')
        setProgress(50)
        setPhaseHint('请审阅特征报告')
      },
      onProcessStream(data) {
        setStreamingChunks(prev => prev + String(data.chunk || ''))
      },
      onPreviewUpdated(data) {
        const urls = (data.preview_image_urls as string[]) || []
        if (urls.length) setPreviewUrls(urls)
      },
      async onComplete() {
        setStatus('completed')
        setProgress(100)
        setPhaseHint('处理完成！')
        try {
          const res = await getResult(batch_task_id)
          setResult(res as unknown as TaskResult)
          setActiveTab('process')
        } catch { /* already set */ }
      },
      onError(data) {
        setStatus('error')
        setPhaseHint(`错误：${String(data.message || '处理失败')}`)
        onError(String(data.message || '处理失败'))
      },
    })
  } catch (err: unknown) {
    setStatus('error')
    const msg = err instanceof Error ? err.message : '批量上传失败'
    setPhaseHint(`上传失败：${msg}`)
    onError(msg)
  }
}, [onError])
```

添加 `batchUpload` import：

```typescript
import { batchUpload, connectSSE, getAssetUrl, getResult, submitReview, uploadFile } from '../api/client'
```

- [ ] **Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/GeneratePage.tsx
git commit -m "feat(upload): 批处理上传支持"
```

---

## Task 9: annotation_required SSE 补全

**Files:**
- Modify: `src/api/client.ts`
- Modify: `src/pages/GeneratePage.tsx`

- [ ] **Step 1: 在 client.ts 添加 annotation_required SSE 处理**

修改 `src/api/client.ts` 的 `connectSSE` 函数，添加 `onAnnotationRequired` handler：

1. 在 handlers 接口中添加：

```typescript
onAnnotationRequired?: (data: Record<string, unknown>) => void
```

2. 在函数体中（`image_ready` listener 之后）添加：

```typescript
es.addEventListener('annotation_required', (e) => {
  const d = JSON.parse(e.data)
  handlers.onAnnotationRequired?.(d)
  handlers.onEvent?.('annotation_required', d)
})
```

- [ ] **Step 2: 在 GeneratePage 处理 annotation_required 事件**

修改 `src/pages/GeneratePage.tsx` 的 `connectSSE` 调用，添加 `onAnnotationRequired` handler：

```typescript
onAnnotationRequired(data) {
  setPhaseHint('检测到标注需求，请完成标注')
  setActiveTab('annotate')
},
```

- [ ] **Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/GeneratePage.tsx
git commit -m "feat(sse): 补全 annotation_required 事件处理"
```

---

## Task 10: DB 页锁定机制

**Files:**
- Modify: `src/pages/DbPage.tsx`

- [ ] **Step 1: 添加锁定状态检查**

在 `src/pages/DbPage.tsx` 组件函数开头（所有 state 声明之前）添加：

```typescript
const zipUnlocked = sessionStorage.getItem('zip_unlocked') === 'true'
const activeScope = sessionStorage.getItem('active_scope') || ''
```

- [ ] **Step 2: 添加 LockShell 组件**

在 `DbPage.tsx` 文件内（组件函数之前或之后）添加一个内部组件：

```tsx
function LockShell() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="card-solid max-w-md text-center p-8">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-100 flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
            <rect x="3" y="11" width="18" height="11" rx="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h3 className="text-[15px] font-bold text-slate-700 mb-2">数据库未解锁</h3>
        <p className="text-[12px] text-slate-400 mb-5">请先完成知识库导入操作后再浏览数据库</p>
        <div className="flex items-center justify-center gap-3">
          <a
            href="#"
            onClick={e => { e.preventDefault(); window.dispatchEvent(new CustomEvent('navigate', { detail: 'zip' })) }}
            className="btn btn-primary !text-[12px]"
          >前往导入</a>
          <button className="btn btn-secondary !text-[12px]">查看公共库</button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 在 DbPage 组件开头添加锁定判断**

在 `DbPage` 组件函数中、第一个 `useState` 之前添加：

```typescript
if (!zipUnlocked) {
  return <LockShell />
}
```

注意：由于 React hooks 不能在条件分支中调用，需要将这个检查移到所有 hooks 之后，或者用一个包装组件。最简方案：在所有 hooks 声明之后、return 之前添加：

```typescript
// 在所有 hooks 之后
if (!zipUnlocked) {
  return <LockShell />
}
```

- [ ] **Step 4: 在 ZipPage 导入成功后设置解锁标志**

修改 `src/pages/ZipPage.tsx`，找到导入成功后的处理逻辑，在设置结果的地方添加：

```typescript
sessionStorage.setItem('zip_unlocked', 'true')
sessionStorage.setItem('active_scope', report.target_library?.library_key || '')
```

具体位置：搜索 `setReport` 或 `setZipState` 相关的成功处理逻辑，在那里添加这两行。

- [ ] **Step 5: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/DbPage.tsx frontend/src/pages/ZipPage.tsx
git commit -m "feat(db): session-based 锁定机制"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: 6 个功能全部有对应 Task
- [x] **Placeholder scan**: 无 TBD/TODO，所有代码块完整
- [x] **Type consistency**: `AnnotationShape`, `AnnotationLabel`, `AnnotationPage` 在所有 Task 中一致
- [x] **Import paths**: 所有 import 路径与文件结构匹配
- [x] **API 函数命名**: `batchUpload`, `getConfig`, `updateConfig` 与 client.ts 现有风格一致
- [x] **CSS 类名**: 使用现有 `.card-solid`, `.btn`, `.data-table` 等
