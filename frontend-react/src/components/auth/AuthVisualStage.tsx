import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

export function AuthVisualStage({ mode, phase }: { mode: 'login' | 'register'; phase: 'home' | 'auth' }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const reduceMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (!rootRef.current || reduceMotion) return

    const ctx = gsap.context(() => {
      gsap.to('.auth-stage-orbit-ring', {
        rotate: 360,
        transformOrigin: '50% 50%',
        duration: 24,
        repeat: -1,
        ease: 'none',
      })

      gsap.to('.auth-stage-node-path', {
        y: mode === 'login' ? -4 : 4,
        duration: 3.6,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      })
    }, rootRef)

    return () => ctx.revert()
  }, [mode, reduceMotion])

  return (
    <div
      ref={rootRef}
      data-testid="auth-visual-stage"
      className={`auth-stage-globe${phase === 'auth' ? ' is-muted' : ''}`}
      aria-hidden="true"
    >
      <div className="auth-stage-orbit" />
      <div className="auth-stage-orbit auth-stage-orbit-vertical" />
      <div className="auth-stage-orbit auth-stage-orbit-horizontal" />
      <div className="auth-stage-orbit-ring" />
      <svg className="auth-stage-node-path" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M235 160L192 255L292 332L380 210L458 282" stroke="currentColor" strokeWidth="1.2" />
        <path d="M292 332L382 404L458 346" stroke="currentColor" strokeWidth="1.2" />
        <path d="M235 160L292 332L210 454" stroke="currentColor" strokeWidth="1.1" opacity="0.72" />
        <circle cx="192" cy="255" r="7" fill="#68B5E8" stroke="rgba(15,23,42,0.26)" strokeWidth="1" />
        <circle cx="292" cy="332" r="7" fill="#7ECB7F" stroke="rgba(15,23,42,0.26)" strokeWidth="1" />
        <circle cx="380" cy="210" r="7" fill="#E7A76A" stroke="rgba(15,23,42,0.26)" strokeWidth="1" />
        <circle cx="458" cy="282" r="3" fill="#D8DBE0" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
        <circle cx="458" cy="346" r="3" fill="#D8DBE0" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
        <circle cx="235" cy="160" r="3" fill="#D8DBE0" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
        <circle cx="210" cy="454" r="6" fill="#EDEDED" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
      </svg>
    </div>
  )
}
