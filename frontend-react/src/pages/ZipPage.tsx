import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getLibraryScopes,
  getSampleZipUrl,
  importZipZip,
} from '../api/client'
import type {
  LibraryScope,
  ZipImportReport,
} from '../api/client'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { useAuth } from '../contexts/AuthContext'

type StatusZone = 'idle' | 'running' | 'done' | 'error'
type ResultTab = 'matched' | 'unmatched' | 'log'
type ConflictMode = 'replace' | 'keep'

interface LibraryTarget {
  mode: 'private_seed_public' | 'private_empty' | 'public'
  name: string
  key: string
}

const ZIP_IMPORT_SECONDS_PER_FILE = 120
const ZIP_PROGRESS_INITIAL = 4
const ZIP_PROGRESS_CAP = 97
const ZIP_PROGRESS_TICK_MS = 3000
const ZIP_CACHE_COMPLETION_MS = 15000
const ZIP_NORMAL_COMPLETION_MS = 1800

function formatProgressPercent(value: number): string {
  if (value >= 99.95) return '100'
  return value.toFixed(1)
}

async function countZipEntries(file: File): Promise<number | null> {
  const eocdMinSize = 22
  const maxCommentSize = 0xffff
  if (file.size < eocdMinSize) return null

  const tailStart = Math.max(0, file.size - eocdMinSize - maxCommentSize)
  const tail = await file.slice(tailStart).arrayBuffer()
  const bytes = new Uint8Array(tail)
  const view = new DataView(tail)

  for (let offset = bytes.length - eocdMinSize; offset >= 0; offset -= 1) {
    if (
      bytes[offset] === 0x50 &&
      bytes[offset + 1] === 0x4b &&
      bytes[offset + 2] === 0x05 &&
      bytes[offset + 3] === 0x06
    ) {
      const totalEntries = view.getUint16(offset + 10, true)
      return totalEntries > 0 && totalEntries < 0xffff ? totalEntries : null
    }
  }

  return null
}

export function ZipPage({ onBusyChange }: { onBusyChange?: (busy: boolean) => void }) {
  const { user } = useAuth()
  const [scopes, setScopes] = useState<LibraryScope[]>([])
  const [selectedScope, setSelectedScope] = useState<string>('__new__')
  const [newLibName, setNewLibName] = useState('我的工艺库')
  const [seedPublic, setSeedPublic] = useState(false)
  const [conflictMode, setConflictMode] = useState<ConflictMode>('replace')
  const [statusZone, setStatusZone] = useState<StatusZone>('idle')
  const [resultTab, setResultTab] = useState<ResultTab>('matched')
  const [busy, setBusy] = useState(false)
  // Report busy state to parent (App) for cross-page navigation guarding
  useEffect(() => {
    onBusyChange?.(busy)
    return () => { onBusyChange?.(false) }
  }, [busy, onBusyChange])
  const [report, setReport] = useState<ZipImportReport | null>(null)
  const [phaseText, setPhaseText] = useState('等待上传工艺包')
  const [progressHint, setProgressHint] = useState('')
  const [percent, setPercent] = useState(0)
  const [matchedPage, setMatchedPage] = useState(1)
  const [unmatchedPage, setUnmatchedPage] = useState(1)
  const [dragOver, setDragOver] = useState(false)
  const dropRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const uploadRunIdRef = useRef(0)
  const progressTimerRef = useRef<number | null>(null)
  const completionTimerRef = useRef<number | null>(null)
  const progressPercentRef = useRef(0)

  // Refs for GSAP animations
  const heroRef = useRef<HTMLDivElement>(null)
  const workspaceRef = useRef<HTMLDivElement>(null)
  const statusRef = useRef<HTMLDivElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  const matchCardsRef = useRef<(HTMLDivElement | null)[]>([])
  const reduceMotion = usePrefersReducedMotion()

  const clearProgressTimers = useCallback(() => {
    if (progressTimerRef.current != null) {
      window.clearInterval(progressTimerRef.current)
      progressTimerRef.current = null
    }
    if (completionTimerRef.current != null) {
      window.clearInterval(completionTimerRef.current)
      completionTimerRef.current = null
    }
  }, [])

  const setProgressValue = useCallback((next: number) => {
    const clamped = Math.max(0, Math.min(100, next))
    progressPercentRef.current = clamped
    setPercent(clamped)
  }, [])

  useEffect(() => clearProgressTimers, [clearProgressTimers])

  const animateProgressTo = useCallback((target: number, durationMs: number, runId: number) => {
    return new Promise<void>(resolve => {
      if (completionTimerRef.current != null) {
        window.clearInterval(completionTimerRef.current)
        completionTimerRef.current = null
      }

      const start = progressPercentRef.current
      const startedAt = performance.now()
      const frameMs = reduceMotion ? ZIP_PROGRESS_TICK_MS : 500

      const tick = () => {
        if (uploadRunIdRef.current !== runId) {
          if (completionTimerRef.current != null) window.clearInterval(completionTimerRef.current)
          completionTimerRef.current = null
          resolve()
          return
        }
        const elapsed = performance.now() - startedAt
        const ratio = durationMs <= 0 ? 1 : Math.min(1, elapsed / durationMs)
        setProgressValue(start + (target - start) * ratio)
        if (ratio >= 1) {
          if (completionTimerRef.current != null) window.clearInterval(completionTimerRef.current)
          completionTimerRef.current = null
          resolve()
        }
      }

      tick()
      completionTimerRef.current = window.setInterval(tick, frameMs)
    })
  }, [reduceMotion, setProgressValue])

  const startEstimatedProgress = useCallback((fileCount: number, runId: number) => {
    if (progressTimerRef.current != null) {
      window.clearInterval(progressTimerRef.current)
      progressTimerRef.current = null
    }

    const safeFileCount = Math.max(1, fileCount)
    const estimatedMs = safeFileCount * ZIP_IMPORT_SECONDS_PER_FILE * 1000
    const startedAt = performance.now()
    const totalTicks = Math.max(1, Math.ceil(estimatedMs / ZIP_PROGRESS_TICK_MS))
    const progressPerTick = (ZIP_PROGRESS_CAP - ZIP_PROGRESS_INITIAL) / totalTicks

    setPhaseText('正在提取工艺与图片特征...')
    setProgressHint(`预计 ${safeFileCount} 个文件，按每条约 2 分钟估算，进度每 3 秒平滑推进。`)
    setProgressValue(ZIP_PROGRESS_INITIAL)

    const tick = () => {
      if (uploadRunIdRef.current !== runId) return
      const elapsedTicks = Math.floor((performance.now() - startedAt) / ZIP_PROGRESS_TICK_MS)
      const next = Math.min(ZIP_PROGRESS_CAP, ZIP_PROGRESS_INITIAL + elapsedTicks * progressPerTick)
      setProgressValue(next)
      if (next >= ZIP_PROGRESS_CAP) {
        setPhaseText('正在完成最后一步，请耐心等待')
        setProgressHint('实际入库时间已超过预估，系统仍在写入和整理报告。')
      }
    }

    tick()
    progressTimerRef.current = window.setInterval(tick, ZIP_PROGRESS_TICK_MS)
  }, [setProgressValue])

  const loadScopes = useCallback(async () => {
    try {
      const data = await getLibraryScopes()
      setScopes(data.items || [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadScopes() }, [loadScopes])

  const visibleScopes = scopes.filter(scope => {
    if (user?.role === 'super_admin') return true
    return scope.scope_type !== 'public'
  })

  useEffect(() => {
    if (selectedScope === '__new__') return
    const stillVisible = visibleScopes.some(scope => scope.library_key === selectedScope)
    if (!stillVisible) setSelectedScope('__new__')
  }, [selectedScope, visibleScopes])

  // GSAP: Page load animation
  useEffect(() => {
    if (reduceMotion) {
      if (heroRef.current) {
        const cards = heroRef.current.querySelectorAll('.card-solid')
        gsap.set(cards, { y: 0, opacity: 1 })
      }
      if (workspaceRef.current) gsap.set(workspaceRef.current, { y: 0, opacity: 1 })
      return
    }

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

    if (heroRef.current) {
      const cards = heroRef.current.querySelectorAll('.card-solid')
      tl.fromTo(cards,
        { y: 40, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6, stagger: 0.15 }
      )
    }

    if (workspaceRef.current) {
      tl.fromTo(workspaceRef.current,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5 },
        '-=0.3'
      )
    }

    return () => { tl.kill() }
  }, [reduceMotion])

  // GSAP: Status zone animation
  useEffect(() => {
    if (statusRef.current && (statusZone === 'running' || statusZone === 'done' || statusZone === 'error')) {
      if (reduceMotion) {
        gsap.set(statusRef.current, { y: 0, opacity: 1 })
        return
      }
      gsap.fromTo(statusRef.current,
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4, ease: 'power2.out' }
      )
    }
  }, [statusZone, reduceMotion])

  // GSAP: Result area animation
  useEffect(() => {
    if (resultRef.current && report) {
      if (reduceMotion) {
        gsap.set(resultRef.current, { y: 0, opacity: 1 })
        return
      }
      gsap.fromTo(resultRef.current,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5, ease: 'power2.out' }
      )
    }
  }, [report, reduceMotion])

  // GSAP: Match card hover animation
  const handleMatchCardHover = (index: number, isEnter: boolean) => {
    const card = matchCardsRef.current[index]
    if (!card) return

    if (reduceMotion) {
      gsap.set(card, isEnter
        ? { y: -4, scale: 1.01, boxShadow: '0 8px 24px rgba(0,0,0,0.12)' }
        : { y: 0, scale: 1, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }
      )
      return
    }

    if (isEnter) {
      gsap.to(card, {
        y: -4,
        scale: 1.01,
        boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        duration: 0.25,
        ease: 'power2.out',
      })
    } else {
      gsap.to(card, {
        y: 0,
        scale: 1,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        duration: 0.25,
        ease: 'power2.out',
      })
    }
  }

  // GSAP: Dropzone hover animation
  useEffect(() => {
    if (dropRef.current) {
      if (reduceMotion) {
        gsap.set(dropRef.current, dragOver
          ? { scale: 1.02, borderColor: '#f97316' }
          : { scale: 1, borderColor: '#cbd5e1' }
        )
        return
      }
      if (dragOver) {
        gsap.to(dropRef.current, {
          scale: 1.02,
          borderColor: '#f97316',
          duration: 0.3,
          ease: 'power2.out',
        })
      } else {
        gsap.to(dropRef.current, {
          scale: 1,
          borderColor: '#cbd5e1',
          duration: 0.3,
          ease: 'power2.out',
        })
      }
    }
  }, [dragOver, reduceMotion])

  const currentTarget = useCallback((): LibraryTarget => {
    if (selectedScope === '__new__') {
      return {
        mode: seedPublic ? 'private_seed_public' : 'private_empty',
        name: newLibName.trim() || '我的工艺库',
        key: '',
      }
    }
    const selected = visibleScopes.find(scope => scope.library_key === selectedScope)
    if (selected?.scope_type === 'public') {
      return { mode: 'public', name: '', key: selectedScope }
    }
    return { mode: 'private_empty', name: '', key: selectedScope }
  }, [selectedScope, seedPublic, newLibName, visibleScopes])

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.zip')) return
    const runId = uploadRunIdRef.current + 1
    uploadRunIdRef.current = runId
    clearProgressTimers()
    setBusy(true)
    setStatusZone('running')
    setPhaseText('正在准备入库...')
    setProgressHint('正在读取 ZIP 文件结构。')
    setProgressValue(ZIP_PROGRESS_INITIAL)
    setReport(null)
    setMatchedPage(1)
    setUnmatchedPage(1)

    const target = currentTarget()
    try {
      const zipEntryCount = await countZipEntries(file)
      if (uploadRunIdRef.current !== runId) return
      startEstimatedProgress(zipEntryCount || 10, runId)

      const result = await importZipZip({
        file,
        conflict_mode: conflictMode,
        library_mode: target.mode,
        library_name: target.name,
        library_key: target.key,
      })
      if (uploadRunIdRef.current !== runId) return
      if (progressTimerRef.current != null) {
        window.clearInterval(progressTimerRef.current)
        progressTimerRef.current = null
      }

      if (result.cached) {
        setPhaseText('命中历史入库结果，正在整理入库报告...')
        setProgressHint('已命中缓存，约 15 秒内平滑完成报告展示。')
        await animateProgressTo(100, ZIP_CACHE_COMPLETION_MS, runId)
      } else {
        setPhaseText('正在整理匹配关系与入库报告...')
        setProgressHint('导入结果已返回，正在完成最后的报告展示。')
        await animateProgressTo(100, ZIP_NORMAL_COMPLETION_MS, runId)
      }

      if (uploadRunIdRef.current !== runId) return
      setReport(result)
      setPhaseText('入库完成')
      setProgressHint('')
      setStatusZone('done')
      sessionStorage.setItem('zip_unlocked', 'true')
      loadScopes()
    } catch (err) {
      if (uploadRunIdRef.current !== runId) return
      clearProgressTimers()
      setStatusZone('error')
      setPhaseText(`错误：${err instanceof Error ? err.message : '上传失败'}`)
      setProgressHint('')
    } finally {
      if (uploadRunIdRef.current === runId) {
        setBusy(false)
      }
    }
  }, [animateProgressTo, clearProgressTimers, currentTarget, conflictMode, loadScopes, setProgressValue, startEstimatedProgress])

  const handleFileInput = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.zip'
    input.onchange = () => { const f = input.files?.[0]; if (f) handleUpload(f) }
    input.click()
  }, [handleUpload])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleUpload(f)
  }, [handleUpload])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => setDragOver(false), [])

  const handleReset = useCallback(() => {
    uploadRunIdRef.current += 1
    clearProgressTimers()
    setStatusZone('idle')
    setReport(null)
    setPhaseText('等待上传工艺包')
    setProgressHint('')
    setProgressValue(0)
    setBusy(false)
    setMatchedPage(1)
    setUnmatchedPage(1)
  }, [clearProgressTimers, setProgressValue])

  // Pagination
  const MATCHED_PAGE_SIZE = 1
  const UNMATCHED_PAGE_SIZE = 6
  const matchedPairs = report?.matched_pairs || []
  const unmatchedPdfs = report?.unmatched_xlsx || []
  const unmatchedPrts = report?.unmatched_pdfs || []
  const errors = report?.errors || []
  const matchedTotalPages = Math.max(1, Math.ceil(matchedPairs.length / MATCHED_PAGE_SIZE))
  const unmatchedTotalPages = Math.max(1, Math.max(
    Math.ceil(unmatchedPrts.length / UNMATCHED_PAGE_SIZE),
    Math.ceil(unmatchedPdfs.length / UNMATCHED_PAGE_SIZE),
  ))
  const matchedPageItems = matchedPairs.slice((matchedPage - 1) * MATCHED_PAGE_SIZE, matchedPage * MATCHED_PAGE_SIZE)
  const unmatchedPrtItems = unmatchedPrts.slice((unmatchedPage - 1) * UNMATCHED_PAGE_SIZE, unmatchedPage * UNMATCHED_PAGE_SIZE)
  const unmatchedPdfItems = unmatchedPdfs.slice((unmatchedPage - 1) * UNMATCHED_PAGE_SIZE, unmatchedPage * UNMATCHED_PAGE_SIZE)

  // Log lines
  const logLines = report ? [
    `接收到 ZIP 批次 ${report.zip_name || '工艺包.zip'}。`,
    `图纸 ${report.summary?.prt_count || 0} 个，PDF ${report.summary?.pdf_count || 0} 个。`,
    `已匹配 ${report.summary?.matched_pairs || 0} 组，导入 ${report.summary?.imported_count || 0} 条。`,
    `未匹配图纸 ${unmatchedPrts.length} 项，未匹配 PDF ${unmatchedPdfs.length} 项。`,
    ...errors.slice(0, 3).map(err => `错误：${err.prefix || err.pdf_name || err.image_name || err.prt_name || '批次项'} - ${err.error || err.message || '解析失败'}`),
  ] : []

  const activeScopeLabel = (() => {
    if (selectedScope === '__new__') return `当前目标：${newLibName.trim() || '新工艺库'}（新建）`
    const opt = visibleScopes.find(s => s.library_key === selectedScope)
    return `当前目标：${opt?.library_name || selectedScope}`
  })()

  const heroTitle = user?.role === 'super_admin'
    ? '上传一个 ZIP，把工艺写进你的库或平台基线库。'
    : '上传一个 ZIP，把工艺写进你的个人工艺库。'
  const heroDescription = user?.role === 'super_admin'
    ? '默认推荐先建"我的工艺库"，确认结果后再决定是否补充到平台基线库。这样更稳，也方便平台侧统一校核共享内容。'
    : user?.role === 'enterprise_admin'
      ? '默认推荐先写入我的工艺库，先确认本次导入结果；本阶段企业范围仅做界面引导，不扩展后端入库范围。'
      : '默认推荐先写入我的工艺库，确认后再决定共享。这样最安全，也方便后续只看自己的入库结果。'
  const helperText = user?.role === 'enterprise_admin'
    ? '本阶段企业范围仅做界面引导；真实入库仍写入你当前可用的个人工艺库。'
    : '默认推荐先写入我的工艺库，确认后再决定共享。'

  return (
    <div className="flex flex-col gap-5">
      {/* ── Hero Section ── */}
      <div ref={heroRef} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left card: description */}
        <div className="card-solid relative overflow-hidden">
          {/* Decorative gradient */}
          <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-flame-50/40 to-transparent rounded-bl-full pointer-events-none" />

          <div className="relative z-10">
            <div className="text-[12px] font-bold uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-secondary)' }}>知识库构建</div>
            <h2 className="text-[22px] font-extrabold leading-tight mb-3" style={{ color: 'var(--text-primary)' }}>
              {heroTitle}
            </h2>
            <p className="text-[13px] leading-relaxed mb-4 max-w-[52ch]" style={{ color: 'var(--text-secondary)' }}>
              {heroDescription}
            </p>
            <div className="flex gap-2 flex-wrap">
              <button className="btn btn-primary" onClick={handleFileInput} disabled={busy}>
                <span className="flex items-center gap-2">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  上传工艺包
                </span>
              </button>
              <a className="btn btn-secondary" href={getSampleZipUrl()} download>
                <span className="flex items-center gap-2">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  下载示例 ZIP
                </span>
              </a>
              <button className="btn btn-ghost" onClick={handleReset}>
                <span className="flex items-center gap-1.5">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                  </svg>
                  刷新状态
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Right card: library target */}
        <div className="card-solid flex flex-col gap-3 relative overflow-hidden">
          {/* Decorative gradient */}
          <div className="absolute bottom-0 left-0 w-32 h-32 bg-gradient-to-tr from-orange-50/40 to-transparent rounded-tr-full pointer-events-none" />

          <div className="relative z-10">
            <h3 className="text-[16px] font-bold mb-3" style={{ color: 'var(--text-primary)' }}>入库目标</h3>
            <div className="mb-3">
              <label htmlFor="zip-target-library" className="text-[12px] font-semibold mb-1.5 block" style={{ color: 'var(--text-secondary)' }}>选择目标库</label>
              <select
                id="zip-target-library"
                className="theme-form-field w-full rounded-xl px-3.5 py-2.5 text-[13px] transition-all"
                value={selectedScope}
                onChange={e => setSelectedScope(e.target.value)}
                disabled={busy}
              >
                {visibleScopes.map(s => (
                  <option key={s.library_key} value={s.library_key}>
                    {s.library_name}（{s.scope_type === 'public' ? '平台基线库' : '我的工艺库'}{s.record_count != null ? ` · ${s.record_count}条` : ''}）
                  </option>
                ))}
                <option value="__new__">＋ 新建工艺库</option>
              </select>
            </div>

            {selectedScope === '__new__' && (
              <div className="flex flex-col gap-2 mb-3">
                <input
                  aria-label="新工艺库名称"
                  className="theme-form-field rounded-xl px-3.5 py-2.5 text-[13px] transition-all"
                  placeholder="例如：张三-液压项目库"
                  value={newLibName}
                  onChange={e => setNewLibName(e.target.value)}
                  disabled={busy}
                />
                <label className="flex items-center gap-2 text-[12px] cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
                  <input
                    type="checkbox"
                    checked={seedPublic}
                    onChange={e => setSeedPublic(e.target.checked)}
                    disabled={busy}
                    className="rounded accent-flame-500"
                  />
                  复制公共工艺库基线（推荐）
                </label>
              </div>
            )}

            <div className="flex gap-2 flex-wrap mb-3">
              <span className="theme-surface-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold">
                SQLite：2d-v.db
              </span>
              <span className="theme-surface-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold">
                {activeScopeLabel}
              </span>
            </div>

            <p className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>
              {helperText}
            </p>
          </div>
        </div>
      </div>

      {/* ── Workspace Card ── */}
      <div ref={workspaceRef} className="card-solid flex flex-col gap-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between">
          <div className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>工艺入库工作台</div>
          <button
            className="btn btn-secondary !text-[12px] !py-2"
            onClick={() => setConflictMode(m => m === 'replace' ? 'keep' : 'replace')}
            disabled={busy}
          >
            {conflictMode === 'replace' ? '⇄ 冲突模式：替换入库' : '⇄ 冲突模式：保留旧版'}
          </button>
        </div>

        {/* Status Zone */}
        {statusZone === 'idle' && (
          <div
            ref={dropRef}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={handleFileInput}
            className={`
              dropzone cursor-pointer transition-all duration-300
              ${dragOver ? 'drag-over' : ''}
            `}
          >
            <div className="theme-empty-accent w-16 h-16 rounded-2xl flex items-center justify-center mb-4">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="text-[16px] font-bold mb-1" style={{ color: 'var(--text-primary)' }}>拖拽 ZIP 工艺包到此处</div>
            <div className="text-[12px] max-w-[42ch]" style={{ color: 'var(--text-secondary)' }}>
              或点击上方 <strong>"上传工艺包"</strong> 按钮 · 将 PDF 工艺图纸打包为 ZIP 后上传，文件名主干需与图纸编号一致
            </div>
          </div>
        )}

        {statusZone === 'running' && (
          <div ref={statusRef} className="rounded-2xl border p-5 theme-surface-panel" style={{ borderColor: 'var(--surface-empty-accent-border)', background: 'linear-gradient(135deg, rgba(255,253,249,0.98) 0%, rgba(255,243,232,0.82) 100%)' }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: 'var(--accent-action)' }} />
                <span className="text-[14px] font-bold" style={{ color: 'var(--text-primary)' }}>{phaseText}</span>
              </div>
              <span className="text-[18px] font-extrabold tabular-nums" style={{ color: 'var(--accent-action-strong)' }}>{formatProgressPercent(percent)}%</span>
            </div>
            <div className="h-2.5 rounded-full overflow-hidden mb-4" style={{ background: 'var(--surface-panel-subtle)', border: '1px solid var(--border)' }}>
              <div
                className="zip-progress-fill h-full rounded-full"
                style={{ background: 'var(--accent-action-gradient)', width: `${percent}%` }}
              />
            </div>
            {progressHint && (
              <div className="text-[12px] mb-3" style={{ color: 'var(--text-secondary)' }} aria-live="polite">
                {progressHint}
              </div>
            )}
            {report && (
              <div className="flex gap-5 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                <span>总文件 <strong style={{ color: 'var(--text-primary)' }}>{report.summary?.total_files || 0}</strong></span>
                <span>配对 <strong style={{ color: 'var(--text-primary)' }}>{report.summary?.matched_pairs || 0}</strong></span>
                <span>未匹配 <strong style={{ color: 'var(--text-primary)' }}>{unmatchedPrts.length + unmatchedPdfs.length}</strong></span>
                <span>错误 <strong className="text-red-500">{report.summary?.error_count || 0}</strong></span>
              </div>
            )}
          </div>
        )}

        {(statusZone === 'done' || statusZone === 'error') && (
          <div
            ref={statusRef}
            className={`
              flex items-center gap-4 p-5 rounded-2xl
              ${statusZone === 'error'
                ? 'bg-gradient-to-r from-red-50 to-red-100/50 border border-red-200'
                : 'bg-gradient-to-r from-emerald-50 to-emerald-100/50 border border-emerald-200'}
            `}
          >
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${statusZone === 'error' ? 'bg-red-100' : 'bg-emerald-100'}`}>
              <span className={`text-[24px] ${statusZone === 'error' ? 'text-red-500' : 'text-emerald-500'}`}>
                {statusZone === 'error' ? '✕' : '✓'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <div className={`text-[15px] font-bold ${statusZone === 'error' ? 'text-red-700' : 'text-emerald-700'}`}>
                {statusZone === 'error' ? '入库失败' : report?.cached ? '复用历史入库结果' : '入库完成'}
              </div>
              <div className={`text-[12px] mt-0.5 ${statusZone === 'error' ? 'text-red-500' : 'text-emerald-600'}`}>
                {statusZone === 'error'
                  ? phaseText
                  : report?.cached
                    ? report.message || `批次 ${report?.batch_id || '-'} 已复用，共 ${report?.summary?.matched_pairs || 0} 组匹配。`
                    : `批次 ${report?.batch_id || '-'} 已完成，共 ${report?.summary?.matched_pairs || 0} 组匹配${report?.summary?.error_count ? `，${report.summary.error_count} 项错误` : ''}。`}
              </div>
            </div>
            <button className="btn btn-secondary !text-[12px] !py-2" onClick={handleReset}>再次上传</button>
          </div>
        )}

        {/* Result Area */}
        {report && (
          <div ref={resultRef} className="flex flex-col gap-3">
            {/* Tabs */}
            <div className="flex items-center gap-1 p-1 rounded-xl w-fit" style={{ background: 'var(--surface-panel-subtle)' }}>
              {([
                { id: 'matched' as ResultTab, label: '已匹配记录' },
                { id: 'unmatched' as ResultTab, label: '未匹配项' },
                { id: 'log' as ResultTab, label: '批次日志' },
              ]).map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setResultTab(tab.id)}
                  className={`
                    px-4 py-2 rounded-lg text-[12px] font-semibold transition-all duration-200
                    ${resultTab === tab.id
                      ? 'theme-surface-panel shadow-sm'
                      : ''}
                  `}
                  style={resultTab === tab.id ? { color: 'var(--text-primary)' } : { color: 'var(--text-secondary)' }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            {resultTab === 'matched' && (
              <div>
                {matchedPairs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12" style={{ color: 'var(--text-muted)' }}>
                    <div className="theme-empty-accent w-16 h-16 rounded-full flex items-center justify-center mb-3">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
                        <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18" /><path d="M9 21V9" />
                      </svg>
                    </div>
                    <div className="text-[15px] font-bold" style={{ color: 'var(--text-secondary)' }}>暂无匹配记录</div>
                    <div className="text-[12px] mt-1">点击"上传工艺包"后，这里会展示匹配记录。</div>
                  </div>
                ) : (
                  <>
                    {/* Pager */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>当前页：第 {matchedPage} / {matchedTotalPages} 页</div>
                      <div className="flex gap-2">
                        <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={matchedPage <= 1} onClick={() => setMatchedPage(p => p - 1)}>上一页</button>
                        <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={matchedPage >= matchedTotalPages} onClick={() => setMatchedPage(p => p + 1)}>下一页</button>
                      </div>
                    </div>
                    {/* Match cards */}
                    {matchedPageItems.map((pair, i) => {
                      const draft = pair.draft || {}
                      const processCount = Array.isArray(draft.process_list) ? draft.process_list.length : 0
                      return (
                        <div
                          key={i}
                          ref={el => { matchCardsRef.current[i] = el }}
                          className="theme-surface-panel rounded-2xl border p-4 mb-3 cursor-default"
                          onMouseEnter={() => handleMatchCardHover(i, true)}
                          onMouseLeave={() => handleMatchCardHover(i, false)}
                        >
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <div className="text-[15px] font-extrabold" style={{ color: 'var(--text-primary)' }}>{pair.prefix || '未命名模型'}</div>
                              <div className="text-[12px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                图纸：{(pair.prt_names || []).join(' · ') || '无'} · 工艺：{(pair.xlsx_names || []).join(' · ') || '无'}
                              </div>
                            </div>
                            <span className={`
                              inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold
                              ${pair.status === 'skipped'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}
                            `}>
                              {pair.status === 'skipped' ? '已跳过' : '已导入'}
                            </span>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                            <div className="theme-empty-accent rounded-xl p-3">
                              <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">已有记录</div>
                              <div className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                {pair.existing?.process_summary || pair.existing?.context || '未检测到历史记录'}
                              </div>
                            </div>
                            <div className="rounded-xl bg-gradient-to-br from-emerald-50/50 to-emerald-100/30 border border-emerald-100 p-3">
                              <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">本次导入</div>
                              <div className="text-[12px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                {draft.process_summary || draft.context || '未生成工艺摘要'}
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-2 flex-wrap">
                            <span className="chip">工序 {processCount} 条</span>
                            <span className="chip">视图页数 {draft.pdf_page_count || 0}</span>
                            <span className="chip">冲突模式：{pair.conflict_mode || report.conflict_mode || 'replace'}</span>
                            <span className="chip">目标库：{report.target_library?.library_name || '公共工艺库'}</span>
                          </div>
                        </div>
                      )
                    })}
                  </>
                )}
              </div>
            )}

            {resultTab === 'unmatched' && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>当前页：第 {unmatchedPage} / {unmatchedTotalPages} 页</div>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={unmatchedPage <= 1} onClick={() => setUnmatchedPage(p => p - 1)}>上一页</button>
                    <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={unmatchedPage >= unmatchedTotalPages} onClick={() => setUnmatchedPage(p => p + 1)}>下一页</button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="theme-surface-panel-muted rounded-xl border p-3" style={{ borderColor: 'var(--border)' }}>
                    <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">其他文件</div>
                    <div className="flex flex-wrap gap-2">
                      {unmatchedPrtItems.length ? unmatchedPrtItems.map((f, i) => (
                        <span key={i} className="chip">{f}</span>
                      )) : <span className="chip" style={{ color: 'var(--text-muted)' }}>暂无</span>}
                    </div>
                  </div>
                  <div className="theme-surface-panel-muted rounded-xl border p-3" style={{ borderColor: 'var(--border)' }}>
                    <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">未匹配 PDF</div>
                    <div className="flex flex-wrap gap-2">
                      {unmatchedPdfItems.length ? unmatchedPdfItems.map((f, i) => (
                        <span key={i} className="chip">{f}</span>
                      )) : <span className="chip" style={{ color: 'var(--text-muted)' }}>暂无</span>}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {resultTab === 'log' && (
              <div className="rounded-xl bg-gradient-to-br from-slate-900 to-slate-800 text-slate-200 p-4 font-mono text-[12px] leading-relaxed max-h-[240px] overflow-auto">
                {logLines.map((line, i) => {
                  const d = new Date()
                  d.setSeconds(d.getSeconds() + i)
                  const ts = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
                  return (
                    <div key={i} className="py-1 px-2 rounded hover:bg-white/5 transition-colors">
                      <span className="text-slate-500 mr-3">{ts}</span>
                      <span>{line}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
