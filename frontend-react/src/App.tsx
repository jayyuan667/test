import { useCallback, useEffect, useRef, useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { ToastStack } from './components/shared/Toast'
import { useToast } from './hooks/useToast'
import { GeneratePage } from './pages/GeneratePage'
import { ZipPage } from './pages/ZipPage'
import { HistoryPage } from './pages/HistoryPage'
import { DbPage } from './pages/DbPage'
import gsap from 'gsap'
import { usePrefersReducedMotion } from './hooks/usePrefersReducedMotion'

import type { PageId } from './types'


export default function App() {
  const [page, setPage] = useState<PageId>('generate')
  const [collapsed, setCollapsed] = useState(false)
  const [generateBusy, setGenerateBusy] = useState(false)
  const [zipBusy, setZipBusy] = useState(false)
  const anyBusy = generateBusy || zipBusy
  const { toasts, show } = useToast()
  const pageContentRef = useRef<HTMLDivElement>(null)
  const prevPageRef = useRef<PageId>('generate')
  const reduceMotion = usePrefersReducedMotion()

  // Lazy-mount pages: first visit mounts, then stays mounted to preserve state
  const [mountedPages, setMountedPages] = useState<Set<PageId>>(() => new Set(['generate']))

  const handleError = useCallback((msg: string) => {
    show(msg, 'error')
  }, [show])

  const handleGenerateBusy = useCallback((busy: boolean) => {
    setGenerateBusy(busy)
  }, [])

  const handleZipBusy = useCallback((busy: boolean) => {
    setZipBusy(busy)
  }, [])

  const handleNavigate = useCallback((id: PageId) => {
    if (anyBusy && id !== page) {
      if (!window.confirm('当前有任务正在进行中，切换页面将中断进程。\n\n确定要离开吗？')) return
      // User confirmed — reset busy flags so the new page starts clean
      setGenerateBusy(false)
      setZipBusy(false)
    }
    setMountedPages(prev => prev.has(id) ? prev : new Set([...prev, id]))
    setPage(id)
  }, [anyBusy, page])

  // GSAP: Page transition
  useEffect(() => {
    if (prevPageRef.current === page) return
    prevPageRef.current = page
    if (pageContentRef.current) {
      if (reduceMotion) {
        gsap.set(pageContentRef.current, { opacity: 1, y: 0 })
        return
      }
      gsap.fromTo(pageContentRef.current,
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }
      )
    }
  }, [page, reduceMotion])

  return (
    <div className="flex h-screen overflow-hidden relative">
      <Sidebar
        active={page}
        onNavigate={handleNavigate}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(c => !c)}
        disabled={anyBusy}
      />
      <main className="flex-1 min-w-0 flex flex-col relative z-10">
        {/* Page content — pages kept mounted after first visit to preserve state */}
        <div ref={pageContentRef} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-8 pb-6">
          {/* GeneratePage: flex layout to fill viewport, handles internal scroll */}
          <div style={{ display: page === 'generate' ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
            {mountedPages.has('generate') && <GeneratePage onError={handleError} onSuccess={(msg) => show(msg, 'success')} onBusyChange={handleGenerateBusy} />}
          </div>
          {/* Other pages: independent scroll containers */}
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'zip' ? 'block' : 'none' }}>
            {mountedPages.has('zip') && <ZipPage onBusyChange={handleZipBusy} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'history' ? 'block' : 'none' }}>
            {mountedPages.has('history') && <HistoryPage />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'db' ? 'block' : 'none' }}>
            {mountedPages.has('db') && <DbPage onNavigate={handleNavigate} />}
          </div>
        </div>
        <footer className="shrink-0 text-center text-[12px] text-slate-500 py-2.5 bg-slate-50 border-t border-slate-200">
          Copyright © 机器学习与工业智能应用教育部工程研究中心
        </footer>
      </main>
      <ToastStack toasts={toasts} />
    </div>
  )
}
