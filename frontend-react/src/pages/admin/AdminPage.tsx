import { useMemo, useState } from 'react'
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

  const tabs = useMemo<{ id: AdminTab; label: string; visible: boolean }[]>(
    () => [
      { id: 'enterprise', label: '企业管理', visible: user?.role === 'super_admin' },
      { id: 'users', label: '用户管理', visible: true },
      { id: 'quota', label: '配额概览', visible: true },
    ],
    [user?.role],
  )

  const firstVisible = tabs.find(t => t.visible)
  const [activeTab, setActiveTab] = useState<AdminTab>(firstVisible?.id ?? 'users')

  return (
    <div className="max-w-6xl mx-auto py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-xl font-bold text-slate-800">系统管理</h1>
        {user && (
          <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            {ROLE_LABELS[user.role] || user.role}
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div className="border-b border-slate-200 mb-6" role="tablist">
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
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
        </div>
      </div>

      {/* Tab panels */}
      {activeTab === 'enterprise' && <EnterpriseTab />}
      {activeTab === 'users' && <UsersTab />}
      {activeTab === 'quota' && <QuotaTab />}
    </div>
  )
}
