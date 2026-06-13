import { useState, useRef, useEffect } from 'react'
import gsap from 'gsap'

interface Props {
  progress: number
  phaseHint: string
  busy: boolean
  completed: boolean
}

export function WorkflowHUD({ progress, phaseHint, busy, completed }: Props) {
  const [collapsed, setCollapsed] = useState(false)
  const progressBarRef = useRef<HTMLDivElement>(null)
  const progressTextRef = useRef<HTMLSpanElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  // GSAP: Progress bar animation
  useEffect(() => {
    if (progressBarRef.current) {
      gsap.to(progressBarRef.current, {
        width: `${Math.max(progress, 2)}%`,
        duration: 0.8,
        ease: 'power2.out',
      })
    }
  }, [progress])

  // GSAP: Progress text animation
  useEffect(() => {
    if (progressTextRef.current) {
      gsap.fromTo(progressTextRef.current,
        { scale: 1.2, opacity: 0.5 },
        { scale: 1, opacity: 1, duration: 0.3, ease: 'back.out(1.7)' }
      )
    }
  }, [progress])

  // GSAP: Collapse/expand animation
  useEffect(() => {
    const body = bodyRef.current
    if (!body) return
    if (collapsed) {
      gsap.to(body, {
        height: 0,
        opacity: 0,
        duration: 0.3,
        ease: 'power2.inOut',
        onComplete: () => { body.style.overflow = 'hidden' },
      })
    } else {
      body.style.overflow = ''
      gsap.fromTo(body,
        { height: 0, opacity: 0 },
        { height: 'auto', opacity: 1, duration: 0.35, ease: 'power2.out' }
      )
    }
  }, [collapsed])

  return (
    <div className="card">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            {busy && (
              <span className="w-2.5 h-2.5 rounded-full bg-flame-500 animate-pulse-soft" />
            )}
            {completed && (
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            )}
            {!busy && !completed && (
              <span className="w-2.5 h-2.5 rounded-full bg-slate-300" />
            )}
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">进度</span>
          </div>
          <span
            ref={progressTextRef}
            className="text-2xl font-extrabold tabular-nums tracking-tight"
            style={{
              background: completed
                ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                : busy
                  ? 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)'
                  : 'linear-gradient(135deg, #94a3b8 0%, #64748b 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            {progress}%
          </span>
        </div>
        <button
          className="btn btn-ghost !px-3 !py-1.5 text-[11px]"
          onClick={() => setCollapsed(c => !c)}
        >
          {collapsed ? '展开详情' : '收起'}
        </button>
      </div>

      {/* Body */}
      {!collapsed && (
        <div ref={bodyRef} className="mt-4 space-y-3">
          {/* Progress bar */}
          <div className="h-2 rounded-full overflow-hidden bg-slate-100 border border-slate-200">
            <div
              ref={progressBarRef}
              className="h-full rounded-full relative overflow-hidden"
              style={{
                width: `${Math.max(progress, 2)}%`,
                background: completed
                  ? 'linear-gradient(90deg, #10b981 0%, #059669 100%)'
                  : 'linear-gradient(90deg, #fb923c 0%, #f97316 50%, #ea580c 100%)',
              }}
            >
              {busy && (
                <div
                  className="absolute inset-0 animate-shimmer"
                  style={{
                    background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                    backgroundSize: '200% 100%',
                  }}
                />
              )}
            </div>
          </div>

          {/* Phase hint */}
          <div
            className="flex items-start gap-2.5 px-4 py-3 rounded-xl text-[12px] font-mono leading-relaxed"
            style={{
              background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
              border: '1px solid #e2e8f0',
              color: '#334155',
            }}
            aria-live="polite"
          >
            <span
              className={`mt-1 w-2 h-2 rounded-full shrink-0 ${busy ? 'animate-pulse-soft' : ''}`}
              style={{
                background: busy ? '#f97316' : completed ? '#10b981' : '#94a3b8',
              }}
            />
            <span className="min-w-0">{phaseHint || '等待文件进入解析流程'}</span>
          </div>
        </div>
      )}
    </div>
  )
}
