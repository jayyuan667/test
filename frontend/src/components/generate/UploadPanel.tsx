import { useCallback, useRef, useState, useEffect, type DragEvent } from 'react'
import gsap from 'gsap'
import { LABEL_DISPLAY_NAMES, BUILT_IN_LABELS } from '../../types/annotate'

interface AnnotationBox {
  label: string
  x: number
  y: number
  width: number
  height: number
}

interface Props {
  onFileSelected: (file: File) => void
  disabled?: boolean
  previewUrls?: string[]
  onFullscreen?: () => void
  annotationShapes?: Record<number, AnnotationBox[]>
  imageNaturalSize?: { w: number; h: number }
  labelColors?: Record<string, string>
}

export function UploadPanel({ onFileSelected, disabled, previewUrls, onFullscreen, annotationShapes, imageNaturalSize, labelColors }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [pageIdx, setPageIdx] = useState(0)
  const dropzoneRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const zoomRef = useRef(zoom)
  const [isPanning, setIsPanning] = useState(false)
  const panStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })

  useEffect(() => { zoomRef.current = zoom }, [zoom])

  // GSAP: Dropzone hover animation
  useEffect(() => {
    if (dropzoneRef.current) {
      if (dragOver) {
        gsap.to(dropzoneRef.current, {
          scale: 1.02,
          borderColor: '#f97316',
          duration: 0.3,
          ease: 'power2.out',
        })
      } else {
        gsap.to(dropzoneRef.current, {
          scale: 1,
          borderColor: '#cbd5e1',
          duration: 0.3,
          ease: 'power2.out',
        })
      }
    }
  }, [dragOver])

  // GSAP: Image page transition & initial load
  useEffect(() => {
    if (imageRef.current) {
      gsap.fromTo(imageRef.current,
        { opacity: 0, scale: 0.97 },
        { opacity: 1, scale: 1, duration: 0.4, ease: 'power2.out' }
      )
    }
  }, [pageIdx, previewUrls])

  // Native wheel handler for Ctrl+zoom with cursor anchoring
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

  // Pan handlers for drag-to-pan
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
    el.scrollLeft = panStartRef.current.scrollLeft - (e.clientX - panStartRef.current.x)
    el.scrollTop = panStartRef.current.scrollTop - (e.clientY - panStartRef.current.y)
  }, [isPanning])

  const handlePanEnd = useCallback(() => {
    setIsPanning(false)
  }, [])

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    const file = e.dataTransfer?.files?.[0]
    if (file) onFileSelected(file)
  }, [disabled, onFileSelected])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onFileSelected(file)
    e.target.value = ''
  }, [onFileSelected])

  const hasImages = previewUrls && previewUrls.length > 0

  if (hasImages) {
    return (
      <div className="flex flex-col h-full min-h-0">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-3 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[13px] font-bold text-slate-700">图纸预览</span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-gradient-to-r from-slate-100 to-slate-50 text-[11px] font-mono font-semibold text-slate-500">
              {pageIdx + 1} / {previewUrls.length}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]" onClick={() => setPageIdx(i => Math.max(0, i - 1))} disabled={pageIdx === 0}>←</button>
            <button className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]" onClick={() => setPageIdx(i => Math.min(previewUrls!.length - 1, i + 1))} disabled={pageIdx >= previewUrls!.length - 1}>→</button>
            <div className="w-px h-4 bg-slate-200 mx-1" />
            <button className="btn btn-ghost !px-2 !py-1.5 text-[11px]" onClick={() => setZoom(z => Math.max(0.1, z / 1.25))}>−</button>
            <span className="inline-flex items-center justify-center min-w-[48px] px-2 py-1 rounded-lg bg-gradient-to-r from-slate-50 to-slate-100 border border-slate-100 text-[11px] font-mono font-semibold text-slate-500">
              {Math.round(zoom * 100)}%
            </span>
            <button className="btn btn-ghost !px-2 !py-1.5 text-[11px]" onClick={() => setZoom(z => Math.min(10, z * 1.25))}>+</button>
            <button className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]" onClick={() => setZoom(1)}>重置</button>
            {onFullscreen && (
              <button className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]" onClick={onFullscreen}>
                <span className="flex items-center gap-1">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
                    <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
                  </svg>
                  全屏
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Image stage */}
        <div
          ref={scrollRef}
          className={`flex-1 min-h-0 mx-4 mb-4 rounded-2xl border border-slate-200 overflow-auto ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
          style={{ background: 'linear-gradient(135deg, #fafbfc 0%, #f8fafc 100%)' }}
          onMouseDown={handlePanStart}
          onMouseMove={handlePanMove}
          onMouseUp={handlePanEnd}
          onMouseLeave={handlePanEnd}
        >
          <div className="relative inline-block" style={{ width: `${zoom * 100}%`, minWidth: '100%' }}>
            <img
              ref={imageRef}
              src={previewUrls[pageIdx]}
              alt={`第 ${pageIdx + 1} 页`}
              className="block w-full h-auto rounded-xl select-none"
              draggable={false}
              style={{ boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}
            />
            {/* Annotation overlay */}
            {annotationShapes && annotationShapes[pageIdx + 1] && imageNaturalSize && imageNaturalSize.w > 0 && (
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none"
                viewBox={`0 0 ${imageNaturalSize.w} ${imageNaturalSize.h}`}
                preserveAspectRatio="xMidYMid meet"
              >
                {annotationShapes[pageIdx + 1].map((shape, i) => {
                  const displayName = LABEL_DISPLAY_NAMES[shape.label] || shape.label
                  const color = labelColors?.[shape.label] || '#f97316'
                  const labelDef = BUILT_IN_LABELS.find(l => l.name === shape.label)
                  const dash = labelDef?.borderStyle === '6,3' ? '6,3' : undefined
                  // Compute seq
                  const prev = annotationShapes[pageIdx + 1].slice(0, i).filter(s => s.label === shape.label)
                  const seq = prev.length + 1
                  const tagText = `${displayName} ${seq}`
                  const tagH = 16
                  const tagW = Math.max(40, tagText.length * 7 + 10)
                  return (
                    <g key={i}>
                      <rect
                        x={shape.x} y={shape.y}
                        width={shape.width} height={shape.height}
                        fill={`${color}1a`} stroke={color} strokeWidth={2}
                        strokeDasharray={dash}
                        rx={3}
                      />
                      <rect
                        x={shape.x} y={Math.max(shape.y - tagH - 2, 0)}
                        width={tagW} height={tagH}
                        fill={color} rx={3}
                      />
                      <text
                        x={shape.x + 5} y={Math.max(shape.y - 4, tagH - 2)}
                        fill="white" fontSize={10} fontWeight="bold"
                      >
                        {tagText}
                      </text>
                    </g>
                  )
                })}
              </svg>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full min-h-0 p-5">
      <div
        ref={dropzoneRef}
        className={`dropzone flex-1 ${dragOver ? 'drag-over' : ''} ${disabled ? 'opacity-40 pointer-events-none' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        {/* Icon */}
        <div
          className="w-18 h-18 rounded-2xl grid place-items-center mb-5 relative"
          style={{
            background: 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)',
            border: '2px solid rgba(249, 115, 22, 0.2)',
            width: '72px',
            height: '72px',
          }}
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#f97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>

        <div className="text-lg font-bold text-slate-800 mb-1.5">上传 2D 工艺图纸</div>
        <div className="text-[13px] text-slate-500 max-w-[360px] leading-relaxed">
          支持 PDF、PNG、JPG 格式，自动提取工艺特征并生成规程
        </div>

        <div className="flex flex-wrap justify-center gap-2 mt-5">
          {['最大 20MB', '支持多页 PDF', '自动 OCR'].map(tag => (
            <span key={tag} className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-white to-slate-50 border border-slate-200 text-[11px] font-medium text-slate-500">
              {tag}
            </span>
          ))}
        </div>
      </div>

      <input ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={handleFileInput} />
    </div>
  )
}
