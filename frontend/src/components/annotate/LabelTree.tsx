import { useState, useEffect } from 'react'
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
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const grouped = new Map<string, AnnotationShape[]>()
  for (const s of shapes) {
    const arr = grouped.get(s.label) || []
    arr.push(s)
    grouped.set(s.label, arr)
  }

  const toggleGroup = (label: string) => {
    setCollapsedGroups(prev => {
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
            onClick={() => toggleGroup(label)}
            className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg text-[11px] font-semibold text-slate-600 hover:bg-slate-100/60 transition-colors"
          >
            <span className={`text-[10px] text-slate-400 transition-transform duration-150 ${collapsedGroups.has(label) ? '' : 'rotate-90'}`}>▶</span>
            <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: getLabelColor(label) }} />
            <span className="flex-1 text-left">{LABEL_DISPLAY_NAMES[label] || label}</span>
            <span className="text-[10px] text-slate-400">{items.length}</span>
          </button>

          {/* Children */}
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
        </div>
      ))}
    </div>
  )
}
