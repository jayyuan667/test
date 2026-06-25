import { useState } from 'react'
import { LoginPage } from '../../pages/LoginPage'
import { RegisterPage } from '../../pages/RegisterPage'

export function AuthEntryScene() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [phase, setPhase] = useState<'home' | 'auth'>('home')

  if (phase === 'home') {
    return (
      <div className="min-h-[100dvh] flex flex-col items-center justify-center bg-slate-50 px-4">
        {/* Brand */}
        <div className="text-center mb-10">
          <div
            className="w-20 h-20 rounded-2xl mx-auto mb-6 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%)',
              boxShadow: '0 8px 24px rgba(249, 115, 22, 0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
            }}
          >
            <div className="absolute inset-0" style={{
              background: 'radial-gradient(circle at 30% 25%, rgba(255,255,255,0.25) 0%, transparent 50%)',
            }} />
          </div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-wide">DiMo</h1>
          <p className="text-sm text-slate-500 mt-2">二维工艺系统 · 图纸解析与工艺编制控制台</p>
        </div>

        {/* Entry CTA */}
        <button
          onClick={() => setPhase('auth')}
          className="bg-orange-500 hover:bg-orange-600 active:scale-[0.97] text-white px-8 py-3 rounded-lg font-semibold text-base transition-all duration-150 shadow-lg shadow-orange-500/20"
        >
          进入系统
        </button>

        <p className="text-center text-xs text-slate-400 mt-12">
          Copyright &copy; 机器学习与工业智能应用教育部工程研究中心
        </p>
      </div>
    )
  }

  // Auth phase — render login or register
  if (mode === 'login') {
    return (
      <LoginPage
        onNavigate={setMode}
        onOpenAuth={() => setPhase('auth')}
        onReturnHome={() => setPhase('home')}
        phase={phase}
      />
    )
  }

  return (
    <RegisterPage
      onNavigate={setMode}
      onOpenAuth={() => setPhase('auth')}
      onReturnHome={() => setPhase('home')}
      phase={phase}
    />
  )
}
