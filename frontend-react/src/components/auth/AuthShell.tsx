import type { ReactNode } from 'react'
import { AuthVisualStage } from './AuthVisualStage'

interface AuthShellProps {
  mode: 'login' | 'register'
  title: string
  subtitle: string
  footer: ReactNode
  children: ReactNode
}

export function AuthShell({ mode, title, subtitle, footer, children }: AuthShellProps) {
  return (
    <div className="auth-shell">
      <section className="auth-panel-wrap">
        <div className="auth-panel">
          <div className="auth-brand">
            <div className="auth-brand-mark" />
            <div>
              <p className="auth-kicker">二维工艺系统</p>
              <h1 className="auth-title">{title}</h1>
              <p className="auth-subtitle">{subtitle}</p>
            </div>
          </div>
          {children}
          <div className="auth-footer">{footer}</div>
        </div>
      </section>
      <section className="auth-stage-wrap">
        <div className="auth-stage-copy">
          <p className="auth-stage-label">图纸解析与工艺编制控制台</p>
          <p className="auth-stage-text">聚焦当前图纸，保持任务链路清晰、稳定、可追溯。</p>
        </div>
        <AuthVisualStage mode={mode} />
      </section>
    </div>
  )
}
