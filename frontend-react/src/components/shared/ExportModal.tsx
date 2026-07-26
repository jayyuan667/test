import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { downloadExport } from '../../api/client'
import { parseReviewFields, filterInfoFields } from '../../utils/featureParser'
import type { TaskResult } from '../../types'
import type { ProcessRow } from '../generate/ProcessPanel'

interface Props {
  taskId: string
  result: TaskResult
  reviewText: string
  editedRows: ProcessRow[]
  onClose: () => void
}

export function ExportModal({ taskId, result, reviewText, editedRows, onClose }: Props) {
  const [downloading, setDownloading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [exiting, setExiting] = useState(false)
  const backdropRef = useRef<HTMLDivElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  // GSAP: Entrance animation
  useEffect(() => {
    const tl = gsap.timeline()
    if (backdropRef.current) {
      tl.fromTo(backdropRef.current, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: 'power2.out' })
    }
    if (cardRef.current) {
      tl.fromTo(cardRef.current, { opacity: 0, scale: 0.96, y: 16 }, { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: 'power3.out' }, '-=0.1')
    }
    return () => { tl.kill() }
  }, [])

  const animateClose = useCallback(() => {
    if (exiting) return
    setExiting(true)
    const tl = gsap.timeline({ onComplete: onClose })
    if (cardRef.current) {
      tl.to(cardRef.current, { opacity: 0, scale: 0.96, y: 16, duration: 0.2, ease: 'power3.in' })
    }
    if (backdropRef.current) {
      tl.to(backdropRef.current, { opacity: 0, duration: 0.25, ease: 'power2.in' }, '-=0.12')
    }
  }, [exiting, onClose])

  // Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') animateClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [animateClose])

  const previewUrl = result.preview_image_urls?.[0] || result.image_url || ''

  // Use edited rows if available, fall back to original result data
  const processRows: ProcessRow[] = useMemo(() => {
    if (editedRows.length > 0) return editedRows
    const raw = result.process_flow?.data || []
    return raw.map(row => {
      if (Array.isArray(row)) {
        return {
          code: String(row[0] || '').trim(),
          trade: row.length >= 3 ? String(row[1] || '').trim() : '',
          content: String(row[row.length >= 3 ? 2 : 1] || '').trim(),
        }
      }
      return { code: '', trade: '', content: String(row || '') }
    })
  }, [editedRows, result])

  // Use edited review text if available, fall back to original
  const featureText = useMemo(() => {
    const raw = reviewText || result.feature_report_text || result.expert_judgment || ''
    if (raw) return filterInfoFields(raw)
    return raw
  }, [reviewText, result])

  // Parse feature fields for display
  const featureFields = useMemo(() => {
    if (!featureText) return []
    return parseReviewFields(featureText)
  }, [featureText])

  const handleDownload = async (format: 'pdf' | 'xlsx') => {
    try {
      setError(null)
      setDownloading(format)
      const rows: [string, string, string][] = processRows.map(row => [
        row.code, row.trade, row.content,
      ])
      const blob = await downloadExport(taskId, format, rows)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Process_${taskId.slice(0, 8)}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError(`导出 ${format.toUpperCase()} 失败，请重试`)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      {/* Backdrop */}
      <div ref={backdropRef} className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={animateClose} />

      {/* Modal card */}
      <div ref={cardRef} className="relative z-10 w-full max-w-3xl max-h-[85vh] flex flex-col card-solid overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200/60 shrink-0">
          <div>
            <h2 className="text-[15px] font-bold text-slate-800">导出工艺文件</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              任务ID：{taskId.slice(0, 8)}  |  文件：{result.pdf_name || result.source_name || '-'}
            </p>
          </div>
          <button
            onClick={animateClose}
            aria-label="关闭"
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

            {/* Info block */}
            <div className="mt-3 flex flex-col gap-1.5">
              {result.pdf_name && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">文件名称</span>
                  <span className="text-slate-600 font-medium">{result.pdf_name}</span>
                </div>
              )}
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">任务ID</span>
                <span className="text-slate-600 font-mono text-[10px]">{taskId.slice(0, 12)}</span>
              </div>
              {result.total_pages && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">页数</span>
                  <span className="text-slate-600 font-medium">{result.total_pages}</span>
                </div>
              )}
            </div>

            {/* Feature info */}
            {featureFields.length > 0 && (
              <div className="mt-3 px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-200/60">
                {featureFields.map((f, i) => (
                  <div key={i} className="text-[11px] leading-relaxed">
                    <span className="text-slate-400">{f.label}：</span>
                    <span className="text-slate-600">{f.value.length > 40 ? f.value.slice(0, 40) + '...' : f.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Process table preview */}
          <div className="flex-1 min-w-0">
            <h3 className="text-[12px] font-bold text-slate-500 uppercase tracking-wider mb-3">工序预览</h3>
            {processRows.length > 0 ? (
              <div className="overflow-auto max-h-[400px] rounded-xl border border-slate-200/60">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 80 }}>工序号</th>
                      <th style={{ width: 80 }}>工种</th>
                      <th>工序内容</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processRows.map((row, i) => (
                      <tr key={i}>
                        <td className="font-mono text-[12px] font-bold text-flame-600">{row.code}</td>
                        <td className="text-[11px]">{row.trade}</td>
                        <td className="text-[12px]">{row.content}</td>
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
          {error && (
            <span className="text-[12px] text-red-600 mr-auto">{error}</span>
          )}
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
