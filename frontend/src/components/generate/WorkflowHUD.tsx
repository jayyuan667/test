import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import gsap from 'gsap'

interface Props {
  progress: number
  phaseHint: string
  busy: boolean
  completed: boolean
  waiting?: boolean
}

/* ── Animation params derived from display progress (0-100) ── */
function useBreathingParams(pct: number, busy: boolean, completed: boolean, waiting?: boolean) {
  return useMemo(() => {
    if (completed) {
      return {
        dotDuration: 2.2, dotScaleMax: 1.12, dotScaleMin: 1.0,
        dotOpacityMax: 1, dotOpacityMin: 0.75,
        glowOpacityMax: 0.35, glowOpacityMin: 0.15,
        cardGlowStrength: 0.08, shimmerSpeed: 0,
      }
    }
    if (waiting) {
      return {
        dotDuration: 2.0, dotScaleMax: 1.2, dotScaleMin: 0.95,
        dotOpacityMax: 0.9, dotOpacityMin: 0.5,
        glowOpacityMax: 0.25, glowOpacityMin: 0.1,
        cardGlowStrength: 0.06, shimmerSpeed: 0,
      }
    }
    if (!busy) {
      return {
        dotDuration: 3, dotScaleMax: 1.06, dotScaleMin: 1.0,
        dotOpacityMax: 0.7, dotOpacityMin: 0.5,
        glowOpacityMax: 0, glowOpacityMin: 0,
        cardGlowStrength: 0, shimmerSpeed: 0,
      }
    }
    const p = Math.max(0, Math.min(100, pct)) / 100
    return {
      dotDuration:       2.6 - p * 1.8,
      dotScaleMax:       1.12 + p * 0.28,
      dotScaleMin:       1.0  - p * 0.15,
      dotOpacityMax:     0.8  + p * 0.2,
      dotOpacityMin:     0.5  + p * 0.1,
      glowOpacityMax:    0.15 + p * 0.4,
      glowOpacityMin:    0.05 + p * 0.12,
      cardGlowStrength:  0.03 + p * 0.1,
      shimmerSpeed:      2.8  - p * 1.6,
    }
  }, [pct, busy, completed, waiting])
}

export function WorkflowHUD({ progress, phaseHint, busy, completed, waiting }: Props) {
  const [collapsed, setCollapsed] = useState(false)
  const [displayPct, setDisplayPct] = useState(0)

  const progressBarRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const dotRef = useRef<HTMLSpanElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const phaseRef = useRef<HTMLDivElement>(null)
  const glowRef = useRef<HTMLDivElement>(null)
  const shimmerRef = useRef<HTMLDivElement>(null)
  const phaseDotRef = useRef<HTMLSpanElement>(null)

  const breathingTl = useRef<gsap.core.Timeline | null>(null)
  const phaseBreathingTl = useRef<gsap.core.Timeline | null>(null)
  const cardBreathingTl = useRef<gsap.core.Timeline | null>(null)
  const glowBreathingTl = useRef<gsap.core.Timeline | null>(null)
  const shimmerTl = useRef<gsap.core.Timeline | null>(null)

  // ── Single tween drives BOTH bar width AND percentage state ──
  const tweenObj = useRef({ value: 0 })
  const prevTarget = useRef(0)
  const stallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const crawlRef = useRef<gsap.core.Tween | null>(null)
  const isCrawlingRef = useRef(false)

  useEffect(() => {
    const bar = progressBarRef.current
    const gap = Math.abs(progress - prevTarget.current)
    prevTarget.current = progress

    // Kill any active crawl — real progress arrived
    if (crawlRef.current) {
      crawlRef.current.kill()
      crawlRef.current = null
      isCrawlingRef.current = false
    }
    if (stallTimerRef.current) {
      clearTimeout(stallTimerRef.current)
      stallTimerRef.current = null
    }

    const duration = Math.max(0.5, gap * 0.06)

    gsap.killTweensOf(tweenObj.current)
    gsap.to(tweenObj.current, {
      value: progress,
      duration,
      ease: 'power1.out',
      onUpdate() {
        const v = tweenObj.current.value
        if (bar) bar.style.width = `${Math.max(v, 2)}%`
        // Show 1 decimal while crawling, integer otherwise
        setDisplayPct(isCrawlingRef.current ? Math.round(v * 10) / 10 : Math.round(v))
      },
      onComplete() {
        if (busyRef.current && !completedRef.current) {
          stallTimerRef.current = setTimeout(() => startCrawl(), 1500)
        }
      },
    })

    return () => {
      gsap.killTweensOf(tweenObj.current)
      if (stallTimerRef.current) clearTimeout(stallTimerRef.current)
      crawlRef.current?.kill()
    }
  }, [progress])

  const busyRef = useRef(busy)
  const completedRef = useRef(completed)
  useEffect(() => { busyRef.current = busy }, [busy])
  useEffect(() => { completedRef.current = completed }, [completed])

  const startCrawl = useCallback(() => {
    if (crawlRef.current?.isActive()) return
    if (!busyRef.current || completedRef.current) return
    const current = tweenObj.current.value
    const cap = Math.min(current + 3, 95)
    if (current >= cap) return
    isCrawlingRef.current = true
    crawlRef.current = gsap.to(tweenObj.current, {
      value: cap,
      duration: 6,
      ease: 'none',
      onUpdate() {
        const v = tweenObj.current.value
        if (progressBarRef.current) progressBarRef.current.style.width = `${Math.max(v, 2)}%`
        setDisplayPct(Math.round(v * 10) / 10)
      },
      onComplete() { isCrawlingRef.current = false },
    })
  }, [])

  useEffect(() => {
    if (!busy) {
      crawlRef.current?.kill()
      crawlRef.current = null
      isCrawlingRef.current = false
      if (stallTimerRef.current) {
        clearTimeout(stallTimerRef.current)
        stallTimerRef.current = null
      }
    }
  }, [busy])

  const params = useBreathingParams(displayPct, busy, completed, waiting)

  // GSAP: Breathing dot
  useEffect(() => {
    const dot = dotRef.current
    if (!dot) return
    breathingTl.current?.kill()
    breathingTl.current = gsap.timeline({ repeat: -1, yoyo: true })
      .to(dot, { scale: params.dotScaleMax, opacity: params.dotOpacityMax, duration: params.dotDuration, ease: 'sine.inOut' })
      .to(dot, { scale: params.dotScaleMin, opacity: params.dotOpacityMin, duration: params.dotDuration, ease: 'sine.inOut' })
    return () => { breathingTl.current?.kill() }
  }, [params])

  // GSAP: Phase dot breathing
  useEffect(() => {
    const pdot = phaseDotRef.current
    if (!pdot) return
    phaseBreathingTl.current?.kill()
    if (busy || completed || waiting) {
      phaseBreathingTl.current = gsap.timeline({ repeat: -1, yoyo: true })
        .to(pdot, { scale: params.dotScaleMax * 0.9, opacity: params.dotOpacityMax, duration: params.dotDuration, ease: 'sine.inOut' })
        .to(pdot, { scale: params.dotScaleMin, opacity: params.dotOpacityMin * 0.8, duration: params.dotDuration, ease: 'sine.inOut' })
      return () => { phaseBreathingTl.current?.kill() }
    } else {
      gsap.set(pdot, { scale: 1, opacity: 1 })
    }
  }, [params, busy, completed, waiting])

  // GSAP: Card glow
  useEffect(() => {
    const card = cardRef.current
    if (!card) return
    cardBreathingTl.current?.kill()
    if (busy) {
      const s = params.cardGlowStrength
      cardBreathingTl.current = gsap.timeline({ repeat: -1, yoyo: true })
        .to(card, {
          boxShadow: `0 0 0 1px rgba(249,115,22,${(s + 0.05).toFixed(2)}), 0 4px 16px rgba(249,115,22,${s.toFixed(2)}), 0 12px 32px rgba(249,115,22,${(s * 0.5).toFixed(2)})`,
          duration: params.dotDuration * 1.3, ease: 'sine.inOut',
        })
      return () => { cardBreathingTl.current?.kill() }
    } else if (waiting) {
      cardBreathingTl.current = gsap.timeline({ repeat: -1, yoyo: true })
        .to(card, { boxShadow: '0 0 0 1px rgba(245,158,11,0.12), 0 4px 16px rgba(245,158,11,0.06), 0 12px 32px rgba(245,158,11,0.03)', duration: 2.5, ease: 'sine.inOut' })
      return () => { cardBreathingTl.current?.kill() }
    } else if (completed) {
      cardBreathingTl.current = gsap.timeline({ repeat: -1, yoyo: true })
        .to(card, { boxShadow: '0 0 0 1px rgba(16,185,129,0.12), 0 4px 16px rgba(16,185,129,0.06), 0 12px 32px rgba(16,185,129,0.03)', duration: 3, ease: 'sine.inOut' })
      return () => { cardBreathingTl.current?.kill() }
    } else {
      gsap.set(card, { boxShadow: '' })
    }
  }, [params, busy, completed, waiting])

  // GSAP: Glow ring
  useEffect(() => {
    const glow = glowRef.current
    if (!glow) return
    glowBreathingTl.current?.kill()
    if (busy || waiting) {
      glowBreathingTl.current = gsap.timeline({ repeat: -1, yoyo: true })
        .to(glow, { opacity: params.glowOpacityMax, scale: 1.01, duration: params.dotDuration * 1.1, ease: 'sine.inOut' })
        .to(glow, { opacity: params.glowOpacityMin, scale: 0.99, duration: params.dotDuration * 1.1, ease: 'sine.inOut' })
      return () => { glowBreathingTl.current?.kill() }
    } else {
      gsap.to(glow, { opacity: 0, duration: 0.5 })
    }
  }, [params, busy, waiting])

  // GSAP: Shimmer (guard against needless recreation)
  const shimmerStateRef = useRef({ busy: false, speed: 0 })
  useEffect(() => {
    const shimmer = shimmerRef.current
    if (!shimmer) return
    const prev = shimmerStateRef.current
    if (prev.busy === busy && prev.speed === params.shimmerSpeed) return
    prev.busy = busy
    prev.speed = params.shimmerSpeed
    shimmerTl.current?.kill()
    if (busy && params.shimmerSpeed > 0) {
      shimmerTl.current = gsap.timeline({ repeat: -1 })
        .fromTo(shimmer, { x: '-100%', opacity: 0.15 }, { x: '200%', opacity: 0.45, duration: params.shimmerSpeed, ease: 'power1.inOut' })
        .to(shimmer, { opacity: 0.15, duration: 0.3 })
      return () => { shimmerTl.current?.kill() }
    }
  }, [busy, params.shimmerSpeed])

  // GSAP: Phase hint text transition
  useEffect(() => {
    if (phaseRef.current) {
      gsap.fromTo(phaseRef.current, { opacity: 0, y: 4 }, { opacity: 1, y: 0, duration: 0.35, ease: 'power2.out' })
    }
  }, [phaseHint])

  // GSAP: Counter pop when phaseHint count changes
  const lastCountRef = useRef<number | null>(null)
  useEffect(() => {
    const match = phaseHint.match(/(\d+)\s*道/)
    if (!match) return
    const count = parseInt(match[1], 10)
    if (lastCountRef.current !== null && count !== lastCountRef.current && phaseRef.current) {
      gsap.fromTo(phaseRef.current,
        { scale: 1.03, color: '#f97316' },
        { scale: 1, color: '#334155', duration: 0.4, ease: 'back.out(1.7)' }
      )
    }
    lastCountRef.current = count
  }, [phaseHint])

  // GSAP: Collapse/expand (measure auto height since GSAP can't tween to 'auto')
  useEffect(() => {
    const body = bodyRef.current
    if (!body) return
    const tl = gsap.timeline()
    if (collapsed) {
      tl.to(body, { height: 0, opacity: 0, duration: 0.3, ease: 'power2.inOut' })
      tl.set(body, { overflow: 'hidden' })
    } else {
      body.style.overflow = 'hidden'
      const autoH = body.scrollHeight
      tl.fromTo(body, { height: 0, opacity: 0 }, { height: autoH, opacity: 1, duration: 0.35, ease: 'power2.out' })
      tl.set(body, { height: 'auto', overflow: '' })
    }
    return () => { tl.kill() }
  }, [collapsed])

  const handleCollapseToggle = useCallback(() => { setCollapsed(c => !c) }, [])

  const statusColor = completed ? '#10b981' : busy ? '#f97316' : waiting ? '#f59e0b' : '#94a3b8'
  const textColor = completed ? '#059669' : busy ? '#ea580c' : waiting ? '#d97706' : '#64748b'
  const dotShadowAlpha = busy
    ? Math.round(20 + (displayPct / 100) * 40).toString(16).padStart(2, '0')
    : waiting ? '30' : '20'

  return (
    <div ref={cardRef} className="card">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <span
              ref={dotRef}
              className="w-2.5 h-2.5 rounded-full"
              style={{
                background: statusColor,
                boxShadow: `0 0 ${6 + (displayPct / 100) * 10}px ${statusColor}${dotShadowAlpha}`,
              }}
            />
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">进度</span>
          </div>
          <span
            className="text-2xl font-extrabold tabular-nums tracking-tight"
            style={{ color: textColor }}
          >
            {Number.isInteger(displayPct) ? `${displayPct}%` : `${displayPct.toFixed(1)}%`}
          </span>
        </div>
        <button
          className="btn btn-ghost !px-3 !py-1.5 text-[11px]"
          onClick={handleCollapseToggle}
        >
          {collapsed ? '展开详情' : '收起'}
        </button>
      </div>

      {/* Body */}
      {!collapsed && (
        <div ref={bodyRef} className="mt-4 space-y-3">
          <div className="relative">
            <div
              ref={glowRef}
              className="absolute inset-0 rounded-full opacity-0"
              style={{
                background: completed
                  ? 'linear-gradient(90deg, rgba(16,185,129,0.15) 0%, rgba(5,150,105,0.08) 100%)'
                  : waiting
                    ? 'linear-gradient(90deg, rgba(245,158,11,0.12) 0%, rgba(217,119,6,0.06) 100%)'
                    : `linear-gradient(90deg, rgba(251,146,60,${(0.06 + (displayPct / 100) * 0.1).toFixed(2)}) 0%, rgba(249,115,22,${(0.03 + (displayPct / 100) * 0.06).toFixed(2)}) 100%)`,
                filter: 'blur(4px)',
              }}
            />
            <div className="relative progress-rail bg-slate-100 border border-slate-200/80">
              <div
                ref={progressBarRef}
                className={`h-full rounded-full relative overflow-hidden ${busy ? 'progress-bar-breathe' : ''}`}
                style={{
                  width: '2%',
                  background: completed
                    ? 'linear-gradient(90deg, #6ee7b7 0%, #34d399 30%, #10b981 60%, #059669 100%)'
                    : waiting
                      ? 'linear-gradient(90deg, #fde68a 0%, #fbbf24 30%, #f59e0b 60%, #d97706 100%)'
                      : 'linear-gradient(90deg, #fed7aa 0%, #fdba74 20%, #fb923c 45%, #f97316 70%, #ea580c 100%)',
                }}
              >
                {/* CSS shimmer — always active during busy for smooth continuous sweep */}
                {busy && <div className="absolute inset-0 progress-bar-shimmer" />}
                {/* GSAP-driven shimmer — overlaid for variable-speed control */}
                {busy && (
                  <div
                    ref={shimmerRef}
                    className="absolute inset-0"
                    style={{
                      background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.25) 50%, transparent 100%)',
                      width: '40%',
                    }}
                  />
                )}
                {/* Inner highlight for depth */}
                <div className="absolute inset-x-0 top-0 h-1/2 rounded-full bg-gradient-to-b from-white/25 to-transparent pointer-events-none" />
              </div>
            </div>
          </div>

          <div
            className="phase-hint-container flex items-start gap-2.5 px-4 py-3 rounded-xl text-[12px] font-mono leading-relaxed"
            style={{
              background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
              border: '1px solid #e2e8f0',
              color: '#334155',
            }}
            aria-live="polite"
          >
            <div className="phase-hint-glow" />
            <span
              ref={phaseDotRef}
              className="mt-1 w-2 h-2 rounded-full shrink-0 relative z-10"
              style={{ background: statusColor }}
            />
            <span ref={phaseRef} className="min-w-0 relative z-10">{phaseHint || '等待文件进入解析流程'}</span>
          </div>
        </div>
      )}
    </div>
  )
}
