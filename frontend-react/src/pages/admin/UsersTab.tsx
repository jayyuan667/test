import { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { getAdminUsers, updateAdminUser, getEnterprises } from '../../api/client'
import { useToast } from '../../hooks/useToast'
import type { AdminUser, Enterprise } from '../../types/auth'

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  enterprise_admin: '企业管理员',
  user: '普通用户',
}

export function UsersTab() {
  const { user: currentUser } = useAuth()
  const { show } = useToast()

  const [users, setUsers] = useState<AdminUser[]>([])
  const [enterprises, setEnterprises] = useState<Enterprise[]>([])
  const [loading, setLoading] = useState(true)
  const [filterEnt, setFilterEnt] = useState<number | undefined>(undefined)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editQuota, setEditQuota] = useState(0)
  const [editEnterprise, setEditEnterprise] = useState<number | null>(null)

  const isSuperAdmin = currentUser?.role === 'super_admin'

  const fetchData = async () => {
    try {
      setLoading(true)
      const [usersData, enterprisesData] = await Promise.all([
        getAdminUsers(filterEnt),
        isSuperAdmin ? getEnterprises() : Promise.resolve([]),
      ])
      setUsers(usersData)
      if (isSuperAdmin) setEnterprises(enterprisesData)
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '获取数据失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [filterEnt])

  const startEditing = (user: AdminUser) => {
    setEditingId(user.id)
    setEditQuota(user.quota_total ?? 0)
    setEditEnterprise(user.enterprise_id)
  }

  const cancelEditing = () => {
    setEditingId(null)
  }

  const saveEditing = async (userId: number) => {
    try {
      await updateAdminUser(userId, {
        quota_total: editQuota,
        enterprise_id: editEnterprise,
      })
      show('用户信息更新成功', 'success')
      setEditingId(null)
      await fetchData()
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '更新失败', 'error')
    }
  }

  const handleToggleActive = async (user: AdminUser) => {
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active })
      show(user.is_active ? '用户已停用' : '用户已启用', 'success')
      await fetchData()
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '操作失败', 'error')
    }
  }

  return (
    <div className="space-y-4">
      {/* Enterprise filter for super_admin */}
      {isSuperAdmin && (
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-600 font-medium">企业筛选：</label>
          <select
            value={filterEnt ?? ''}
            onChange={e =>
              setFilterEnt(e.target.value ? Number(e.target.value) : undefined)
            }
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
          >
            <option value="">全部企业</option>
            {enterprises.map(ent => (
              <option key={ent.id} value={ent.id}>
                {ent.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">ID</th>
              <th className="text-left px-4 py-3 font-medium">用户名</th>
              <th className="text-left px-4 py-3 font-medium">角色</th>
              <th className="text-left px-4 py-3 font-medium">企业</th>
              <th className="text-left px-4 py-3 font-medium">配额</th>
              <th className="text-left px-4 py-3 font-medium">状态</th>
              <th className="text-left px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-slate-500">加载中...</td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-slate-500">暂无用户</td>
              </tr>
            ) : (
              users.map(u => {
                const isEditing = editingId === u.id
                const isSuperAdminUser = u.role === 'super_admin'
                return (
                  <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3">{u.id}</td>
                    <td className="px-4 py-3">{u.username}</td>
                    <td className="px-4 py-3">
                      <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                        {ROLE_LABELS[u.role] || u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isEditing && isSuperAdmin ? (
                        <select
                          value={editEnterprise ?? ''}
                          onChange={e =>
                            setEditEnterprise(
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                          className="border border-slate-300 rounded px-2 py-1 text-xs focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                        >
                          <option value="">无</option>
                          {enterprises.map(ent => (
                            <option key={ent.id} value={ent.id}>
                              {ent.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        u.enterprise_name || '-'
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {isEditing ? (
                        <input
                          type="number"
                          value={editQuota}
                          onChange={e => setEditQuota(Number(e.target.value))}
                          className="w-24 border border-slate-300 rounded px-2 py-1 text-xs focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none"
                          min={0}
                        />
                      ) : (
                        <span>
                          {u.quota_used ?? 0}/{u.quota_total ?? 0}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          u.is_active
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-red-50 text-red-700'
                        }`}
                      >
                        {u.is_active ? '正常' : '已停用'}
                      </span>
                    </td>
                    <td className="px-4 py-3 space-x-2">
                      {isSuperAdminUser ? (
                        <span className="text-xs text-slate-400">不可操作</span>
                      ) : isEditing ? (
                        <>
                          <button
                            onClick={() => saveEditing(u.id)}
                            className="text-orange-600 hover:text-orange-800 text-xs font-medium"
                          >
                            保存
                          </button>
                          <button
                            onClick={cancelEditing}
                            className="text-slate-500 hover:text-slate-700 text-xs font-medium"
                          >
                            取消
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => startEditing(u)}
                            className="text-orange-600 hover:text-orange-800 text-xs font-medium"
                          >
                            修改配额
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            className="text-orange-600 hover:text-orange-800 text-xs font-medium"
                          >
                            {u.is_active ? '停用' : '启用'}
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
