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
import type { PageId } from '../types'
import { useAuth } from '../contexts/AuthContext'
import { isUnassignedUser } from '../types/auth'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { normalizeAssetUrls, normalizeProcessRows, normalizeStringArray } from '../utils/processRows'

type ViewMode = 'list' | 'detail' | 'edit'

function LockShell({ onNavigate }: { onNavigate: (id: PageId) => void }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="card-solid max-w-md text-center p-8">
        <div className="theme-empty-accent w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
            <rect x="3" y="11" width="18" height="11" rx="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h3 className="text-[15px] font-bold mb-2" style={{ color: 'var(--text-primary)' }}>数据库未解锁</h3>
        <p className="text-[12px] mb-5" style={{ color: 'var(--text-secondary)' }}>请先完成知识库导入操作后再浏览数据库</p>
        <div className="flex items-center justify-center gap-3">
          <button className="btn btn-primary !text-[12px]" onClick={() => onNavigate('zip')}>前往导入</button>
          <button className="btn btn-secondary !text-[12px]" onClick={() => {
            sessionStorage.setItem('zip_unlocked', 'true')
            onNavigate('db')
          }}>查看公共库</button>
        </div>
      </div>
    </div>
  )
}

function UnassignedUserShell({ onNavigate }: { onNavigate: (id: PageId) => void }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="card-solid max-w-md text-center p-8">
        <div className="theme-empty-accent w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
            <path d="M12 3v18" />
            <path d="M3 12h18" />
            <circle cx="12" cy="12" r="9" />
          </svg>
        </div>
        <h3 className="text-[15px] font-bold mb-2" style={{ color: 'var(--text-primary)' }}>暂未开放知识库浏览</h3>
        <p className="text-[12px] mb-5" style={{ color: 'var(--text-secondary)' }}>当前账号尚未分配企业，仅可查看个人资料与授权状态。</p>
        <button className="btn btn-primary !text-[12px]" onClick={() => onNavigate('profile')}>前往个人中心</button>
      </div>
    </div>
  )
}

function getScopeUiLabel(scope: Pick<LibraryScope, 'scope_type'> | { scope_type: string } | null | undefined) {
  return scope?.scope_type === 'public' ? '平台工艺库' : '个人工艺库'
}

export function DbPage({ onNavigate }: { onNavigate: (id: PageId) => void }) {
  const { user } = useAuth()
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
  const [zipUnlocked, setZipUnlocked] = useState(sessionStorage.getItem('zip_unlocked') === 'true')

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
  const reduceMotion = usePrefersReducedMotion()

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
      setRecords((data.items || []).map((r: LibraryRecord) => ({
        ...r,
        process_list: normalizeProcessRows(r.process_list),
        trades: normalizeStringArray(r.trades),
      })))
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
      if (reduceMotion) {
        gsap.set(lockStateRef.current, { scale: 1, opacity: 1 })
        gsap.set(lockStateRef.current.querySelectorAll('h2, p, .btn'), { y: 0, opacity: 1 })
        return
      }
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
  }, [ready, reduceMotion])

  // GSAP: Page load animation (unlocked)
  useEffect(() => {
    if (ready !== true) return

    if (reduceMotion) {
      if (bannerRef.current) gsap.set(bannerRef.current, { y: 0, opacity: 1 })
      if (toolbarRef.current) gsap.set(toolbarRef.current, { y: 0, opacity: 1 })
      if (statsRef.current) {
        const cards = statsRef.current.querySelectorAll('.stat-card')
        gsap.set(cards, { y: 0, opacity: 1 })
      }
      if (filterRef.current) gsap.set(filterRef.current, { x: 0, opacity: 1 })
      if (recordListRef.current) gsap.set(recordListRef.current, { y: 0, opacity: 1 })
      return
    }

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
  }, [ready, reduceMotion])

  // GSAP: Record card hover animation
  const handleRecordCardHover = (index: number, isEnter: boolean) => {
    const card = recordCardsRef.current[index]
    if (!card) return

    if (reduceMotion) {
      gsap.set(card, isEnter
        ? { y: -3, scale: 1.01, boxShadow: '0 6px 20px rgba(0,0,0,0.1)' }
        : { y: 0, scale: 1, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }
      )
      return
    }

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
      if (reduceMotion) {
        gsap.set(detailRef.current, { x: 0, opacity: 1 })
        return
      }
      gsap.fromTo(detailRef.current,
        { x: 40, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' }
      )
    }
  }, [viewMode, reduceMotion])

  // GSAP: Modal animation
  useEffect(() => {
    if (deleteRecordConfirm || deleteLibraryConfirm || snapshotPreview) {
      const modal = document.querySelector('.modal-overlay')
      if (modal) {
        const content = modal.querySelector('.modal-content')
        if (content) {
          if (reduceMotion) {
            gsap.set(content, { scale: 1, opacity: 1 })
            return
          }
          gsap.fromTo(content,
            { scale: 0.9, opacity: 0 },
            { scale: 1, opacity: 1, duration: 0.35, ease: 'back.out(1.7)' }
          )
        }
      }
    }
  }, [deleteRecordConfirm, deleteLibraryConfirm, snapshotPreview, reduceMotion])

  const handleApplyFilter = () => { setPage(1); loadRecords() }
  const handleResetFilter = () => {
    setQuery(''); setFilterProductType(''); setFilterSource(''); setFilterStatus(''); setPage(1)
  }
  const handleRefresh = () => loadRecords()

  // Select record
  const handleSelectRecord = useCallback(async (record: LibraryRecord) => {
    try {
      const full = await getLibraryRecord(record.id, filterScope || undefined)
      setSelectedRecord({
        ...full,
        process_list: normalizeProcessRows(full.process_list),
        trades: normalizeStringArray(full.trades),
      })
      setViewMode('detail')
    } catch {
      setSelectedRecord({
        ...record,
        process_list: normalizeProcessRows(record.process_list),
        trades: normalizeStringArray(record.trades),
      })
      setViewMode('detail')
    }
  }, [filterScope])

  // Edit
  const [editProcessRows, setEditProcessRows] = useState<{ code: string; trade: string; content: string }[]>([])

  const handleEdit = () => {
    if (!selectedRecord || !canManageRecords) return
    const rows = normalizeProcessRows(selectedRecord.process_list)
    setEditDraft({
      prefix: selectedRecord.prefix,
      product_type: selectedRecord.product_type,
      process_summary: selectedRecord.process_summary,
      tech_requirement: selectedRecord.tech_requirement,
      content: selectedRecord.content,
      process_list: rows,
    } as Partial<LibraryRecord> & { process_list?: unknown })
    setEditProcessRows(rows)
    setEditFeaturePage(0)
    setViewMode('edit')
  }

  const handleSave = async () => {
    if (!selectedRecord || !canManageRecords) return
    setSaving(true)
    try {
      const body = { ...editDraft, process_list: editProcessRows } as Partial<LibraryRecord> & { library_key?: string; process_list?: unknown }
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
    setEditProcessRows([])
    setViewMode(selectedRecord ? 'detail' : 'list')
  }

  // Delete record with confirmation
  const handleDeleteRecord = async () => {
    if (!deleteRecordConfirm || !canManageRecords) return
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

  const getPreviewUrls = (record: LibraryRecord) => {
    const taskId = record.preview_task_id || record.source_task_id
    return normalizeAssetUrls(record.preview_image_urls, taskId, getAssetUrl)
  }

  const renderPreviewThumb = (record: LibraryRecord) => {
    const urls = getPreviewUrls(record)
    const firstUrl = urls[0]
    if (!firstUrl) {
      return (
        <button
          type="button"
          aria-label={`${record.prefix || '记录'} 暂无图纸快照`}
          className="theme-empty-accent w-20 h-20 shrink-0 rounded-xl border border-dashed text-orange-300 flex flex-col items-center justify-center cursor-default"
          onClick={e => e.stopPropagation()}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M8 12h8" />
            <path d="M12 8v8" />
          </svg>
          <span className="text-[10px] mt-1">暂无预览</span>
        </button>
      )
    }
    return (
      <button
        type="button"
        aria-label={`查看 ${record.prefix || '记录'} 图纸快照`}
        className="theme-preview-frame w-20 h-20 shrink-0 rounded-xl border overflow-hidden group/thumb"
        onClick={e => {
          e.stopPropagation()
          handleSelectRecord(record)
          handleViewSnapshot(record)
        }}
      >
        <img
          src={firstUrl}
          alt={`${record.prefix || '记录'} 图纸缩略图`}
          className="w-full h-full object-cover transition-transform duration-200 group-hover/thumb:scale-105"
          onError={e => {
            const img = e.currentTarget
            img.style.display = 'none'
            const parent = img.parentElement
            if (parent) parent.setAttribute('aria-label', `${record.prefix || '记录'} 暂无图纸快照`)
          }}
        />
      </button>
    )
  }

  // Snapshot preview
  const handleViewSnapshot = (record: LibraryRecord) => {
    const taskId = record.preview_task_id || record.source_task_id
    const urls = normalizeAssetUrls(record.preview_image_urls, taskId, getAssetUrl)
    if (taskId && urls.length) {
      setSnapshotPreview({ taskId, urls, page: 0, zoom: 1 })
    }
  }

  const backToList = () => {
    setSelectedRecord(null)
    setViewMode('list')
    setEditDraft({})
  }

  const selectedScope = scopes.find(scope => scope.library_key === filterScope) ?? activeScope
  const currentScopeLabel = getScopeUiLabel(selectedScope)
  const canManageRecords = !browseOnly && selectedScope?.scope_type !== 'public' && user?.role !== 'user'
  const allowDeleteScope = selectedScope?.scope_type !== 'public' && user?.role !== 'user'
  const bannerCopy = user?.role === 'super_admin'
    ? '查看平台与个人工艺记录。'
    : user?.role === 'enterprise_admin'
      ? '查看企业复用相关记录与个人工艺库。'
      : '查询、复用与回看我的工艺记录。'

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

  const getTradeBadgeClass = (trade?: string) => {
    if (!trade) return 'bg-stone-50 text-stone-600 border-stone-200'
    if (trade === '检') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    if (trade === '热处理') return 'bg-red-50 text-red-700 border-red-200'
    if (trade === '钳') return 'bg-amber-50 text-amber-700 border-amber-200'
    return 'bg-stone-50 text-stone-700 border-stone-200'
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
    return text.replace(regex, '<mark class="bg-orange-100/80 rounded px-0.5 text-orange-900">$1</mark>')
  }

  // Editable sources for filter
  const sourceOptions = useMemo(() => {
    const set = new Set(records.map(r => getSourceLabel(r)).filter(Boolean))
    return Array.from(set)
  }, [records])

  // Poll sessionStorage for unlock changes (handles in-page "查看公共库" click)
  useEffect(() => {
    if (zipUnlocked) return
    const interval = setInterval(() => {
      if (sessionStorage.getItem('zip_unlocked') === 'true') {
        setZipUnlocked(true)
        clearInterval(interval)
      }
    }, 200)
    return () => clearInterval(interval)
  }, [zipUnlocked])

  if (isUnassignedUser(user)) {
    return <UnassignedUserShell onNavigate={onNavigate} />
  }

  if (!zipUnlocked) {
    return <LockShell onNavigate={onNavigate} />
  }

  // Stat card data
  const statCards = [
    { label: '库内条目', value: total, color: 'from-stone-500 to-stone-700', bgColor: 'theme-surface-panel-subtle',
      iconSvg: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-stone-500"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg> },
    { label: '当前页', value: records.length, color: 'from-emerald-500 to-emerald-600', bgColor: 'bg-gradient-to-br from-emerald-50 to-emerald-100',
      iconSvg: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg> },
    { label: '编辑状态', value: viewMode === 'edit' ? '编辑中' : browseOnly ? '只读' : '启用', color: browseOnly ? 'from-stone-500 to-stone-700' : 'from-flame-500 to-flame-600', bgColor: browseOnly ? 'theme-surface-panel-subtle' : 'bg-gradient-to-br from-flame-50 to-orange-100',
      iconSvg: viewMode === 'edit'
        ? <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-flame-500"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
        : browseOnly
        ? <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-stone-500"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
        : <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-flame-500"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 9.9-1" /></svg> },
  ]

  // Lock state
  if (ready === false) {
    return (
      <div ref={lockStateRef} className="flex flex-col items-center justify-center h-full">
        <div className="card-solid max-w-[520px] text-center relative overflow-hidden">
          {/* Decorative background */}
          <div className="absolute inset-0 theme-surface-panel-muted opacity-70" />
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-flame-50/30 to-transparent rounded-bl-full" />

          <div className="relative z-10">
            <div className="theme-empty-accent w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <h2 className="text-[20px] font-extrabold mb-2" style={{ color: 'var(--text-primary)' }}>请先完成知识入库</h2>
            <p className="text-[13px] mb-6 leading-relaxed max-w-[380px] mx-auto" style={{ color: 'var(--text-secondary)' }}>
              数据库浏览页默认受"当前会话先入库"规则保护。你可以先浏览平台工艺库或个人工艺记录。
            </p>
            <div className="flex gap-3 justify-center flex-wrap">
              <button className="btn btn-primary !px-6 !py-3">前往工艺入库</button>
              <button className="btn btn-secondary !px-5 !py-3" onClick={() => { setReady(true); setBrowseOnly(true); setFilterScope('public') }}>查看平台工艺库</button>
              <button className="btn btn-secondary !px-5 !py-3" onClick={() => { setReady(true); setBrowseOnly(true) }}>查看个人工艺库</button>
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
        <div ref={bannerRef} className="theme-info-note flex items-center gap-3 px-4 py-3 rounded-xl shrink-0">
          <div className="theme-empty-accent w-8 h-8 rounded-lg flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--accent-action-strong)' }}><circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" /></svg>
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-[13px] font-bold">只读浏览模式</span>
            <span className="text-[12px] ml-2">你可以先查看公共库和自己之前的数据库记录；编辑、删除与保存会在完成入库后解锁。</span>
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
            className="btn btn-ghost theme-link-danger !text-[12px]"
            disabled={!allowDeleteScope}
            title={selectedScope?.scope_type === 'public' ? '平台工艺库只读' : user?.role === 'user' ? '仅管理员可删除个人工艺库' : ''}
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
            <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>当前库</label>
            <select
              className="theme-form-field rounded-lg px-2.5 py-1.5 text-[12px] transition-all"
              value={filterScope}
              onChange={e => { setFilterScope(e.target.value); setPage(1) }}
            >
              {scopes.map(s => (
                <option key={s.library_key} value={s.library_key}>{getScopeUiLabel(s)}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>页大小</label>
            <select
              className="theme-form-field rounded-lg px-2.5 py-1.5 text-[12px] transition-all"
              value={pageSize}
              onChange={e => { setPageSize(Number(e.target.value)); setPage(1) }}
            >
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
            </select>
          </div>
          <span className="chip">{currentScopeLabel} · {total} 条记录</span>
        </div>
      </div>

      <div className="card-solid !p-4 shrink-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="chip">{currentScopeLabel}</span>
          <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{bannerCopy}</span>
        </div>
      </div>

      {/* Filter disclosure panel (mobile) */}
      {filterOpen && (
        <div className="lg:hidden relative shrink-0">
          <div className="theme-modal-shell absolute inset-x-0 top-0 z-50 rounded-xl border shadow-lg p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="text-[12px] font-bold" style={{ color: 'var(--text-secondary)' }}>筛选条件</div>
              <button className="btn btn-ghost !p-1 !text-[14px]" onClick={() => setFilterOpen(false)}>&times;</button>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="mobile-filter-query" className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>模型编号/关键词</label>
              <input
                id="mobile-filter-query"
                className="theme-form-field rounded-lg px-2.5 py-2 text-[12px] transition-all"
                placeholder="搜索模型编号、工艺内容、摘要"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { handleApplyFilter(); setFilterOpen(false) } }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="mobile-filter-product" className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>产品类型</label>
              <select
                id="mobile-filter-product"
                className="theme-form-field rounded-lg px-2.5 py-2 text-[12px] transition-all"
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
      <div ref={statsRef} className="grid grid-cols-1 sm:grid-cols-3 gap-3 shrink-0">
        {statCards.map((stat) => (
          <div
            key={stat.label}
            className={`stat-card card-solid !p-4 cursor-default ${stat.bgColor}`}
          >
            <div className="flex items-center justify-between mb-2">
              {stat.iconSvg}
              <span className={`text-[11px] font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`}>
                {stat.label}
              </span>
            </div>
            <div className="text-[24px] font-extrabold leading-none" style={{ color: 'var(--text-primary)' }}>
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
            <div className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>筛选条件</div>
            <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>支持模型编号、来源、状态和产品类型筛选。</div>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="desktop-filter-query" className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>模型编号/关键词</label>
            <input
              id="desktop-filter-query"
              className="theme-form-field rounded-lg px-2.5 py-2 text-[12px] transition-all"
              placeholder="搜索模型编号、工艺内容、摘要"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleApplyFilter() }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="desktop-filter-product" className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>产品类型</label>
            <select
              id="desktop-filter-product"
              className="theme-form-field rounded-lg px-2.5 py-2 text-[12px] transition-all"
              value={filterProductType}
              onChange={e => setFilterProductType(e.target.value)}
            >
              <option value="">全部</option>
              {productTypes.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="desktop-filter-source" className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>来源</label>
            <select
              id="desktop-filter-source"
              className="theme-form-field rounded-lg px-2.5 py-2 text-[12px] transition-all"
              value={filterSource}
              onChange={e => setFilterSource(e.target.value)}
            >
              <option value="">全部来源</option>
              {sourceOptions.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="desktop-filter-status" className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>记录状态</label>
            <select
              id="desktop-filter-status"
              className="theme-form-field rounded-lg px-2.5 py-2 text-[12px] transition-all"
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
            <div className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>记录列表</div>
            <div className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>{records.length} / {total} · 当前显示 {currentScopeLabel} 的 {records.length} 条记录</div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16 text-[13px]" style={{ color: 'var(--text-muted)' }}>
              <div className="flex items-center gap-3">
                <svg className="animate-spin h-5 w-5 text-flame-500" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                加载中...
              </div>
            </div>
          ) : records.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16" style={{ color: 'var(--text-muted)' }}>
              <div className="theme-empty-accent w-16 h-16 rounded-full flex items-center justify-center mb-3">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--surface-empty-accent-stroke)' }}>
                  <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                </svg>
              </div>
              <div className="text-[14px] font-bold mb-1" style={{ color: 'var(--text-secondary)' }}>暂无记录</div>
              <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>调整筛选条件或先完成工艺入库。</div>
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
                        : 'border-[color:var(--border)] bg-[var(--surface-panel)] hover:border-[color:var(--border-strong)] hover:shadow-sm'}
                    `}
                    onMouseEnter={() => handleRecordCardHover(index, true)}
                    onMouseLeave={() => handleRecordCardHover(index, false)}
                  >
                    <div className="flex items-start gap-3">
                      {renderPreviewThumb(r)}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between mb-1.5">
                          <div className="min-w-0 flex items-center gap-2">
                            <div className="text-[14px] font-bold truncate" style={{ color: 'var(--text-primary)' }} dangerouslySetInnerHTML={{ __html: highlightText(r.prefix || '未命名', query) }} />
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${st.cls}`}>{st.label}</span>
                          </div>
                          <span className="chip shrink-0 ml-2 !text-[10px]">{r.process_count || 0} 工序</span>
                        </div>
                        <div className="text-[11px] mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                          <span dangerouslySetInnerHTML={{ __html: highlightText(r.product_type || '未分类', query) }} />
                          {' · '}
                          <span>{src}</span>
                          {' · '}
                          <span>工序 {r.process_count || 0} 条</span>
                        </div>
                        {r.process_summary && (
                          <div className="text-[12px] line-clamp-2 leading-relaxed mb-1.5" style={{ color: 'var(--text-secondary)' }} dangerouslySetInnerHTML={{ __html: highlightText(r.process_summary, query) }} />
                        )}
                        <div className="flex gap-1.5 flex-wrap">
                          {r.trades?.slice(0, 3).map(t => (
                            <span key={t} className="theme-surface-chip text-[10px] px-2 py-0.5 rounded-full border">{t}</span>
                          ))}
                        </div>
                      </div>
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
                  <div className="text-[16px] font-extrabold" style={{ color: 'var(--text-primary)' }}>{selectedRecord.prefix}</div>
                  {(() => { const st = getRecordStatus(selectedRecord); return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${st.cls}`}>{st.label}</span> })()}
                </div>
                <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  来源：{getSourceLabel(selectedRecord)} · 最近更新：{selectedRecord.created_at ? new Date(selectedRecord.created_at).toLocaleDateString() : '-'}
                  {selectedRecord.preview_total_pages > 0 && ` · ${selectedRecord.preview_total_pages} 张图片`}
                </div>
              </div>
              <div className="flex gap-2">
                {viewMode === 'detail' && canManageRecords && (
                  <>
                    <button className="btn btn-secondary !text-[12px] !py-2" onClick={handleEdit}>编辑记录</button>
                    <button className="btn btn-ghost theme-link-danger !text-[12px] !py-2" onClick={() => setDeleteRecordConfirm(selectedRecord)}>删除</button>
                  </>
                )}
                {viewMode === 'detail' && !canManageRecords && (
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
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="theme-surface-panel-muted rounded-xl border p-3" style={{ borderColor: 'var(--border)' }}>
                      <div className="text-[11px] font-bold mb-1" style={{ color: 'var(--text-secondary)' }}>产品类型</div>
                      <div className="text-[13px]" style={{ color: 'var(--text-primary)' }}>{selectedRecord.product_type || '-'}</div>
                    </div>
                    <div className="theme-surface-panel-muted rounded-xl border p-3" style={{ borderColor: 'var(--border)' }}>
                      <div className="text-[11px] font-bold mb-1" style={{ color: 'var(--text-secondary)' }}>技术要求</div>
                      <div className="text-[13px]" style={{ color: 'var(--text-primary)' }}>{selectedRecord.tech_requirement || '-'}</div>
                    </div>
                  </div>

                  {selectedRecord.process_summary && (
                    <div className="theme-surface-panel-muted rounded-xl border p-3" style={{ borderColor: 'var(--border)' }}>
                      <div className="text-[11px] font-bold mb-1" style={{ color: 'var(--text-secondary)' }}>工艺摘要</div>
                      <div className="text-[13px] leading-relaxed" style={{ color: 'var(--text-primary)' }}>{selectedRecord.process_summary}</div>
                    </div>
                  )}

                  {/* Process table */}
                  <div>
                    <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">工艺规程</div>
                    {selectedRecord.process_list?.length ? (
                      <div className="theme-surface-panel rounded-xl border overflow-hidden">
                        <table className="data-table">
                          <thead><tr><th style={{ width: 60 }}>工序号</th><th style={{ width: 56 }}>工种</th><th>工序内容</th></tr></thead>
                          <tbody>
                            {normalizeProcessRows(selectedRecord.process_list).map((row, i) => {
                              return (
                                <tr key={i}>
                                  <td className="theme-code-accent font-mono text-[12px] font-bold">{row.code || `#${i + 1}`}</td>
                                  <td>
                                    {row.trade ? (
                                      <span className={[
                                        'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border',
                                        getTradeBadgeClass(row.trade)
                                      ].join(' ')}>{row.trade}</span>
                                    ) : <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>—</span>}
                                  </td>
                                  <td className="text-[12px]">{row.content}</td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>暂无工艺数据</div>}
                  </div>

                  {/* Feature report */}
                  {selectedRecord.feature_report_text && (
                    <div>
                      <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">特征提取</div>
                    <div className="theme-surface-panel-muted rounded-xl border p-3 text-[12px] leading-relaxed whitespace-pre-wrap max-h-[200px] overflow-auto" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
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
                  <div className="text-[12px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--text-secondary)' }}>编辑记录 <span className="font-normal normal-case tracking-normal ml-1">保存后自动同步到数据库</span></div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>产品类型</label>
                      <input
                        className="theme-form-field rounded-lg px-3 py-2 text-[13px] transition-all"
                        value={editDraft.product_type || ''}
                        onChange={e => setEditDraft(d => ({ ...d, product_type: e.target.value }))}
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>图号</label>
                      <input
                        className="theme-form-field rounded-lg px-3 py-2 text-[13px] transition-all"
                        value={editDraft.prefix || ''}
                        onChange={e => setEditDraft(d => ({ ...d, prefix: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>技术要求</label>
                    <textarea
                      className="theme-form-field rounded-lg px-3 py-2.5 text-[13px] transition-all resize-none"
                      rows={2}
                      placeholder="例：调质处理 HB 240-280；未注倒角 C1"
                      value={editDraft.tech_requirement || ''}
                      onChange={e => setEditDraft(d => ({ ...d, tech_requirement: e.target.value }))}
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>工艺摘要</label>
                    <textarea
                      className="theme-form-field rounded-lg px-3 py-2.5 text-[13px] transition-all resize-none"
                      rows={2}
                      placeholder="例：0010 备料 | 0020 车 | 0030 铣 | 0040 钳 | 0050 检"
                      value={editDraft.process_summary || ''}
                      onChange={e => setEditDraft(d => ({ ...d, process_summary: e.target.value }))}
                    />
                  </div>

                  {/* Editable process table */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>工艺规程表</label>
                      <button
                        className="btn btn-ghost !text-[10px] !py-1 !px-2 text-flame-600"
                        onClick={() => {
                          const newRow = { code: '', trade: '', content: '' }
                          setEditProcessRows(prev => [...prev, newRow])
                        }}
                      >
                        + 添加工序
                      </button>
                    </div>
                    {editProcessRows.length > 0 ? (
                      <div className="theme-surface-panel rounded-xl border overflow-hidden">
                        <table className="data-table">
                          <thead><tr><th style={{ width: 56 }}>工序号</th><th style={{ width: 52 }}>工种</th><th>工序内容</th><th style={{ width: 32 }}></th></tr></thead>
                          <tbody>
                            {editProcessRows.map((row, i) => (
                              <tr key={i} className="group">
                                <td>
                                  <input
                                    className="theme-code-accent w-full border-0 outline-none focus:ring-1 focus:ring-flame-400 rounded px-1 py-0.5 text-[11px] font-mono font-bold"
                                    placeholder="0010"
                                    value={row.code}
                                    onChange={e => {
                                      const next = [...editProcessRows]
                                      next[i] = { ...next[i], code: e.target.value }
                                      setEditProcessRows(next)
                                    }}
                                  />
                                </td>
                                <td>
                                  <input
                                    className="w-full bg-transparent text-[11px] font-semibold border-0 outline-none focus:ring-1 focus:ring-flame-400 rounded px-1 py-0.5"
                                    placeholder="车"
                                    value={row.trade}
                                    onChange={e => {
                                      const next = [...editProcessRows]
                                      next[i] = { ...next[i], trade: e.target.value }
                                      setEditProcessRows(next)
                                    }}
                                  />
                                </td>
                                <td>
                                  <input
                                    className="w-full bg-transparent text-[11px] border-0 outline-none focus:ring-1 focus:ring-flame-400 rounded px-1 py-0.5"
                                    placeholder="工序内容..."
                                    value={row.content}
                                    onChange={e => {
                                      const next = [...editProcessRows]
                                      next[i] = { ...next[i], content: e.target.value }
                                      setEditProcessRows(next)
                                    }}
                                  />
                                </td>
                                <td>
                                  <button
                                    className="text-[14px] transition-colors leading-none"
                                    style={{ color: 'var(--text-muted)' }}
                                    onClick={() => setEditProcessRows(prev => prev.filter((_, idx) => idx !== i))}
                                    title="删除此行"
                                  >×</button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-[11px] py-3 text-center border border-dashed rounded-xl" style={{ color: 'var(--text-muted)', borderColor: 'var(--border)' }}>暂无工序，点击"+ 添加工序"</div>
                    )}
                  </div>

                  {/* Feature report page editor */}
                  {featurePages.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>特征提取（按页编辑）</label>
                        <div className="flex items-center gap-1.5">
                          <button className="btn btn-ghost !text-[10px] !py-1 !px-2" disabled={editFeaturePage <= 0} onClick={() => setEditFeaturePage(p => p - 1)}>&larr;</button>
                          <span className="text-[11px] min-w-[56px] text-center" style={{ color: 'var(--text-secondary)' }}>第 {editFeaturePage + 1} / {featurePages.length} 页</span>
                          <button className="btn btn-ghost !text-[10px] !py-1 !px-2" disabled={editFeaturePage >= featurePages.length - 1} onClick={() => setEditFeaturePage(p => p + 1)}>&rarr;</button>
                        </div>
                      </div>
                      {featurePages[editFeaturePage] && (
                        <div className="theme-surface-panel-muted rounded-xl border p-3" style={{ borderColor: 'var(--border)' }}>
                          <div className="text-[11px] mb-2" style={{ color: 'var(--text-secondary)' }}>第 {String((featurePages[editFeaturePage] as Record<string, unknown>)._page_number || editFeaturePage + 1)} 页</div>
                          {(() => {
                            const fp = featurePages[editFeaturePage] as Record<string, unknown>
                            const fields = fp.fields || fp.key_features
                            if (fields && typeof fields === 'object') {
                              return Object.entries(fields as Record<string, unknown>).map(([k, v]) => (
                                <div key={k} className="flex gap-2 text-[12px] py-1 border-b last:border-0" style={{ borderColor: 'var(--border-subtle)' }}>
                                  <span className="font-semibold shrink-0 w-[100px]" style={{ color: 'var(--text-secondary)' }}>{k}</span>
                                  <span style={{ color: 'var(--text-primary)' }}>{String(v)}</span>
                                </div>
                              ))
                            }
                            return <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>{String(fp.description || fp.text || '无结构化数据')}</div>
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
        <div className="flex items-center justify-between shrink-0 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          <span>第 {page} / {totalPages} 页</span>
          <div className="flex gap-2">
            <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
            <button className="btn btn-secondary !text-[11px] !py-1.5 !px-3" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
          </div>
        </div>
      )}

      {/* Delete Record Confirmation Modal */}
      {deleteRecordConfirm && (
        <div className="modal-overlay fixed inset-0 z-[2000] flex items-center justify-center" onClick={() => setDeleteRecordConfirm(null)}>
          <div className="absolute inset-0 backdrop-blur-sm" style={{ background: 'var(--modal-overlay)' }} />
          <div className="theme-modal-shell modal-content relative rounded-2xl shadow-2xl border max-w-[420px] w-[90vw] p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-[16px] font-bold mb-2" style={{ color: 'var(--text-primary)' }}>确认删除记录</h3>
            <p className="text-[13px] mb-3 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>删除会影响数据库浏览与后续检索结果。此操作不可恢复。</p>
            <div className="theme-danger-note rounded-xl px-3 py-2 mb-4 text-[12px]">
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
        <div className="modal-overlay fixed inset-0 z-[2000] flex items-center justify-center" onClick={() => setDeleteLibraryConfirm(null)}>
          <div className="absolute inset-0 backdrop-blur-sm" style={{ background: 'var(--modal-overlay)' }} />
          <div className="theme-modal-shell modal-content relative rounded-2xl shadow-2xl border max-w-[420px] w-[90vw] p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-[16px] font-bold mb-2" style={{ color: 'var(--text-primary)' }}>确认删除当前数据库</h3>
            <p className="text-[13px] mb-3 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>这会清空当前选中的个人工艺库，平台工艺库不受影响。删除后该库里的记录将无法浏览，除非重新导入。</p>
            <div className="theme-danger-note rounded-xl px-3 py-2 mb-4 text-[12px]">
              {getScopeUiLabel(deleteLibraryConfirm)}｜{deleteLibraryConfirm.library_key}
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
        <div className="modal-overlay fixed inset-0 z-[2000] flex items-center justify-center" onClick={() => setSnapshotPreview(null)}>
          <div className="absolute inset-0 backdrop-blur-sm" style={{ background: 'var(--modal-overlay)' }} />
          <div
            className="theme-modal-shell modal-content relative rounded-2xl shadow-2xl border max-w-[900px] w-[90vw] max-h-[85vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b shrink-0" style={{ borderColor: 'var(--modal-subtle-border)' }}>
              <div>
                <div className="text-[15px] font-bold" style={{ color: 'var(--text-primary)' }}>库记录快照</div>
                <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>{selectedRecord?.prefix || ''} · 来源 · {snapshotPreview.urls.length} 张图片</div>
              </div>
              <button onClick={() => setSnapshotPreview(null)} className="btn btn-ghost !p-1.5 !text-[18px]" style={{ color: 'var(--text-muted)' }}>&times;</button>
            </div>
            <div className="flex-1 min-h-0 flex">
              {/* Left: Image */}
              <div className="theme-preview-frame flex-1 min-w-0 border-r border flex flex-col items-center justify-center p-4">
                <div className="text-[11px] mb-2 shrink-0" style={{ color: 'var(--text-muted)' }}>{selectedRecord?.prefix || ''} · {selectedRecord ? getSourceLabel(selectedRecord) : ''}</div>
                <div className="flex-1 min-h-0 flex items-center justify-center overflow-auto w-full">
                  <img
                    src={snapshotPreview.urls[snapshotPreview.page]}
                    alt="快照"
                    className="max-w-full max-h-[55vh] object-contain transition-transform duration-200"
                    style={{ transform: `scale(${snapshotPreview.zoom})` }}
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                </div>
                {/* Controls */}
                <div className="flex items-center gap-2 mt-3 shrink-0 flex-wrap justify-center">
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2.5" disabled={snapshotPreview.page <= 0} onClick={() => setSnapshotPreview(p => p ? { ...p, page: p.page - 1 } : null)}>&larr; 上一张</button>
                  <span className="text-[12px] min-w-[48px] text-center" style={{ color: 'var(--text-secondary)' }}>{snapshotPreview.page + 1} / {snapshotPreview.urls.length}</span>
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2.5" disabled={snapshotPreview.page >= snapshotPreview.urls.length - 1} onClick={() => setSnapshotPreview(p => p ? { ...p, page: p.page + 1 } : null)}>下一张 &rarr;</button>
                  <span className="w-px h-4 mx-1" style={{ background: 'var(--border)' }} />
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2" disabled={snapshotPreview.zoom <= 0.6} onClick={() => setSnapshotPreview(p => p ? { ...p, zoom: Math.max(0.6, p.zoom - 0.2) } : null)}>缩小</button>
                  <span className="text-[11px] w-12 text-center" style={{ color: 'var(--text-secondary)' }}>{Math.round(snapshotPreview.zoom * 100)}%</span>
                  <button className="btn btn-secondary !text-[11px] !py-1 !px-2" disabled={snapshotPreview.zoom >= 2.4} onClick={() => setSnapshotPreview(p => p ? { ...p, zoom: Math.min(2.4, p.zoom + 0.2) } : null)}>放大</button>
                  <button className="btn btn-ghost !text-[11px] !py-1 !px-2" onClick={() => setSnapshotPreview(p => p ? { ...p, zoom: 1 } : null)}>重置</button>
                </div>
              </div>
              {/* Right: Details */}
              <div className="w-[300px] shrink-0 overflow-auto p-4 flex flex-col gap-4">
                <div>
                  <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">特征提取</div>
                  <div className="theme-surface-panel-muted rounded-xl border p-3 text-[12px] leading-relaxed whitespace-pre-wrap max-h-[180px] overflow-auto" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                    {selectedRecord?.feature_report_text || '暂无特征数据'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-bold text-flame-600 uppercase tracking-wider mb-2">工艺规程</div>
                  {selectedRecord?.process_list?.length ? (
                    <div className="theme-surface-panel rounded-xl border overflow-hidden">
                      <table className="data-table">
                        <thead><tr><th style={{ width: 48 }}>工序号</th><th style={{ width: 44 }}>工种</th><th>工序内容</th></tr></thead>
                        <tbody>
                          {normalizeProcessRows(selectedRecord.process_list).map((row, i) => {
                            return (
                              <tr key={i}>
                                <td className="theme-code-accent font-mono text-[10px] font-bold">{row.code || `#${i + 1}`}</td>
                                <td>
                                  {row.trade ? (
                                    <span className={[
                                      'inline-flex items-center px-1 py-0.5 rounded text-[9px] font-semibold border',
                                      getTradeBadgeClass(row.trade)
                                    ].join(' ')}>{row.trade}</span>
                                  ) : <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>—</span>}
                                </td>
                                <td className="text-[10px] leading-relaxed">{row.content}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : <div className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>暂无工艺数据</div>}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
