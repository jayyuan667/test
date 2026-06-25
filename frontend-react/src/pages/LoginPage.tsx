import { useState, type FormEvent } from 'react'
import { AuthShell } from '../components/auth/AuthShell'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../hooks/useToast'

interface LoginPageProps {
  onNavigate: (page: 'register') => void
  onOpenAuth: () => void
  onReturnHome: () => void
  phase: 'home' | 'auth'
}

export function LoginPage({ onNavigate, onOpenAuth, onReturnHome, phase }: LoginPageProps) {
  const { login } = useAuth()
  const { show } = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!username.trim() || !password) {
      setError('请输入用户名和密码')
      return
    }

    setLoading(true)
    try {
      await login(username.trim(), password)
      show('登录成功', 'success')
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message :
        typeof err === 'object' && err !== null && 'message' in err
          ? String((err as { message: unknown }).message)
          : '登录失败，请检查用户名和密码'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      mode="login"
      phase={phase}
      onOpenAuth={onOpenAuth}
      onReturnHome={onReturnHome}
      title="欢迎登录"
      subtitle="进入图纸检视台，继续你的工艺流程。"
      footer={(
        <p className="text-center text-xs text-slate-400">
          &copy; {new Date().getFullYear()} 二维工艺系统
        </p>
      )}
    >
      <form onSubmit={handleSubmit} className="space-y-5 auth-form">
          {/* Username */}
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1.5">
              用户名
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="block w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
              placeholder="请输入用户名"
              autoComplete="username"
            />
          </div>

          {/* Password */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1.5">
              密码
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="block w-full border border-slate-300 rounded-lg px-3 py-2.5 pr-10 text-sm focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition"
                placeholder="请输入密码"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                tabIndex={-1}
                aria-label={showPassword ? '隐藏密码' : '显示密码'}
              >
                {showPassword ? (
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 text-red-600 text-sm">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-orange-500 hover:bg-orange-600 active:scale-[0.97] text-white px-6 py-2.5 rounded-lg font-semibold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '登录中...' : '登录'}
          </button>

          {/* Register link */}
          <p className="text-center text-sm text-slate-500">
            还没有账号？{' '}
            <button
              type="button"
              onClick={() => onNavigate('register')}
              className="text-orange-500 hover:text-orange-600 font-medium transition-colors"
            >
              立即注册
            </button>
          </p>
      </form>
    </AuthShell>
  )
}
