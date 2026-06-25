import type { ReactNode } from 'react'

interface AuthShellProps {
  mode: 'login' | 'register'
  phase: 'home' | 'auth'
  onOpenAuth: () => void
  onReturnHome: () => void
  title: string
  subtitle: string
  footer: ReactNode
  children: ReactNode
}

export function AuthShell({ phase, title, subtitle, footer, children }: AuthShellProps) {
  if (phase !== 'auth') return null

  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div
            className="w-14 h-14 rounded-2xl mx-auto mb-4 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%)',
              boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3), inset 0 1px 0 rgba(255,255,255,0.2)',
            }}
          >
            <div className="absolute inset-0" style={{
              background: 'radial-gradient(circle at 30% 25%, rgba(255,255,255,0.25) 0%, transparent 50%)',
            }} />
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-wide">{title}</h1>
          <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-6">
          {children}
        </div>

        {footer}
      </div>
    </div>
  )
}
