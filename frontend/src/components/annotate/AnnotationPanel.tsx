import { useCallback, useEffect, useRef, useState, useImperativeHandle, forwardRef } from 'react'
import type { AnnotationShape, AnnotationLabel, AnnotationPage } from '../../types/annotate'
import { BUILT_IN_LABELS, CUSTOM_LABEL_COLORS, LABEL_DISPLAY_NAMES } from '../../types/annotate'
import { useDebounce } from '../../hooks/useDebounce'
import { AnnotationToolbar } from './AnnotationToolbar'
import { LabelTree } from './LabelTree'
import AddLabelModal from './AddLabelModal'
import { getAnnotations, saveAnnotation, exportAnnotations } from '../../api/client'

interface Props {
  taskId: string
  previewImages: string[]
  getAssetUrl: (filename: string) => string
  onClose?: () => void
}

export interface AnnotationPanelHandle {
  saveAndClose: () => Promise<void>
}

const CUSTOM_LABELS_KEY = 'annotate.customLabels.v1'
const MIN_SHAPE_SIZE = 6

export const AnnotationPanel = forwardRef<AnnotationPanelHandle, Props>(
function AnnotationPanel({ taskId, previewImages, getAssetUrl, onClose }, ref) {
  // Labels
  const [customLabels, setCustomLabels] = useState<AnnotationLabel[]>(() => {
    try {
      const raw = localStorage.getItem(CUSTOM_LABELS_KEY)
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })
  const allLabels = [...BUILT_IN_LABELS, ...customLabels]
  const [activeLabel, setActiveLabel] = useState(BUILT_IN_LABELS[0].name)
  const [showAddModal, setShowAddModal] = useState(false)

  const handleAddLabel = (label: AnnotationLabel) => {
    setCustomLabels(prev => [...prev, label])
  }

  const handleDeleteLabel = (name: string) => {
    setCustomLabels(prev => prev.filter(l => l.name !== name))
    if (activeLabel === name) {
      setActiveLabel(allLabels[0]?.name || '')
    }
  }

  // Pages
  const [pageNumber, setPageNumber] = useState(1)
  const [allPages, setAllPages] = useState<Record<number, AnnotationPage>>({})
  const totalPages = previewImages.length || 1

  // Zoom
  const [zoom, setZoom] = useState(1)
  const zoomRef = useRef(zoom)
  useEffect(() => { zoomRef.current = zoom }, [zoom])
  const scrollRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const [imgNatural, setImgNatural] = useState({ w: 0, h: 0 })

  // Pan state
  const [isPanning, setIsPanning] = useState(false)
  const panStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })
  const isDrawingRef = useRef(false)

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null)
  const [drawCurrent, setDrawCurrent] = useState<{ x: number; y: number } | null>(null)

  // Selection
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Sidebar
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

  // Auto-save debounce
  const currentPage = allPages[pageNumber]
  const debouncedShapes = useDebounce(currentPage?.shapes || [], 1000)

  // Current shapes helper
  const shapes = currentPage?.shapes || []

  // Load annotations from backend on mount
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await getAnnotations(taskId)
        if (cancelled) return
        const loaded: Record<number, AnnotationPage> = {}
        for (const [pg, ann] of Object.entries(data)) {
          const pageNum = Number(pg)
          loaded[pageNum] = {
            pageNumber: pageNum,
            shapes: (ann.shapes || []).map(s => ({
              id: crypto.randomUUID(),
              label: s.label,
              x: s.points[0][0],
              y: s.points[0][1],
              width: s.points[1][0] - s.points[0][0],
              height: s.points[1][1] - s.points[0][1],
            })),
            imageWidth: ann.imageWidth || 0,
            imageHeight: ann.imageHeight || 0,
            imagePath: ann.imagePath || '',
          }
        }
        if (Object.keys(loaded).length > 0) {
          setAllPages(loaded)
        }
      } catch {
        // No saved annotations yet — that's fine
      }
    })()
    return () => { cancelled = true }
  }, [taskId])

  // Ensure current page exists in allPages
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

  // Auto-save effect (debounced) — persist to backend
  useEffect(() => {
    if (!imgNatural.w || !imgNatural.h) return
    if (debouncedShapes.length === 0 && (!currentPage || currentPage.shapes.length > 0)) return
    saveAnnotation(taskId, {
      page: pageNumber,
      shapes: debouncedShapes.map(s => ({
        label: s.label,
        points: [[s.x, s.y], [s.x + s.width, s.y + s.height]],
        shape_type: 'rectangle',
      })),
      imageWidth: imgNatural.w,
      imageHeight: imgNatural.h,
      imagePath: previewImages[pageNumber - 1] || `page_${pageNumber}.png`,
    }).catch(() => {/* save failed silently */})
  }, [debouncedShapes, pageNumber, imgNatural, currentPage, taskId, previewImages])

  // Save-and-close handler (called by parent via ref on exit)
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
    isDrawingRef.current = true
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
    isDrawingRef.current = false
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

  // Sidebar resize
  const handleSidebarResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isResizingRef.current = true

    const onMove = (ev: MouseEvent) => {
      if (!isResizingRef.current) return
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

  // Zoom controls
  const handleZoomIn = useCallback(() => setZoom(z => Math.min(z * 1.25, 8)), [])
  const handleZoomOut = useCallback(() => setZoom(z => Math.max(z / 1.25, 0.05)), [])
  const handleZoom100 = useCallback(() => setZoom(1), [])
  const handleZoomFit = useCallback(() => {
    const scroll = scrollRef.current
    const img = imgRef.current
    if (!scroll || !img?.naturalWidth) return
    const fitW = (scroll.clientWidth - 32) / img.naturalWidth
    const fitH = (scroll.clientHeight - 32) / img.naturalHeight
    setZoom(Math.min(fitW, fitH))
  }, [])

  // Pan handlers
  const handlePanStart = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0 || isDrawingRef.current) return
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

  // Wheel zoom — cursor-anchored, ref-based to avoid stale closures
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
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const handler = (e: WheelEvent) => handleWheelRef.current(e)
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [])

  // Page navigation
  const handlePrevPage = useCallback(() => {
    if (pageNumber > 1) setPageNumber(p => p - 1)
  }, [pageNumber])
  const handleNextPage = useCallback(() => {
    if (pageNumber < totalPages) setPageNumber(p => p + 1)
  }, [pageNumber, totalPages])

  // Export — download annotation ZIP from backend
  const handleExport = useCallback(async () => {
    try {
      const blob = await exportAnnotations(taskId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `annotations_${taskId}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Annotation export failed:', err)
    }
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
        onAddLabel={() => setShowAddModal(true)}
        onDeleteLabel={handleDeleteLabel}
        canDeleteLabel={(name) => !BUILT_IN_LABELS.some(l => l.name === name)}
      />

      <div className="flex-1 min-h-0 flex">
        {/* Canvas area */}
        <div
          ref={scrollRef}
          className={`flex-1 min-w-0 overflow-auto flex items-start justify-center p-6 anno-grid-bg ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
          onMouseDown={handlePanStart}
          onMouseMove={handlePanMove}
          onMouseUp={handlePanEnd}
          onMouseLeave={handlePanEnd}
        >
          {currentImageUrl ? (
            <div className="anno-canvas-wrap">
              <img
                ref={imgRef}
                src={currentImageUrl}
                alt={`Page ${pageNumber}`}
                style={{ width: displayW, height: displayH, maxWidth: 'none' }}
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
                  const dash = label?.borderStyle === '6,3' ? '6,3' : undefined

                  // Compute sequence number (how many shapes of this label type come before this one)
                  let seq = 0
                  for (let j = 0; j < shapes.indexOf(shape); j++) {
                    if (shapes[j].label === shape.label) seq++
                  }
                  seq++ // 1-based
                  const displayName = LABEL_DISPLAY_NAMES[shape.label] || shape.label
                  const tagText = `${displayName} ${seq}`

                  // Font/tag sizing
                  const fontSize = isSelected ? 12 : 10
                  const tagH = isSelected ? 22 : 18
                  const tagW = Math.max(isSelected ? 56 : 44, tagText.length * (fontSize * 0.7) + 12)
                  const tagX = shape.x
                  const tagY = Math.max(shape.y - tagH - 4, 2)

                  return (
                    <g key={shape.id} onClick={(e) => handleShapeClick(shape.id, e)}>
                      {/* Selection halo */}
                      {isSelected && (
                        <>
                          <rect
                            x={shape.x - 6} y={shape.y - 6}
                            width={shape.width + 12} height={shape.height + 12}
                            fill="none" stroke="#ffffff" strokeWidth={6} rx={4}
                          />
                          <rect
                            x={shape.x - 6} y={shape.y - 6}
                            width={shape.width + 12} height={shape.height + 12}
                            fill="none" stroke="#111827" strokeWidth={2.5}
                            strokeDasharray="6 4" rx={4}
                          />
                        </>
                      )}

                      {/* Bounding rect */}
                      <rect
                        x={shape.x} y={shape.y}
                        width={shape.width} height={shape.height}
                        fill={isSelected ? `${color}55` : `${color}22`}
                        stroke={color}
                        strokeWidth={isSelected ? 3 : 2}
                        strokeDasharray={dash}
                      />

                      {/* Label tag background */}
                      <rect
                        x={tagX} y={tagY}
                        width={tagW} height={tagH}
                        fill={isSelected ? color : `${color}cc`}
                        rx={3}
                      />

                      {/* Label tag text */}
                      <text
                        x={tagX + tagW / 2}
                        y={tagY + tagH / 2 + fontSize * 0.35}
                        textAnchor="middle"
                        fill="#ffffff"
                        fontSize={fontSize}
                        fontWeight={isSelected ? 700 : 600}
                        fontFamily="sans-serif"
                        style={{ pointerEvents: 'none', userSelect: 'none' }}
                      >
                        {tagText}
                      </text>

                      {/* Tooltip */}
                      <title>{tagText}</title>
                    </g>
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
                labels={allLabels}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onDelete={handleDeleteShape}
                onRename={handleRenameShape}
              />
            </div>

            {/* 提示 */}
            <div className="px-3 py-2 border-t border-slate-200">
              <p className="text-[10px] text-slate-400 leading-relaxed">
                选择标签 → 在图片上拖拽绘制矩形
                <br />双击标签名可重命名
              </p>
            </div>
          </div>
        )}
      </div>

      {showAddModal && (
        <AddLabelModal
          onAdd={handleAddLabel}
          onClose={() => setShowAddModal(false)}
          existingNames={allLabels.map(l => l.name)}
        />
      )}
    </div>
  )
}
)
