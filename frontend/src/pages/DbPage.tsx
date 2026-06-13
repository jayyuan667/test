import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getLibraryRecords,
  getLibraryRecord,
  updateLibraryRecord,
  deleteLibraryRecord,
  deleteLibraryScope,
  getLibraryScopes,
  getAssetUrl,
} from '../api/client'
import type { LibraryRecord, LibraryRecordsResponse, LibraryScope } from '../api/client'
import gsap from 'gsap'

type ViewMode = 'list' | 'detail' | 'edit'

export function DbPage() {
  const [ready, setReady] = useState<boolean | null>(null)
  const [browseOnly, setBrowseOnly] = useState(false)
  const [scopes, setScopes] = useState<LibraryScope[]>([])
  const [activeScope, setActiveScope] = useState<{ library_key: string; library_name: string; scope_type: string } | null>(null)
  const [records, setRecords] = useState<LibraryRecord[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(3)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [productTypes, setProductTypes] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  // Filters
  const [query, setQuery] = useState('')
  const [filterProductType, setFilterProductType] = useState('')
  const [filterSource, setFilterSource] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterScope, setFilterScope] = useState('')
  const [filterOpen, setFilterOpen] = useState(false)

  // Detail / Edit
  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [selectedRecord, setSelectedRecord] = useState<LibraryRecord | null>(null)
  const [editDraft, setEditDraft] = useState<Partial<LibraryRecord>>({})
  const [editFeaturePage, setEditFeaturePage] = useState(0)
  const [saving, setSaving] = useState(false)
  const [snapshotPreview, setSnapshotPreview] = useState<{ taskId: string; urls: string[]; page: number; zoom: number } | null>(null)

  // Delete confirmations
  const [deleteRecordConfirm, setDeleteRecordConfirm] = useState<LibraryRecord | null>(null)
  const [deleteLibraryConfirm, setDeleteLibraryConfirm] = useState<LibraryScope | null>(null)

  // Refs for GSAP animations
  const lockStateRef = useRef<HTMLDivElement>(null)
  const bannerRef = useRef<HTMLDivElement>(null)
  const toolbarRef = useRef<HTMLDivElement>(null)
  const statsRef = useRef<HTMLDivElement>(null)
  const filterRef = useRef<HTMLDivElement>(null)
  const recordListRef = useRef<HTMLDivElement>(null)
  const detailRef = useRef<HTMLDivElement>(null)
  const recordCardsRef = useRef<(HTMLDivElement | null)[]>([])

  // Initial load
  useEffect(() => {
    (async () => {
      try {
        const data = await getLibraryScopes()
        setScopes(data.items || [])
        const canBrowse = data.can_browse_db !== false
        setReady(canBrowse)
        if (!canBrowse) {
          setBrowseOnly(true)
          setReady(true) // Show the page but in browse-only mode
        }
        if (data.items?.length && !filterScope) {
          setFilterScope(data.items[0].library_key)
        }
      } catch {
        setReady(false)
      }
    })()
  }, [])

  // Load records
  const loadRecords = useCallback(async () => {
    if (ready === false) return
    setLoading(true)
    try {
      const data: LibraryRecordsResponse = await getLibraryRecords({
        page,
        page_size: pageSize,
        query: query || undefined,
        product_type: filterProductType || undefined,
        library_key: filterScope || undefined,
      })
      setRecords(data.items || [])
      setTotalPages(data.total_pages || 1)
      setTotal(data.total || 0)
      setProductTypes(data.product_types || [])
      if (data.active_scope) setActiveScope(data.active_scope)
    } catch { /* ignore */ }
    setLoading(false)
  }, [ready, page, pageSize, query, filterProductType, filterScope])

  useEffect(() => { loadRecords() }, [loadRecords])

  // GSAP: Lock state animation
  useEffect(() => {
    if (ready === false && lockStateRef.current) {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })
      tl.fromTo(lockStateRef.current,
        { scale: 0.9, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.6 }
      )
      tl.fromTo(lockStateRef.current.querySelectorAll('h2, p, .btn'),
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4, stagger: 0.1 },
        '-=0.3'
      )
      return () => { tl.kill() }
    }
  }, [ready])

  // GSAP: Page load animation (unlocked)
  useEffect(() => {
    if (ready !== true) return

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

    // Banner
    if (bannerRef.current) {
      tl.fromTo(bannerRef.current,
        { y: -20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4 }
      )
    }

    // Toolbar
    if (toolbarRef.current) {
      tl.fromTo(toolbarRef.current,
        { y: -15, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4 },
        '-=0.2'
      )
    }

    // Stats
    if (statsRef.current) {
      const cards = statsRef.current.querySelectorAll('.stat-card')
      tl.fromTo(cards,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5, stagger: 0.1 },
        '-=0.3'
      )
    }

    // Filter panel
    if (filterRef.current) {
      tl.fromTo(filterRef.current,
        { x: -30, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.5 },
        '-=0.4'
      )
    }

    // Record list
    if (recordListRef.current) {
      tl.fromTo(recordListRef.current,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5 },
        '-=0.4'
      )
    }

    return () => { tl.kill() }
  }, [ready])

  // GSAP: Record card hover animation
  const handleRecordCardHover = (index: number, isEnter: boolean) => {
    const card = recordCardsRef.current[index]
    if (!card) return

    if (isEnter) {
      gsap.to(card, {
        y: -3,
        scale: 1.01,
        boxShadow: '0 6px 20px rgba(0,0,0,0.1)',
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

  // GSAP: Detail panel animation
  useEffect(() => {
    if (viewMode !== 'list' && detailRef.current) {
      gsap.fromTo(detailRef.current,
        { x: 40, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' }
      )
    }
  }, [viewMode])

  // GSAP: Modal animation
  useEffect(() => {
    if (deleteRecordConfirm || deleteLibraryConfirm || snapshotPreview) {
      const modal = document.querySelector('.modal-overlay')
      if (modal) {
        const content = modal.querySelector('.modal-content')
        if (content) {
          gsap.fromTo(content,
            { scale: 0.9, opacity: 0 },
            { scale: 1, opacity: 1, duration: 0.35, ease: 'back.out(1.7)' }
          )
        }
      }
    }
  }, [deleteRecordConfirm, deleteLibraryConfirm, snapshotPreview])

  const handleApplyFilter = () => { setPage(1); loadRecords() }
  const handleResetFilter = () => {
    setQuery(''); setFilterProductType(''); setFilterSource(''); setFilterStatus(''); setPage(1)
  }
  const handleRefresh = () => loadRecords()

  // Select record
  const handleSelectRecord = useCallback(async (record: LibraryRecord) => {
    try {
      const full = await getLibraryRecord(record.id, filterScope || undefined)
      setSelectedRecord(full)
      setViewMode('detail')
    } catch {
      setSelectedRecord(record)
      setViewMode('detail')
    }
  }, [filterScope])

  // Edit
  const handleEdit = () => {
    if (!selectedRecord || browseOnly) return
    setEditDraft({
      prefix: selectedRecord.prefix,
      product_type: selectedRecord.product_type,
      process_summary: selectedRecord.process_summary,
      tech_requirement: selectedRecord.tech_requirement,
      content: selectedRecord.content,
    })
    setEditFeaturePage(0)
    setViewMode('edit')
  }

  const handleSave = async () => {
    if (!selectedRecord) return
    setSaving(true)
    try {
      const body = { ...editDraft } as Partial<LibraryRecord> & { library_key?: string }
      if (filterScope) body.library_key = filterScope
      const updated = await updateLibraryRecord(selectedRecord.id, body)
      setSelectedRecord(updated)
      setViewMode('detail')
      loadRecords()
    } catch { /* ignore */ }
    setSaving(false)
  }

  const handleCancelEdit = () => {
    setEditDraft({})
    setViewMode(selectedRecord ? 'detail' : 'list')
  }

  // Delete record with confirmation
  const handleDeleteRecord = async () => {
    if (!deleteRecordConfirm) return
    try {
      await deleteLibraryRecord(deleteRecordConfirm.id, filterScope || undefined)
      if (selectedRecord?.id === deleteRecordConfirm.id) {
        setSelectedRecord(null)
        setViewMode('list')
      }
      setDeleteRecordConfirm(null)
      loadRecords()
    } catch { /* ignore */ }
  }

  // Delete library scope
  const handleDeleteLibrary = async () => {
    if (!deleteLibraryConfirm) return
    try {
      await deleteLibraryScope(deleteLibraryConfirm.library_key)
      setDeleteLibraryConfirm(null)
      // Reload scopes
      const data = await getLibraryScopes()
      setScopes(data.items || [])
      if (data.items?.length) {
        setFilterScope(data.items[0].library_key)
      }
      setPage(1)
    } catch { /* ignore */ }
  }

  // Snapshot preview
  const handleViewSnapshot = (record: LibraryRecord) => {
    let urls: string[] = []
    try {
      const raw = record.preview_image_urls
      if (typeof raw === 'string' && raw.trim()) urls = JSON.parse(raw)
      else if (Array.isArray(raw)) urls = raw as unknown as string[]
    } catch { /* ignore */ }
    const taskId = record.preview_task_id || record.source_task_id
    if (taskId && urls.length) {
      setSnapshotPreview({ taskId, urls, page: 0, zoom: 1 })
    }
  }

  const backToList = () => {
    setSelectedRecord(null)
    setViewMode('list')
    setEditDraft({})
  }

  const isPublicLib = activeScope?.scope_type === 'public'

  // Feature report pages (from feature_report_json)
  const featurePages = useMemo(() => {
    if (!selectedRecord?.feature_report_json) return []
    const json = selectedRecord.feature_report_json
    const pages = json.pages
    if (Array.isArray(pages)) return pages as Record<string, unknown>[]
    return []
  }, [selectedRecord])

  // Status label
  const getRecordStatus = (r: LibraryRecord) => {
    if (r.real === 0) return { label: '草稿', cls: 'bg-amber-50 text-amber-700 border-amber-200' }
    return { label: '可用', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' }
  }

  const getSourceLabel = (r: LibraryRecord) => {
    if (r.source_type === 'zip_import' || r.source_type === 'import') return '工艺入库'
    if (r.source_type === 'manual' || r.source_type === 'text') return '手工修订'
    return r.source_type || '-'
  }

  // Search highlight
  const highlightText = (text: string, q: string) => {
    if (!q.trim() || !text) return text
    const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    return text.replace(regex, '<mark class="bg-yellow-200/70 rounded px-0.5">$1</mark>')
  }

  // Editable sources for filter
  const sourceOptions = useMemo(() => {
    const set = new Set(records.map(r => getSourceLabel(r)).filter(Boolean))
    return Array.from(set)
  }, [records])

  // Stat card data
  const statCards = [
    { label: '库内条目', value: total, icon: '📚', color: 'from-blue-500 to-blue-600', bgColor: 'bg-gradient-to-br from-blue-50 to-blue-100' },
    { label: '当前页', value: records.length, icon: '📄', color: 'from-emerald-500 to-emerald-600', bgColor: 'bg-gradient-to-br from-emerald-50 to-emerald-100' },
    { label: '编辑状态', value: viewMode === 'edit' ? '编辑中' : browseOnly ? '只读' : '启用', icon: viewMode === 'edit' ? '✏️' : browseOnly ? '🔒' : '🔓', color: browseOnly ? 'from-slate-500 to-slate-600' : 'from-flame-500 to-flame-600', bgColor: browseOnly ? 'bg-gradient-to-br from-slate-50 to-slate-100' : 'bg-gradient-to-br from-flame-50 to-orange-100' },
  ]

  // Lock state
  if (ready === false) {
    return (
      <div ref={lockStateRef} className="flex flex-col items-center justify-center h-full">
        <div className="card-solid max-w-[520px] text-center relative overflow-hidden">
          {/* Decorative background */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-50 via-white to-slate-50 opacity-50" />
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-flame-50/30 to-transparent rounded-bl-full" />

          <div className="relative z-10">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center mx-auto mb-4 shadow-sm">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-500">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <h2 className="text-[20px] font-extrabold text-slate-800 mb-2">请先完成知识入库</h2>
            <p className="text-[13px] text-slate-500 mb-6 leading-relaxed max-w-[380px] mx-auto">
              数据库浏览页默认受"当前会话先入库"规则保护。你可以先浏览公共库或自己的历史库。
            </p>
            <div className="flex gap-3 justify-center flex-wrap">
              <button className="btn btn-primary !px-6 !py-3">前往工艺入库</button>
              <button className="btn btn-secondary !px-5 !py-3" onClick={() => { setReady(true); setBrowseOnly(true); setFilterScope('public') }}>查看公共数据库</button>
              <button className="btn btn-secondary !px-5 !py-3" onClick={() => { setReady(true); setBrowseOnly(true) }}>查看我的数据库</button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 h-full min-h-0">
      {/* Browse-only banner */}
      {browseOnly && (
        <div ref={bannerRef} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-blue-600"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" /></svg>
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-[13px] font-bold text-blue-700">只读浏览模式</span>
            <span className="text-[12px] text-blue-600 ml-2">你可以先查看公共库和自己之前的数据库记录；编辑、删除与保存会在完成入库后解锁。</span>
          </div>
          <button className="btn btn-secondary !text-[11px] !py-1.5 shrink-0">前往工艺入库</button>
        </div>
      )}

      {/* Toolbar */}
      <div ref={toolbarRef} className="flex items-center justify-between shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <button
            className="btn btn-ghost !text-[12px] lg:hidden"
            onClick={() => setFilterOpen(o => !o)}
          >
            <span className="flex items-center gap-1.5">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" /></svg>
              筛选
            </span>
          </button>
          <button className="btn btn-ghost !text-[12px]" onClick={handleResetFilter}>重置筛选</button>
          <button className="btn btn-ghost !text-[12px]" onClick={handleRefresh}>
            <span className="flex items-center gap-1.5">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></svg>
              刷新列表
            </span>
          </button>
          <button
            className="btn btn-ghost !text-[12px] !text-red-500"
            disabled={isPublicLib}
            title={isPublicLib ? '公共库只读' : ''}
            onClick={() => {
              const s = scopes.find(s => s.library_key === filterScope)
              if (s && s.scope_type !== 'public') setDeleteLibraryConfirm(s)
            }}
          >
            删除当前数据库
          </button>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <label className="text-[11px] font-semibold text-slate-500">当前库</label>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
              value={filterScope}
              onChange={e => { setFilterScope(e.target.value); setPage(1) }}
            >
              {scopes.map(s => (
                <option key={s.library_key} value={s.library_key}>{s.library_name}（{s.scope_type === 'public' ? '公共' : '私有'}）</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-[11px] font-semibold text-slate-500">页大小</label>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
              value={pageSize}
              onChange={e => { setPageSize(Number(e.target.value)); setPage(1) }}
            >
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
            </select>
          </div>
          <span className="chip">{activeScope?.library_name || '公共工艺库'} · {total} 条记录</span>
        </div>
      </div>

      {/* Filter disclosure panel (mobile) */}
      {filterOpen && (
        <div className="lg:hidden relative shrink-0">
          <div className="absolute inset-x-0 top-0 z-50 bg-white rounded-xl border border-slate-200 shadow-lg p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="text-[12px] font-bold text-slate-500">筛选条件</div>
              <button className="btn btn-ghost !p-1 !text-[14px]" onClick={() => setFilterOpen(false)}>&times;</button>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-slate-500">模型编号/关键词</label>
              <input
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-1 focus:ring-flame-glow transition-all"
                placeholder="搜索模型编号、工艺内容、摘要"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { handleApplyFilter(); setFilterOpen(false) } }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-slate-500">产品类型</label>
              <select
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
                value={filterProductType}
                onChange={e => setFilterProductType(e.target.value)}
              >
                <option value="">全部</option>
                {productTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex gap-2 mt-1">
              <button className="btn btn-primary !text-[11px] !py-2 flex-1" onClick={() => { handleApplyFilter(); setFilterOpen(false) }}>应用筛选</button>
              <button className="btn btn-ghost !text-[11px] !py-2" onClick={() => { handleResetFilter(); setFilterOpen(false) }}>重置</button>
            </div>
          </div>
        </div>
      )}

      {/* Stat strip */}
      <div ref={statsRef} className="grid grid-cols-3 gap-3 shrink-0">
        {statCards.map((stat) => (
          <div
            key={stat.label}
            className={`stat-card card-solid !p-4 cursor-default ${stat.bgColor}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[22px]">{stat.icon}</span>
              <span className={`text-[11px] font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`}>
                {stat.label}
              </span>
            </div>
            <div className="text-[24px] font-extrabold text-slate-800 leading-none">
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Three-column layout */}
      <div className="flex-1 min-h-0 flex gap-4">
        {/* Left: Filter panel */}
        <div ref={filterRef} className="hidden lg:flex w-[220px] shrink-0 card-solid flex-col gap-3 overflow-auto">
          <div>
            <div className="text-[12px] font-bold text-slate-500 uppercase tracking-wider">筛选条件</div>
            <div className="text-[10px] text-slate-400 mt-0.5">支持模型编号、来源、状态和产品类型筛选。</div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold text-slate-500">模型编号/关键词</label>
            <input
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-1 focus:ring-flame-glow transition-all"
              placeholder="搜索模型编号、工艺内容、摘要"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleApplyFilter() }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold text-slate-500">产品类型</label>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
              value={filterProductType}
              onChange={e => setFilterProductType(e.target.value)}
            >
              <option value="">全部</option>
              {productTypes.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold text-slate-500">来源</label>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
              value={filterSource}
              onChange={e => setFilterSource(e.target.value)}
            >
              <option value="">全部来源</option>
              {sourceOptions.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold text-slate-500">记录状态</label>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
            >
              <option value="">全部状态</option>
              <option value="available">可用</option>
              <option value="draft">草稿</option>
            </select>
          </div>
          <div className="flex gap-2 mt-auto">
            <button className="btn btn-primary !text-[11px] !py-2 flex-1" onClick={handleApplyFilter}>应用筛选</button>
            <button className="btn btn-ghost !text-[11px] !py-2" onClick={handleResetFilter}>重置</button>
          </div>
        </div>

        {/* Middle: Record list */}
        <div ref={recordListRef} className={`${viewMode !== 'list' ? 'w-[35%]' : 'flex-1'} card-solid min-h-0 overflow-auto flex flex-col transition-all duration-300`}>
          <div className="flex items-center justify-between mb-2 shrink-0">
            <div className="text-[12px] font-bold text-slate-500 uppercase tracking-wider">记录列表</div>
            <div className="text-[11px] text-slate-400">{records.length} / {total} · 当前显示 {activeScope?.library_name || '公共工艺库'} 的 {records.length} 条记录</div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16 text-slate-400 text-[13px]">
              <div className="flex items-center gap-3">
                <svg className="animate-spin h-5 w-5 text-flame-500" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                加载中...
              </div>
            </div>
          ) : records.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center mb-3">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
                  <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                </svg>
              </div>
              <div className="text-[14px] font-bold text-slate-500 mb-1">暂无记录</div>
              <div className="text-[11px] text-slate-400">调整筛选条件或先完成工艺入库。</div>
            </div>
          ) : (
            <div className="flex-1 min-h-0 overflow-auto flex flex-col gap-2">
              {records.map((r, index) => {
                const st = getRecordStatus(r)
                const src = getSourceLabel(r)
                const isActive = selectedRecord?.id === r.id
                return (
                  <div
                    key={r.id}
                    ref={el => { recordCardsRef.current[index] = el }}
                    onClick={() => handleSelectRecord(r)}
                    className={`
                      rounded-xl border p-3.5 cursor-pointer transition-all duration-200
                      ${isActive
                        ? 'border-flame-400 bg-flame-soft shadow-sm'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'}
                    `}
                    onMouseEnter={() => handleRecordCardHover(index, true)}
                    onMouseLeave={() => handleRecordCardHover(index, false)}
                  >
                    <div className="flex items-start justify-between mb-1.5">
                      <div className="min-w-0 flex items-center gap-2">
                        <div className="text-[14px] font-bold text-slate-800 truncate" dangerouslySetInnerHTML={{ __html: highlightText(r.prefix || '未命名', query) }} />
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${st.cls}`}>{st.label}</span>
                      </div>
                      <span className="chip shrink-0 ml-2 !text-[10px]">{r.process_count || 0} 工序</span>
                    </div>
                    <div className="text-[11px] text-slate-400 mb-1.5">
                      <span dangerouslySetInnerHTML={{ __html: highlightText(r.product_type || '未分类', query) }} />
                      {' · '}
                      <span>{src}</span>
                      {' · '}
                      <span>工序 {r.process_count || 0} 条</span>
                    </div>
                    {r.process_summary && (
                      <div className="text-[12px] text-slate-500 line-clamp-2 leading-relaxed mb-1.5" dangerouslySetInnerHTML={{ __html: highlightText(r.process_summary, query) }} />
                    )}
                    <div className="flex gap-1.5 flex-wrap">
                      {r.trades?.slice(0, 3).map(t => (
                        <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100">{t}</span>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Right: Detail / Edit panel */}
        {viewMode !== 'list' && selectedRecord && (
          <div ref={detailRef} className="flex-1 card-solid min-h-0 overflow-auto flex flex-col">
            {/* Header */}
            <div className="flex items-start justify-between mb-3 shrink-0">
              <div>
                <button className="btn btn-ghost !text-[11px] !py-1 !px-2 mb-1" onClick={backToList}>&larr; 返回列表</button>
                <div className="flex items-center gap-2">
                  <div className="text-[16px] font-extrabold text-slate-800">{selectedRecord.prefix}</div>
                  {(() => { const st = getRecordStatus(selectedRecord); return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${st.cls}`}>{st.label}</span> })()}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  来源：{getSourceLabel(selectedRecord)} · 最近更新：{selectedRecord.created_at ? new Date(selectedRecord.created_at).toLocaleDateString() : '-'}
                  {selectedRecord.preview_total_pages > 0 && ` · ${selectedRecord.preview_total_pages} 张图片`}
                </div>
              </div>
              <div className="flex gap-2">
                {viewMode === 'detail' && !browseOnly && (
                  <>
                    <button className="btn btn-secondary !text-[12px] !py-2" onClick={handleEdit}>编辑记录</button>
                    <button className="btn btn-ghost !text-[12px] !py-2 !text-red-500" onClick={() => setDeleteRecordConfirm(selectedRecord)}>删除</button>
                  </>
                )}
                {viewMode === 'detail' && browseOnly && (
                  <span className="chip !text-[11px]">只读浏览</span>
                )}
              </div>
            </div>

            {/* Chip row */}
            {viewMode === 'detail' && (
              <div className="flex gap-2 flex-wrap mb-3 shrink-0">
                <span className="chip">{selectedRecord.prefix}</span>
                <span className="chip">{activeScope?.library_name || '公共工艺库'}</span>
                <span className="chip">{selectedRecord.product_type || '未分类'}</span>
                {(() => { const st = getRecordStatus(selectedRecord); return <span className={`chip border ${st.cls}`}>{st.label}</span> })()}
              </div>
            )}

            {/* Content area */}
            <div className="flex-1 min-h-0 overflow-auto">
              {viewMode === 'detail' ? (
                <div className="flex flex-col gap-4">
                  {/* Info grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-3">
                      <div className="text-[11px] font-bold text-slate-500 mb-1">产品类型</div>
                      <div className="text-[13px] text-slate-700">{selectedRecord.product_type || '-'}</div>
                    </div>
                    <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-3">
                      <div className="text-[11px] font-bold text-slate-500 mb-1">技术要求</div>
                      <div className="text-[13px] text-slate-700">{selectedRecord.tech_requirement || '-'}</div>
                    </div>
                  </div>

                  {selectedRecord.process_summary && (
                    <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-3">
                      <div className="text-[11px] font-bold text-slate-500 mb-1">工艺摘要</div>
                      <div className="text-[13px] text-slate-700 leading-relaxed">{selectedRecord.process_summary}</div>
                    </div>
                  )}

                  {/* Process table */}
                  <div>
                    <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">工艺规程</div>
                    {selectedRecord.process_list?.length ? (
                      <div className="rounded-xl border border-slate-200 overflow-hidden">
                        <table className="data-table">
                          <thead><tr><th style={{ width: 70 }}>工序号</th><th>内容</th></tr></thead>
                          <tbody>
                            {selectedRecord.process_list.map((row, i) => {
                              const parts = String(row).split('@')
                              return (
                                <tr key={i}>
                                  <td className="font-mono text-blue-600">{parts[0] || `#${i + 1}`}</td>
                                  <td>{parts.slice(1).join('@') || row}</td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : <div className="text-[12px] text-slate-400">暂无工艺数据</div>}
                  </div>

                  {/* Feature report */}
                  {selectedRecord.feature_report_text && (
                    <div>
                      <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">特征提取</div>
                      <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-3 text-[12px] text-slate-600 leading-relaxed whitespace-pre-wrap max-h-[200px] overflow-auto">
                        {selectedRecord.feature_report_text}
                      </div>
                    </div>
                  )}

                  {/* Snapshot button */}
                  {selectedRecord.preview_task_id && (
                    <button className="btn btn-secondary !text-[12px] w-fit" onClick={() => handleViewSnapshot(selectedRecord)}>查看快照</button>
                  )}
                </div>
              ) : (
                /* Edit mode */
                <div className="flex flex-col gap-4">
                  <div className="text-[12px] font-bold text-slate-500 uppercase tracking-wider mb-1">编辑记录 <span className="font-normal text-slate-400 normal-case tracking-normal ml-1">保存后自动同步到数据库</span></div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-semibold text-slate-500">产品类型</label>
                      <input
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-1 focus:ring-flame-glow transition-all"
                        value={editDraft.product_type || ''}
                        onChange={e => setEditDraft(d => ({ ...d, product_type: e.target.value }))}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-semibold text-slate-500">图号</label>
                      <input
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-1 focus:ring-flame-glow transition-all"
                        value={editDraft.prefix || ''}
                        onChange={e => setEditDraft(d => ({ ...d, prefix: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-semibold text-slate-500">工艺内容</label>
                    <textarea
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-[13px] text-slate-700 font-mono focus:outline-none focus:border-flame-400 focus:ring-1 focus:ring-flame-glow transition-all resize-none"
                      rows={6}
                      value={editDraft.content || ''}
                      onChange={e => setEditDraft(d => ({ ...d, content: e.target.value }))}
                    />
                  </div>

                  {/* Feature report page editor */}
                  {featurePages.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-semibold text-slate-500">特征提取（按页编辑）</label>
                        <div className="flex items-center gap-1.5">
                          <button className="btn btn-ghost !text-[10px] !py-1 !px-2" disabled={editFeaturePage <= 0} onClick={() => setEditFeaturePage(p => p - 1)}>&larr;</button>
                          <span className="text-[11px] text-slate-500 min-w-[56px] text-center">第 {editFeaturePage + 1} / {featurePages.length} 页</span>
                          <button className="btn btn-ghost !text-[10px] !py-1 !px-2" disabled={editFeaturePage >= featurePages.length - 1} onClick={() => setEditFeaturePage(p => p + 1)}>&rarr;</button>
                        </div>
                      </div>
                      {/* Page fields */}
                      {featurePages[editFeaturePage] && (
                        <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-3">
                          <div className="text-[11px] text-slate-400 mb-2">第 {String((featurePages[editFeaturePage] as Record<string, unknown>)._page_number || editFeaturePage + 1)} 页</div>
                          {(() => {
                            const fp = featurePages[editFeaturePage] as Record<string, unknown>
                            const fields = fp.fields || fp.key_features
                            if (fields && typeof fields === 'object') {
                              return Object.entries(fields as Record<string, unknown>).map(([k, v]) => (
                                <div key={k} className="flex gap-2 text-[12px] py-1 border-b border-slate-100 last:border-0">
                                  <span className="font-semibold text-slate-600 shrink-0 w-[100px]">{k}</span>
                                  <span className="text-slate-700">{String(v)}</span>
                                </div>
                              ))
                            }
                            return <div className="text-[12px] text-slate-500">{String(fp.description || fp.text || '无结构化数据')}</div>
                          })()}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex gap-2 mt-2">
                    <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? '保存中...' : '保存修改'}</button>
                    <button className="btn btn-ghost" onClick={handleCancelEdit}>取消</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Pagination */}
      {records.length > 0 && (
        <div className="flex items-center justify-between shrink-0 text-[12px] text-slate-500">
          <span>第 {page} / {totalPages} 页</span>
          <div className="flex gap-2">
            <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
            <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
          </div>
        </div>
      )}

      {/* Delete Record Confirmation Modal */}
      {deleteRecordConfirm && (
        <div className="modal-overlay fixed inset-0 z-[9000] flex items-center justify-center" onClick={() => setDeleteRecordConfirm(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="modal-content relative bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-[420px] w-[90vw] p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-[16px] font-bold text-slate-800 mb-2">确认删除记录</h3>
            <p className="text-[13px] text-slate-500 mb-3 leading-relaxed">删除会影响数据库浏览与后续检索结果。此操作不可恢复。</p>
            <div className="rounded-xl bg-gradient-to-br from-red-50 to-red-100 border border-red-200 px-3 py-2 mb-4 text-[12px] text-red-700">
              {deleteRecordConfirm.prefix}｜{deleteRecordConfirm.product_type || '未分类'}｜{getSourceLabel(deleteRecordConfirm)}
            </div>
            <div className="flex gap-2 justify-end">
              <button className="btn btn-ghost" onClick={() => setDeleteRecordConfirm(null)}>取消</button>
              <button className="btn btn-primary !bg-red-500 !from-red-500 !to-red-600" onClick={handleDeleteRecord}>确认删除</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Library Confirmation Modal */}
      {deleteLibraryConfirm && (
        <div className="modal-overlay fixed inset-0 z-[9000] flex items-center justify-center" onClick={() => setDeleteLibraryConfirm(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="modal-content relative bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-[420px] w-[90vw] p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-[16px] font-bold text-slate-800 mb-2">确认删除当前数据库</h3>
            <p className="text-[13px] text-slate-500 mb-3 leading-relaxed">这会清空当前选中的用户库/当前表，保留公共库不受影响。删除后该库里的记录将无法浏览，除非重新导入。</p>
            <div className="rounded-xl bg-gradient-to-br from-red-50 to-red-100 border border-red-200 px-3 py-2 mb-4 text-[12px] text-red-700">
              {deleteLibraryConfirm.library_name}｜{deleteLibraryConfirm.library_key}
            </div>
            <div className="flex gap-2 justify-end">
              <button className="btn btn-ghost" onClick={() => setDeleteLibraryConfirm(null)}>取消</button>
              <button className="btn btn-primary !bg-red-500 !from-red-500 !to-red-600" onClick={handleDeleteLibrary}>确认删除当前数据库</button>
            </div>
          </div>
        </div>
      )}

      {/* Snapshot Preview Modal */}
      {snapshotPreview && (
        <div className="modal-overlay fixed inset-0 z-[9000] flex items-center justify-center" onClick={() => setSnapshotPreview(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div
            className="modal-content relative bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-[900px] w-[90vw] max-h-[85vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 shrink-0">
              <div>
                <div className="text-[15px] font-bold text-slate-800">库记录快照</div>
                <div className="text-[11px] text-slate-400 mt-0.5">{selectedRecord?.prefix || ''} · 来源 · {snapshotPreview.urls.length} 张图片</div>
              </div>
              <button onClick={() => setSnapshotPreview(null)} className="btn btn-ghost !p-1.5 !text-[18px] text-slate-400 hover:text-slate-700">&times;</button>
            </div>
            <div className="flex-1 min-h-0 flex">
              {/* Left: Image */}
              <div className="flex-1 min-w-0 border-r border-slate-200 flex flex-col items-center justify-center p-4 bg-gradient-to-br from-slate-50 to-slate-100">
                <div className="text-[11px] text-slate-400 mb-2 shrink-0">{selectedRecord?.prefix || ''} · {selectedRecord ? getSourceLabel(selectedRecord) : ''}</div>
                <div className="flex-1 min-h-0 flex items-center justify-center overflow-auto w-full">
                  <img
                    src={getAssetUrl(snapshotPreview.taskId, snapshotPreview.urls[snapshotPreview.page])}
                    alt="快照"
                    className="max-w-full max-h-[55vh] object-contain transition-transform duration-200"
                    style={{ transform: `scale(${snapshotPreview.zoom})` }}
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                </div>
                {/* Controls */}
                <div className="flex items-center gap-2 mt-3 shrink-0 flex-wrap justify-center">
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2.5" disabled={snapshotPreview.page <= 0} onClick={() => setSnapshotPreview(p => p ? { ...p, page: p.page - 1 } : null)}>&larr; 上一张</button>
                  <span className="text-[12px] text-slate-500 min-w-[48px] text-center">{snapshotPreview.page + 1} / {snapshotPreview.urls.length}</span>
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2.5" disabled={snapshotPreview.page >= snapshotPreview.urls.length - 1} onClick={() => setSnapshotPreview(p => p ? { ...p, page: p.page + 1 } : null)}>下一张 &rarr;</button>
                  <span className="w-px h-4 bg-slate-200 mx-1" />
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2" disabled={snapshotPreview.zoom <= 0.6} onClick={() => setSnapshotPreview(p => p ? { ...p, zoom: Math.max(0.6, p.zoom - 0.2) } : null)}>缩小</button>
                  <span className="text-[11px] text-slate-500 w-12 text-center">{Math.round(snapshotPreview.zoom * 100)}%</span>
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2" disabled={snapshotPreview.zoom >= 2.4} onClick={() => setSnapshotPreview(p => p ? { ...p, zoom: Math.min(2.4, p.zoom + 0.2) } : null)}>放大</button>
                  <button className="btn btn-ghost !text-[11px] !py-1 !px-2" onClick={() => setSnapshotPreview(p => p ? { ...p, zoom: 1 } : null)}>重置</button>
                </div>
              </div>
              {/* Right: Details */}
              <div className="w-[300px] shrink-0 overflow-auto p-4 flex flex-col gap-4">
                <div>
                  <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">特征提取</div>
                  <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 p-3 text-[12px] text-slate-600 leading-relaxed whitespace-pre-wrap max-h-[180px] overflow-auto">
                    {selectedRecord?.feature_report_text || '暂无特征数据'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">工艺规程</div>
                  {selectedRecord?.process_list?.length ? (
                    <div className="rounded-xl border border-slate-200 overflow-hidden">
                      <table className="data-table">
                        <thead><tr><th style={{ width: 60 }}>工序号</th><th>内容</th></tr></thead>
                        <tbody>
                          {selectedRecord.process_list.map((row, i) => {
                            const parts = String(row).split('@')
                            return (
                              <tr key={i}>
                                <td className="font-mono text-blue-600 text-[11px]">{parts[0] || `#${i + 1}`}</td>
                                <td className="text-[11px]">{parts.slice(1).join('@') || row}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : <div className="text-[12px] text-slate-400">暂无工艺数据</div>}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
