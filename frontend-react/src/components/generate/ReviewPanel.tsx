import { useEffect, useState, useCallback, useRef } from 'react'
import gsap from 'gsap'
import { parseReviewFields, serializeReviewFields, type FeatureField } from '../../utils/featureParser'
import { LABEL_DISPLAY_NAMES, BUILT_IN_LABELS } from '../../types/annotate'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

interface Props {
  reviewText: string
  onReviewTextChange: (text: string) => void
  onConfirm: () => void
  onRerun: () => void
  busy: boolean
  ocrThicknessHint?: string
  feedback?: { message: string; tone: 'warn' | 'danger' | 'info' }
  annotateSummary?: Record<string, number>
}

export function ReviewPanel({ reviewText, onReviewTextChange, onConfirm, onRerun, busy, ocrThicknessHint, feedback, annotateSummary }: Props) {
  const [fields, setFields] = useState<FeatureField[]>([])
  const tableRef = useRef<HTMLDivElement>(null)
  const emptyStateRef = useRef<HTMLDivElement>(null)
  const reduceMotion = usePrefersReducedMotion()

  // Parse reviewText into structured fields
  useEffect(() => {
    setFields(parseReviewFields(reviewText))
  }, [reviewText])

  // GSAP: Table row animation
  useEffect(() => {
    if (reduceMotion) return
    if (tableRef.current) {
      const rows = tableRef.current.querySelectorAll('tbody tr')
      if (rows.length > 0) {
        gsap.fromTo(rows,
          { opacity: 0, x: -10 },
          { opacity: 1, x: 0, duration: 0.3, stagger: 0.05, ease: 'power2.out' }
        )
      }
    }
  }, [fields.length, reduceMotion])

  // GSAP: Empty state animation
  useEffect(() => {
    if (reduceMotion) return
    if (emptyStateRef.current) {
      gsap.fromTo(emptyStateRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }
      )
    }
  }, [reduceMotion])

  const handleFieldChange = useCallback((index: number, key: 'label' | 'value', newVal: string) => {
    setFields(prev => {
      const next = [...prev]
      next[index] = { ...next[index], [key]: newVal }
      // Sync back to parent
      onReviewTextChange(serializeReviewFields(next))
      return next
    })
  }, [onReviewTextChange])

  const hasContent = fields.length > 0 && fields.some(f => f.value.trim())

  return (
    <div className="flex flex-col h-full min-h-0 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 shrink-0">
        <div>
          <h3 className="text-[15px] font-bold text-slate-800 mb-0.5">特征审阅</h3>
          <p className="text-[12px] text-slate-500">
            {hasContent ? `已收到 ${fields.length} 项特征，内容可编辑，字段名固定。` : '确认或修改 AI 提取的工艺特征后继续'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn btn-secondary" onClick={onConfirm} disabled={busy || !hasContent}>
            确认特征并继续
          </button>
          <button className="btn btn-primary" onClick={onRerun} disabled={busy || !hasContent}>
            {busy ? (
              <span className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                处理中
              </span>
            ) : '修改后重新生成'}
          </button>
        </div>
      </div>

      {/* Annotation summary — YOLO + manual annotation counts */}
      {annotateSummary && Object.keys(annotateSummary).length > 0 && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200/60 flex-wrap">
          <span className="text-[11px] text-slate-500 shrink-0">标注汇总：</span>
          {Object.entries(annotateSummary)
            .filter(([, v]) => v > 0)
            .map(([key, count]) => {
              const labelDef = BUILT_IN_LABELS.find(l => l.name === key)
              return (
                <span
                  key={key}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold text-white"
                  style={{ background: labelDef?.color || '#94a3b8' }}
                >
                  {LABEL_DISPLAY_NAMES[key] || key}
                  <span className="opacity-80">{count}处</span>
                </span>
              )
            })}
        </div>
      )}

      {/* OCR hint */}
      {ocrThicknessHint && (
        <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl text-[12px] leading-relaxed"
          style={{ background: 'var(--info-soft)', border: '1px solid #bfdbfe', color: '#1e40af' }}
        >
          <span className="mt-0.5">ℹ</span>
          <span>{ocrThicknessHint}</span>
        </div>
      )}

      {/* Feedback message */}
      {feedback && (
        <div className={`flex items-start gap-2.5 px-4 py-3 rounded-xl text-[12px] leading-relaxed ${
          feedback.tone === 'danger' ? 'bg-red-50 border border-red-200 text-red-700' :
          feedback.tone === 'warn' ? 'bg-amber-50 border border-amber-200 text-amber-700' :
          'bg-blue-50 border border-blue-200 text-blue-700'
        }`}>
          <span className="mt-0.5">{feedback.tone === 'danger' ? '⚠' : feedback.tone === 'warn' ? '⚠' : 'ℹ'}</span>
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Table */}
      <div ref={tableRef} className="flex-1 min-h-0 rounded-2xl border border-slate-200 overflow-y-auto overflow-x-hidden bg-white">
        {!hasContent ? (
          <div ref={emptyStateRef} className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8 min-h-[300px]">
            <div
              className="w-16 h-16 rounded-xl grid place-items-center"
              style={{ background: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)', border: '1px solid #bfdbfe' }}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18" />
                <path d="M9 21V9" />
              </svg>
            </div>
            <div className="text-[14px] font-semibold text-slate-600">上传图纸后查看特征</div>
            <div className="text-[12px] text-slate-500 max-w-[280px] leading-relaxed">
              AI 将自动识别尺寸公差、粗糙度、形位公差等关键特征
            </div>
          </div>
        ) : (
          <table className="data-table" style={{ tableLayout: 'fixed' }}>
            <colgroup>
              <col style={{ width: 180 }} />
              <col />
            </colgroup>
            <thead>
              <tr>
                <th>字段</th>
                <th>内容</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field, i) => (
                <tr key={i}>
                  <td className="font-mono text-[12px] text-slate-500 font-semibold">
                    {field.label}
                  </td>
                  <td>
                    <span
                      contentEditable
                      suppressContentEditableWarning
                      onBlur={e => handleFieldChange(i, 'value', e.currentTarget.textContent || '')}
                      className="cell-editable block"
                    >
                      {field.value}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
