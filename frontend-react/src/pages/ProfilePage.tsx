import { useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { changePassword } from '../api/client'
import { useToast } from '../hooks/useToast'
import { UNASSIGNED_ENTERPRISE_LABEL } from '../types/auth'

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  enterprise_admin: '企业管理员',
  user: '普通用户',
}

export function ProfilePage() {
  const { user } = useAuth()
  const { show } = useToast()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changing, setChanging] = useState(false)

  const handlePasswordChange = async (e: FormEvent) => {
    e.preventDefault()

    if (!currentPassword || !newPassword || !confirmPassword) {
      show('请填写所有密码字段', 'error')
      return
    }
    if (newPassword.length < 6) {
      show('新密码至少需要 6 个字符', 'error')
      return
    }
    if (newPassword !== confirmPassword) {
      show('两次输入的新密码不一致', 'error')
      return
    }

    setChanging(true)
    try {
      await changePassword(currentPassword, newPassword)
      show('密码修改成功', 'success')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '密码修改失败'
      show(message, 'error')
    } finally {
      setChanging(false)
    }
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-8 space-y-6">
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>请先登录</p>
      </div>
    )
  }

  const quota = user.quota
  const quotaTotal = quota?.total_granted ?? 0
  const quotaUsed = quota?.used ?? 0
  const quotaRemaining = quota?.remaining ?? 0
  const quotaPercent = quotaTotal > 0 ? Math.round((quotaRemaining / quotaTotal) * 100) : 0
  const isLowQuota = quotaPercent < 20
  const statusHint = user.role === 'enterprise_admin'
    ? '你当前负责本企业运营治理。'
    : user.role === 'super_admin'
      ? '你当前拥有平台治理权限。'
      : user.enterprise_id == null
        ? '当前账号尚未分配企业，业务能力受限。'
        : '当前账号可执行工艺业务任务。'
  const statusDetail = user.role === 'enterprise_admin'
    ? user.grant_expires_at
      ? `企业授权有效期持续到 ${new Date(user.grant_expires_at).toLocaleDateString('zh-CN')}。`
      : '请持续关注本企业成员配额与授权状态。'
    : user.role === 'super_admin'
      ? '可统筹企业、用户与平台级配额策略。'
      : user.enterprise_id == null
        ? '请联系管理员完成企业分配后再执行工艺任务。'
        : '可继续处理工艺生成、入库与历史回看。'

  const infoRows = [
    { label: '用户名', value: user.username },
    { label: '角色', value: ROLE_LABELS[user.role] || user.role },
    { label: '所属企业', value: user.enterprise_name || UNASSIGNED_ENTERPRISE_LABEL },
    {
      label: '账户状态',
      value: user.is_active ? '正常' : '已停用',
      color: user.is_active ? 'text-emerald-600' : 'text-red-600',
    },
    ...(user.role === 'enterprise_admin' && user.grant_expires_at
      ? [{
          label: '授权到期',
          value: new Date(user.grant_expires_at).toLocaleDateString('zh-CN'),
        }]
      : []),
  ]

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-6">
      {/* Account Info Card */}
      <div className="theme-surface-panel border rounded-lg p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--text-secondary)' }}>
          账户信息
        </h2>
        <div className="mb-4 rounded-lg border px-4 py-3" style={{ borderColor: 'var(--border)', background: 'var(--surface-panel-subtle)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{statusHint}</p>
          <p className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>{statusDetail}</p>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
          {infoRows.map((row) => (
            <div key={row.label} className="contents">
              <dt className="whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>{row.label}</dt>
              <dd className={row.color || ''} style={{ color: row.color ? undefined : 'var(--text-primary)' }}>{row.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Quota Card */}
      <div className="theme-surface-panel border rounded-lg p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--text-secondary)' }}>
          使用配额
        </h2>
        <div className="flex items-baseline gap-1 mb-3">
          <span className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {quotaRemaining}
          </span>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            / {quotaTotal}
          </span>
        </div>
        <div className="h-2.5 rounded-full overflow-hidden mb-2" style={{ background: 'var(--surface-panel-subtle)' }}>
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              isLowQuota
                ? 'bg-gradient-to-r from-red-400 to-red-500'
                : 'bg-gradient-to-r from-orange-400 to-orange-500'
            }`}
            style={{ width: `${quotaPercent}%` }}
          />
        </div>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          已使用 {quotaUsed} 次
        </p>
      </div>

      {/* Password Change Card */}
      <div className="theme-surface-panel border rounded-lg p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--text-secondary)' }}>
          修改密码
        </h2>
        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div>
            <label htmlFor="current-password" className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
              当前密码
            </label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              className="theme-form-field block w-full rounded-lg px-3 py-2 text-sm transition"
              autoComplete="current-password"
            />
          </div>
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
              新密码
            </label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              className="theme-form-field block w-full rounded-lg px-3 py-2 text-sm transition"
              autoComplete="new-password"
            />
          </div>
          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
              确认新密码
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="theme-form-field block w-full rounded-lg px-3 py-2 text-sm transition"
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            disabled={changing}
            className="bg-orange-500 hover:bg-orange-600 active:scale-[0.97] text-white px-6 py-2 rounded-lg font-semibold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {changing ? '修改中...' : '修改密码'}
          </button>
        </form>
      </div>
    </div>
  )
}
