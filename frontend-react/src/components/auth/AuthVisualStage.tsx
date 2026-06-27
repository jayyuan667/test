import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

export function AuthVisualStage({ mode, phase }: { mode: 'login' | 'register'; phase: 'home' | 'auth' }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const reduceMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (!rootRef.current || reduceMotion) return

    const ctx = gsap.context(() => {
      gsap.to('.auth-stage-tilt-ring', {
        rotate: 360,
        transformOrigin: '50% 50%',
        duration: 34,
        repeat: -1,
        ease: 'none',
      })

      gsap.to('.auth-stage-lat-ring', {
        rotate: -360,
        transformOrigin: '50% 50%',
        duration: 56,
        repeat: -1,
        ease: 'none',
      })

      gsap.to('.auth-stage-continent-layer', {
        xPercent: -10,
        duration: 18,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      })

      gsap.to('.auth-stage-node-group', {
        y: mode === 'login' ? -5 : 5,
        duration: 3.8,
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
      <div className="auth-stage-sphere" />
      <div className="auth-stage-continent-layer auth-stage-continent-a" />
      <div className="auth-stage-continent-layer auth-stage-continent-b" />
      <div className="auth-stage-continent-layer auth-stage-continent-c" />
      <div className="auth-stage-meridian auth-stage-meridian-a" />
      <div className="auth-stage-meridian auth-stage-meridian-b" />
      <div className="auth-stage-lat-ring" />
      <div className="auth-stage-tilt-ring" />

      <svg className="auth-stage-node-group" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M240 170L196 255L300 334L388 214L468 286" stroke="currentColor" strokeWidth="1.15" />
        <path d="M300 334L390 406L468 346" stroke="currentColor" strokeWidth="1.15" />
        <path d="M240 170L300 334L214 456" stroke="currentColor" strokeWidth="1.05" opacity="0.72" />
        <circle cx="196" cy="255" r="7" fill="#68B5E8" stroke="rgba(15,23,42,0.22)" strokeWidth="1" />
        <circle cx="300" cy="334" r="7" fill="#7ECB7F" stroke="rgba(15,23,42,0.22)" strokeWidth="1" />
        <circle cx="388" cy="214" r="7" fill="#E7A76A" stroke="rgba(15,23,42,0.22)" strokeWidth="1" />
        <circle cx="468" cy="286" r="3" fill="#D8DBE0" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
        <circle cx="468" cy="346" r="3" fill="#D8DBE0" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
        <circle cx="240" cy="170" r="3" fill="#D8DBE0" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
        <circle cx="214" cy="456" r="6" fill="#EDEDED" stroke="rgba(15,23,42,0.2)" strokeWidth="1" />
      </svg>
    </div>
  )
}
