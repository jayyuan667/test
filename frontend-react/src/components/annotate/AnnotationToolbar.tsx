import type { AnnotationLabel } from '../../types/annotate'
import { LABEL_DISPLAY_NAMES } from '../../types/annotate'

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
  onAddLabel?: () => void
  onDeleteLabel?: (name: string) => void
  canDeleteLabel?: (name: string) => boolean
}

export function AnnotationToolbar({
  labels, activeLabel, onLabelChange,
  zoom, onZoomIn, onZoomOut, onZoomFit, onZoom100,
  pageNumber, totalPages, onPrevPage, onNextPage,
  shapeCount, onExport,
  onAddLabel, onDeleteLabel, canDeleteLabel,
}: Props) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-200 bg-white flex-wrap">
      {/* Label buttons */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {labels.map(label => {
          const deletable = onDeleteLabel && canDeleteLabel?.(label.name)
          return (
            <div key={label.name} className="relative group">
              <button
                onClick={() => onLabelChange(label.name)}
                className={`
                  px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all duration-150
                  ${activeLabel === label.name
                    ? 'text-white shadow-sm'
                    : 'bg-white/60 text-slate-600 border-slate-200/60 hover:border-slate-300'}
                  ${deletable ? 'pr-5' : ''}
                `}
                style={activeLabel === label.name ? {
                  background: label.color,
                  borderColor: label.color,
                  boxShadow: `0 2px 8px ${label.color}40`,
                } : undefined}
              >
                {LABEL_DISPLAY_NAMES[label.name] || label.name}
              </button>
              {deletable && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteLabel(label.name) }}
                  className="absolute right-0.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5
                             rounded-full flex items-center justify-center text-[9px]
                             text-white/80 hover:text-white hover:bg-red-500/80
                             opacity-0 group-hover:opacity-100 transition-opacity"
                  title={`删除 ${LABEL_DISPLAY_NAMES[label.name] || label.name}`}
                >
                  x
                </button>
              )}
            </div>
          )
        })}
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
