import { useState, useEffect } from 'react'
import { getAdminQuotas } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../hooks/useToast'
import type { QuotaInfo } from '../../types/auth'

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  enterprise_admin: '企业管理员',
  user: '普通用户',
}

export function QuotaTab() {
  const { user } = useAuth()
  const { show } = useToast()
  const [quotas, setQuotas] = useState<QuotaInfo[]>([])
  const [loading, setLoading] = useState(true)
  const isSuperAdmin = user?.role === 'super_admin'
  const summaryTitle = isSuperAdmin ? '平台配额概览' : '本企业配额概览'

  useEffect(() => {
    const fetchQuotas = async () => {
      try {
        setLoading(true)
        const data = await getAdminQuotas()
        setQuotas(data.quotas)
      } catch (err: unknown) {
        show(err instanceof Error ? err.message : '获取配额数据失败', 'error')
      } finally {
        setLoading(false)
      }
    }
    fetchQuotas()
  }, [])

  const totalGranted = quotas.reduce((sum, q) => sum + q.total_granted, 0)
  const totalUsed = quotas.reduce((sum, q) => sum + q.used, 0)
  const totalRemaining = totalGranted - totalUsed

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{summaryTitle}</h2>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="theme-surface-panel border rounded-lg p-5">
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>总配额</div>
          <div className="text-2xl font-bold text-orange-600">{totalGranted}</div>
        </div>
        <div className="theme-surface-panel border rounded-lg p-5">
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>已使用</div>
          <div className="text-2xl font-bold text-orange-600">{totalUsed}</div>
        </div>
        <div className="theme-surface-panel border rounded-lg p-5">
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>剩余</div>
          <div className="text-2xl font-bold text-orange-600">{totalRemaining}</div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>总配额</th>
              <th>已使用</th>
              <th>剩余</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>加载中...</td>
              </tr>
            ) : quotas.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>暂无数据</td>
              </tr>
            ) : (
              quotas.map(q => (
                <tr key={q.user_id}>
                  <td>{q.username}</td>
                  <td>
                    <span className="theme-surface-chip inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border">
                      {ROLE_LABELS[q.role] || q.role}
                    </span>
                  </td>
                  <td>{q.total_granted}</td>
                  <td className="text-red-600">{q.used}</td>
                  <td className="text-emerald-600">{q.remaining}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
