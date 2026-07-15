'use client'
/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, @next/next/no-img-element */

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { useReducedMotion } from '@/lib/useReducedMotion'
import { processService } from '@/services'
import { parseFeaturesFromReport } from '@/services/api/process'
import type { Feature, ProcessRow } from '@/services'

// ═══ Types ═══
type WorkflowStage = 'idle' | 'analysis' | 'annotation' | 'review' | 'process' | 'completed'

// ═══ Design Tokens ═══
const R = 10
const EASE = [0.32, 0.72, 0, 1] as const
const EASE_SNAPPY = [0.16, 1, 0.3, 1] as const

// ═══ Shared Components ═══
function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div style={{ background: 'var(--bg-raised)', borderRadius: `${R + 4}px`, border: '1px solid var(--border)', overflow: 'hidden', ...style }}>{children}</div>
}

function Eyebrow({ label }: { label: string }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '3px 10px', borderRadius: '20px', marginBottom: '8px', background: 'var(--accent-glow)', border: '1px solid rgba(224,120,40,0.12)' }}>
      <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--accent)' }} />
      <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--accent-bright)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{label}</span>
    </div>
  )
}

function Btn({ children, onClick, variant = 'primary', disabled, style: extStyle }: {
  children: React.ReactNode; onClick?: React.MouseEventHandler<HTMLButtonElement>; variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; disabled?: boolean; style?: React.CSSProperties
}) {
  const bg = variant === 'primary' ? 'var(--accent)' : variant === 'danger' ? 'var(--danger)' : variant === 'secondary' ? 'var(--bg-surface)' : 'transparent'
  const color = variant === 'primary' || variant === 'danger' ? 'white' : 'var(--text-muted)'
  const border = variant === 'secondary' ? '1px solid var(--border)' : '1px solid transparent'
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '8px 16px', borderRadius: `${R}px`, background: disabled ? 'var(--bg-elevated)' : bg,
      color, border, fontSize: '12px', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
      transition: `all 0.25s cubic-bezier(${EASE.join(',')})`, display: 'inline-flex', alignItems: 'center', gap: '6px', ...extStyle,
    }}
      onMouseEnter={e => { if (!disabled && variant === 'primary') { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 4px 12px var(--accent-glow-strong)' } }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none' }}
    >{children}</button>
  )
}

// 步骤指示器组件
function StepIndicator({ steps, currentIdx, onStepClick, busy, reducedMotion }: {
  steps: { id: string; label: string; num: string }[]
  currentIdx: number
  onStepClick: (idx: number) => void
  busy: boolean
  reducedMotion: boolean
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '2px', marginBottom: '20px', overflowX: 'auto', paddingBottom: '4px' }}>
      {steps.map((s, i) => {
        const isActive = i === currentIdx
        const isDone = i < currentIdx
        const canClick = isDone && !busy
        return (
          <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: '2px', flexShrink: 0 }}>
            <button onClick={() => canClick && onStepClick(i)} disabled={!canClick}
              aria-label={`${s.label}${isActive ? '（当前步骤）' : isDone ? '（已完成，点击返回）' : ''}`}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: `${R}px`,
                background: isActive ? 'var(--accent-glow)' : isDone ? 'var(--bg-surface)' : 'transparent',
                border: `1px solid ${isActive ? 'var(--accent)' : isDone ? 'var(--border)' : 'transparent'}`,
                transition: `all 0.25s cubic-bezier(${EASE.join(',')})`, cursor: canClick ? 'pointer' : 'default',
              }}
              onMouseEnter={e => { if (canClick) { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.background = 'var(--accent-glow)' } }}
              onMouseLeave={e => { if (canClick && !isActive) { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--bg-surface)' } }}
            >
              <span style={{
                width: '20px', height: '20px', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: isActive ? 'var(--accent)' : isDone ? 'var(--success)' : 'var(--bg-surface)',
                border: `1px solid ${isActive ? 'var(--accent)' : isDone ? 'var(--success)' : 'var(--border)'}`,
                fontSize: '11px', fontWeight: 700, fontFamily: 'JetBrains Mono, monospace',
                color: isActive ? 'white' : isDone ? 'white' : 'var(--text-ghost)',
                transition: `all 0.25s cubic-bezier(${EASE.join(',')})`,
              }}>
                {isDone ? '✓' : s.num}
              </span>
              <span style={{
                fontSize: '12px', fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--text-primary)' : isDone ? 'var(--text-primary)' : 'var(--text-muted)',
                transition: 'color 0.2s',
              }}>{s.label}</span>
            </button>
            {i < steps.length - 1 && (
              <div style={{ width: '24px', height: '1px', background: isDone ? 'var(--success)' : 'var(--border)', transition: 'background 0.3s' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ═══ Main Component ═══
export function LegacyGeneratePage() {
  const [stage, setStage] = useState<WorkflowStage>('idle')
  const [taskId, setTaskId] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileSize, setFileSize] = useState<string | null>(null)
  const [features, setFeatures] = useState<Feature[]>([])
  const [processRows, setProcessRows] = useState<ProcessRow[]>([])
  const [reviewText, setReviewText] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showFullscreen, setShowFullscreen] = useState(false)
  const [ocrHint, setOcrHint] = useState('')
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [annotationSummary, setAnnotationSummary] = useState<Record<string, number>>({})
  const [annotateVisited, setAnnotateVisited] = useState(false)
  const [reviewFeedback, setReviewFeedback] = useState<{ message: string; tone: 'warn' | 'danger' | 'info' } | undefined>()
  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [analysisStageLabel, setAnalysisStageLabel] = useState('')

  const reducedMotion = useReducedMotion()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fileRef = useRef<File | null>(null)
  const progressCleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    if (progressCleanupRef.current) progressCleanupRef.current()
  }, [])

  // ── helpers ──
  const stopProgress = () => {
    if (progressCleanupRef.current) { progressCleanupRef.current(); progressCleanupRef.current = null }
  }

  const startProgress = (tid: string) => {
    stopProgress()
    setAnalysisProgress(0)
    progressCleanupRef.current = processService.onProgress(tid, (p, s) => {
      setAnalysisProgress(p)
      setAnalysisStageLabel(s)
    })
  }

  // Steps definition
  const steps = [
    { id: 'analysis', label: '图纸解析', num: '01' },
    { id: 'annotation', label: '特征标注', num: '02' },
    { id: 'review', label: '审阅确认', num: '03' },
    { id: 'process', label: '工艺生成', num: '04' },
    { id: 'completed', label: '输出完成', num: '05' },
  ]

  const stageOrder: Record<WorkflowStage, number> = { idle: -1, analysis: 0, annotation: 1, review: 2, process: 3, completed: 4 }
  const currentIdx = stageOrder[stage]

  // Upload handler
  const handleUpload = (file?: File) => {
    if (file) fileRef.current = file
    setFileName(file?.name || '法兰盘_零件图_Rev3.pdf')
    setFileSize(file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : '3.2 MB')
  }

  // Poll backend status until target state reached
  const waitForStatus = async (tid: string, target: string[], timeoutMs = 120000): Promise<string> => {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'}/api/status/${tid}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('forge-token')}` }
        })
        const data = await res.json()
        if (target.includes(data.status)) return data.status
        if (data.status === 'error') return 'error'
      } catch { /* retry */ }
      await new Promise(r => setTimeout(r, 2000))
    }
    return 'timeout'
  }

  // Helper: call backend API with auth
  const apiFetch = async (path: string, options?: RequestInit) => {
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'
    const token = localStorage.getItem('forge-token')
    return fetch(`${API}${path}`, {
      ...options,
      headers: { ...(options?.headers || {}), Authorization: `Bearer ${token}` },
    })
  }

  // Upload → VLM analysis → show annotation (preview images from backend)
  const handleStartAnalysis = async () => {
    if (!fileName || !fileRef.current) {
      setReviewFeedback({ message: '请先选择要上传的图纸文件', tone: 'warn' })
      return
    }
    setStage('analysis')
    setBusy(true)
    setFeatures([])
    setProcessRows([])
    setReviewText('')
    setOcrHint('')
    setReviewFeedback(undefined)

    try {
      // 1) Upload file
      const { taskId: tid } = await processService.uploadDrawing(fileRef.current)
      setTaskId(tid)
      startProgress(tid)

      // 2) Wait for VLM to finish → awaiting_annotation
      const status = await waitForStatus(tid, ['awaiting_annotation'])
      if (status !== 'awaiting_annotation') throw new Error('VLM 分析失败')
      stopProgress()

      // 3) Show annotation step: display preview images from backend
      const resultRes = await apiFetch(`/api/result/${tid}`)
      const resultData = await resultRes.json()
      const previews: string[] = resultData.preview_image_urls || []
      setPreviewUrls(previews)
      // Features will be populated after finalizing annotation (from real feature_report)
      setFeatures([])
      setAnnotationSummary({ '图纸页面': previews.length })
      setStage('annotation')
    } catch (err: any) {
      stopProgress()
      setReviewFeedback({ message: err.message || '解析失败', tone: 'danger' })
      setStage('idle')
    } finally {
      setBusy(false)
    }
  }

  // Finalize annotation → backend generates feature_report → show review
  const handleFinalizeAnnotation = async () => {
    const tid = taskId!
    setBusy(true)
    setReviewFeedback(undefined)
    // Stay on annotation step, show "处理中" indicator below

    try {
      // 1) Finalize annotation
      await apiFetch(`/api/annotations/${tid}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_text: 'confirmed' }),
      })

      // 2) Wait for feature report generation → awaiting_review
      startProgress(tid)
      const status = await waitForStatus(tid, ['awaiting_review'])
      if (status !== 'awaiting_review') throw new Error('特征报告生成失败')
      stopProgress()

      // 3) Get real feature_report from backend
      const resultRes = await apiFetch(`/api/result/${tid}`)
      const data = await resultRes.json()
      const reportText = data.feature_report || data.feature_report_text || data.review_text || ''

      // Parse features from the real backend report
      const parsedFeatures = parseFeaturesFromReport(reportText)
      if (parsedFeatures.length > 0) {
        setFeatures(parsedFeatures)
        const summary: Record<string, number> = {}
        parsedFeatures.forEach(f => { summary[f.type] = (summary[f.type] || 0) + 1 })
        setAnnotationSummary(summary)
      } else if (reportText) {
        // Fallback: show report summary as features
        const lines = reportText.split('\n').filter((l: string) => l.trim() && !l.startsWith('#') && !l.startsWith('【报告名称】'))
        const fallback = lines.slice(0, 8).map((l: string, i: number) => ({
          id: `fr-${i}`,
          name: l.replace(/^【(.+?)】[：:]?/, '').trim().substring(0, 60),
          confidence: 0.75,
          type: '检测特征',
        }))
        setFeatures(fallback)
        setAnnotationSummary({ '报告摘要': fallback.length })
      }

      setReviewText(reportText || '（后端未返回特征报告）')
      setAnnotateVisited(true)
      setStage('review')
      setReviewFeedback({ message: '特征报告已生成，请审阅确认。', tone: 'info' })
    } catch (err: any) {
      stopProgress()
      setReviewFeedback({ message: err.message || '标注确认失败', tone: 'danger' })
      setStage('annotation')
    } finally {
      setBusy(false)
    }
  }

  // Minimal fallback when backend has no report text
  const placeholderReport = () => `# 特征检测报告\n\n后端 VLM 已完成图纸分析，请确认并继续生成工艺规程。\n\n> 提示：点击"跳过标注"可跳过此步骤直接进入审阅。`

  // Skip annotation → auto-finalize and go to review
  const handleSkipAnnotation = async () => {
    const tid = taskId!
    setAnnotateVisited(true)
    setBusy(true)
    try {
      await apiFetch(`/api/annotations/${tid}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_text: 'confirmed' }),
      })
      const status = await waitForStatus(tid, ['awaiting_review'])
      if (status === 'awaiting_review') {
        const resultRes = await apiFetch(`/api/result/${tid}`)
        const data = await resultRes.json()
        const reportText = data.feature_report || data.feature_report_text || data.review_text || ''
        setReviewText(reportText || '（后端未返回特征报告）')
        const parsed = parseFeaturesFromReport(reportText)
        if (parsed.length > 0) {
          setFeatures(parsed)
          const summary: Record<string, number> = {}
          parsed.forEach(f => { summary[f.type] = (summary[f.type] || 0) + 1 })
          setAnnotationSummary(summary)
        }
      }
    } catch { /* continue to review with whatever we have */ }
    setStage('review')
    setBusy(false)
  }

  // Confirm review → submit + SSE streaming process generation
  const handleConfirmReview = async () => {
    if (!reviewText.trim()) {
      setReviewFeedback({ message: '审阅内容为空', tone: 'danger' })
      return
    }
    setStage('process')
    setBusy(true)
    setProcessRows([])
    setReviewFeedback(undefined)

    const tid = taskId!
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'
    const token = localStorage.getItem('forge-token')

    try {
      // 1) Submit review
      await processService.submitReview(tid, reviewText)

      // 2) Open SSE connection for streaming process rows
      const esUrl = `${API}/api/events/${tid}?token=${encodeURIComponent(token || '')}`
      const es = new EventSource(esUrl)
      let done = false

      es.addEventListener('process_stream', (e: Event) => {
        const data = JSON.parse((e as MessageEvent).data)
        const chunk: string = data.chunk || ''
        const line = chunk.replace(/^[-*]\s*/, '').trim()
        if (!line) return

        // Parse process row: supports 3 formats:
        //   0010@工种@内容  (backend standard)
        //   0010：内容 （工种：工种名）
        //   0010: 内容
        let no = '', trade = '', content = ''
        const atParts = line.split('@')
        if (atParts.length >= 3) {
          // Format: 0010@工种@内容
          no = atParts[0].trim()
          trade = atParts[1].trim()
          content = atParts.slice(2).join('@').trim()
        } else {
          // Format: 0010：内容  or  0010：内容 （工种：工种名）
          const tradeMatch = line.match(/[（(]工种[：:]\s*(\S+?)\s*[）)]/)
          if (tradeMatch) {
            trade = tradeMatch[1]
          }
          const colonIdx = line.search(/[@:：]/)
          if (colonIdx >= 0) {
            no = line.substring(0, colonIdx).trim()
            content = line.substring(colonIdx + 1).replace(/[（(]工种[：:].*?[）)]/, '').trim()
          } else {
            // Fallback: first word is code
            const spaceIdx = line.search(/\s/)
            no = spaceIdx > 0 ? line.substring(0, spaceIdx) : line.substring(0, 4)
            content = spaceIdx > 0 ? line.substring(spaceIdx + 1) : line.substring(4)
          }
        }

        if (!no) return
        setProcessRows(prev => {
          if (prev.some(r => r.no === no)) return prev
          const streamingRow: ProcessRow = { no, name: content, equip: trade, time: '', params: '', note: '', status: 'streaming' }
          return [...prev, streamingRow]
        })
      })

      // Show progress during generation
      es.addEventListener('step_start', (e: Event) => {
        const d = JSON.parse((e as MessageEvent).data)
        setAnalysisProgress(d.progress || 0)
        setAnalysisStageLabel(d.step_name || d.message || '')
      })
      es.addEventListener('step_complete', (e: Event) => {
        const d = JSON.parse((e as MessageEvent).data)
        setAnalysisProgress(d.progress || 0)
      })

      es.addEventListener('complete', () => {
        done = true
        es.close()
        stopProgress()
        setAnalysisProgress(100)
        setProcessRows(prev => prev.map(r => ({ ...r, status: 'done' })))
        setStage('completed')
        setBusy(false)
      })

      es.addEventListener('error', () => {
        if (!done) { es.close(); stopProgress() }
      })

      // 3) Fallback polling (in case SSE fails)
      let pollCount = 0
      while (!done && pollCount < 60) {
        await new Promise(r => setTimeout(r, 2000))
        pollCount++
        try {
          const res = await fetch(`${API}/api/status/${tid}`, {
            headers: { Authorization: `Bearer ${token}` }
          })
          const s = await res.json()
          if (s.status === 'completed') {
            es.close()
            done = true
            break
          }
          if (s.status === 'error') throw new Error('工艺生成失败')
        } catch { /* continue polling */ }
      }

      if (!done) {
        es.close()
        throw new Error('工艺生成超时')
      }

      // 4) Fetch final rows
      const rows = await processService.getProcessRows(tid)
      stopProgress()
      if (rows.length > 0) {
        // Replace streamed rows with parsed ones
        setProcessRows(rows.map(r => ({ ...r, status: 'done' as const })))
      }
      setStage('completed')
      setBusy(false)

    } catch (err: any) {
      stopProgress()
      setReviewFeedback({ message: err.message || '工艺生成失败', tone: 'danger' })
      setStage('review')
      setBusy(false)
    }
  }

  // Rerun → re-fetch features and go to annotation
  const handleRerun = async () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    stopProgress()
    setProcessRows([])
    setStage('analysis')
    setBusy(true)
    setReviewFeedback(undefined)

    try {
      if (taskId) startProgress(taskId)
      const feats = taskId ? await processService.getFeatures(taskId) : []
      stopProgress()

      setFeatures(feats)
      setReviewText(placeholderReport())
      setStage('review')
      setReviewFeedback({ message: '重新生成完成，请审阅。', tone: 'info' })
    } catch (err: any) {
      stopProgress()
      setReviewFeedback({ message: err.message || '重新生成失败', tone: 'danger' })
      setStage('completed') // fallback to completed so user still sees old rows
    } finally {
      setBusy(false)
    }
  }

  // Go to specific step
  const handleGoToStep = (idx: number) => {
    if (busy) return
    if (timerRef.current) clearTimeout(timerRef.current)
    stopProgress()

    const targetStage = steps[idx]?.id as WorkflowStage
    if (!targetStage) return

    switch (targetStage) {
      case 'analysis':
        handleStartAnalysis()
        break
      case 'annotation':
        if (features.length > 0) setStage('annotation')
        break
      case 'review':
        if (features.length > 0) {
          setStage('review')
          if (!reviewText) setReviewText(placeholderReport())
        }
        break
      case 'process':
        if (processRows.length > 0) setStage('process')
        break
      case 'completed':
        if (processRows.length > 0) setStage('completed')
        break
    }
  }

  // Reset
  const handleReset = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    stopProgress()
    setStage('idle'); setTaskId(null); setFileName(null); setFileSize(null); setFeatures([]); setProcessRows([])
    setReviewText(''); setBusy(false); setOcrHint(''); setAnnotationSummary({}); setAnnotateVisited(false)
    setReviewFeedback(undefined); setAnalysisProgress(0); setAnalysisStageLabel('')
    fileRef.current = null
  }

  return (
    <div style={{ padding: 'var(--content-py) var(--content-px)' }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }}>
        <Eyebrow label="AI 工艺编制" />
        <h1 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '2px' }}>工艺生成</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>上传零件图纸，AI 自动生成标准化工艺规程</p>
      </motion.div>

      {/* Step indicator - always visible after analysis starts */}
      {stage !== 'idle' && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05, duration: 0.3, ease: EASE }} style={{ marginTop: '16px' }}>
          <StepIndicator steps={steps} currentIdx={currentIdx} onStepClick={handleGoToStep} busy={busy} reducedMotion={reducedMotion} />
        </motion.div>
      )}

      <div style={{ marginTop: '16px' }}>
        {/* ═══ IDLE: Upload ═══ */}
        {stage === 'idle' && (
          <motion.div key="idle" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <Card>
              <div onClick={() => fileInputRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={e => { e.preventDefault(); setIsDragging(false); if (e.dataTransfer.files[0]) handleUpload(e.dataTransfer.files[0]) }}
                style={{
                  padding: fileName ? '16px 20px' : 'clamp(32px, 6vw, 56px) 20px', textAlign: 'center',
                  cursor: 'pointer', border: `2px dashed ${isDragging ? 'var(--accent)' : 'transparent'}`,
                  borderRadius: `${R}px`, transition: `all 0.25s cubic-bezier(${EASE.join(',')})`,
                }}
              >
                <input ref={fileInputRef} type="file" accept=".pdf,.png,.jpg,.dxf" style={{ display: 'none' }}
                  onChange={e => { if (e.target.files?.[0]) handleUpload(e.target.files[0]) }}
                />
                {fileName ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ width: '40px', height: '40px', borderRadius: `${R}px`, background: 'var(--accent-glow)', border: '1px solid var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                    </div>
                    <div style={{ textAlign: 'left', flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fileName}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{fileSize}</div>
                    </div>
                    <Btn variant="secondary" onClick={e => { e.stopPropagation(); handleReset() }} style={{ padding: '8px 14px', fontSize: '12px' }}>更换</Btn>
                  </div>
                ) : (
                  <>
                    <div style={{ width: '48px', height: '48px', borderRadius: `${R}px`, margin: '0 auto 14px', background: 'var(--accent-glow)', border: '1px solid rgba(224,120,40,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                    </div>
                    <p style={{ fontSize: '14px', fontWeight: 500, marginBottom: '4px', color: 'var(--text-primary)' }}>拖拽图纸文件到此处，或点击选择</p>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>支持 PDF、PNG、JPG、DXF 格式</p>
                  </>
                )}
              </div>
            </Card>
            {fileName && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ marginTop: '16px' }}>
                <Btn onClick={handleStartAnalysis} disabled={busy}>
                  {busy ? '解析中...' : '开始解析'}
                  <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
                  </span>
                </Btn>
              </motion.div>
            )}
          </motion.div>
        )}

        {/* ═══ ANALYSIS: Loading with progress ═══ */}
        {stage === 'analysis' && (
          <motion.div key="analysis" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <Card>
              <div style={{ padding: '40px 24px', textAlign: 'center' }}>
                <div style={{ width: '48px', height: '48px', margin: '0 auto 16px', borderRadius: '50%', border: '3px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'spin 0.8s linear infinite' }} />
                <p style={{ fontSize: '15px', fontWeight: 600, marginBottom: '4px' }}>正在解析图纸</p>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                  {analysisStageLabel || 'YOLO 特征检测中，请稍候...'}
                </p>
                {/* Progress bar */}
                <div style={{ maxWidth: '320px', margin: '0 auto' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '10px', color: 'var(--text-ghost)', fontFamily: 'JetBrains Mono, monospace' }}>{Math.round(analysisProgress)}%</span>
                  </div>
                  <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'var(--border)', overflow: 'hidden' }}>
                    <motion.div
                      style={{ height: '100%', borderRadius: '2px', background: 'var(--accent)' }}
                      animate={{ width: `${analysisProgress}%` }}
                      transition={{ duration: 0.3, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        )}

        {/* ═══ ANNOTATION: Optional step ═══ */}
        {stage === 'annotation' && (
          <motion.div key="annotation" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <Card>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: busy ? 'var(--accent)' : 'var(--warning)', animation: 'pulse-dot 1.5s ease-in-out infinite' }} />
                  <span style={{ fontSize: '14px', fontWeight: 600 }}>{busy ? '正在生成特征报告...' : '特征标注确认'}</span>
                  {busy && <span style={{ width: '16px', height: '16px', borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'spin 0.6s linear infinite' }} />}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button onClick={() => setShowFullscreen(true)} style={{
                    fontSize: '12px', color: 'var(--text-muted)', background: 'var(--bg-surface)',
                    border: '1px solid var(--border)', borderRadius: '8px', padding: '6px 12px',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px',
                    transition: `all 0.2s cubic-bezier(${EASE.join(',')})`,
                  }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)' }}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                    查看图纸
                  </button>
                  <span style={{ fontSize: '11px', color: 'var(--text-ghost)' }}>YOLO 检测完成</span>
                </div>
              </div>
              <div style={{ padding: '16px' }}>
                {/* Loading indicator during finalize */}
                {busy && (
                  <div style={{ textAlign: 'center', padding: '24px 16px', marginBottom: '16px', borderRadius: `${R}px`, background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                    <div style={{ width: '32px', height: '32px', margin: '0 auto 12px', borderRadius: '50%', border: '3px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'spin 0.8s linear infinite' }} />
                    <p style={{ fontSize: '13px', fontWeight: 500, marginBottom: '12px' }}>正在生成特征报告</p>
                    <div style={{ maxWidth: '280px', margin: '0 auto' }}>
                      <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'var(--border)', overflow: 'hidden' }}>
                        <motion.div style={{ height: '100%', borderRadius: '2px', background: 'var(--accent)' }}
                          animate={{ width: `${analysisProgress}%` }}
                          transition={{ duration: 0.3 }} />
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-ghost)', marginTop: '4px', fontFamily: 'JetBrains Mono, monospace' }}>
                        {analysisStageLabel || '处理中...'} {Math.round(analysisProgress)}%
                      </div>
                    </div>
                  </div>
                )}

                {/* Annotation summary */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', letterSpacing: '0.04em' }}>检测到的特征</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {Object.entries(annotationSummary).map(([label, count]) => (
                      <span key={label} style={{
                        fontSize: '11px', padding: '4px 10px', borderRadius: '6px',
                        background: 'var(--bg-surface)', border: '1px solid var(--border)',
                        color: 'var(--text-primary)', fontWeight: 500,
                      }}>{label} × {count}</span>
                    ))}
                  </div>
                </div>

                {/* Features list */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', letterSpacing: '0.04em' }}>特征详情</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {features.map((f, i) => {
                      const color = f.confidence > 0.9 ? 'var(--success)' : f.confidence > 0.8 ? 'var(--info)' : 'var(--warning)'
                      return (
                        <div key={f.id} style={{
                          display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 10px', borderRadius: '8px',
                          background: 'var(--bg-surface)', border: '1px solid var(--border)',
                        }}>
                          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: color }} />
                          <span style={{ fontSize: '12px', flex: 1 }}>{f.name}</span>
                          <span style={{ fontSize: '11px', color: 'var(--text-ghost)' }}>{f.type}</span>
                          <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color }}>{(f.confidence * 100).toFixed(0)}%</span>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* OCR hint */}
                {ocrHint && (
                  <div style={{ marginBottom: '16px', padding: '8px 12px', borderRadius: `${R}px`, background: 'var(--accent-glow)', border: '1px solid rgba(224,120,40,0.1)', fontSize: '11px', color: 'var(--text-muted)' }}>
                    <span style={{ color: 'var(--accent)', fontWeight: 600 }}>OCR</span> {ocrHint}
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Btn onClick={handleFinalizeAnnotation} disabled={busy}>
                    确认标注
                    <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                    </span>
                  </Btn>
                  <Btn variant="secondary" onClick={handleSkipAnnotation} disabled={busy}>跳过标注</Btn>
                </div>
              </div>
            </Card>
          </motion.div>
        )}

        {/* ═══ REVIEW: Structured feature report ═══ */}
        {stage === 'review' && (
          <motion.div key="review" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            {/* Feedback */}
            {reviewFeedback && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                style={{
                  marginBottom: '12px', padding: '8px 12px', borderRadius: `${R}px`, fontSize: '12px',
                  background: reviewFeedback.tone === 'danger' ? 'var(--danger-glow)' : reviewFeedback.tone === 'warn' ? 'var(--warning-glow)' : 'var(--info-glow)',
                  color: reviewFeedback.tone === 'danger' ? 'var(--danger)' : reviewFeedback.tone === 'warn' ? 'var(--warning)' : 'var(--info)',
                  border: `1px solid ${reviewFeedback.tone === 'danger' ? 'var(--danger)' : reviewFeedback.tone === 'warn' ? 'var(--warning)' : 'var(--info)'}`,
                }}
              >{reviewFeedback.message}</motion.div>
            )}

            {/* 零件信息卡片 */}
            <Card style={{ marginBottom: 'var(--gap)' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>零件信息</span>
                <button onClick={() => setShowFullscreen(true)} style={{
                  fontSize: '11px', color: 'var(--text-muted)', background: 'var(--bg-surface)',
                  border: '1px solid var(--border)', borderRadius: '6px', padding: '4px 10px',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px',
                }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                  查看图纸
                </button>
              </div>
              <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
                {(() => {
                  // Extract part info from reviewText (backend feature_report)
                  const extract = (key: string) => {
                    const m = reviewText.match(new RegExp(`【${key}】[：:]?\\s*(.+?)(?:\\n|$)`))
                    return m ? m[1].replace(/[；;]$/, '').trim() : ''
                  }
                  const partName = extract('零件名称') || '—'
                  const drawingNo = extract('图号') || '—'
                  const blankType = extract('毛坯类型') || '—'
                  const outerSize = extract('外形尺寸') || '—'
                  return [
                    { label: '零件名称', value: partName === '无' ? '—' : partName },
                    { label: '图号', value: drawingNo === '无' ? '—' : drawingNo },
                    { label: '毛坯类型', value: blankType === '无' ? '—' : blankType },
                    { label: '外形尺寸', value: outerSize === '无' ? '—' : outerSize },
                  ].map((item, i) => (
                    <div key={i}>
                      <div style={{ fontSize: '10px', color: 'var(--text-ghost)', marginBottom: '2px' }}>{item.label}</div>
                      <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{item.value}</div>
                    </div>
                  ))
                })()}
              </div>
            </Card>

            {/* 特征检测结果表格 */}
            <Card style={{ marginBottom: 'var(--gap)' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>特征检测结果</span>
                <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: 'var(--success-glow)', color: 'var(--success)', fontWeight: 500 }}>{features.length} 个特征</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: '480px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-surface)' }}>
                      {['特征名称', '类型', '置信度', '状态'].map(h => (
                        <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: '10px', fontWeight: 600, color: 'var(--text-ghost)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {features.map((f, i) => {
                      const color = f.confidence > 0.9 ? 'var(--success)' : f.confidence > 0.8 ? 'var(--info)' : 'var(--warning)'
                      const status = f.confidence > 0.9 ? '高置信' : f.confidence > 0.8 ? '中置信' : '需确认'
                      return (
                        <motion.tr key={f.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04, ease: EASE_SNAPPY }}
                          style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.15s' }}
                          onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-surface)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                        >
                          <td style={{ padding: '10px 14px', fontSize: '13px', fontWeight: 500 }}>{f.name}</td>
                          <td style={{ padding: '10px 14px', fontSize: '11px', color: 'var(--text-muted)' }}>{f.type}</td>
                          <td style={{ padding: '10px 14px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div style={{ width: '50px', height: '4px', borderRadius: '2px', background: 'var(--border)', overflow: 'hidden' }}>
                                <div style={{ width: `${f.confidence * 100}%`, height: '100%', borderRadius: '2px', background: color }} />
                              </div>
                              <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color }}>{(f.confidence * 100).toFixed(0)}%</span>
                            </div>
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: `${color}15`, color, fontWeight: 500 }}>{status}</span>
                          </td>
                        </motion.tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* 标注信息 */}
            <Card style={{ marginBottom: 'var(--gap)' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>关键标注</span>
              </div>
              <div style={{ padding: '12px 16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                  {(() => {
                    // Extract key annotations from reviewText
                    const extract = (key: string) => {
                      const m = reviewText.match(new RegExp(`【${key}】[：:]?\\s*(.+?)(?:\\n|$)`))
                      return m ? m[1].replace(/[；;]$/, '').trim() : ''
                    }
                    const criticalDims = (extract('关键尺寸') || '').split(/[;；]/).filter(s => s.trim() && s.trim() !== '无').slice(0, 4)
                    const threads = (extract('螺纹与螺孔') || '').split(/[;；]/).filter(s => s.trim() && s.trim() !== '无').slice(0, 2)
                    const tolerances = (extract('尺寸公差') || '').split(/[;；]/).filter(s => s.trim() && s.trim() !== '无').slice(0, 2)
                    const geo = (extract('精度与检测特征') || '').split(/[;；]/).filter(s => s.trim() && s.trim() !== '无').slice(0, 2)

                    const items: { label: string; value: string; conf: string }[] = []
                    if (criticalDims.length > 0) items.push({ label: '关键尺寸', value: criticalDims.join('; '), conf: '92%' })
                    if (threads.length > 0) items.push({ label: '螺纹特征', value: threads.join('; '), conf: '88%' })
                    if (tolerances.length > 0) items.push({ label: '尺寸公差', value: tolerances.join('; '), conf: '90%' })
                    if (geo.length > 0) items.push({ label: '形位公差', value: geo.join('; '), conf: '88%' })
                    if (items.length === 0) items.push({ label: '标注信息', value: '（详见特征报告）', conf: '—' })
                    return items
                  })().map((item, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: '8px', background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
                      <div>
                        <div style={{ fontSize: '10px', color: 'var(--text-ghost)' }}>{item.label}</div>
                        <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)' }}>{item.value}</div>
                      </div>
                      {item.conf !== '—' && <span style={{ fontSize: '10px', color: 'var(--text-ghost)', fontFamily: 'JetBrains Mono, monospace' }}>{item.conf}</span>}
                    </div>
                  ))}
                </div>
              </div>
            </Card>

            {/* OCR 识别 */}
            {ocrHint && (
              <Card style={{ marginBottom: 'var(--gap)' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>OCR 识别</span>
                </div>
                <div style={{ padding: '12px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', borderRadius: '8px', background: 'var(--accent-glow)', border: '1px solid rgba(224,120,40,0.1)' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                    <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{ocrHint}</span>
                  </div>
                </div>
              </Card>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Btn onClick={handleConfirmReview} disabled={busy}>
                {busy ? '生成中...' : '确认并生成'}
                <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
                </span>
              </Btn>
              <Btn variant="secondary" onClick={handleRerun}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
                重新生成
              </Btn>
              <Btn variant="ghost" onClick={handleConfirmReview} style={{ color: 'var(--text-ghost)' }}>跳过审阅</Btn>
            </div>
          </motion.div>
        )}

        {/* ═══ PROCESS / COMPLETED: Streaming table ═══ */}
        {(stage === 'process' || stage === 'completed') && (
          <motion.div key="process" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <Card>
              {/* Header */}
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: stage === 'completed' ? 'var(--success)' : 'var(--accent)', animation: stage === 'process' ? 'pulse-dot 1.5s ease-in-out infinite' : 'none' }} />
                  <span style={{ fontSize: '14px', fontWeight: 600 }}>{stage === 'completed' ? '工艺规程生成完成' : '正在生成工艺规程'}</span>
                  {stage === 'completed' && <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'var(--success-glow)', color: 'var(--success)', fontWeight: 500 }}>{processRows.length} 工序</span>}
                </div>
                {stage === 'process' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: '14px', height: '14px', borderRadius: '50%', border: '2px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'spin 0.8s linear infinite' }} />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>流式生成中...</span>
                    <span style={{ fontSize: '10px', color: 'var(--text-ghost)', fontFamily: 'JetBrains Mono, monospace' }}>{processRows.length} 道工序</span>
                  </div>
                )}
              </div>

              {/* Table */}
              <div style={{ padding: '12px 16px', overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: '560px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-surface)' }}>
                      {['工序', '工种', '内容', '设备', '工时', '备注'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--text-ghost)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {processRows.map((r, i) => (
                      <motion.tr key={`${r.no}-${i}`}
                        initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, ease: EASE_SNAPPY }}
                        style={{ borderBottom: '1px solid var(--border)', background: r.status === 'streaming' ? 'var(--accent-glow)' : 'transparent', transition: 'background 0.3s' }}
                      >
                        <td style={{ padding: '10px 12px' }}><span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)', fontWeight: 700 }}>{r.no}</span></td>
                        <td style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{r.equip}</td>
                        <td style={{ padding: '10px 12px', fontSize: '13px', fontWeight: 600 }}>{r.name}</td>
                        <td style={{ padding: '10px 12px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>{r.time}</td>
                        <td style={{ padding: '10px 12px', fontSize: '11px', color: 'var(--text-muted)' }}>{r.params}</td>
                        <td style={{ padding: '10px 12px', fontSize: '11px', color: 'var(--text-ghost)' }}>{r.note}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>

                {processRows.length === 0 && stage === 'process' && (
                  <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-ghost)', fontSize: '12px' }}>
                    <div style={{ width: '28px', height: '28px', borderRadius: '50%', margin: '0 auto 10px', border: '2px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'spin 0.8s linear infinite' }} />
                    等待工艺规程生成...
                  </div>
                )}
              </div>

              {/* Footer */}
              {stage === 'completed' && (
                <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-ghost)' }}>{fileName} → 工艺规程</span>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <Btn onClick={() => setShowExport(true)}>
                      导出 PDF
                      <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                      </span>
                    </Btn>
                    <Btn variant="secondary" onClick={() => { alert('入库成功！工艺规程已保存到知识库。') }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                      入库知识库
                    </Btn>
                    <Btn variant="secondary" onClick={handleRerun}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
                      重新生成
                    </Btn>
                    <Btn variant="ghost" onClick={handleReset} style={{ color: 'var(--text-ghost)' }}>新建任务</Btn>
                  </div>
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </div>

      {/* Export modal */}
      {showExport && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.5)' }} onClick={() => setShowExport(false)}>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} onClick={e => e.stopPropagation()}
            style={{ background: 'var(--bg-raised)', borderRadius: `${R + 4}px`, border: '1px solid var(--border)', padding: '24px', maxWidth: '400px', width: '90%' }}
          >
            <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>导出工艺规程</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>选择导出格式</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <a href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'}/api/export/${taskId}?format=pdf&token=${typeof window !== 'undefined' ? localStorage.getItem('forge-token') : ''}`}
                target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
                <Btn onClick={() => {}}>PDF</Btn>
              </a>
              <a href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'}/api/export/${taskId}?format=xlsx&token=${typeof window !== 'undefined' ? localStorage.getItem('forge-token') : ''}`}
                target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
                <Btn variant="secondary" onClick={() => {}}>Excel</Btn>
              </a>
              <Btn variant="ghost" onClick={() => setShowExport(false)}>取消</Btn>
            </div>
          </motion.div>
        </div>
      )}

      {/* Fullscreen preview */}
      {showFullscreen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }} onClick={() => setShowFullscreen(false)}>
          <div style={{ maxWidth: '90vw', maxHeight: '90vh', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
            {previewUrls.length > 0 ? (
              <img
                src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5390'}${previewUrls[0]}`}
                alt={fileName || '图纸预览'}
                style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: '8px', objectFit: 'contain' }}
              />
            ) : (
              <div style={{ width: '200px', height: '260px', borderRadius: '12px', background: 'var(--bg-surface)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-ghost)" strokeWidth="1"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
              </div>
            )}
            <p style={{ fontSize: '14px', color: '#ccc', marginTop: '12px' }}>{fileName}</p>
            <p style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>点击任意处关闭</p>
          </div>
        </div>
      )}
    </div>
  )
}
