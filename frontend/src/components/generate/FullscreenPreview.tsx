import { useCallback, useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { LABEL_DISPLAY_NAMES } from '../../types/annotate'

interface AnnotationBox {
  label: string
  x: number
  y: number
  width: number
  height: number
}

interface Props {
  urls: string[]
  startIndex: number
  onClose: () => void
  annotationShapes?: Record<number, AnnotationBox[]>
  imageNaturalSize?: { w: number; h: number }
  labelColors?: Record<string, string>
}

export function FullscreenPreview({ urls, startIndex, onClose, annotationShapes, imageNaturalSize, labelColors }: Props) {
  const [index, setIndex] = useState(startIndex)
  const [zoom, setZoom] = useState(1)
  const stageRef = useRef<HTMLDivElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)
  const shellRef = useRef<HTMLDivElement>(null)

  // GSAP: Entrance animation
  useEffect(() => {
    const tl = gsap.timeline()
    if (backdropRef.current) {
      tl.fromTo(backdropRef.current, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: 'power2.out' })
    }
    if (shellRef.current) {
      tl.fromTo(shellRef.current, { opacity: 0, scale: 0.95, y: 20 }, { opacity: 1, scale: 1, y: 0, duration: 0.4, ease: 'power3.out' }, '-=0.15')
    }
    return () => { tl.kill() }
  }, [])

  // Reset zoom on page change
  useEffect(() => { setZoom(1) }, [index])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') setIndex(i => Math.max(0, i - 1))
      if (e.key === 'ArrowRight') setIndex(i => Math.min(urls.length - 1, i + 1))
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [urls.length, onClose])

  // Wheel zoom (Ctrl+scroll, multiplicative, cursor-anchored)
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

  // Backdrop click
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose()
  }, [onClose])

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-[3000] flex items-center justify-center"
      style={{ background: 'rgba(11, 19, 31, 0.78)', backdropFilter: 'blur(10px)' }}
      onClick={handleBackdropClick}
    >
      {/* Shell */}
      <div ref={shellRef} className="relative flex flex-col" style={{ width: '96vw', height: '92vh', maxWidth: 1500, maxHeight: 1100, borderRadius: 22, background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)' }}>
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors text-[16px]"
        >✕</button>

        {/* Prev / Next */}
        {urls.length > 1 && (
          <>
            <button
              onClick={() => setIndex(i => Math.max(0, i - 1))}
              disabled={index === 0}
              className="absolute left-3 top-1/2 -translate-y-1/2 z-10 w-10 h-10 flex items-center justify-center rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors text-[20px] disabled:opacity-20"
            >❮</button>
            <button
              onClick={() => setIndex(i => Math.min(urls.length - 1, i + 1))}
              disabled={index >= urls.length - 1}
              className="absolute right-3 top-1/2 -translate-y-1/2 z-10 w-10 h-10 flex items-center justify-center rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors text-[20px] disabled:opacity-20"
            >❯</button>
          </>
        )}

        {/* Counter */}
        <span className="absolute top-3 left-3 z-10 text-[12px] font-mono text-white/50">
          {index + 1} / {urls.length}
        </span>

        {/* Zoom label */}
        <span className="absolute bottom-3 right-3 z-10 text-[11px] font-mono text-white/40">
          {Math.round(zoom * 100)}%
        </span>

        {/* Stage */}
        <div
          ref={stageRef}
          className="flex-1 overflow-auto flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)' }}
        >
          <div className="relative inline-block" style={{ width: `${zoom * 100}%`, minWidth: '100%', minHeight: '100%' }}>
            <img
              src={urls[index]}
              alt={`Page ${index + 1}`}
              className="block w-full h-auto transition-none select-none"
              draggable={false}
              style={{ maxWidth: 'none' }}
            />
            {annotationShapes && annotationShapes[index + 1] && imageNaturalSize && imageNaturalSize.w > 0 && (
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none"
                viewBox={`0 0 ${imageNaturalSize.w} ${imageNaturalSize.h}`}
                preserveAspectRatio="xMidYMid meet"
              >
                {annotationShapes[index + 1].map((shape, i) => {
                  const displayName = LABEL_DISPLAY_NAMES[shape.label] || shape.label
                  const color = labelColors?.[shape.label] || '#f97316'
                  const prev = annotationShapes[index + 1].slice(0, i).filter(s => s.label === shape.label)
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
    </div>
  )
}
