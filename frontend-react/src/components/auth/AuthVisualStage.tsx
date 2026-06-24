import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

export function AuthVisualStage({ mode }: { mode: 'login' | 'register' }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const reduceMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (!rootRef.current || reduceMotion) return

    const ctx = gsap.context(() => {
      gsap.fromTo('.auth-stage-beam', { opacity: 0.45 }, { opacity: 0.7, duration: 2.2, repeat: -1, yoyo: true, ease: 'sine.inOut' })
      gsap.fromTo('.auth-stage-sheet', { y: 0 }, { y: mode === 'login' ? -6 : -4, duration: 3, repeat: -1, yoyo: true, ease: 'sine.inOut' })
      gsap.fromTo('.auth-stage-scan', { xPercent: -20, opacity: 0.18 }, { xPercent: 20, opacity: 0.3, duration: 2.6, repeat: -1, yoyo: true, ease: 'sine.inOut' })
    }, rootRef)

    return () => ctx.revert()
  }, [mode, reduceMotion])

  return (
    <div ref={rootRef} data-testid="auth-visual-stage" className="auth-stage" aria-hidden="true">
      <div className="auth-stage-beam" />
      <div className="auth-stage-grid" />
      <div className="auth-stage-sheet" />
      <div className="auth-stage-sheet auth-stage-sheet-secondary" />
      <div className="auth-stage-hud" />
      <div className="auth-stage-scan" />
    </div>
  )
}
