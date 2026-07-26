import { useCallback, useEffect, useRef, useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { ToastStack } from './components/shared/Toast'
import { useToast } from './hooks/useToast'
import { ToastProvider } from './contexts/ToastContext'
import { GeneratePage } from './pages/GeneratePage'
import { ZipPage } from './pages/ZipPage'
import { HistoryPage } from './pages/HistoryPage'
import { DbPage } from './pages/DbPage'
import { ProfilePage } from './pages/ProfilePage'
import { AdminPage } from './pages/admin/AdminPage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { AuthEntryScene } from './components/auth/AuthEntryScene'
import gsap from 'gsap'
import { usePrefersReducedMotion } from './hooks/usePrefersReducedMotion'
import { isUnassignedUser } from './types/auth'

import type { PageId } from './types'

const APP_THEME: 'v1' | 'v2' = 'v2'

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </ToastProvider>
  )
}

function AppShell() {
  const { isAuthenticated, isLoading } = useAuth()
  const { toasts } = useToast()

  if (isLoading) {
    return (
      <div className="app-shell-loading min-h-[100dvh] flex items-center justify-center">
        <div className="app-shell-loading-text text-sm">加载中...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <>
        <AuthEntryScene />
        <ToastStack toasts={toasts} />
      </>
    )
  }

  return <AppLayout />
}

function AppLayout() {
  const { user, logout } = useAuth()
  const isUnassigned = isUnassignedUser(user)
  const initialPage: PageId = isUnassigned ? 'profile' : 'generate'
  const [page, setPage] = useState<PageId>(initialPage)
  const [collapsed, setCollapsed] = useState(false)
  const [generateBusy, setGenerateBusy] = useState(false)
  const [zipBusy, setZipBusy] = useState(false)
  const anyBusy = generateBusy || zipBusy
  const { toasts, show } = useToast()
  const pageContentRef = useRef<HTMLDivElement>(null)
  const prevPageRef = useRef<PageId>(initialPage)
  const reduceMotion = usePrefersReducedMotion()

  const [mountedPages, setMountedPages] = useState<Set<PageId>>(() => new Set([initialPage]))

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
    if (id === 'login') {
      logout()
      return
    }
    if (isUnassigned && id !== 'profile') {
      setMountedPages(prev => prev.has('profile') ? prev : new Set([...prev, 'profile']))
      setPage('profile')
      return
    }
    if (anyBusy && id !== page) {
      if (!window.confirm('当前有任务正在进行中，切换页面将中断进程。\n\n确定要离开吗？')) return
      setGenerateBusy(false)
      setZipBusy(false)
    }
    setMountedPages(prev => prev.has(id) ? prev : new Set([...prev, id]))
    setPage(id)
  }, [anyBusy, isUnassigned, page, logout])

  useEffect(() => {
    if (!isUnassigned || page === 'profile') return
    setMountedPages(prev => prev.has('profile') ? prev : new Set([...prev, 'profile']))
    setPage('profile')
  }, [isUnassigned, page])

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

  const isAdmin = user?.role === 'super_admin' || user?.role === 'enterprise_admin'

  return (
    <div className="app-shell flex h-screen overflow-hidden relative" data-app-shell="true" data-theme={APP_THEME}>
      <Sidebar
        active={page}
        onNavigate={handleNavigate}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(c => !c)}
        disabled={anyBusy}
        userRole={user?.role}
        userEnterpriseId={user?.enterprise_id}
      />
      <main className="app-shell-main flex-1 min-w-0 flex flex-col relative z-10">
        <div ref={pageContentRef} className="app-shell-content flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-8 pb-6">
          <div style={{ display: page === 'generate' ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
            {mountedPages.has('generate') && <GeneratePage onError={handleError} onSuccess={(msg) => show(msg, 'success')} onBusyChange={handleGenerateBusy} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'zip' ? 'block' : 'none' }}>
            {mountedPages.has('zip') && <ZipPage onBusyChange={handleZipBusy} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'history' ? 'block' : 'none' }}>
            {mountedPages.has('history') && <HistoryPage visible={page === 'history'} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'db' ? 'block' : 'none' }}>
            {mountedPages.has('db') && <DbPage onNavigate={handleNavigate} />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'profile' ? 'block' : 'none' }}>
            {mountedPages.has('profile') && <ProfilePage />}
          </div>
          <div className="h-full overflow-y-auto overflow-x-hidden" style={{ display: page === 'admin' && isAdmin ? 'block' : 'none' }}>
            {mountedPages.has('admin') && isAdmin && <AdminPage />}
          </div>
        </div>
        <footer className="app-shell-footer shrink-0 text-center text-[12px] py-2.5">
          Copyright © 机器学习与工业智能应用教育部工程研究中心
        </footer>
      </main>
      <ToastStack toasts={toasts} />
    </div>
  )
}
