import { useEffect, useRef, type ReactNode } from 'react'
import gsap from 'gsap'
import { AuthVisualStage } from './AuthVisualStage'

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

export function AuthShell({
  mode,
  phase,
  onOpenAuth,
  onReturnHome,
  title,
  subtitle,
  footer,
  children,
}: AuthShellProps) {
  const copyRef = useRef<HTMLElement>(null)
  const cursorBlobRef = useRef<HTMLDivElement>(null)
  const blobXRef = useRef<((value: number) => void) | null>(null)
  const blobYRef = useRef<((value: number) => void) | null>(null)
  const blobScaleRef = useRef<((value: number) => void) | null>(null)
  const blobOpacityRef = useRef<((value: number) => void) | null>(null)

  useEffect(() => {
    if (!cursorBlobRef.current) return

    const blob = cursorBlobRef.current

    gsap.set(blob, {
      x: 0,
      y: 0,
      scale: 0.78,
      opacity: 0,
      xPercent: -50,
      yPercent: -50,
    })

    blobXRef.current = gsap.quickTo(blob, 'x', {
      duration: 0.48,
      ease: 'power4.out',
    })
    blobYRef.current = gsap.quickTo(blob, 'y', {
      duration: 0.48,
      ease: 'power4.out',
    })
    blobScaleRef.current = gsap.quickTo(blob, 'scale', {
      duration: 0.36,
      ease: 'power3.out',
    })
    blobOpacityRef.current = gsap.quickTo(blob, 'opacity', {
      duration: 0.32,
      ease: 'power2.out',
    })
  }, [])

  const handleCopyPointerEnter = (event: React.PointerEvent<HTMLElement>) => {
    event.currentTarget.dataset.active = 'true'
    blobOpacityRef.current?.(0.94)
    blobScaleRef.current?.(0.96)
  }

  const handleCopyPointerMove = (event: React.PointerEvent<HTMLElement>) => {
    blobXRef.current?.(event.clientX)
    blobYRef.current?.(event.clientY)
    blobScaleRef.current?.(0.96)
    blobOpacityRef.current?.(0.94)
  }

  const resetCopyPointer = (event: React.PointerEvent<HTMLElement>) => {
    event.currentTarget.dataset.active = 'false'
    blobScaleRef.current?.(0.78)
    blobOpacityRef.current?.(0)
  }

  return (
    <div className="auth-entry-shell" data-phase={phase}>
      <div ref={cursorBlobRef} className="auth-entry-cursor-blob" aria-hidden="true" />
      <header className="auth-entry-topbar">
        <div className="auth-entry-brand">
          <img src="/dica-logo.png" alt="DICA" className="h-7 w-auto" />
          <span>智能工艺系统</span>
        </div>

        <nav className="auth-entry-nav" aria-label="认证入口导航">
          <button type="button" className="auth-entry-nav-item">图纸</button>
          <button type="button" className="auth-entry-nav-item">工艺</button>
          <button type="button" className="auth-entry-nav-item">动态</button>
          <button type="button" className="auth-entry-nav-item">联系我们</button>
          <button type="button" className="auth-entry-nav-item">中文</button>
          <button type="button" className="auth-entry-cta" onClick={onOpenAuth}>
            进入系统
          </button>
        </nav>
      </header>

      <main className="auth-entry-main">
        <section
          ref={copyRef}
          className="auth-entry-copy"
          data-active="false"
          onPointerEnter={handleCopyPointerEnter}
          onPointerMove={handleCopyPointerMove}
          onPointerLeave={resetCopyPointer}
        >
          <h1 className="auth-entry-title">DICA</h1>
          <p className="auth-entry-subtitle">聚焦当前图纸，进入工艺编制与检视控制台。</p>
        </section>

        <section className="auth-entry-visual-wrap">
          <AuthVisualStage mode={mode} phase={phase} />

          <div className={`auth-entry-panel${phase === 'auth' ? ' is-open' : ''}`}>
            <div className="auth-entry-panel-header">
              <div>
                <h2 className="auth-entry-panel-title">{title}</h2>
                <p className="auth-entry-panel-text">{subtitle}</p>
              </div>
              <button
                type="button"
                className="auth-entry-panel-close"
                onClick={onReturnHome}
                aria-label="返回首页"
              >
                返回首页
              </button>
            </div>

            <div className="auth-entry-panel-body">{children}</div>
            <div className="auth-entry-panel-footer">{footer}</div>
          </div>
        </section>
      </main>
    </div>
  )
}
