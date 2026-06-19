import { useCallback, useEffect, useRef, useState } from 'react'
import { AnnotationLabel } from '../../types/annotate'
import gsap from 'gsap'

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
  const [exiting, setExiting] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  // GSAP: Entrance animation
  useEffect(() => {
    if (overlayRef.current) {
      gsap.fromTo(overlayRef.current, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: 'power2.out' })
    }
    if (contentRef.current) {
      gsap.fromTo(contentRef.current, { opacity: 0, scale: 0.92, y: 16 }, { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: 'back.out(1.7)' })
    }
  }, [])

  const animateClose = useCallback(() => {
    if (exiting) return
    setExiting(true)
    const tl = gsap.timeline({ onComplete: onClose })
    if (contentRef.current) {
      tl.to(contentRef.current, { opacity: 0, scale: 0.92, y: 12, duration: 0.2, ease: 'power3.in' })
    }
    if (overlayRef.current) {
      tl.to(overlayRef.current, { opacity: 0, duration: 0.22, ease: 'power2.in' }, '-=0.12')
    }
  }, [exiting, onClose])

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
    animateClose()
  }

  return (
    <div ref={overlayRef} className="fixed inset-0 z-[3000] flex items-center justify-center bg-black/40"
         onClick={animateClose}>
      <div ref={contentRef} className="bg-white rounded-xl shadow-2xl w-[360px] p-5"
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
          <button onClick={animateClose}
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
