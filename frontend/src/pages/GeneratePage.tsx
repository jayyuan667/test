import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { batchUpload, connectSSE, finalizeAnnotation, getAnnotations, getAssetUrl, getResult, submitReview, uploadDrawing, uploadFile, getLibraryScopes } from '../api/client'
import type { TaskResult } from '../types'
import { WorkflowHUD } from '../components/generate/WorkflowHUD'
import { UploadPanel } from '../components/generate/UploadPanel'
import { ReviewPanel } from '../components/generate/ReviewPanel'
import { ProcessPanel, type ProcessRow } from '../components/generate/ProcessPanel'
import { AnnotationPanel, type AnnotationPanelHandle } from '../components/annotate/AnnotationPanel'
import { ExportModal } from '../components/shared/ExportModal'
import { FullscreenPreview } from '../components/generate/FullscreenPreview'
import { LABEL_DISPLAY_NAMES, BUILT_IN_LABELS } from '../types/annotate'
import gsap from 'gsap'

type ActiveTab = 'review' | 'process'

export function GeneratePage({ onError, onSuccess, onBusyChange }: { onError: (msg: string) => void; onSuccess?: (msg: string) => void; onBusyChange?: (busy: boolean) => void }) {
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
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError
  // runToken increments on each new run (upload / confirm / rerun / reset)
  // so ProcessPanel can reset internal state even when taskId stays the same
  const [runToken, setRunToken] = useState(0)

  // Shared SSE connection helper — used by initial upload, confirm, and rerun flows
  const connectStream = useCallback((tid: string) => {
    esRef.current?.close()
    esRef.current = connectSSE(tid, {
      onStepStart(data) { setPhaseHint(String(data.message || data.step_name || '处理中...')) },
      onStepComplete(data) { setPhaseHint(String(data.message || '步骤完成')) },
      onLog(data) { setPhaseHint(String(data.message || '')) },
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
        // Use preview URLs from the event (backend includes them)
        let urls = (data.preview_image_urls as string[]) || []
        // Fallback: fetch from result endpoint if event didn't include URLs
        if (!urls.length) {
          try {
            const res = await getResult(tid) as Record<string, unknown>
            urls = (res.preview_image_urls as string[]) || []
          } catch { /* ignore */ }
        }
        if (urls.length) setPreviewUrls(urls)
      },
      async onComplete() {
        setStatus('completed')
        setProgress(90)
        setPhaseHint('渲染工艺表格...')
        try {
          const res = await getResult(tid)
          setResult(res as unknown as TaskResult)
          const rawUrls = (res as Record<string, unknown>).preview_image_urls as string[] || []
          if (rawUrls.length) {
            setPreviewUrls(rawUrls.map(u => u.startsWith('/api') ? u : getAssetUrl(tid, u)))
          }
          setActiveTab('process')
        } catch { /* already set */ }
      },
      onError(data) {
        const msg = String(data.message || data.error || '处理失败')
        setStatus('error')
        setPhaseHint(`错误：${msg}`)
        onErrorRef.current(msg)
      },
    })
  }, [])
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
  const [editedRows, setEditedRows] = useState<ProcessRow[]>([])

  const annotationRef = useRef<AnnotationPanelHandle>(null)
  const tabContentRef = useRef<HTMLDivElement>(null)
  const annotationOverlayRef = useRef<HTMLDivElement>(null)

  // Retrieval library & feature cache state
  const [retrievalKey, setRetrievalKey] = useState<string>(() => sessionStorage.getItem('retrieval_scope') || 'public')
  const [retrievalName, setRetrievalName] = useState('公共工艺库')
  const [featureCache, setFeatureCache] = useState(false)
  const [showRetrievalModal, setShowRetrievalModal] = useState(false)
  const [libraryScopes, setLibraryScopes] = useState<{ library_key: string; library_name: string; scope_type: string }[]>([])

  // Load library scopes
  useEffect(() => {
    getLibraryScopes().then(data => {
      setLibraryScopes(data.items || [])
      const found = (data.items || []).find((s: { library_key: string }) => s.library_key === retrievalKey)
      if (found) setRetrievalName(found.library_name)
    }).catch(() => {})
  }, [])

  // Load natural image size from first preview
  useEffect(() => {
    if (!previewUrls.length) return
    const img = new Image()
    img.onload = () => setImgNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
    img.src = previewUrls[0]
  }, [previewUrls])

  // Load annotations for preview overlay (only on taskId change)
  // Real-time shape updates come via onShapesChanged callback from AnnotationPanel
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
        // Only update if server returned data — don't overwrite local shapes with empty
        if (Object.keys(shapes).length > 0) {
          setAnnotateShapes(shapes)
          if (Object.keys(counts).length > 0) setAnnotateSummary(counts)
        }
      } catch { /* no annotations yet */ }
    })()
    return () => { cancelled = true }
  }, [taskId])

  // Refs for GSAP animations
  const hudRef = useRef<HTMLDivElement>(null)
  const tabBarRef = useRef<HTMLDivElement>(null)
  const workbenchRef = useRef<HTMLDivElement>(null)

  const busy = status === 'processing' || status === 'pending'
  const completed = status === 'completed'
  const hasTask = taskId !== null
  const isAnnotating = status === 'awaiting_annotation'

  // Notify App when page has active work (prevent navigation away)
  const hasActiveWork = status !== 'idle' && status !== 'completed' && status !== 'error'
  useEffect(() => {
    onBusyChange?.(hasActiveWork)
    return () => { onBusyChange?.(false) }
  }, [hasActiveWork, onBusyChange])

  useEffect(() => { return () => { esRef.current?.close() } }, [])

  // GSAP: Tab content transition
  useEffect(() => {
    if (tabContentRef.current) {
      gsap.fromTo(tabContentRef.current,
        { opacity: 0, x: 12 },
        { opacity: 1, x: 0, duration: 0.3, ease: 'power2.out' }
      )
    }
  }, [activeTab, isAnnotating])

  // GSAP: Annotation overlay entrance
  useEffect(() => {
    if (annotateOpen && annotationOverlayRef.current) {
      gsap.fromTo(annotationOverlayRef.current,
        { opacity: 0, y: 8 },
        { opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }
      )
    }
  }, [annotateOpen])

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

  // GSAP: Workbench cards breathing when busy
  useEffect(() => {
    const wb = workbenchRef.current
    if (!wb) return
    const cards = wb.querySelectorAll('.card-solid')
    if (busy) {
      const tl = gsap.timeline({ repeat: -1, yoyo: true })
        .to(cards, {
          boxShadow: '0 1px 3px rgba(249,115,22,0.04), 0 6px 24px rgba(249,115,22,0.06)',
          duration: 3,
          ease: 'sine.inOut',
          stagger: 0.4,
        })
      return () => { tl.kill() }
    } else {
      cards.forEach(c => gsap.set(c, { boxShadow: '' }))
    }
  }, [busy])

  // GSAP: Tab bar subtle glow when busy
  useEffect(() => {
    const bar = tabBarRef.current
    if (!bar) return
    if (busy) {
      const tl = gsap.timeline({ repeat: -1, yoyo: true })
        .to(bar, {
          borderColor: 'rgba(249,115,22,0.25)',
          duration: 2.5,
          ease: 'sine.inOut',
        })
      return () => { tl.kill() }
    } else {
      gsap.set(bar, { borderColor: '' })
    }
  }, [busy])

  // Annotation handlers
  const handleOpenAnnotate = useCallback(async () => {
    if (!taskId) return
    setAnnotateVisited(true)
    try {
      const data = await getAnnotations(taskId)
      const counts: Record<string, number> = {}
      for (const ann of Object.values(data)) {
        for (const s of (ann.shapes || [])) {
          counts[s.label] = (counts[s.label] || 0) + 1
        }
      }
      if (Object.keys(counts).length > 0) setAnnotateSummary(counts)
    } catch { /* no annotations yet */ }
    setAnnotateOpen(true)
  }, [taskId])

  const handleCloseAnnotate = useCallback(async () => {
    try {
      await annotationRef.current?.saveNow()
    } catch { /* save failed, still close */ }
    // Update summary from current annotations (guarded against empty object)
    const counts = annotationRef.current?.getShapeCounts()
    if (counts && Object.keys(counts).length > 0) setAnnotateSummary(counts)
    // Shapes are already synced via onShapesChanged callback — no need to re-fetch
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
      setEditedRows([])
      setProgress(0)
      setPhaseHint(`正在上传 ${files.length} 个文件...`)
      setStatus('processing')
      setFileName(files.map(f => f.name).join(', '))
      setAnnotateVisited(false)
      setAnnotateSummary({})

      const opts = { retrieval_library_key: retrievalKey, feature_cache: featureCache }
      const { batch_task_id, files: uploaded } = await batchUpload(files, opts)
      setTaskId(batch_task_id)
      setActiveTab('review')
      setPhaseHint(`${uploaded.length} 个文件已上传，等待处理...`)
      setRunToken(t => t + 1)

      connectStream(batch_task_id)
    } catch (err: unknown) {
      setStatus('error')
      const msg = err instanceof Error ? err.message : '批量上传失败'
      setPhaseHint(`上传失败：${msg}`)
      onErrorRef.current(msg)
    }
  }, [connectStream])

  const handleFileSelected = useCallback(async (file: File) => {
    try {
      setResult(null)
      setReviewText('')
      setStreamingChunks('')
      setPreviewUrls([])
      setEditedRows([])
      setProgress(0)
      setPhaseHint('正在上传文件...')
      setStatus('processing')
      setFileName(file.name)
      setAnnotateVisited(false)
      setAnnotateSummary({})

      const ext = file.name.toLowerCase().split('.').pop() || ''
      const isDrawing = ['pdf', 'png', 'jpg', 'jpeg'].includes(ext)
      const opts = { retrieval_library_key: retrievalKey, feature_cache: featureCache }
      const { task_id } = isDrawing ? await uploadDrawing(file, opts) : await uploadFile(file, opts)
      setTaskId(task_id)
      setActiveTab('review')
      setPhaseHint('文件已上传，等待视觉分析...')
      setRunToken(t => t + 1)

      connectStream(task_id)
    } catch (err: unknown) {
      setStatus('error')
      const msg = err instanceof Error ? err.message : '上传失败'
      setPhaseHint(`上传失败：${msg}`)
      onErrorRef.current(msg)
    }
  }, [connectStream])

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
      setPhaseHint('特征已确认，等待后端响应...')
      setResult(null)
      setStreamingChunks('')
      setActiveTab('process')
      setRunToken(t => t + 1)
      // SSE connection stays alive from upload — backend streams on same connection
      await submitReview(taskId, { review_text: reviewText, action: 'continue', library_key: retrievalKey })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '审阅提交失败'
      setStatus('awaiting_review')
      setReviewFeedback({ message: msg, tone: 'danger' })
      onErrorRef.current(msg)
    }
  }, [taskId, reviewText])

  const handleRerun = useCallback(async () => {
    if (!taskId) {
      setReviewFeedback({ message: '暂无可继续的任务', tone: 'danger' })
      return
    }
    try {
      setReviewFeedback(undefined)
      setStatus('processing')
      setProgress(40)
      setPhaseHint('重新生成中，正在特征审阅...')
      setResult(null)
      setStreamingChunks('')
      setActiveTab('process')
      setRunToken(t => t + 1)
      // SSE connection stays alive — backend streams rerun results on same connection
      await submitReview(taskId, { review_text: reviewText, action: 'rerun' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '重新生成失败'
      setStatus('awaiting_review')
      setReviewFeedback({ message: msg, tone: 'danger' })
      onErrorRef.current(msg)
    }
  }, [taskId, reviewText])

  const handleReviewTextChange = useCallback((text: string) => {
    setReviewText(text)
    if (reviewFeedback) setReviewFeedback(undefined)
  }, [reviewFeedback])

  // Typewriter progress → incremental progress bar + dynamic phaseHint
  const progressThrottleRef = useRef(0)

  const handleTypewriterProgress = useCallback((info: { displayed: number; queued: number; currentChar: number; currentTotal: number }) => {
    const active = (info.currentChar < info.currentTotal) ? 1 : 0
    const total = info.displayed + info.queued + active

    // Throttle progress update to ~200ms to avoid excessive re-renders
    const now = Date.now()
    if (total > 0 && now - progressThrottleRef.current > 200) {
      progressThrottleRef.current = now
      const pct = info.displayed / total
      setProgress(60 + Math.round(pct * 25))
    }

    // Phase hint with live count
    if (info.queued > 0 || info.currentChar < info.currentTotal) {
      setPhaseHint(`正在生成工艺规程... 已完成 ${info.displayed} 道工序，共 ${total} 道`)
    } else if (info.displayed > 0) {
      setPhaseHint(`工艺内容生成完成，共 ${info.displayed} 道工序`)
    }
  }, [])

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
    setEditedRows([])
    setRunToken(t => t + 1)
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
      {/* ── Toolbar ── */}
      <div className="shrink-0 flex items-center gap-2 px-2 py-1.5 border-b border-slate-200 bg-white">
        <button
          className="btn btn-secondary !text-[11px] !py-1.5 !px-2.5"
          onClick={() => setShowRetrievalModal(true)}
          disabled={busy}
        >
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            检索库：{retrievalName}
          </span>
        </button>
        <button
          className={`btn !text-[11px] !py-1.5 !px-2.5 ${featureCache ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFeatureCache(c => !c)}
          disabled={busy}
          title="开启后，同一份图纸再次上传时跳过 VLM 提取，直接恢复上次分析结果"
        >
          <span className="flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            特征缓存：{featureCache ? '开' : '关'}
          </span>
        </button>
        <div className="flex-1" />
        <button
          className="btn btn-ghost !text-[11px] !py-1.5 !px-2.5"
          onClick={handleReset}
          disabled={busy}
        >
          <span className="flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></svg>
            重置工作区
          </span>
        </button>
      </div>

      {/* ── HUD ── */}
      <div ref={hudRef} className="shrink-0 px-1">
        <WorkflowHUD progress={progress} phaseHint={phaseHint} busy={busy} completed={completed} waiting={status === 'awaiting_review' || status === 'awaiting_annotation'} />
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
              <div ref={tabContentRef} className="flex-1 min-h-0 p-4 flex flex-col">
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
                    annotateSummary={Object.keys(annotateSummary).length > 0 ? annotateSummary : undefined}
                  />
                ) : (
                  <ProcessPanel
                    result={result}
                    taskId={taskId}
                    runToken={runToken}
                    streamingChunks={streamingChunks}
                    reviewText={reviewText}
                    onTypewriterComplete={() => {
                      setProgress(100)
                      setPhaseHint(`工艺生成完成，共 ${editedRows.length || 0} 道工序`)
                    }}
                    onTypewriterProgress={handleTypewriterProgress}
                    onRowsChange={setEditedRows}
                  />
                )}
              </div>
            </div>
          </div>
      </div>

      {/* ── Export Modal ── */}
      {showExport && result && (
        <ExportModal
          taskId={taskId!}
          result={result}
          reviewText={reviewText}
          editedRows={editedRows}
          onClose={() => setShowExport(false)}
        />
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
        <div ref={annotationOverlayRef} className="fixed inset-0 z-[2000] flex flex-col bg-white">
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

      {/* ── Retrieval Library Modal ── */}
      {showRetrievalModal && (
        <div className="fixed inset-0 z-[9000] flex items-center justify-center" onClick={() => setShowRetrievalModal(false)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="relative bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-[420px] w-[90vw] p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-[16px] font-bold text-slate-800 mb-1">选择检索知识库</h3>
            <p className="text-[12px] text-slate-400 mb-4">工艺生成时用于 RAG 检索的知识库，默认使用公共工艺库。</p>
            <div className="mb-4">
              <div className="text-[12px] text-slate-500 mb-1.5">当前检索库：<span className="font-semibold text-slate-700">{retrievalName}｜{retrievalKey}</span></div>
              <select
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-[13px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-2 focus:ring-flame-glow transition-all"
                value={retrievalKey}
                onChange={e => {
                  const key = e.target.value
                  setRetrievalKey(key)
                  const found = libraryScopes.find(s => s.library_key === key)
                  if (found) setRetrievalName(found.library_name)
                  sessionStorage.setItem('retrieval_scope', key)
                }}
              >
                {libraryScopes.map(s => (
                  <option key={s.library_key} value={s.library_key}>
                    {s.library_name}{s.scope_type === 'public' ? '（默认）' : '（可检索）'}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2 justify-end">
              <button className="btn btn-ghost" onClick={() => setShowRetrievalModal(false)}>取消</button>
              <button className="btn btn-primary" onClick={() => setShowRetrievalModal(false)}>确定</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
