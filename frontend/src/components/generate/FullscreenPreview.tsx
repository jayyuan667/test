import { useCallback, useEffect, useRef, useState } from 'react'

interface Props {
  urls: string[]
  startIndex: number
  onClose: () => void
}

export function FullscreenPreview({ urls, startIndex, onClose }: Props) {
  const [index, setIndex] = useState(startIndex)
  const [zoom, setZoom] = useState(1)
  const stageRef = useRef<HTMLDivElement>(null)

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
      className="fixed inset-0 z-[3000] flex items-center justify-center"
      style={{ background: 'rgba(11, 19, 31, 0.78)', backdropFilter: 'blur(10px)' }}
      onClick={handleBackdropClick}
    >
      {/* Shell */}
      <div className="relative flex flex-col" style={{ width: '96vw', height: '92vh', maxWidth: 1500, maxHeight: 1100, borderRadius: 22, background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', overflow: 'hidden' }}>
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
          <img
            src={urls[index]}
            alt={`Page ${index + 1}`}
            className="block object-contain transition-none select-none"
            draggable={false}
            style={{
              width: `${zoom * 100}%`,
              height: 'auto',
              minWidth: '100%',
              minHeight: '100%',
              maxWidth: 'none',
            }}
          />
        </div>
      </div>
    </div>
  )
}
