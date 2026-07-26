import React, { useState } from 'react'
import type { PageId } from '../../types'
import { isUnassignedUser, type User } from '../../types/auth'

interface NavItem {
  id: PageId
  icon: React.ReactNode
  title: string
  sub: string
  roles?: string[]
}

const NAV_ITEMS: NavItem[] = [
  { id: 'zip',       icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>, title: '工艺入库', sub: 'ZIP 导入工艺知识库' },
  { id: 'generate',  icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>, title: '工艺生成', sub: '图纸分析与工艺编制' },
  { id: 'history',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>, title: '历史记录', sub: '历史输出与特征回看' },
  { id: 'db',        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>, title: '知识库浏览', sub: '工艺记录查询与管理' },
  { id: 'profile',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>, title: '个人中心', sub: '账户信息与配额' },
  { id: 'admin',     icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>, title: '管理后台', sub: '用户与企业管理', roles: ['super_admin', 'enterprise_admin'] },
]

interface Props {
  active: PageId
  onNavigate: (id: PageId) => void
  collapsed: boolean
  onToggleCollapse: () => void
  disabled?: boolean
  userRole?: User['role']
  userEnterpriseId?: User['enterprise_id']
}

export function Sidebar({ active, onNavigate, collapsed, onToggleCollapse, disabled, userRole, userEnterpriseId }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)
  const isUnassigned = isUnassignedUser(userRole ? { role: userRole, enterprise_id: userEnterpriseId ?? null } : undefined)
  const visibleItems = NAV_ITEMS
    .map(item => (
      item.id === 'admin'
        ? {
            ...item,
            sub: userRole === 'super_admin' ? '平台治理与配额总览' : '企业成员与授权管理',
          }
        : item
    ))
    .filter(item => {
      if (item.roles && !item.roles.includes(userRole || '')) return false
      if (isUnassigned && item.id !== 'profile') return false
      return true
    })

  return (
    <aside
      className="flex flex-col relative overflow-hidden shrink-0 select-none"
      style={{
        width: collapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)',
        transition: 'width 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* ── Background layers ── */}
      <div className="absolute inset-0" style={{
        background: 'var(--sidebar-bg)',
      }} />
      <div className="absolute inset-0" style={{
        background: 'var(--sidebar-glow-top)',
      }} />
      <div className="absolute inset-0" style={{
        background: 'var(--sidebar-glow-bottom)',
      }} />
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
      }} />

      {/* ── Content ── */}
      <div className="relative z-10 flex flex-col h-full">
        {/* Brand + Collapse toggle */}
        <div
          className="border-b relative"
          style={{
            borderColor: 'var(--sidebar-border)',
            padding: collapsed ? '16px 0 14px' : '20px 20px 18px',
          }}
        >
          {collapsed ? (
            /* Collapsed: logo + arrow stacked vertically */
            <div className="flex flex-col items-center gap-2">
              <div className="w-12 h-8 shrink-0 relative overflow-hidden rounded-md bg-white">
                <img src="/dica-logo.png" alt="DICA" className="w-full h-full object-contain" />
              </div>
              <button
                onClick={onToggleCollapse}
                aria-label="展开侧栏"
                title="展开侧栏"
                className="sidebar-utility-button flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-200"
                style={{
                  color: 'var(--sidebar-text-secondary)',
                  background: 'var(--sidebar-hover-bg)',
                  border: '1px solid var(--sidebar-hover-border)',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            </div>
          ) : (
            /* Expanded: logo + text + collapse in a row */
            <div className="flex items-center gap-3">
              <div className="w-12 h-8 shrink-0 relative overflow-hidden rounded-md bg-white">
                <img src="/dica-logo.png" alt="DICA" className="w-full h-full object-contain" />
              </div>
              <div className="overflow-hidden flex-1 min-w-0">
                <div className="text-[15px] font-bold tracking-wide leading-tight" style={{ color: 'var(--sidebar-text-primary)' }}>DICA智能工艺系统</div>
                <div className="text-[11px] mt-0.5 font-medium tracking-wider uppercase" style={{ color: 'var(--sidebar-text-muted)' }}>DICA</div>
              </div>
              <button
                onClick={onToggleCollapse}
                aria-label="折叠侧栏"
                title="折叠侧栏"
                className="sidebar-utility-button shrink-0 flex items-center justify-center w-7 h-7 rounded-lg transition-all duration-200"
                style={{ color: 'var(--sidebar-text-secondary)' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-3 pt-5 flex-1">
          <div className="px-2 mb-3 text-[10px] font-bold uppercase tracking-[0.12em] overflow-hidden" style={{ color: 'var(--sidebar-text-faint)', opacity: collapsed ? 0 : 1, maxHeight: collapsed ? 0 : '1.5em', transition: 'opacity 0.2s ease, max-height 0.2s ease' }}>导航</div>
          {visibleItems.map(item => {
            const isActive = active === item.id
            const isHovered = hovered === item.id
            const isDisabled = disabled && !isActive
            return (
              <button
                key={item.id}
                onClick={() => isDisabled ? undefined : onNavigate(item.id)}
                onMouseEnter={() => setHovered(item.id)}
                onMouseLeave={() => setHovered(null)}
                disabled={isDisabled}
                title={collapsed ? item.title : undefined}
                className={`
                  group relative flex items-center rounded-xl cursor-pointer
                  border transition-all duration-200 ease-out text-left
                  ${isDisabled ? 'cursor-not-allowed' : ''}
                `}
                style={{
                  padding: collapsed ? '10px 0' : '11px 14px',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  gap: collapsed ? 0 : 12,
                  color: isActive
                    ? 'var(--sidebar-text-primary)'
                    : isDisabled
                      ? 'var(--sidebar-text-disabled)'
                      : isHovered
                        ? 'var(--sidebar-text-hover)'
                        : 'var(--sidebar-text-secondary)',
                  borderColor: isActive
                    ? 'var(--sidebar-active-border)'
                    : isHovered
                      ? 'var(--sidebar-hover-border)'
                      : 'transparent',
                  background: isActive
                    ? 'var(--sidebar-active-bg)'
                    : isHovered
                      ? 'var(--sidebar-hover-bg)'
                      : 'transparent',
                  boxShadow: isActive
                    ? 'var(--sidebar-active-shadow)'
                    : 'none',
                }}
              >
                {/* Active indicator */}
                {isActive && (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                    style={{ background: 'var(--accent-action-gradient-vertical)' }}
                  />
                )}

                {/* Icon */}
                <span
                  className="inline-flex items-center justify-center rounded-lg shrink-0 transition-all duration-200"
                  style={{
                    width: collapsed ? 36 : 30,
                    height: collapsed ? 36 : 30,
                    color: isActive ? 'var(--sidebar-icon-active)' : 'var(--sidebar-icon-default)',
                    background: isActive
                      ? 'var(--sidebar-icon-active-bg)'
                      : 'var(--sidebar-icon-bg)',
                    border: `1px solid ${isActive ? 'var(--sidebar-icon-active-border)' : 'var(--sidebar-icon-border)'}`,
                  }}
                >
                  {item.icon}
                </span>

                {/* Label — hidden when collapsed */}
                {!collapsed && (
                  <span className="overflow-hidden min-w-0 flex-1">
                    <div className="text-[13px] font-semibold whitespace-nowrap overflow-hidden text-ellipsis leading-tight">
                      {item.title}
                    </div>
                    <div className="text-[11px] mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis" style={{ color: isActive ? 'var(--sidebar-text-muted)' : 'var(--sidebar-text-faint)' }}>
                      {item.sub}
                    </div>
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Spacer pushes logout to bottom */}
        <div className="flex-1" />

        {/* Logout button */}
        {userRole && (
          <div className="px-3 pb-4">
            <button onClick={() => onNavigate('login')}
              title={collapsed ? '退出登录' : undefined}
              className="sidebar-utility-button w-full flex items-center justify-center gap-2 rounded-xl transition-all duration-200 border border-transparent"
              style={{
                padding: collapsed ? '10px 0' : '10px 14px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                color: 'var(--sidebar-text-faint)',
              }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              {!collapsed && <span className="text-[11px] font-medium">退出登录</span>}
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
