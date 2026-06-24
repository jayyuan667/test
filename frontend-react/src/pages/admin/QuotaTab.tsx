import { useState, useEffect } from 'react'
import { getAdminQuotas } from '../../api/client'
import { useToast } from '../../hooks/useToast'
import type { QuotaInfo } from '../../types/auth'

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  enterprise_admin: '企业管理员',
  user: '普通用户',
}

export function QuotaTab() {
  const { show } = useToast()
  const [quotas, setQuotas] = useState<QuotaInfo[]>([])
  const [loading, setLoading] = useState(true)

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
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <div className="text-xs text-slate-500 font-medium mb-1">总配额</div>
          <div className="text-2xl font-bold text-orange-600">{totalGranted}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <div className="text-xs text-slate-500 font-medium mb-1">已使用</div>
          <div className="text-2xl font-bold text-orange-600">{totalUsed}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <div className="text-xs text-slate-500 font-medium mb-1">剩余</div>
          <div className="text-2xl font-bold text-orange-600">{totalRemaining}</div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">用户名</th>
              <th className="text-left px-4 py-3 font-medium">角色</th>
              <th className="text-left px-4 py-3 font-medium">总配额</th>
              <th className="text-left px-4 py-3 font-medium">已使用</th>
              <th className="text-left px-4 py-3 font-medium">剩余</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-slate-500">加载中...</td>
              </tr>
            ) : quotas.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-slate-500">暂无数据</td>
              </tr>
            ) : (
              quotas.map(q => (
                <tr key={q.user_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">{q.username}</td>
                  <td className="px-4 py-3">
                    <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                      {ROLE_LABELS[q.role] || q.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">{q.total_granted}</td>
                  <td className="px-4 py-3 text-red-600">{q.used}</td>
                  <td className="px-4 py-3 text-emerald-600">{q.remaining}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
