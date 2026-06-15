import { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef, memo } from 'react'
import type { ProcessRow } from './ProcessPanel'

export interface TypewriterProgress {
  displayed: number
  queued: number
  currentChar: number
  currentTotal: number
}

export interface TypingRowHandle {
  enqueue: (row: ProcessRow) => void
  reset: () => void
  getQueueLength: () => number
  isActive: () => boolean
}

interface Props {
  onRowComplete: (row: ProcessRow) => void
  onProgress?: (info: TypewriterProgress) => void
  onAllDone?: () => void
  onStart?: () => void
}

export const TypingRow = memo(forwardRef<TypingRowHandle, Props>(
  function TypingRow({ onRowComplete, onProgress, onAllDone, onStart }, ref) {
    const [currentRow, setCurrentRow] = useState<ProcessRow | null>(null)
    const [field, setField] = useState<'code' | 'trade' | 'content'>('code')
    const [typedText, setTypedText] = useState('')
    const [status, setStatus] = useState<'idle' | 'typing' | 'completing'>('idle')

    const queueRef = useRef<ProcessRow[]>([])
    const isActiveRef = useRef(false)
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const completedCountRef = useRef(0)
    const currentRowRef = useRef<ProcessRow | null>(null)
    const processNextRef = useRef<() => void>(null!)
    const onAllDoneRef = useRef(onAllDone)
    useEffect(() => { onAllDoneRef.current = onAllDone }, [onAllDone])
    const onStartRef = useRef(onStart)
    useEffect(() => { onStartRef.current = onStart }, [onStart])
    const typeRowRef = useRef<(row: ProcessRow) => void>(null!)

    useEffect(() => {
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current)
      }
    }, [])

    useImperativeHandle(ref, () => ({
      enqueue(row: ProcessRow) {
        // Dedup: skip rows already in queue or currently typing
        const inQueue = queueRef.current.some(r => r.code === row.code)
        const isCurrent = currentRowRef.current?.code === row.code
        if (inQueue || isCurrent) return
        queueRef.current.push(row)
        if (!isActiveRef.current) {
          processNextRef.current()
        }
      },
      reset() {
        if (timerRef.current) clearTimeout(timerRef.current)
        timerRef.current = null
        queueRef.current = []
        isActiveRef.current = false
        completedCountRef.current = 0
        currentRowRef.current = null
        setCurrentRow(null)
        setField('code')
        setTypedText('')
        setStatus('idle')
      },
      getQueueLength() { return queueRef.current.length },
      isActive() { return isActiveRef.current },
    }), [])

    const typeField = useCallback((text: string, speed: 'fast' | 'slow', onDone: () => void) => {
      if (!text) { onDone(); return }
      let i = 0
      const tick = () => {
        if (i >= text.length) { onDone(); return }
        i++
        setTypedText(text.slice(0, i))
        onProgress?.({
          displayed: completedCountRef.current,
          queued: queueRef.current.length,
          currentChar: i,
          currentTotal: text.length,
        })
        const ch = text[i - 1]
        let delay: number
        if (speed === 'fast') {
          delay = /\d/.test(ch) ? 14 + Math.random() * 14 : 9 + Math.random() * 9
        } else {
          if (/[，。、；：！？,.!?]/.test(ch)) delay = 55 + Math.random() * 75
          else if (/[一-鿿]/.test(ch)) delay = 20 + Math.random() * 20
          else if (/\d/.test(ch)) delay = 16 + Math.random() * 16
          else delay = 11 + Math.random() * 11
        }
        timerRef.current = setTimeout(tick, delay)
      }
      tick()
    }, [onProgress])

    const typeRow = useCallback((row: ProcessRow) => {
      onStartRef.current?.()
      isActiveRef.current = true
      currentRowRef.current = row
      setCurrentRow(row)
      setField('code')
      setTypedText('')
      setStatus('typing')

      typeField(row.code, 'fast', () => {
        setField('trade')
        setTypedText('')
        typeField(row.trade, 'fast', () => {
          setField('content')
          setTypedText('')
          typeField(row.content, 'slow', () => {
            setStatus('completing')
            completedCountRef.current++
            onRowComplete(row)
            timerRef.current = setTimeout(() => {
              currentRowRef.current = null
              setCurrentRow(null)
              setTypedText('')
              setStatus('idle')
              isActiveRef.current = false
              timerRef.current = setTimeout(() => {
                processNextRef.current()
              }, 80)
            }, 600)
          })
        })
      })
    }, [typeField, onRowComplete])
    typeRowRef.current = typeRow

    function processNext() {
      const next = queueRef.current.shift()
      if (next) {
        typeRowRef.current(next)
      } else {
        onAllDoneRef.current?.()
      }
    }
    processNextRef.current = processNext

    function tradeBadgeClass(trade: string): string {
      if (trade === '热处理') return 'bg-emerald-100 text-emerald-700 border-emerald-200'
      if (trade === '检验') return 'bg-amber-100 text-amber-700 border-amber-200'
      return 'bg-blue-50 text-blue-600 border-blue-200'
    }

    if (status === 'idle' || !currentRow) return null

    return (
      <tr className={`tw-typing-row${status === 'completing' ? ' completing' : ''}`}>
        <td className="text-center font-mono text-[15px] font-bold text-flame-600 bg-gradient-to-r from-flame-50/50 to-orange-50/30">
          {field === 'code' ? (
            <span className="relative">
              <span className="invisible">{currentRow.code}</span>
              <span className="absolute left-0 top-0">
                {typedText}<span className="typing-cursor">▍</span>
              </span>
            </span>
          ) : currentRow.code}
        </td>
        <td>
          {field === 'trade' ? (
            <span className="relative inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border border-slate-200">
              <span className="invisible">{currentRow.trade || ' '}</span>
              <span className="absolute left-2">
                {typedText}<span className="typing-cursor">▍</span>
              </span>
            </span>
          ) : (field === 'content' || status === 'completing') && currentRow.trade ? (
            <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${tradeBadgeClass(currentRow.trade)}`}>
              {currentRow.trade}
            </span>
          ) : null}
        </td>
        <td>
          {field === 'content' || status === 'completing' ? (
            <span className="relative block whitespace-pre-wrap break-words">
              <span className="invisible">{currentRow.content || ' '}</span>
              <span className="absolute left-0 top-0">
                {status === 'completing' ? currentRow.content : typedText}
                {status !== 'completing' && <span className="typing-cursor">▍</span>}
              </span>
            </span>
          ) : null}
        </td>
      </tr>
    )
  }
))
