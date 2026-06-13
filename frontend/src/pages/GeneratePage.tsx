import { useCallback, useEffect, useRef, useState } from 'react'
import { batchUpload, connectSSE, finalizeAnnotation, getAnnotations, getAssetUrl, getResult, submitReview, uploadDrawing, uploadFile } from '../api/client'
import type { TaskResult } from '../types'
import { WorkflowHUD } from '../components/generate/WorkflowHUD'
import { UploadPanel } from '../components/generate/UploadPanel'
import { ReviewPanel } from '../components/generate/ReviewPanel'
import { ProcessPanel } from '../components/generate/ProcessPanel'
import { AnnotationPanel, type AnnotationPanelHandle } from '../components/annotate/AnnotationPanel'
import { ExportModal } from '../components/shared/ExportModal'
import { FullscreenPreview } from '../components/generate/FullscreenPreview'
import { LABEL_DISPLAY_NAMES, BUILT_IN_LABELS } from '../types/annotate'
import gsap from 'gsap'

type ActiveTab = 'review' | 'process'

export function GeneratePage({ onError, onSuccess }: { onError: (msg: string) => void; onSuccess?: (msg: string) => void }) {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('idle')
  const [progress, setProgress] = useState(0)
  const [phaseHint, setPhaseHint] = useState('等待文件进入解析流程')
  const [activeTab, setActiveTab] = useState<ActiveTab>('review')
  const [reviewText, setReviewText] = useState('')
  const [ocrThicknessHint, setOcrThicknessHint] = useState('')
  const [result, setResult] = useState<TaskResult | null>(null)
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [streamingChunks, setStreamingChunks] = useState('')
  const [fileName, setFileName] = useState('')
  const esRef = useRef<EventSource | null>(null)
  const [showExport, setShowExport] = useState(false)
  const [showFullscreen, setShowFullscreen] = useState(false)
  const [fullscreenIndex, setFullscreenIndex] = useState(0)
  const [reviewFeedback, setReviewFeedback] = useState<{ message: string; tone: 'warn' | 'danger' | 'info' } | undefined>()

  // Annotation overlay state
  const [annotateOpen, setAnnotateOpen] = useState(false)
  const [annotateVisited, setAnnotateVisited] = useState(false)
  const [annotateSummary, setAnnotateSummary] = useState<Record<string, number>>({})
  const [annotateShapes, setAnnotateShapes] = useState<Record<number, { label: string; x: number; y: number; width: number; height: number }[]>>({})
  const [imgNaturalSize, setImgNaturalSize] = useState({ w: 0, h: 0 })

  const annotationRef = useRef<AnnotationPanelHandle>(null)

  // Load natural image size from first preview
  useEffect(() => {
    if (!previewUrls.length) return
    const img = new Image()
    img.onload = () => setImgNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
    img.src = previewUrls[0]
  }, [previewUrls])

  // Load annotations for preview overlay
  useEffect(() => {
    if (!taskId) return
    let cancelled = false
    ;(async () => {
      try {
        const data = await getAnnotations(taskId)
        if (cancelled) return
        const shapes: typeof annotateShapes = {}
        const counts: Record<string, number> = {}
        for (const [pg, ann] of Object.entries(data)) {
          const pageNum = Number(pg)
          shapes[pageNum] = (ann.shapes || []).map(s => ({
            label: s.label,
            x: s.points[0][0],
            y: s.points[0][1],
            width: s.points[1][0] - s.points[0][0],
            height: s.points[1][1] - s.points[0][1],
          }))
          for (const s of shapes[pageNum]) {
            counts[s.label] = (counts[s.label] || 0) + 1
          }
        }
        setAnnotateShapes(shapes)
        if (Object.keys(counts).length > 0) setAnnotateSummary(counts)
      } catch { /* no annotations yet */ }
    })()
    return () => { cancelled = true }
  }, [taskId, annotateOpen]) // re-load when annotation panel closes

  // Refs for GSAP animations
  const hudRef = useRef<HTMLDivElement>(null)
  const tabBarRef = useRef<HTMLDivElement>(null)
  const workbenchRef = useRef<HTMLDivElement>(null)

  const busy = status === 'processing' || status === 'pending'
  const completed = status === 'completed'
  const hasTask = taskId !== null
  const isAnnotating = status === 'awaiting_annotation'

  useEffect(() => { return () => { esRef.current?.close() } }, [])

  // GSAP: Page load animation
  useEffect(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

    if (hudRef.current) {
      tl.fromTo(hudRef.current,
        { y: 10, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4 },
        '-=0.25'
      )
    }

    if (tabBarRef.current) {
      tl.fromTo(tabBarRef.current,
        { y: 10, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.3 },
        '-=0.25'
      )
    }

    if (workbenchRef.current) {
      const cards = workbenchRef.current.querySelectorAll('.card-solid')
      tl.fromTo(cards,
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5, stagger: 0.1 },
        '-=0.2'
      )
    }

    return () => { tl.kill() }
  }, [])

  // GSAP: Status change animation
  useEffect(() => {
    if (completed || status === 'error') {
      const hud = hudRef.current
      if (hud) {
        gsap.fromTo(hud,
          { scale: 0.98 },
          { scale: 1, duration: 0.3, ease: 'back.out(1.7)' }
        )
      }
    }
  }, [completed, status])

  // Annotation handlers
  const handleOpenAnnotate = useCallback(() => {
    setAnnotateOpen(true)
    setAnnotateVisited(true)
  }, [])

  const handleCloseAnnotate = useCallback(async () => {
    try {
      await annotationRef.current?.saveNow()
    } catch { /* save failed, still close */ }
    // Update summary from current annotations
    const counts = annotationRef.current?.getShapeCounts()
    if (counts) setAnnotateSummary(counts)
    setAnnotateOpen(false)
  }, [])

  const handleFinalizeAnnotation = useCallback(async () => {
    if (!taskId) return
    try {
      setStatus('processing')
      setProgress(45)
      setPhaseHint('视觉分析中...')
      await finalizeAnnotation(taskId)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '标注确认失败'
      onError(msg)
      setStatus('awaiting_annotation')
    }
  }, [taskId, onError])

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
      setAnnotateVisited(false)
      setAnnotateSummary({})

      const { batch_task_id, files: uploaded } = await batchUpload(files)
      setTaskId(batch_task_id)
      setActiveTab('review')
      setPhaseHint(`${uploaded.length} 个文件已上传，等待处理...`)

      esRef.current?.close()
      esRef.current = connectSSE(batch_task_id, {
        onStepStart(data) { setPhaseHint(String(data.message || '处理中...')) },
        onStepComplete(data) { setPhaseHint(String(data.message || '步骤完成')) },
        onLog(data) { setPhaseHint(String(data.message || '')) },
        onReviewRequired(data) {
          const text = String(data.content || data.review_text || data.raw_content || '')
          setReviewText(text)
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
        async onAnnotationRequired(data) {
          setAnnotateSummary((data.summary as Record<string, number>) || {})
          setAnnotateVisited(false)
          setStatus('awaiting_annotation')
          setProgress(35)
          setPhaseHint('等待人工补全标注')
          setActiveTab('review')
          try {
            const res = await getResult(batch_task_id) as Record<string, unknown>
            const urls = (res.preview_image_urls as string[]) || []
            if (urls.length) setPreviewUrls(urls)
          } catch { /* ignore */ }
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

  const handleFileSelected = useCallback(async (file: File) => {
    try {
      setResult(null)
      setReviewText('')
      setStreamingChunks('')
      setPreviewUrls([])
      setProgress(0)
      setPhaseHint('正在上传文件...')
      setStatus('processing')
      setFileName(file.name)
      setAnnotateVisited(false)
      setAnnotateSummary({})

      const ext = file.name.toLowerCase().split('.').pop() || ''
      const isDrawing = ['pdf', 'png', 'jpg', 'jpeg'].includes(ext)
      const { task_id } = isDrawing ? await uploadDrawing(file) : await uploadFile(file)
      setTaskId(task_id)
      setActiveTab('review')
      setPhaseHint('文件已上传，等待视觉分析...')

      esRef.current?.close()
      esRef.current = connectSSE(task_id, {
        onStepStart(data) {
          setPhaseHint(String(data.message || data.step_name || '处理中...'))
        },
        onStepComplete(data) {
          setPhaseHint(String(data.message || '步骤完成'))
        },
        onLog(data) {
          setPhaseHint(String(data.message || ''))
        },
        onReviewRequired(data) {
          const text = String(data.content || data.review_text || data.raw_content || '')
          setReviewText(text)
          setStatus('awaiting_review')
          setProgress(50)
          setPhaseHint('请审阅特征报告')
          const urls = (data.preview_image_urls as string[]) || []
          if (urls.length) setPreviewUrls(urls)
        },
        onProcessStream(data) {
          setStreamingChunks(prev => prev + String(data.chunk || ''))
        },
        onPreviewUpdated(data) {
          const urls = (data.preview_image_urls as string[]) || []
          if (urls.length) setPreviewUrls(urls)
        },
        async onAnnotationRequired(data) {
          setAnnotateSummary((data.summary as Record<string, number>) || {})
          setAnnotateVisited(false)
          setStatus('awaiting_annotation')
          setProgress(35)
          setPhaseHint('等待人工补全标注')
          setActiveTab('review')
          try {
            const res = await getResult(task_id) as Record<string, unknown>
            const urls = (res.preview_image_urls as string[]) || []
            if (urls.length) setPreviewUrls(urls)
          } catch { /* ignore */ }
        },
        async onComplete() {
          setStatus('completed')
          setProgress(100)
          setPhaseHint('处理完成！')
          try {
            const res = await getResult(task_id)
            setResult(res as unknown as TaskResult)
            const rawUrls = (res as Record<string, unknown>).preview_image_urls as string[] || []
            if (rawUrls.length) {
              setPreviewUrls(rawUrls.map(u => u.startsWith('/api') ? u : getAssetUrl(task_id, u)))
            }
            setActiveTab('process')
          } catch { /* already set */ }
        },
        onError(data) {
          const msg = String(data.message || data.error || '处理失败')
          setStatus('error')
          setPhaseHint(`错误：${msg}`)
          onError(msg)
        },
      })
    } catch (err: unknown) {
      setStatus('error')
      const msg = err instanceof Error ? err.message : '上传失败'
      setPhaseHint(`上传失败：${msg}`)
      onError(msg)
    }
  }, [onError])

  const handleConfirmReview = useCallback(async () => {
    if (!taskId) {
      setReviewFeedback({ message: '暂无可继续的任务', tone: 'danger' })
      return
    }
    if (!reviewText.trim()) {
      setReviewFeedback({ message: '审阅内容为空', tone: 'danger' })
      return
    }
    try {
      setReviewFeedback(undefined)
      setStatus('processing')
      setProgress(60)
      setPhaseHint('特征已确认，正在生成工艺规程...')
      setStreamingChunks('')
      setActiveTab('process')
      await submitReview(taskId, { review_text: reviewText, action: 'continue' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '审阅提交失败'
      setStatus('awaiting_review')
      setReviewFeedback({ message: msg, tone: 'danger' })
      onError(msg)
    }
  }, [taskId, reviewText, onError])

  const handleRerun = useCallback(async () => {
    if (!taskId) {
      setReviewFeedback({ message: '暂无可继续的任务', tone: 'danger' })
      return
    }
    try {
      setReviewFeedback(undefined)
      setStatus('processing')
      setProgress(50)
      setPhaseHint('修改已提交，正在重新生成...')
      setStreamingChunks('')
      setActiveTab('process')
      await submitReview(taskId, { review_text: reviewText, action: 'rerun' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '重新生成失败'
      setStatus('awaiting_review')
      setReviewFeedback({ message: msg, tone: 'danger' })
      onError(msg)
    }
  }, [taskId, reviewText, onError])

  const handleReviewTextChange = useCallback((text: string) => {
    setReviewText(text)
    if (reviewFeedback) setReviewFeedback(undefined)
  }, [reviewFeedback])

  const handleReset = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setTaskId(null)
    setStatus('idle')
    setProgress(0)
    setPhaseHint('等待文件进入解析流程')
    setReviewText('')
    setStreamingChunks('')
    setResult(null)
    setPreviewUrls([])
    setOcrThicknessHint('')
    setActiveTab('review')
    setFileName('')
    setAnnotateOpen(false)
    setAnnotateVisited(false)
    setAnnotateSummary({})
    setReviewFeedback(undefined)
  }, [])

  const handleUploadClick = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.pdf,.png,.jpg,.jpeg'
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
  }, [handleFileSelected, handleBatchSelected])

  // Annotation summary label counts
  const summaryEntries = Object.entries(annotateSummary).filter(([, v]) => v > 0)
  const summaryLabels = LABEL_DISPLAY_NAMES
  const labelColors = Object.fromEntries(BUILT_IN_LABELS.map(l => [l.name, l.color]))

  return (
    <div className="flex flex-col gap-0 h-full min-h-0">
      {/* ── HUD ── */}
      <div ref={hudRef} className="shrink-0 px-1">
        <WorkflowHUD progress={progress} phaseHint={phaseHint} busy={busy} completed={completed} />
      </div>

      {/* ── Tab bar: [上传 | 特征审阅 | 工艺规程] ... [导出] [重置] ── */}
      <div ref={tabBarRef} className="shrink-0 flex items-center gap-0 border-b border-slate-200 bg-white px-1">
        <div className="flex items-center gap-0">
          {([
            { id: 'review' as ActiveTab, label: '特征审阅' },
            { id: 'process' as ActiveTab, label: '工艺规程' },
          ]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-2.5 text-[12px] font-semibold transition-all duration-200 border-b-2
                ${activeTab === tab.id
                  ? 'text-orange-600 border-orange-500'
                  : 'text-slate-400 border-transparent hover:text-slate-600'}
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {hasTask && (
          <span className="text-[11px] text-slate-400 ml-2 max-w-[140px] truncate">{fileName}</span>
        )}

        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-1.5 py-1.5">
          {completed && result && (
            <button className="btn btn-ghost !text-[11px] !py-1.5 !px-2.5" onClick={() => setShowExport(true)}>
              <span className="flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                导出
              </span>
            </button>
          )}
          <button className="btn btn-ghost !text-[11px] !py-1.5 !px-2.5" onClick={handleReset}>
            <span className="flex items-center gap-1">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></svg>
              重置
            </span>
          </button>
        </div>
      </div>

      {/* ── Workbench ── */}
      <div ref={workbenchRef} className="flex-1 min-h-0 pt-3">
          {/* ── Two-column: Preview + Review/Process ── */}
          <div className="h-full min-h-0 grid gap-3 items-stretch" style={{ gridTemplateColumns: 'minmax(260px, 1fr) minmax(300px, 1.2fr)' }}>
            {/* Left: Preview / Upload */}
            <div className="card-solid flex flex-col min-h-0 overflow-hidden">
              <UploadPanel
                onFileSelected={handleFileSelected}
                disabled={busy}
                previewUrls={previewUrls.length ? previewUrls : undefined}
                onFullscreen={previewUrls.length ? () => setShowFullscreen(true) : undefined}
                annotationShapes={Object.keys(annotateShapes).length > 0 ? annotateShapes : undefined}
                imageNaturalSize={imgNaturalSize.w > 0 ? imgNaturalSize : undefined}
                labelColors={labelColors}
              />
            </div>

            {/* Right: Review / Process / Annotation Pending */}
            <div className="card-solid flex flex-col min-h-0 overflow-hidden">
              <div className="flex-1 min-h-0 p-4 flex flex-col transition-opacity duration-200">
                {isAnnotating ? (
                  /* ── Annotation Pending Card ── */
                  <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center">
                      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M9 9l6 6m0-6l-6 6" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-[14px] font-bold text-slate-700 mb-1">等待标注确认</h3>
                      <p className="text-[12px] text-slate-400">YOLO 已预标注以下特征，请审阅或补充</p>
                    </div>

                    {/* Summary chips */}
                    {summaryEntries.length > 0 && (
                      <div className="flex items-center gap-2 flex-wrap justify-center">
                        {summaryEntries.map(([key, count]) => (
                          <span key={key} className="chip">
                            {summaryLabels[key] || key}: {count}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center gap-3 mt-2">
                      <button className="btn btn-primary !text-[12px]" onClick={handleOpenAnnotate}>
                        开始标注
                      </button>
                      <button
                        className="btn btn-secondary !text-[12px]"
                        disabled={!annotateVisited}
                        onClick={handleFinalizeAnnotation}
                        title={!annotateVisited ? '请先完成标注' : ''}
                      >
                        完成标注 → 继续
                      </button>
                    </div>
                    {!annotateVisited && (
                      <p className="text-[10px] text-slate-300">需先完成至少一次标注后才能继续</p>
                    )}
                  </div>
                ) : activeTab === 'review' ? (
                  <ReviewPanel
                    reviewText={reviewText}
                    onReviewTextChange={handleReviewTextChange}
                    onConfirm={handleConfirmReview}
                    onRerun={handleRerun}
                    busy={busy}
                    ocrThicknessHint={ocrThicknessHint || undefined}
                    feedback={reviewFeedback}
                  />
                ) : (
                  <ProcessPanel result={result} taskId={taskId} streamingChunks={streamingChunks} />
                )}
              </div>
            </div>
          </div>
      </div>

      {/* ── Export Modal ── */}
      {showExport && result && (
        <ExportModal taskId={taskId!} result={result} onClose={() => setShowExport(false)} />
      )}

      {/* ── Fullscreen Preview ── */}
      {showFullscreen && previewUrls.length > 0 && (
        <FullscreenPreview
          urls={previewUrls}
          startIndex={fullscreenIndex}
          onClose={() => setShowFullscreen(false)}
          annotationShapes={Object.keys(annotateShapes).length > 0 ? annotateShapes : undefined}
          imageNaturalSize={imgNaturalSize.w > 0 ? imgNaturalSize : undefined}
          labelColors={labelColors}
        />
      )}

      {/* ── Annotation Fullscreen Overlay ── */}
      {annotateOpen && taskId && (
        <div className="fixed inset-0 z-[2000] flex flex-col bg-white">
          {/* Top ribbon */}
          <div className="shrink-0 flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-200">
            <span className="text-[13px] font-bold text-slate-700">标注工具</span>
            <div className="flex items-center gap-2">
              <button
                className="btn btn-ghost !text-[11px] !py-1.5 !px-3 text-slate-500 hover:text-flame-600"
                onClick={async () => {
                  try {
                    await annotationRef.current?.saveNow()
                  } catch { onSuccess?.('保存失败') }
                  const counts = annotationRef.current?.getShapeCounts()
                  if (counts) setAnnotateSummary(counts)
                }}
              >
                保存修改
              </button>
              <button
                className="btn btn-ghost !text-[11px] !py-1.5 !px-3 text-slate-500 hover:text-slate-700"
                onClick={handleCloseAnnotate}
              >
                退出标注
              </button>
            </div>
          </div>
          {/* Annotation panel body */}
          <div className="flex-1 min-h-0">
            <AnnotationPanel
              ref={annotationRef}
              taskId={taskId}
              previewImages={previewUrls.map(u => {
                const idx = u.indexOf('/asset/')
                return idx >= 0 ? u.slice(idx + 7) : u.split('/').pop() || u
              })}
              getAssetUrl={(filename) => getAssetUrl(taskId, filename)}
              onClose={() => setAnnotateOpen(false)}
              onSuccess={onSuccess}
              onShapesChanged={setAnnotateShapes}
            />
          </div>
        </div>
      )}
    </div>
  )
}
