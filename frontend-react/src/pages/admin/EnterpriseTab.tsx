import { useState, useEffect } from 'react'
import { getEnterprises, createEnterprise, updateEnterprise, createAdminGrant } from '../../api/client'
import { useToast } from '../../hooks/useToast'
import type { Enterprise } from '../../types/auth'

export function EnterpriseTab() {
  const { show } = useToast()
  const [enterprises, setEnterprises] = useState<Enterprise[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const [renewModal, setRenewModal] = useState<{
    enterprise: Enterprise
    userId: string
    durationDays: number
  } | null>(null)

  const fetchEnterprises = async () => {
    try {
      setLoading(true)
      const data = await getEnterprises()
      setEnterprises(data.enterprises)
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '获取企业列表失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEnterprises()
  }, [])

  const handleCreate = async () => {
    if (!newName.trim()) {
      show('请输入企业名称', 'error')
      return
    }
    setCreating(true)
    try {
      await createEnterprise(newName.trim())
      show('企业创建成功', 'success')
      setNewName('')
      await fetchEnterprises()
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '创建企业失败', 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleToggleActive = async (enterprise: Enterprise) => {
    try {
      await updateEnterprise(enterprise.id, { is_active: !enterprise.is_active })
      show(enterprise.is_active ? '企业已停用' : '企业已启用', 'success')
      await fetchEnterprises()
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '操作失败', 'error')
    }
  }

  const handleRenew = async () => {
    if (!renewModal) return
    const { enterprise, userId, durationDays } = renewModal
    if (!userId.trim()) {
      show('请输入用户 ID', 'error')
      return
    }
    if (!durationDays || durationDays <= 0) {
      show('请输入有效天数', 'error')
      return
    }
    try {
      await createAdminGrant(Number(userId), enterprise.id, durationDays)
      show('管理员续期成功', 'success')
      setRenewModal(null)
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '续期失败', 'error')
    }
  }

  return (
    <div className="space-y-6">
      {/* Create form */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder="输入企业名称"
          className="block w-72 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
          onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
        />
        <button
          onClick={handleCreate}
          disabled={creating}
          className="bg-orange-500 hover:bg-orange-600 active:scale-[0.97] text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {creating ? '创建中...' : '新建企业'}
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">企业名称</th>
              <th className="text-left px-4 py-3 font-medium">用户数</th>
              <th className="text-left px-4 py-3 font-medium">状态</th>
              <th className="text-left px-4 py-3 font-medium">创建时间</th>
              <th className="text-left px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-slate-500">加载中...</td>
              </tr>
            ) : enterprises.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-slate-500">暂无企业</td>
              </tr>
            ) : (
              enterprises.map(ent => (
                <tr key={ent.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">{ent.name}</td>
                  <td className="px-4 py-3">{ent.user_count ?? '-'}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        ent.is_active
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-red-50 text-red-700'
                      }`}
                    >
                      {ent.is_active ? '正常' : '已停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(ent.created_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="px-4 py-3 space-x-2">
                    <button
                      onClick={() => handleToggleActive(ent)}
                      className="text-orange-600 hover:text-orange-800 text-xs font-medium"
                    >
                      {ent.is_active ? '停用' : '启用'}
                    </button>
                    <button
                      onClick={() =>
                        setRenewModal({ enterprise: ent, userId: '', durationDays: 365 })
                      }
                      className="text-orange-600 hover:text-orange-800 text-xs font-medium"
                    >
                      续期管理员
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Renew Modal */}
      {renewModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">
              续期管理员 - {renewModal.enterprise.name}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">用户 ID</label>
                <input
                  type="number"
                  value={renewModal.userId}
                  onChange={e =>
                    setRenewModal(prev =>
                      prev ? { ...prev, userId: e.target.value } : null,
                    )
                  }
                  className="block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
                  placeholder="输入用户 ID"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">续期天数</label>
                <input
                  type="number"
                  value={renewModal.durationDays}
                  onChange={e =>
                    setRenewModal(prev =>
                      prev ? { ...prev, durationDays: Number(e.target.value) } : null,
                    )
                  }
                  className="block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
                  min={1}
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setRenewModal(null)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleRenew}
                  className="bg-orange-500 hover:bg-orange-600 active:scale-[0.97] text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all"
                >
                  确认
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
