import { useState, useEffect } from 'react'
import { getEnterprises, createEnterprise, updateEnterprise, createAdminGrant, getAdminUsers } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../hooks/useToast'
import type { Enterprise, AdminUser } from '../../types/auth'

export function EnterpriseTab() {
  const { user } = useAuth()
  const { show } = useToast()
  const [enterprises, setEnterprises] = useState<Enterprise[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const [renewModal, setRenewModal] = useState<{
    enterprise: Enterprise
    userId: number | null
    durationDays: number
    unassignedUsers: AdminUser[]
  } | null>(null)

  if (user?.role !== 'super_admin') {
    return null
  }

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

  const openRenewModal = async (enterprise: Enterprise) => {
    try {
      // Fetch unassigned users (no enterprise) as candidates for admin role
      const data = await getAdminUsers()
      const unassigned = data.users.filter(
        u => (u.enterprise_id === null || u.enterprise_id === enterprise.id) && u.role !== 'super_admin'
      )
      setRenewModal({ enterprise, userId: null, durationDays: 365, unassignedUsers: unassigned })
    } catch {
      setRenewModal({ enterprise, userId: null, durationDays: 365, unassignedUsers: [] })
    }
  }

  const handleRenew = async () => {
    if (!renewModal) return
    const { enterprise, userId, durationDays } = renewModal
    if (!userId) {
      show('请选择用户', 'error')
      return
    }
    if (!durationDays || durationDays <= 0) {
      show('请输入有效天数', 'error')
      return
    }
    try {
      await createAdminGrant(userId, enterprise.id, durationDays)
      show('管理员续期成功', 'success')
      setRenewModal(null)
      await fetchEnterprises()
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
          className="theme-form-field block w-72 rounded-lg px-3 py-2 text-sm transition"
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
        <table className="data-table">
          <thead>
            <tr>
              <th>企业名称</th>
              <th>用户数</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>加载中...</td>
              </tr>
            ) : enterprises.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>暂无企业</td>
              </tr>
            ) : (
              enterprises.map(ent => (
                <tr key={ent.id}>
                  <td>{ent.name}</td>
                  <td>{ent.user_count ?? '-'}</td>
                  <td>
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
                  <td style={{ color: 'var(--text-secondary)' }}>
                    {new Date(ent.created_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="space-x-2">
                    <button
                      onClick={() => handleToggleActive(ent)}
                      className="theme-link-action text-xs font-medium"
                    >
                      {ent.is_active ? '停用' : '启用'}
                    </button>
                    <button
                      onClick={() => openRenewModal(ent)}
                      className="theme-link-action text-xs font-medium"
                    >
                      设置/续期管理员
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
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'var(--modal-overlay)' }} onClick={() => setRenewModal(null)}>
          <div className="theme-modal-shell rounded-lg border p-6 w-full max-w-sm shadow-xl mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              设置/续期管理员 - {renewModal.enterprise.name}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>选择用户</label>
                <select
                  value={renewModal.userId ?? ''}
                  onChange={e =>
                    setRenewModal(prev =>
                      prev ? { ...prev, userId: e.target.value ? Number(e.target.value) : null } : null
                    )
                  }
                  className="theme-form-field block w-full rounded-lg px-3 py-2 text-sm transition"
                >
                  <option value="">-- 选择用户 --</option>
                  {renewModal.unassignedUsers.map(u => (
                    <option key={u.id} value={u.id}>
                      {u.username} (ID: {u.id}) {u.enterprise_name ? `- ${u.enterprise_name}` : '- 未分配'}
                    </option>
                  ))}
                </select>
                {renewModal.unassignedUsers.length === 0 && (
                  <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>暂无可分配的用户</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>续期天数</label>
                <input
                  type="number"
                  value={renewModal.durationDays}
                  onChange={e =>
                    setRenewModal(prev =>
                      prev ? { ...prev, durationDays: Number(e.target.value) } : null
                    )
                  }
                  className="theme-form-field block w-full rounded-lg px-3 py-2 text-sm transition"
                  min={1}
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setRenewModal(null)}
                  className="px-4 py-2 text-sm font-medium transition-colors"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  取消
                </button>
                <button
                  onClick={handleRenew}
                  className="bg-orange-500 hover:bg-orange-600 active:scale-[0.97] text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all"
                >
                  确认续期
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
