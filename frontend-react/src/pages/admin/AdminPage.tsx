import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { EnterpriseTab } from './EnterpriseTab'
import { UsersTab } from './UsersTab'
import { QuotaTab } from './QuotaTab'

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  enterprise_admin: '企业管理员',
}

type AdminTab = 'enterprise' | 'users' | 'quota'

export function AdminPage() {
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'super_admin'
  const title = isSuperAdmin ? '平台管理' : '企业运营台'
  const intro = isSuperAdmin
    ? '管理企业、用户与平台配额。'
    : '管理本企业成员、配额与授权状态。'

  const tabs = useMemo<{ id: AdminTab; label: string; visible: boolean }[]>(
    () => [
      { id: 'enterprise', label: '企业管理', visible: isSuperAdmin },
      { id: 'users', label: '用户管理', visible: true },
      { id: 'quota', label: '配额概览', visible: true },
    ],
    [isSuperAdmin],
  )

  const firstVisible = tabs.find(t => t.visible)
  const [activeTab, setActiveTab] = useState<AdminTab>(firstVisible?.id ?? 'users')
  const visibleTabs = tabs.filter(t => t.visible)

  useEffect(() => {
    const activeTabVisible = tabs.some(tab => tab.id === activeTab && tab.visible)
    if (!activeTabVisible && firstVisible) {
      setActiveTab(firstVisible.id)
    }
  }, [activeTab, firstVisible, tabs])

  return (
    <div className="max-w-6xl mx-auto py-8">
      {/* Header */}
      <div className="mb-6 space-y-2">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{title}</h1>
          {user && (
            <span className="theme-surface-chip inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border">
              {ROLE_LABELS[user.role] || user.role}
            </span>
          )}
        </div>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{intro}</p>
      </div>

      {/* Tab bar */}
      <div className="border-b mb-6" style={{ borderColor: 'var(--border)' }} role="tablist">
        <div className="flex gap-6">
          {tabs
            .filter(t => t.visible)
            .map(tab => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === tab.id
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent'
                }`}
                style={activeTab === tab.id ? undefined : { color: 'var(--text-secondary)' }}
              >
                {tab.label}
              </button>
            ))}
        </div>
      </div>

      {/* Tab panels */}
      {visibleTabs.some(tab => tab.id === activeTab) && activeTab === 'enterprise' && <EnterpriseTab />}
      {visibleTabs.some(tab => tab.id === activeTab) && activeTab === 'users' && <UsersTab />}
      {visibleTabs.some(tab => tab.id === activeTab) && activeTab === 'quota' && <QuotaTab />}
    </div>
  )
}
