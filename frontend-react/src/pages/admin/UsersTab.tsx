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
  const [userScope, setUserScope] = useState<'members' | 'unassigned'>('members')

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editQuota, setEditQuota] = useState(0)
  const [editEnterprise, setEditEnterprise] = useState<number | null>(null)

  const isSuperAdmin = currentUser?.role === 'super_admin'
  const filterLabel = isSuperAdmin ? '企业筛选' : '成员列表'
  const canEditEnterprise = isSuperAdmin

  const fetchData = async () => {
    try {
      setLoading(true)
      const [usersData, enterprisesData] = await Promise.all([
        getAdminUsers(isSuperAdmin ? filterEnt : userScope === 'unassigned' ? { scope: 'unassigned' } : undefined),
        isSuperAdmin ? getEnterprises() : Promise.resolve({ enterprises: [] }),
      ])
      setUsers(usersData.users)
      if (isSuperAdmin) setEnterprises(enterprisesData.enterprises)
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '获取数据失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [filterEnt, isSuperAdmin, userScope])

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
      const updates = {
        quota_total: editQuota,
        ...(canEditEnterprise ? { enterprise_id: editEnterprise } : {}),
      }
      await updateAdminUser(userId, updates)
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

  const claimUser = async (user: AdminUser) => {
    if (!currentUser?.enterprise_id) {
      show('当前管理员尚未分配企业', 'error')
      return
    }
    try {
      await updateAdminUser(user.id, { enterprise_id: currentUser.enterprise_id })
      show('用户已分配到本企业', 'success')
      await fetchData()
    } catch (err: unknown) {
      show(err instanceof Error ? err.message : '分配失败', 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{filterLabel}</label>
        {isSuperAdmin && (
          <select
            value={filterEnt ?? ''}
            onChange={e =>
              setFilterEnt(e.target.value ? Number(e.target.value) : undefined)
            }
            className="theme-form-field rounded-lg px-3 py-2 text-sm transition"
          >
            <option value="">全部企业</option>
            {enterprises.map(ent => (
              <option key={ent.id} value={ent.id}>
                {ent.name}
              </option>
            ))}
          </select>
        )}
        {!isSuperAdmin && (
          <div
            className="inline-flex items-center rounded-lg border p-1"
            style={{ borderColor: 'var(--border)', background: 'var(--surface-panel-subtle)' }}
          >
            <button
              type="button"
              onClick={() => setUserScope('members')}
              className={`min-h-[36px] px-3 text-xs font-medium transition ${userScope === 'members' ? 'theme-surface-chip rounded-md border' : ''}`}
              aria-pressed={userScope === 'members'}
            >
              成员列表
            </button>
            <button
              type="button"
              onClick={() => setUserScope('unassigned')}
              className={`min-h-[36px] px-3 text-xs font-medium transition ${userScope === 'unassigned' ? 'theme-surface-chip rounded-md border' : ''}`}
              aria-pressed={userScope === 'unassigned'}
            >
              未分配用户
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>角色</th>
              <th>企业</th>
              <th>配额</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>加载中...</td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8" style={{ color: 'var(--text-secondary)' }}>暂无用户</td>
              </tr>
            ) : (
              users.map(u => {
                const isEditing = editingId === u.id
                const isSuperAdminUser = u.role === 'super_admin'
                const isUnassignedRow = !isSuperAdmin && userScope === 'unassigned'
                return (
                  <tr key={u.id}>
                    <td>{u.id}</td>
                    <td>{u.username}</td>
                    <td>
                      <span className="theme-surface-chip inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border">
                        {ROLE_LABELS[u.role] || u.role}
                      </span>
                    </td>
                    <td>
                      {isEditing && canEditEnterprise ? (
                        <select
                          value={editEnterprise ?? ''}
                          onChange={e =>
                            setEditEnterprise(
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                          className="theme-form-field rounded px-2 py-1 text-xs"
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
                    <td>
                      {isEditing ? (
                        <input
                          type="number"
                          value={editQuota}
                          onChange={e => setEditQuota(Number(e.target.value))}
                          className="theme-form-field w-24 rounded px-2 py-1 text-xs"
                          min={0}
                        />
                      ) : (
                        <span>
                          {u.quota_used ?? 0}/{u.quota_total ?? 0}
                        </span>
                      )}
                    </td>
                    <td>
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
                    <td className="space-x-2">
                      {isSuperAdminUser ? (
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>不可操作</span>
                      ) : isUnassignedRow ? (
                        <button
                          onClick={() => claimUser(u)}
                          className="theme-link-action text-xs font-medium min-h-[44px]"
                        >
                          分配到本企业
                        </button>
                      ) : isEditing ? (
                        <>
                          <button
                            onClick={() => saveEditing(u.id)}
                            className="theme-link-action text-xs font-medium"
                          >
                            保存
                          </button>
                          <button
                            onClick={cancelEditing}
                            className="text-xs font-medium"
                            style={{ color: 'var(--text-secondary)' }}
                          >
                            取消
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => startEditing(u)}
                            className="theme-link-action text-xs font-medium"
                          >
                            修改配额
                          </button>
                          <button
                            onClick={() => handleToggleActive(u)}
                            className="theme-link-action text-xs font-medium"
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
