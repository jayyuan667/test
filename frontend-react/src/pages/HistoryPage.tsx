import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { deleteTask, getHistory, getAssetUrl, getResult } from '../api/client'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { normalizeAssetUrls, normalizeProcessRows, displayStepCode } from '../utils/processRows'

interface HistoryEntry {
  task_id: string
  pdf_name: string
  progress: number
  created_at: string
  completed_at?: string
  file_count?: number
  status?: string
}

interface SnapshotData {
  task_id: string
  pdf_name: string
  preview_image_urls: string[]
  review_text: string
  feature_report_text: string
  process_flow?: { data?: unknown[]; raw?: string }
  process_flow_raw?: string
  gltf_url?: string
}

function parseRawProcessFlow(raw: string) {
  const rows: unknown[] = []
  let current: { code: string; header: string; details: string[] } | null = null
  const flush = () => {
    if (!current) return
    let trade = ''
    let header = current.header.trim()
    const tradeMatch = header.match(/\s*[（(]工种[：:]\s*([一-鿿\-]{1,6})\s*[）)]\s*$/)
    if (tradeMatch) {
      trade = tradeMatch[1]
      header = header.slice(0, tradeMatch.index).trim()
    }
    const content = current.details.length ? current.details.join('\n').trim() : header
    rows.push({ code: current.code, trade, content })
  }

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(/^-?\s*(\d{4})\s*[:：@]\s*(.+)$/)
    if (match) {
      flush()
      current = { code: match[1], header: match[2].trim(), details: [] }
    } else if (current) {
      current.details.push(trimmed)
    }
  }
  flush()
  return rows
}

const PAGE_SIZE = 6

export function HistoryPage({ visible = true }: { visible?: boolean }) {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null)
  const [snapshotPage, setSnapshotPage] = useState(0)
  const [snapshotZoom, setSnapshotZoom] = useState(1)
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [snapshotError, setSnapshotError] = useState('')
  const [snapshotImageFailed, setSnapshotImageFailed] = useState(false)
  const [dateFilter, setDateFilter] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const selectAllRef = useRef<HTMLInputElement>(null)

  // Refs for GSAP animations
  const headerRef = useRef<HTMLDivElement>(null)
  const statsRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLDivElement>(null)
  const paginationRef = useRef<HTMLDivElement>(null)
  const statCardsRef = useRef<(HTMLDivElement | null)[]>([])
  const reduceMotion = usePrefersReducedMotion()

  const loadHistory = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getHistory()
      const list = (data as unknown as { history: HistoryEntry[] }).history || []
      setHistory(list)
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  // Reload when page becomes visible (fix stale data after upload)
  useEffect(() => {
    if (visible) loadHistory()
  }, [visible, loadHistory])

  // GSAP: Page load animation
  useEffect(() => {
    if (loading) return

    if (reduceMotion) {
      if (headerRef.current) gsap.set(headerRef.current, { y: 0, opacity: 1 })
      if (statsRef.current) {
        const cards = statsRef.current.querySelectorAll('.stat-card')
        gsap.set(cards, { y: 0, opacity: 1 })
      }
      if (tableRef.current) gsap.set(tableRef.current, { y: 0, opacity: 1 })
      if (paginationRef.current) gsap.set(paginationRef.current, { y: 0, opacity: 1 })
      return
    }

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

    // Animate header
    if (headerRef.current) {
      tl.fromTo(headerRef.current,
        { y: -20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5 }
      )
    }

    // Animate stat cards with stagger
    if (statsRef.current) {
      const cards = statsRef.current.querySelectorAll('.stat-card')
      tl.fromTo(cards,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6, stagger: 0.1 },
        '-=0.3'
      )
    }

    // Animate table
    if (tableRef.current) {
      tl.fromTo(tableRef.current,
        { y: 40, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6 },
        '-=0.4'
      )
    }

    // Animate pagination
    if (paginationRef.current) {
      tl.fromTo(paginationRef.current,
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4 },
        '-=0.3'
      )
    }

    return () => {
      tl.kill()
    }
  }, [loading, reduceMotion])

  // GSAP: Stat card hover animation
  const handleStatCardHover = (index: number, isEnter: boolean) => {
    const card = statCardsRef.current[index]
    if (!card) return

    if (reduceMotion) {
      gsap.set(card, isEnter
        ? { y: -4, scale: 1.02, boxShadow: '0 8px 24px rgba(0,0,0,0.12)' }
        : { y: 0, scale: 1, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }
      )
      return
    }

    if (isEnter) {
      gsap.to(card, {
        y: -4,
        scale: 1.02,
        boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        duration: 0.3,
        ease: 'power2.out',
      })
    } else {
      gsap.to(card, {
        y: 0,
        scale: 1,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        duration: 0.3,
        ease: 'power2.out',
      })
    }
  }

  // GSAP: Table row hover animation
  const handleRowHover = (e: React.MouseEvent<HTMLTableRowElement>, isEnter: boolean) => {
    const row = e.currentTarget
    if (reduceMotion) {
      gsap.set(row, { scale: isEnter ? 1.005 : 1 })
      return
    }
    gsap.to(row, {
      scale: isEnter ? 1.005 : 1,
      duration: 0.2,
      ease: 'power1.out',
    })
  }

  // GSAP: Modal animation
  useEffect(() => {
    if (snapshot) {
      const modal = document.querySelector('.snapshot-modal')
      if (modal) {
        if (reduceMotion) {
          gsap.set(modal, { scale: 1, opacity: 1 })
          return
        }
        gsap.fromTo(modal,
          { scale: 0.9, opacity: 0 },
          { scale: 1, opacity: 1, duration: 0.4, ease: 'back.out(1.7)' }
        )
      }
    }
  }, [snapshot, reduceMotion])

  // Filter by date
  const filtered = useMemo(() => {
    if (!dateFilter) return history
    return history.filter(h => {
      const d = h.completed_at || h.created_at
      if (!d) return false
      return d.startsWith(dateFilter)
    })
  }, [history, dateFilter])

  // Stats
  const total = filtered.length
  const completedCount = filtered.filter(h => h.progress >= 100).length
  const reviewCount = filtered.filter(h => h.progress < 100).length
  const stepCount = useMemo(() => {
    return filtered.reduce((sum, h) => sum + (h.file_count || 0), 0)
  }, [filtered])

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Indeterminate checkbox
  useEffect(() => {
    if (selectAllRef.current) {
      const allChecked = pageItems.length > 0 && selected.size === pageItems.length
      const someChecked = selected.size > 0 && selected.size < pageItems.length
      selectAllRef.current.indeterminate = someChecked && !allChecked
    }
  }, [selected.size, pageItems.length])

  // Selection
  const toggleSelect = (taskId: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === pageItems.length && pageItems.length > 0) {
      setSelected(new Set())
    } else {
      setSelected(new Set(pageItems.map(h => h.task_id)))
    }
  }

  // Delete
  const handleDelete = useCallback(async (taskId: string) => {
    setDeleting(taskId)
    try {
      await deleteTask(taskId)
      setHistory(prev => prev.filter(h => h.task_id !== taskId))
      setSelected(prev => { const n = new Set(prev); n.delete(taskId); return n })
    } catch { /* ignore */ }
    setDeleting(null)
  }, [])

  const handleBatchDelete = useCallback(async () => {
    if (!confirm(`确认删除选中的 ${selected.size} 条历史记录？\n\n删除后本地文件将一并清除，此操作不可恢复。`)) return
    let failCount = 0
    for (const taskId of selected) {
      try { await deleteTask(taskId) } catch { failCount++ }
    }
    setHistory(prev => prev.filter(h => !selected.has(h.task_id)))
    setSelected(new Set())
    if (failCount > 0) {
      // Could show toast here
    }
  }, [selected])

  const handleClearFilter = () => {
    setDateFilter('')
    setPage(1)
  }

  // Snapshot
  const openSnapshot = useCallback(async (taskId: string) => {
    setSnapshotLoading(true)
    setSnapshotError('')
    setSnapshotImageFailed(false)
    setSnapshotPage(0)
    setSnapshotZoom(1)
    setSnapshot({ task_id: taskId, pdf_name: '', preview_image_urls: [], review_text: '', feature_report_text: '' })
    try {
      const data = await getResult(taskId)
      const d = data as unknown as Record<string, unknown>
      setSnapshot({
        task_id: taskId,
        pdf_name: String(d.pdf_name || ''),
        preview_image_urls: normalizeAssetUrls(d.preview_image_urls, taskId, getAssetUrl),
        review_text: String(d.review_text || d.feature_report_text || ''),
        feature_report_text: String(d.feature_report_text || ''),
        process_flow: d.process_flow as SnapshotData['process_flow'],
        process_flow_raw: String(d.process_flow_raw || ''),
        gltf_url: String(d.gltf_url || ''),
      })
    } catch (err) {
      setSnapshotError(err instanceof Error ? err.message : '快照加载失败')
    }
    setSnapshotLoading(false)
  }, [])

  const closeSnapshot = () => setSnapshot(null)

  const processRows = (() => {
    if (!snapshot) return []
    const pf = snapshot.process_flow
    if (pf?.data && Array.isArray(pf.data)) {
      const rows = normalizeProcessRows(pf.data)
      if (rows.length) return rows
    }
    if (snapshot.process_flow_raw) {
      return parseRawProcessFlow(snapshot.process_flow_raw)
    }
    return []
  })()
  const normalizedProcessRows = normalizeProcessRows(processRows)

  const snapshotUrls = snapshot?.preview_image_urls || []
  const has3D = !!(snapshot?.gltf_url)

  const formatDate = (iso?: string) => {
    if (!iso) return '-'
    const d = new Date(iso)
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    return `${mm}-${dd} ${hh}:${mi}`
  }

  const getTradeBadgeClass = (trade?: string) => {
    if (!trade) return 'bg-stone-50 text-stone-600 border-stone-200'
    if (trade === '检') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    if (trade === '热处理') return 'bg-red-50 text-red-700 border-red-200'
    if (trade === '钳') return 'bg-amber-50 text-amber-700 border-amber-200'
    return 'bg-stone-50 text-stone-700 border-stone-200'
  }

  // Stat card data
  const statCards = [
    { label: '总数', value: total, color: 'from-stone-500 to-stone-700', bgColor: 'theme-surface-panel-subtle',
      iconSvg: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-stone-500"><path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" /></svg> },
    { label: '完成', value: completedCount, color: 'from-emerald-500 to-emerald-600', bgColor: 'bg-gradient-to-br from-emerald-50 to-emerald-100',
      iconSvg: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500"><polyline points="20 6 9 17 4 12" /></svg> },
    { label: '待审阅', value: reviewCount, color: 'from-amber-500 to-amber-600', bgColor: 'bg-gradient-to-br from-amber-50 to-amber-100',
      iconSvg: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg> },
    { label: '工序', value: stepCount, color: 'from-orange-500 to-orange-600', bgColor: 'bg-gradient-to-br from-orange-50 to-orange-100',
      iconSvg: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-orange-500"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg> },
  ]

  return (
    <div className="flex flex-col gap-4 h-full min-h-0">
      <div className="shrink-0">
        <h1 className="text-[22px] font-bold" style={{ color: 'var(--text-primary)' }}>历史记录</h1>
        <p className="mt-1 text-[12px]" style={{ color: 'var(--text-secondary)' }}>查看历史输出、快照与工艺回看，不承载治理操作。</p>
      </div>

      {/* Toolbar */}
      <div ref={headerRef} className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button className="btn btn-ghost !text-[12px]" onClick={loadHistory}>
            <span className="flex items-center gap-1.5">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></svg>
              刷新历史
            </span>
          </button>
          <div className="flex items-center gap-2">
            <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>完成日期</label>
            <input
              type="date"
              className="theme-form-field rounded-lg px-2.5 py-1.5 text-[12px] transition-all"
              value={dateFilter}
              onChange={e => { setDateFilter(e.target.value); setPage(1) }}
            />
          </div>
          {dateFilter && (
            <button className="btn btn-ghost !text-[11px] !py-1.5" onClick={handleClearFilter}>清空筛选</button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button className="btn btn-ghost !text-[12px] !text-red-500" onClick={handleBatchDelete}>
              批量删除 ({selected.size})
            </button>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div ref={statsRef} className="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">
        {statCards.map((stat, index) => (
          <div
            key={stat.label}
            ref={el => { statCardsRef.current[index] = el }}
            className={`stat-card card-solid !p-4 cursor-default transition-all duration-200 ${stat.bgColor} flex flex-row lg:flex-col items-center lg:items-stretch gap-3 lg:gap-0`}
            onMouseEnter={() => handleStatCardHover(index, true)}
            onMouseLeave={() => handleStatCardHover(index, false)}
          >
            <div className="flex items-center justify-between mb-0 lg:mb-2 flex-1 lg:flex-none">
              {stat.iconSvg}
              <span className={`text-[11px] font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent hidden lg:inline`}>
                {stat.label}
              </span>
            </div>
            <div className="text-[22px] lg:text-[28px] font-extrabold leading-none" style={{ color: 'var(--text-primary)' }}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Table card */}
      <div ref={tableRef} className="card-solid flex-1 min-h-0 overflow-auto flex flex-col">
        {/* Table header meta */}
        <div className="flex items-center justify-between mb-3 shrink-0">
          <div className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>历史任务表</div>
          <div className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>{filtered.length} 条 · 当前展示第 {page} 页，共 {totalPages} 页，最近任务会优先显示。</div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-[14px]" style={{ color: 'var(--text-muted)' }}>
            <div className="flex items-center gap-3">
              <svg className="animate-spin h-5 w-5 text-flame-500" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              加载中...
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20" style={{ color: 'var(--text-muted)' }}>
            <div className="theme-empty-accent w-20 h-20 rounded-full flex items-center justify-center mb-4">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
                <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18" /><path d="M9 21V9" />
              </svg>
            </div>
            <div className="text-[16px] font-bold mb-1" style={{ color: 'var(--text-secondary)' }}>暂无历史任务</div>
            <div className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>上传文件生成工艺后，记录会出现在这里。</div>
          </div>
        ) : (
          <>
          {/* Mobile card list */}
          <div className="md:hidden flex flex-col gap-2 flex-1 min-h-0 overflow-auto">
            {pageItems.map(h => {
              const isDone = h.progress >= 100
              return (
                <div
                  key={h.task_id}
                  className="theme-surface-panel rounded-xl border p-3.5"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{h.pdf_name || h.task_id}</div>
                      <div className="text-[11px] mt-0.5 font-mono" style={{ color: 'var(--text-secondary)' }}>{h.task_id}</div>
                    </div>
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold shrink-0 ml-2 ${isDone ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
                      {isDone ? '已完成' : '待审阅'}
                    </span>
                  </div>
                  <div className="text-[11px] mb-2" style={{ color: 'var(--text-secondary)' }}>
                    {formatDate(h.completed_at || h.created_at)}
                    {h.file_count != null ? ` · 已输出 ${h.file_count} 条工序` : ''}
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selected.has(h.task_id)}
                      onChange={() => toggleSelect(h.task_id)}
                      className="rounded accent-flame-500"
                    />
                    <button
                      className="btn btn-ghost theme-link-action !text-[11px] !py-1 !px-2.5"
                      onClick={() => openSnapshot(h.task_id)}
                    >
                      查看快照
                    </button>
                    <button
                      className="btn btn-ghost theme-link-danger !text-[11px] !py-1 !px-2 ml-auto"
                      disabled={deleting === h.task_id}
                      onClick={() => handleDelete(h.task_id)}
                    >
                      {deleting === h.task_id ? '删除中...' : '删除'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
          {/* Desktop table */}
          <div className="hidden md:block flex-1 min-h-0 overflow-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input
                      ref={selectAllRef}
                      type="checkbox"
                      checked={pageItems.length > 0 && selected.size === pageItems.length}
                      onChange={toggleSelectAll}
                      className="rounded accent-flame-500"
                    />
                  </th>
                  <th>任务 / 模型</th>
                  <th style={{ width: 80 }}>状态</th>
                  <th style={{ width: 120 }}>完成时间</th>
                  <th style={{ width: 80 }}>工序</th>
                  <th style={{ width: 80 }}>快照</th>
                  <th style={{ width: 70 }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map(h => {
                  const isDone = h.progress >= 100
                  const isReview = h.progress < 100
                  return (
                    <tr
                      key={h.task_id}
                      onMouseEnter={(e) => handleRowHover(e, true)}
                      onMouseLeave={(e) => handleRowHover(e, false)}
                      className="cursor-pointer"
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(h.task_id)}
                          onChange={() => toggleSelect(h.task_id)}
                          className="rounded accent-flame-500"
                        />
                      </td>
                      <td>
                        <div className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>{h.pdf_name || h.task_id}</div>
                        <div className="text-[11px] mt-0.5 font-mono" style={{ color: 'var(--text-secondary)' }}>{h.task_id} · {formatDate(h.created_at)}</div>
                      </td>
                      <td>
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold ${isDone ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
                          {isDone ? '已完成' : '待审阅'}
                        </span>
                      </td>
                      <td className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{formatDate(h.completed_at || h.created_at)}</td>
                      <td className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{h.file_count != null ? `已输出 ${h.file_count} 条工序` : '-'}</td>
                      <td>
                        <button
                          className="btn btn-ghost theme-link-action !text-[11px] !py-1 !px-2.5 hover:!underline"
                          onClick={() => openSnapshot(h.task_id)}
                        >
                          查看快照
                        </button>
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost theme-link-danger !text-[11px] !py-1 !px-2"
                          disabled={deleting === h.task_id}
                          onClick={() => handleDelete(h.task_id)}
                        >
                          {deleting === h.task_id ? '删除中...' : '删除'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>

      {/* Pagination */}
      {filtered.length > 0 && (
        <div ref={paginationRef} className="flex items-center justify-between shrink-0 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          <span>第 {page} / {totalPages} 页</span>
          <div className="flex gap-2">
            <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
            <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
          </div>
        </div>
      )}

      {/* Snapshot Modal */}
      {snapshot && (
        <div className="snapshot-modal fixed inset-0 z-[2000] flex items-center justify-center" onClick={closeSnapshot}>
          <div className="absolute inset-0 backdrop-blur-sm" style={{ background: 'var(--modal-overlay)' }} />
          <div
            className="theme-modal-shell relative rounded-2xl shadow-2xl border max-w-[960px] w-[92vw] max-h-[88vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b shrink-0" style={{ borderColor: 'var(--modal-subtle-border)' }}>
              <div>
                <div className="text-[15px] font-bold" style={{ color: 'var(--text-primary)' }}>{snapshot.pdf_name || '工艺快照'}</div>
                <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>{snapshot.task_id} · {snapshotUrls.length} 页视图</div>
              </div>
              <button onClick={closeSnapshot} className="btn btn-ghost !p-1.5 !text-[18px]" style={{ color: 'var(--text-muted)' }}>&times;</button>
            </div>

            {/* Body */}
            <div className="flex-1 min-h-0 overflow-auto flex flex-col md:flex-row">
              {/* Left: Image preview */}
              <div className="theme-preview-frame flex-1 min-w-0 md:border-r border flex flex-col items-center justify-center p-4">
                {snapshotLoading ? (
                  <div className="text-[13px]" style={{ color: 'var(--text-muted)' }}>加载中...</div>
                ) : snapshotError ? (
                  <div className="theme-danger-note max-w-sm rounded-xl p-4 text-center">
                    <div className="text-[13px] font-semibold">快照加载失败</div>
                    <div className="mt-1 text-[11px]">{snapshotError}</div>
                  </div>
                ) : snapshotUrls.length === 0 && !has3D ? (
                  <div className="flex flex-col items-center" style={{ color: 'var(--text-muted)' }}>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2" style={{ color: 'var(--text-muted)' }}><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></svg>
                    <div className="text-[13px] font-semibold">暂无可预览图片</div>
                    <div className="text-[11px] mt-1">该任务未生成预览视图</div>
                  </div>
                ) : (
                  <>
                    {/* Source info */}
                    <div className="text-[11px] mb-2 shrink-0" style={{ color: 'var(--text-muted)' }}>{snapshot.task_id} · {has3D ? '3D 模型' : `${snapshotUrls.length} 页视图`}</div>
                    <div className="flex-1 min-h-0 flex items-center justify-center overflow-auto w-full">
                      {snapshotImageFailed ? (
                        <div className="theme-empty-accent rounded-xl p-4 text-center">
                          <div className="text-[13px] font-semibold text-amber-700">预览图片加载失败</div>
                          <div className="mt-1 break-all text-[10px] text-amber-600">{snapshotUrls[snapshotPage]}</div>
                        </div>
                      ) : (
                        <img
                          src={snapshotUrls[snapshotPage]}
                          alt={`预览 ${snapshotPage + 1}`}
                          className="max-w-full max-h-[50vh] object-contain transition-transform duration-200"
                          style={{ transform: `scale(${snapshotZoom})` }}
                          onLoad={() => setSnapshotImageFailed(false)}
                          onError={() => setSnapshotImageFailed(true)}
                        />
                      )}
                    </div>
                    {/* Controls */}
                    <div className="flex items-center gap-2 mt-3 shrink-0 flex-wrap justify-center">
                      <button className="btn btn-secondary !text-[11px] !py-1 !px-2.5" disabled={snapshotPage <= 0 || has3D} onClick={() => { setSnapshotImageFailed(false); setSnapshotPage(p => p - 1) }}>&larr; 上一页</button>
                      <span className="text-[12px] min-w-[48px] text-center" style={{ color: 'var(--text-secondary)' }}>{has3D ? '3D 模型' : `${snapshotPage + 1} / ${snapshotUrls.length}`}</span>
                      <button className="btn btn-secondary !text-[11px] !py-1 !px-2.5" disabled={snapshotPage >= snapshotUrls.length - 1 || has3D} onClick={() => { setSnapshotImageFailed(false); setSnapshotPage(p => p + 1) }}>下一页 &rarr;</button>
                      <span className="w-px h-4 mx-1" style={{ background: 'var(--border)' }} />
                      <button className="btn btn-secondary !text-[11px] !py-1 !px-2" disabled={snapshotZoom <= 0.6 || has3D} onClick={() => setSnapshotZoom(z => Math.max(0.6, z - 0.2))}>缩小</button>
                      <span className="text-[11px] w-12 text-center" style={{ color: 'var(--text-secondary)' }}>{has3D ? '拖拽旋转' : `${Math.round(snapshotZoom * 100)}%`}</span>
                      <button className="btn btn-secondary !text-[11px] !py-1 !px-2" disabled={snapshotZoom >= 2.4 || has3D} onClick={() => setSnapshotZoom(z => Math.min(2.4, z + 0.2))}>放大</button>
                      <button className="btn btn-ghost !text-[11px] !py-1 !px-2" disabled={has3D} onClick={() => setSnapshotZoom(1)}>重置</button>
                    </div>
                  </>
                )}
              </div>

              {/* Right: Details */}
              <div className="w-full md:w-[320px] shrink-0 overflow-auto p-4 flex flex-col gap-4 border-t md:border-t-0 md:border-l" style={{ borderColor: 'var(--modal-subtle-border)' }}>
                {/* Feature review */}
                <div>
                  <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">特征审阅</div>
                  <div className="text-[12px] leading-relaxed whitespace-pre-wrap max-h-[200px] overflow-auto rounded-xl p-3 theme-preview-frame" style={{ color: 'var(--text-secondary)' }}>
                    {snapshot.review_text || snapshot.feature_report_text || '暂无特征数据'}
                  </div>
                </div>

                {/* Process */}
                <div>
                  <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">工艺规程</div>
                  {normalizedProcessRows.length === 0 ? (
                    <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>暂无工艺数据</div>
                  ) : (
                    <div className="theme-surface-panel rounded-xl border overflow-hidden">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th style={{ width: 56 }}>工序号</th>
                            <th style={{ width: 48 }}>工种</th>
                            <th>工序内容</th>
                          </tr>
                        </thead>
                        <tbody>
                          {normalizedProcessRows.map((row, i) => (
                            <tr key={i}>
                              <td className="theme-code-accent font-mono text-[11px] font-bold">{displayStepCode(i)}</td>
                              <td>
                                {row.trade ? (
                                  <span className={[
                                    'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border',
                                    getTradeBadgeClass(row.trade)
                                  ].join(' ')}>{row.trade}</span>
                                ) : <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>—</span>}
                              </td>
                              <td className="text-[11px]">{row.content}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
