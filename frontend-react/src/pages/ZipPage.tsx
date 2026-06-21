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

type StatusZone = 'idle' | 'running' | 'done' | 'error'
type ResultTab = 'matched' | 'unmatched' | 'log'
type ConflictMode = 'replace' | 'keep'

interface LibraryTarget {
  mode: 'private_seed_public' | 'private_empty' | 'public'
  name: string
  key: string
}

export function ZipPage({ onBusyChange }: { onBusyChange?: (busy: boolean) => void }) {
  const [scopes, setScopes] = useState<LibraryScope[]>([])
  const [selectedScope, setSelectedScope] = useState<string>('__new__')
  const [newLibName, setNewLibName] = useState('我的工艺库')
  const [seedPublic, setSeedPublic] = useState(true)
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
  const [percent, setPercent] = useState(0)
  const [matchedPage, setMatchedPage] = useState(1)
  const [unmatchedPage, setUnmatchedPage] = useState(1)
  const [dragOver, setDragOver] = useState(false)
  const dropRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Refs for GSAP animations
  const heroRef = useRef<HTMLDivElement>(null)
  const workspaceRef = useRef<HTMLDivElement>(null)
  const statusRef = useRef<HTMLDivElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  const matchCardsRef = useRef<(HTMLDivElement | null)[]>([])
  const reduceMotion = usePrefersReducedMotion()

  const loadScopes = useCallback(async () => {
    try {
      const data = await getLibraryScopes()
      setScopes(data.items || [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadScopes() }, [loadScopes])

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
    return { mode: 'private_empty', name: '', key: selectedScope }
  }, [selectedScope, seedPublic, newLibName])

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.zip')) return
    setBusy(true)
    setStatusZone('running')
    setPhaseText('正在上传并解析...')
    setPercent(10)
    setReport(null)
    setMatchedPage(1)
    setUnmatchedPage(1)

    const target = currentTarget()
    try {
      setPercent(30)
      setPhaseText('正在解析知识库内容...')
      const result = await importZipZip({
        file,
        conflict_mode: conflictMode,
        library_mode: target.mode,
        library_name: target.name,
        library_key: target.key,
      })
      setPercent(60)
      setPhaseText('正在整理匹配关系...')
      setReport(result)
      await new Promise(r => setTimeout(r, 400))
      setPercent(85)
      setPhaseText('正在写入目标库...')
      await new Promise(r => setTimeout(r, 400))
      setPercent(100)
      setPhaseText('入库完成')
      setStatusZone('done')
      sessionStorage.setItem('zip_unlocked', 'true')
      loadScopes()
    } catch (err) {
      setStatusZone('error')
      setPhaseText(`错误：${err instanceof Error ? err.message : '上传失败'}`)
    } finally {
      setBusy(false)
    }
  }, [currentTarget, conflictMode, loadScopes])

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
    setStatusZone('idle')
    setReport(null)
    setPhaseText('等待上传工艺包')
    setPercent(0)
    setBusy(false)
    setMatchedPage(1)
    setUnmatchedPage(1)
  }, [])

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
    ...errors.slice(0, 3).map(err => `错误：${err.prefix || err.pdf_name || err.prt_name || '批次项'} - ${err.error || err.message || '解析失败'}`),
  ] : []

  const activeScopeLabel = (() => {
    if (selectedScope === '__new__') return `当前目标：${newLibName.trim() || '新工艺库'}（新建）`
    const opt = scopes.find(s => s.library_key === selectedScope)
    return `当前目标：${opt?.library_name || selectedScope}`
  })()

  return (
    <div className="flex flex-col gap-5">
      {/* ── Hero Section ── */}
      <div ref={heroRef} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left card: description */}
        <div className="card-solid relative overflow-hidden">
          {/* Decorative gradient */}
          <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-flame-50/40 to-transparent rounded-bl-full pointer-events-none" />

          <div className="relative z-10">
            <div className="text-[12px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">知识库构建</div>
            <h2 className="text-[22px] font-extrabold text-slate-800 leading-tight mb-3">
              上传一个 ZIP，把工艺直接写进你的库或公共库。
            </h2>
            <p className="text-[13px] text-slate-500 leading-relaxed mb-4 max-w-[52ch]">
              默认推荐先建"我的工艺库"，可选复制公共基线后再导入。这样最安全，也方便后续只看自己的入库结果；如需共享，再直接追加到公共库。
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
          <div className="absolute bottom-0 left-0 w-32 h-32 bg-gradient-to-tr from-blue-50/40 to-transparent rounded-tr-full pointer-events-none" />

          <div className="relative z-10">
            <h3 className="text-[16px] font-bold text-slate-800 mb-3">入库目标</h3>
            <div className="mb-3">
              <label htmlFor="zip-target-library" className="text-[12px] font-semibold text-slate-500 mb-1.5 block">选择目标库</label>
              <select
                id="zip-target-library"
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-[13px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-2 focus:ring-flame-glow transition-all"
                value={selectedScope}
                onChange={e => setSelectedScope(e.target.value)}
                disabled={busy}
              >
                {scopes.map(s => (
                  <option key={s.library_key} value={s.library_key}>
                    {s.library_name}（{s.scope_type === 'public' ? '公共库' : '私有库'}{s.record_count != null ? ` · ${s.record_count}条` : ''}）
                  </option>
                ))}
                <option value="__new__">＋ 新建工艺库</option>
              </select>
            </div>

            {selectedScope === '__new__' && (
              <div className="flex flex-col gap-2 mb-3">
                <input
                  aria-label="新工艺库名称"
                  className="rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-[13px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-2 focus:ring-flame-glow transition-all"
                  placeholder="例如：张三-液压项目库"
                  value={newLibName}
                  onChange={e => setNewLibName(e.target.value)}
                  disabled={busy}
                />
                <label className="flex items-center gap-2 text-[12px] text-slate-600 cursor-pointer">
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
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-r from-slate-50 to-slate-100 border border-slate-200 text-[11px] font-semibold text-slate-500">
                SQLite：2d-v.db
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-r from-slate-50 to-slate-100 border border-slate-200 text-[11px] font-semibold text-slate-500">
                {activeScopeLabel}
              </span>
            </div>

            <p className="text-[11px] text-slate-500">
              数据库浏览页会在至少完成一次 ZIP 入库后解锁，并默认打开你刚刚导入的那一个库。
            </p>
          </div>
        </div>
      </div>

      {/* ── Workspace Card ── */}
      <div ref={workspaceRef} className="card-solid flex flex-col gap-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between">
          <div className="text-[12px] font-bold text-slate-500 uppercase tracking-wider">工艺入库工作台</div>
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
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center mb-4">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="text-[16px] font-bold text-slate-600 mb-1">拖拽 ZIP 工艺包到此处</div>
            <div className="text-[12px] text-slate-500 max-w-[42ch]">
              或点击上方 <strong>"上传工艺包"</strong> 按钮 · 将 PDF 工艺图纸打包为 ZIP 后上传，文件名主干需与图纸编号一致
            </div>
          </div>
        )}

        {statusZone === 'running' && (
          <div ref={statusRef} className="rounded-2xl border border-blue-200 bg-gradient-to-br from-white to-blue-50/50 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
                <span className="text-[14px] font-bold text-slate-800">{phaseText}</span>
              </div>
              <span className="text-[18px] font-extrabold text-blue-600 tabular-nums">{percent}%</span>
            </div>
            <div className="h-2.5 rounded-full bg-slate-100 border border-slate-200 overflow-hidden mb-4">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-500 ease-out"
                style={{ width: `${percent}%` }}
              />
            </div>
            {report && (
              <div className="flex gap-5 text-[12px] text-slate-500">
                <span>总文件 <strong className="text-slate-700">{report.summary?.total_files || 0}</strong></span>
                <span>配对 <strong className="text-slate-700">{report.summary?.matched_pairs || 0}</strong></span>
                <span>未匹配 <strong className="text-slate-700">{unmatchedPrts.length + unmatchedPdfs.length}</strong></span>
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
                {statusZone === 'error' ? '入库失败' : '入库完成'}
              </div>
              <div className={`text-[12px] mt-0.5 ${statusZone === 'error' ? 'text-red-500' : 'text-emerald-600'}`}>
                {statusZone === 'error'
                  ? phaseText
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
            <div className="flex items-center gap-1 p-1 rounded-xl bg-gradient-to-r from-slate-100/80 to-slate-50/80 w-fit">
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
                      ? 'bg-white text-slate-800 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'}
                  `}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            {resultTab === 'matched' && (
              <div>
                {matchedPairs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                    <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center mb-3">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-blue-400">
                        <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18" /><path d="M9 21V9" />
                      </svg>
                    </div>
                    <div className="text-[15px] font-bold text-slate-500">暂无匹配记录</div>
                    <div className="text-[12px] mt-1">点击"上传工艺包"后，这里会展示匹配记录。</div>
                  </div>
                ) : (
                  <>
                    {/* Pager */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-[12px] text-slate-500">当前页：第 {matchedPage} / {matchedTotalPages} 页</div>
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
                          className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50/50 p-4 mb-3 cursor-default"
                          onMouseEnter={() => handleMatchCardHover(i, true)}
                          onMouseLeave={() => handleMatchCardHover(i, false)}
                        >
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <div className="text-[15px] font-extrabold text-slate-800">{pair.prefix || '未命名模型'}</div>
                              <div className="text-[12px] text-slate-500 mt-0.5">
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
                            <div className="rounded-xl bg-gradient-to-br from-blue-50/50 to-blue-100/30 border border-blue-100 p-3">
                              <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">已有记录</div>
                              <div className="text-[12px] text-slate-600 leading-relaxed">
                                {pair.existing?.process_summary || pair.existing?.context || '未检测到历史记录'}
                              </div>
                            </div>
                            <div className="rounded-xl bg-gradient-to-br from-emerald-50/50 to-emerald-100/30 border border-emerald-100 p-3">
                              <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">本次导入</div>
                              <div className="text-[12px] text-slate-600 leading-relaxed">
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
                  <div className="text-[12px] text-slate-500">当前页：第 {unmatchedPage} / {unmatchedTotalPages} 页</div>
                  <div className="flex gap-2">
                    <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={unmatchedPage <= 1} onClick={() => setUnmatchedPage(p => p - 1)}>上一页</button>
                    <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={unmatchedPage >= unmatchedTotalPages} onClick={() => setUnmatchedPage(p => p + 1)}>下一页</button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100/50 border border-slate-200 p-3">
                    <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">其他文件</div>
                    <div className="flex flex-wrap gap-2">
                      {unmatchedPrtItems.length ? unmatchedPrtItems.map((f, i) => (
                        <span key={i} className="chip">{f}</span>
                      )) : <span className="chip text-slate-400">暂无</span>}
                    </div>
                  </div>
                  <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100/50 border border-slate-200 p-3">
                    <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">未匹配 PDF</div>
                    <div className="flex flex-wrap gap-2">
                      {unmatchedPdfItems.length ? unmatchedPdfItems.map((f, i) => (
                        <span key={i} className="chip">{f}</span>
                      )) : <span className="chip text-slate-400">暂无</span>}
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
