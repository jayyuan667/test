import { useEffect, useState } from 'react'

/**
 * Returns `true` when the user has enabled "reduce motion" in their OS settings.
 *
 * Usage — gate GSAP animations:
 *   const reduceMotion = usePrefersReducedMotion()
 *   useEffect(() => {
 *     if (reduceMotion) { gsap.set(el, { opacity: 1, y: 0 }); return }
 *     gsap.fromTo(el, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.35 })
 *   }, [reduceMotion])
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  useEffect(() => {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  return reduced
}
