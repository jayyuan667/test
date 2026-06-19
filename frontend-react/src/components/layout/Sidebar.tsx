import React, { useState } from 'react'
import type { PageId } from '../../types'

const NAV_ITEMS: { id: PageId; icon: React.ReactNode; title: string; sub: string }[] = [
  { id: 'zip',       icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>, title: '工艺入库', sub: 'ZIP 导入工艺知识库' },
  { id: 'generate',  icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>, title: '工艺生成', sub: '图纸分析与工艺编制' },
  { id: 'history',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>, title: '历史记录', sub: '历史输出与特征回看' },
  { id: 'db',        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>, title: '知识库浏览', sub: '工艺记录查询与管理' },
]

interface Props {
  active: PageId
  onNavigate: (id: PageId) => void
  collapsed: boolean
  onToggleCollapse: () => void
  disabled?: boolean
}

export function Sidebar({ active, onNavigate, collapsed, onToggleCollapse, disabled }: Props) {
  const [hovered, setHovered] = useState<string | null>(null)

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
        background: 'linear-gradient(175deg, #0f1d35 0%, #0b1526 40%, #081220 100%)',
      }} />
      {/* Radial glow top-left */}
      <div className="absolute inset-0" style={{
        background: 'radial-gradient(ellipse 60% 50% at 15% 5%, rgba(59, 130, 246, 0.12) 0%, transparent 70%)',
      }} />
      {/* Radial glow bottom-right */}
      <div className="absolute inset-0" style={{
        background: 'radial-gradient(ellipse 50% 40% at 85% 90%, rgba(249, 115, 22, 0.06) 0%, transparent 70%)',
      }} />
      {/* Noise texture overlay */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
      }} />

      {/* ── Content ── */}
      <div className="relative z-10 flex flex-col h-full">
        {/* Brand */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-white/[0.06]">
          <div
            className="w-10 h-10 rounded-xl shrink-0 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%)',
              boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
            }}
          >
            <div className="absolute inset-0" style={{
              background: 'radial-gradient(circle at 30% 25%, rgba(255,255,255,0.25) 0%, transparent 50%)',
            }} />
          </div>
          <div className="overflow-hidden" style={{ opacity: collapsed ? 0 : 1, transition: 'opacity 0.2s ease' }}>
            <div className="text-[15px] font-bold text-white tracking-wide leading-tight">二维工艺系统</div>
            <div className="text-[11px] text-white/40 mt-0.5 font-medium tracking-wider uppercase">2D Process Intelligence</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-3 pt-5 flex-1">
          <div className="px-2 mb-3 text-[10px] font-bold text-white/25 uppercase tracking-[0.12em] overflow-hidden" style={{ opacity: collapsed ? 0 : 1, maxHeight: collapsed ? 0 : '1.5em', transition: 'opacity 0.2s ease, max-height 0.2s ease' }}>导航</div>
          {NAV_ITEMS.map(item => {
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
                className={`
                  group relative flex items-center gap-3 rounded-xl cursor-pointer
                  border transition-all duration-200 ease-out text-left
                  ${isActive
                    ? 'text-white border-white/[0.08]'
                    : isDisabled
                      ? 'text-white/20 border-transparent cursor-not-allowed'
                      : 'text-white/50 border-transparent hover:text-white/80 hover:border-white/[0.05]'}
                `}
                style={{
                  padding: collapsed ? '12px 0' : '11px 14px',
                  justifyContent: collapsed ? 'center' : undefined,
                  background: isActive
                    ? 'linear-gradient(135deg, rgba(249, 115, 22, 0.15) 0%, rgba(234, 88, 12, 0.08) 100%)'
                    : isHovered
                      ? 'rgba(255, 255, 255, 0.04)'
                      : 'transparent',
                  boxShadow: isActive
                    ? 'inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 8px rgba(249, 115, 22, 0.08)'
                    : 'none',
                }}
              >
                {/* Active indicator */}
                {isActive && (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                    style={{ background: 'linear-gradient(180deg, #fb923c 0%, #f97316 100%)' }}
                  />
                )}

                {/* Icon */}
                <span
                  className={`
                    inline-flex items-center justify-center text-sm rounded-lg shrink-0
                    transition-all duration-200
                    ${isActive ? 'text-white' : 'text-white/40 group-hover:text-white/60'}
                  `}
                  style={{
                    width: collapsed ? 36 : 30,
                    height: collapsed ? 36 : 30,
                    background: isActive
                      ? 'rgba(249, 115, 22, 0.2)'
                      : 'rgba(255, 255, 255, 0.04)',
                    border: `1px solid ${isActive ? 'rgba(249, 115, 22, 0.2)' : 'rgba(255, 255, 255, 0.04)'}`,
                  }}
                >
                  {item.icon}
                </span>

                {/* Label */}
                <span className="overflow-hidden min-w-0" style={{ opacity: collapsed ? 0 : 1, transition: 'opacity 0.2s ease' }}>
                  <div className="text-[13px] font-semibold whitespace-nowrap overflow-hidden text-ellipsis leading-tight">
                    {item.title}
                  </div>
                  <div className={`text-[11px] mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis ${isActive ? 'text-white/50' : 'text-white/25'}`}>
                    {item.sub}
                  </div>
                </span>
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-3 pb-4 border-t border-white/[0.06] pt-3">
          <button
            onClick={onToggleCollapse}
            aria-label={collapsed ? '展开侧栏' : '折叠侧栏'}
            className="w-full flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-[11px] font-medium text-white/30 hover:text-white/50 hover:bg-white/[0.04] transition-all duration-200 border border-transparent hover:border-white/[0.05]"
          >
            <span className="text-sm" aria-hidden="true">{collapsed ? '→' : '←'}</span>
            {!collapsed && <span>折叠侧栏</span>}
          </button>
        </div>
      </div>
    </aside>
  )
}
