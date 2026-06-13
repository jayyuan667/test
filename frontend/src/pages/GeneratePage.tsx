import { useCallback, useEffect, useRef, useState } from 'react'
import { connectSSE, getAssetUrl, getResult, submitReview, uploadFile } from '../api/client'
import type { TaskResult } from '../types'
import { WorkflowHUD } from '../components/generate/WorkflowHUD'
import { UploadPanel } from '../components/generate/UploadPanel'
import { ReviewPanel } from '../components/generate/ReviewPanel'
import { ProcessPanel } from '../components/generate/ProcessPanel'
import gsap from 'gsap'

type ActiveTab = 'review' | 'process'

export function GeneratePage({ onError }: { onError: (msg: string) => void }) {
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

  // Refs for GSAP animations
  const topBarRef = useRef<HTMLDivElement>(null)
  const hudRef = useRef<HTMLDivElement>(null)
  const tabBarRef = useRef<HTMLDivElement>(null)
  const workbenchRef = useRef<HTMLDivElement>(null)

  const busy = status === 'processing' || status === 'pending'
  const completed = status === 'completed'
  const hasTask = taskId !== null

  useEffect(() => { return () => { esRef.current?.close() } }, [])

  // GSAP: Page load animation
  useEffect(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

    if (topBarRef.current) {
      tl.fromTo(topBarRef.current,
        { y: -20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5 }
      )
    }

    if (hudRef.current) {
      tl.fromTo(hudRef.current,
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5 },
        '-=0.3'
      )
    }

    if (tabBarRef.current) {
      tl.fromTo(tabBarRef.current,
        { y: 15, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4 },
        '-=0.3'
      )
    }

    if (workbenchRef.current) {
      const cards = workbenchRef.current.querySelectorAll('.card-solid')
      tl.fromTo(cards,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6, stagger: 0.15 },
        '-=0.3'
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

      const { task_id } = await uploadFile(file)
      setTaskId(task_id)
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
          setReviewText(String(data.content || ''))
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
    if (!taskId) return
    try {
      setStatus('processing')
      setProgress(60)
      setPhaseHint('特征已确认，正在生成工艺规程...')
      setStreamingChunks('')
      setActiveTab('process')
      await submitReview(taskId, { review_text: reviewText, action: 'continue' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '提交失败'
      setStatus('awaiting_review')
      onError(msg)
    }
  }, [taskId, reviewText, onError])

  const handleRerun = useCallback(async () => {
    if (!taskId) return
    try {
      setStatus('processing')
      setProgress(50)
      setPhaseHint('修改已提交，正在重新生成...')
      setStreamingChunks('')
      setActiveTab('process')
      await submitReview(taskId, { review_text: reviewText, action: 'rerun' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '重新生成失败'
      setStatus('awaiting_review')
      onError(msg)
    }
  }, [taskId, reviewText, onError])

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
  }, [])

  const handleUploadClick = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.pdf,.png,.jpg,.jpeg'
    input.onchange = () => { const f = input.files?.[0]; if (f) handleFileSelected(f) }
    input.click()
  }, [handleFileSelected])

  return (
    <div className="flex flex-col gap-4 h-full min-h-0">
      {/* Top bar */}
      <div ref={topBarRef} className="flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <button className="btn btn-primary" onClick={handleUploadClick}>
            <span className="flex items-center gap-2">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              上传文件
            </span>
          </button>
          {hasTask && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/60 border border-slate-200/60">
              <span className="w-1.5 h-1.5 rounded-full bg-flame-500" />
              <span className="text-[12px] font-medium text-slate-600 max-w-[200px] truncate">{fileName}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {hasTask && (
            <button className="btn btn-ghost !text-[12px]" onClick={handleReset}>
              <span className="flex items-center gap-1.5">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></svg>
                重置
              </span>
            </button>
          )}
        </div>
      </div>

      {/* HUD */}
      <div ref={hudRef}>
        <WorkflowHUD progress={progress} phaseHint={phaseHint} busy={busy} completed={completed} />
      </div>

      {/* Tab bar */}
      <div ref={tabBarRef} className="flex items-center gap-1 shrink-0 p-1 rounded-xl bg-gradient-to-r from-slate-100/80 to-slate-50/80 w-fit">
        {([
          { id: 'review' as ActiveTab, label: '特征审阅' },
          { id: 'process' as ActiveTab, label: '工艺规程' },
        ]).map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              px-4 py-2 rounded-lg text-[12px] font-semibold transition-all duration-200
              ${activeTab === tab.id
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'}
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Workbench */}
      <div ref={workbenchRef} className="flex-1 min-h-0 grid gap-4 items-stretch" style={{ gridTemplateColumns: 'minmax(280px, 1fr) minmax(320px, 1.2fr)' }}>
        {/* Left: Upload / Preview */}
        <div className="card-solid flex flex-col min-h-0 overflow-hidden">
          <UploadPanel
            onFileSelected={handleFileSelected}
            disabled={busy}
            previewUrls={previewUrls.length ? previewUrls : undefined}
          />
        </div>

        {/* Right: Review / Process */}
        <div className="card-solid flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 p-5 flex flex-col transition-opacity duration-200">
            {activeTab === 'review' ? (
              <ReviewPanel
                reviewText={reviewText}
                onReviewTextChange={setReviewText}
                onConfirm={handleConfirmReview}
                onRerun={handleRerun}
                busy={busy}
                ocrThicknessHint={ocrThicknessHint || undefined}
              />
            ) : (
              <ProcessPanel result={result} taskId={taskId} streamingChunks={streamingChunks} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
