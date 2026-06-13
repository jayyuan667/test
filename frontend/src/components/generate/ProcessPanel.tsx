import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import type { TaskResult } from '../../types'
import { CommitToLibraryModal } from './CommitToLibraryModal'
import type { CommitDraft } from '../../api/client'
import gsap from 'gsap'

interface ProcessRow {
  code: string
  trade: string
  content: string
}

interface Props {
  result: TaskResult | null
  taskId: string | null
  streamingChunks: string
}

// Parse a single line into a process row (matches H5's twParseLine)
function parseLine(line: string): ProcessRow | null {
  let content = line.trim()
  if (!content || content.startsWith('#') || /^[-=]{3,}$/.test(content)) return null
  if (content.startsWith('- ') || content.startsWith('* ')) content = content.slice(2).trim()

  // Three-part: 0010@工种@内容
  const m3 = content.match(/^(\d{4})@([^@]*)@(.+)$/)
  if (m3) return { code: m3[1].trim(), trade: m3[2].trim(), content: m3[3].trim() }

  // Two-part: 0010@内容 or 0010: 内容
  const m2 = content.match(/^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$/)
  if (!m2) return null

  const rawContent = m2[2].trim()
  // Try to extract embedded trade: "料@备料..." or "工序内容 （工种：料）"
  const mSuffix = rawContent.match(/^(.*?)\s*[（(]工种[：:]\s*([一-龥\-]{1,6})\s*[）)]\s*$/)
  if (mSuffix) return { code: m2[1].trim(), trade: mSuffix[2].trim(), content: mSuffix[1].trim() }

  const mTrade = rawContent.match(/^([^\d\s@（）【】\[\]()]{1,6})@(.+)/s)
  if (mTrade && mTrade[2].trim()) return { code: m2[1].trim(), trade: mTrade[1].trim(), content: mTrade[2].trim() }

  return { code: m2[1].trim(), trade: '', content: rawContent }
}

// Parse all streaming text into rows
function parseStreamingRows(text: string): ProcessRow[] {
  const rows: ProcessRow[] = []
  const seen = new Set<string>()
  for (const line of text.split(/\r?\n/)) {
    const row = parseLine(line)
    if (!row) continue
    const key = `${row.code}::${row.content}`
    if (seen.has(key)) continue
    seen.add(key)
    rows.push(row)
  }
  return rows
}

// Trade badge color
function tradeBadgeClass(trade: string): string {
  if (trade === '热处理') return 'bg-emerald-100 text-emerald-700 border-emerald-200'
  if (trade === '检验') return 'bg-amber-100 text-amber-700 border-amber-200'
  return 'bg-blue-50 text-blue-600 border-blue-200'
}

export function ProcessPanel({ result, taskId, streamingChunks }: Props) {
  const tableRef = useRef<HTMLDivElement>(null)
  const emptyStateRef = useRef<HTMLDivElement>(null)

  // Streaming typewriter state
  const [displayedRows, setDisplayedRows] = useState<ProcessRow[]>([])
  const [typingRow, setTypingRow] = useState<ProcessRow | null>(null)
  const [typingField, setTypingField] = useState<'code' | 'trade' | 'content'>('code')
  const [typingText, setTypingText] = useState('')
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const rowQueueRef = useRef<ProcessRow[]>([])
  const isTypingRef = useRef(false)
  const animatedCountRef = useRef(0)
  const userScrolledRef = useRef(false)

  // Editable rows & row management
  const [editRows, setEditRows] = useState<ProcessRow[]>([])
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)
  const [showCommitModal, setShowCommitModal] = useState(false)

  // Final result rows
  const finalRows = useMemo(() => {
    if (!result?.process_flow?.data) return []
    return result.process_flow.data.map(row => {
      if (Array.isArray(row)) {
        return {
          code: String(row[0] || '').trim(),
          trade: row.length >= 3 ? String(row[1] || '').trim() : '',
          content: String(row[row.length >= 3 ? 2 : 1] || '').trim(),
        }
      }
      return { code: '', trade: '', content: String(row || '') }
    })
  }, [result])

  // Computed draft for commit-to-library
  const commitDraft: CommitDraft = useMemo(() => {
    const rows = editRows.length > 0 ? editRows : finalRows
    const content = rows.map(r => `${r.code}\t${r.trade}\t${r.content}`).join('\n')
    const processSummary = rows.map(r => `${r.code} ${r.trade} ${r.content}`).join('; ')

    // Parse prefix from feature_report_text (【零件名称】xxx)
    let prefix = ''
    if (result?.feature_report_text) {
      const m = result.feature_report_text.match(/【零件名称】\s*(.+)/)
      if (m) prefix = m[1].trim()
    }
    if (!prefix && result?.source_name) prefix = result.source_name
    if (!prefix && result?.pdf_name) prefix = result.pdf_name.replace(/\.\w+$/, '')

    return {
      prefix,
      content,
      process_summary: processSummary,
      feature_report: result?.feature_report_text || '',
    }
  }, [editRows, finalRows, result])

  // Sync editRows when result changes
  useEffect(() => {
    if (finalRows.length > 0) {
      setEditRows(finalRows)
    }
  }, [finalRows])

  // Row management callbacks
  const renumberRows = useCallback((rows: ProcessRow[]) => {
    return rows.map((row, i) => ({ ...row, code: String((i + 1) * 10) }))
  }, [])

  const handleAddRow = useCallback(() => {
    setEditRows(prev => renumberRows([...prev, { code: '', trade: '', content: '' }]))
  }, [renumberRows])

  const handleInsertRow = useCallback((afterIdx: number) => {
    setEditRows(prev => {
      const newRows = [...prev]
      newRows.splice(afterIdx + 1, 0, { code: '', trade: '', content: '' })
      return renumberRows(newRows)
    })
  }, [renumberRows])

  const handleDeleteRow = useCallback((idx: number) => {
    setEditRows(prev => renumberRows(prev.filter((_, i) => i !== idx)))
  }, [renumberRows])

  const handleCellEdit = useCallback((idx: number, field: 'trade' | 'content', value: string) => {
    setEditRows(prev => {
      const newRows = [...prev]
      newRows[idx] = { ...newRows[idx], [field]: value }
      return newRows
    })
  }, [])

  // Reset streaming state when task changes
  useEffect(() => {
    setDisplayedRows([])
    setTypingRow(null)
    setTypingText('')
    rowQueueRef.current = []
    isTypingRef.current = false
    processedLinesRef.current = 0
    resultArrivedRef.current = false
    animatedCountRef.current = 0
    if (typingTimerRef.current) clearTimeout(typingTimerRef.current)
  }, [taskId])

  // Auto-scroll to bottom unless user has scrolled up
  const scrollToBottom = useCallback(() => {
    if (userScrolledRef.current) return
    const el = tableRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [])

  // Typewriter: type a single field char by char
  const typeField = useCallback((text: string, speed: 'fast' | 'slow', onDone: () => void) => {
    let i = 0
    const tick = () => {
      if (i >= text.length) { onDone(); return }
      i++
      setTypingText(text.slice(0, i))
      scrollToBottom()

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
      typingTimerRef.current = setTimeout(tick, delay)
    }
    tick()
  }, [scrollToBottom])

  // Typewriter: type fields sequence for a row
  const typeRow = useCallback((row: ProcessRow) => {
    isTypingRef.current = true
    setTypingRow(row)
    setTypingField('code')
    setTypingText('')

    // Type code
    typeField(row.code, 'fast', () => {
      setTypingField('trade')
      setTypingText('')
      typeField(row.trade, 'fast', () => {
        setTypingField('content')
        setTypingText('')
        typeField(row.content, 'slow', () => {
          // Row done
          setDisplayedRows(prev => [...prev, row])
          setTimeout(scrollToBottom, 50)
          setTypingRow(null)
          setTypingText('')
          isTypingRef.current = false
          // Pause between rows
          typingTimerRef.current = setTimeout(() => {
            kickTyping()
          }, 320 + Math.random() * 280)
        })
      })
    })
  }, [typeField, scrollToBottom])

  // Kick the typing queue
  const kickTyping = useCallback(() => {
    if (isTypingRef.current) return
    const next = rowQueueRef.current.shift()
    if (next) {
      typeRow(next)
    }
  }, [typeRow])

  // Process streaming chunks — track processed line count to avoid re-parsing
  const processedLinesRef = useRef(0)
  const resultArrivedRef = useRef(false)

  // Mark when result arrives — stop queuing new rows but let typewriter finish
  useEffect(() => {
    if (result && !resultArrivedRef.current) {
      resultArrivedRef.current = true
    }
  }, [result])

  useEffect(() => {
    if (!streamingChunks) return
    // Don't add new rows after result arrived — let typewriter finish queued rows
    if (resultArrivedRef.current) return

    const lines = streamingChunks.split(/\r?\n/)
    const completeCount = lines.length - 1

    for (let i = processedLinesRef.current; i < completeCount; i++) {
      const row = parseLine(lines[i])
      if (row) {
        const inQueue = rowQueueRef.current.some(r => r.code === row.code)
        const inDisplayed = displayedRows.some(r => r.code === row.code)
        const isCurrentTyping = typingRow?.code === row.code
        if (!inQueue && !inDisplayed && !isCurrentTyping) {
          rowQueueRef.current.push(row)
          kickTyping()
        }
      }
    }
    processedLinesRef.current = completeCount
  }, [streamingChunks, displayedRows, typingRow, kickTyping])

  // Reset user scroll flag when streaming starts
  useEffect(() => {
    if (streamingChunks) {
      userScrolledRef.current = false
    }
  }, [streamingChunks])

  // GSAP: Table row animation (only animate new rows to prevent flickering)
  useEffect(() => {
    if (!tableRef.current) return
    const rows = tableRef.current.querySelectorAll('tbody tr')
    if (rows.length <= animatedCountRef.current) return

    const newRows = Array.from(rows).slice(animatedCountRef.current)
    if (newRows.length === 0) return

    gsap.fromTo(newRows,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.3, stagger: 0.04, ease: 'power2.out' }
    )
    animatedCountRef.current = rows.length
  }, [finalRows, displayedRows, editRows])

  // GSAP: Empty state animation
  useEffect(() => {
    if (emptyStateRef.current && !result && !streamingChunks) {
      gsap.fromTo(emptyStateRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }
      )
    }
  }, [result, streamingChunks])

  // Determine what to show
  // When result arrives, let typewriter finish before switching to finalRows
  const typewriterActive = isTypingRef.current || rowQueueRef.current.length > 0
  const hasFinalResult = finalRows.length > 0 && !typewriterActive
  const hasStreamingContent = displayedRows.length > 0 || typingRow !== null
  const isStreaming = !result || typewriterActive

  if (!result && !streamingChunks) {
    return (
      <div ref={emptyStateRef} className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8">
        <div
          className="w-16 h-16 rounded-xl grid place-items-center"
          style={{ background: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)', border: '1px solid #bfdbfe' }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
        </div>
        <div className="text-[14px] font-semibold text-slate-600">请先上传文件</div>
        <div className="text-[12px] text-slate-400 max-w-[280px] leading-relaxed">
          上传工艺图纸后，这里将显示生成的工艺规程
        </div>
      </div>
    )
  }

  // Render rows (final or streaming)
  const rows = hasFinalResult ? editRows : displayedRows
  const showTyping = isStreaming && typingRow !== null

  return (
    <div className="flex flex-col h-full min-h-0 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 shrink-0">
        <div>
          <h3 className="text-[15px] font-bold text-slate-800 mb-0.5">工艺规程</h3>
          <p className="text-[12px] text-slate-400">
            {hasFinalResult ? `${finalRows.length} 道工序` : isStreaming ? `工艺生成中... ${displayedRows.length} 道工序` : '等待生成...'}
          </p>
        </div>
        {hasFinalResult && (
          <button
            onClick={() => setShowCommitModal(true)}
            className="px-5 py-2 rounded-xl bg-gradient-to-r from-flame-500 to-orange-500 text-white text-[13px] font-semibold shadow-sm hover:shadow-md transition-shadow"
          >
            入库
          </button>
        )}
      </div>

      {/* Process table */}
      <div
        ref={tableRef}
        className="flex-1 min-h-0 rounded-2xl border border-slate-200 overflow-y-auto overflow-x-hidden bg-white"
        onScroll={() => {
          const el = tableRef.current
          if (!el) return
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
          userScrolledRef.current = !atBottom
        }}
      >
        {rows.length > 0 || showTyping ? (
          <table className="data-table">
            <colgroup>
              <col style={{ width: 80 }} />
              <col style={{ width: 90 }} />
              <col />
              {hasFinalResult && <col style={{ width: 64 }} />}
            </colgroup>
            <thead>
              <tr>
                <th className="text-center">工序号</th>
                <th>工种</th>
                <th>工序名称及内容</th>
                {hasFinalResult && <th></th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  className="group relative"
                  onMouseEnter={() => hasFinalResult && setHoveredRow(i)}
                  onMouseLeave={() => hasFinalResult && setHoveredRow(null)}
                >
                  <td className="text-center font-mono text-[15px] font-bold text-flame-600 bg-gradient-to-r from-flame-50/50 to-orange-50/30">
                    {row.code}
                  </td>
                  <td>
                    {hasFinalResult ? (
                      <span
                        contentEditable
                        suppressContentEditableWarning
                        onBlur={(e) => handleCellEdit(i, 'trade', e.currentTarget.textContent || '')}
                        className="cell-editable block"
                      >
                        {row.trade}
                      </span>
                    ) : row.trade ? (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${tradeBadgeClass(row.trade)}`}>
                        {row.trade}
                      </span>
                    ) : null}
                  </td>
                  <td>
                    <span
                      contentEditable
                      suppressContentEditableWarning
                      onBlur={(e) => hasFinalResult && handleCellEdit(i, 'content', e.currentTarget.textContent || '')}
                      className="cell-editable block"
                    >
                      {row.content}
                    </span>
                  </td>
                  {hasFinalResult && (
                    <td className="w-16 text-right opacity-0 group-hover:opacity-100 transition-opacity">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => handleInsertRow(i)}
                          className="w-6 h-6 flex items-center justify-center rounded text-slate-400 hover:text-blue-500 hover:bg-blue-50 text-[14px]"
                          title="在下方插入"
                        >+</button>
                        <button
                          onClick={() => handleDeleteRow(i)}
                          className="w-6 h-6 flex items-center justify-center rounded text-slate-400 hover:text-red-500 hover:bg-red-50 text-[13px]"
                          title="删除此行"
                        >×</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {/* Typing row */}
              {showTyping && (
                <tr className="tw-typing-row">
                  <td className="text-center font-mono text-[15px] font-bold text-flame-600 bg-gradient-to-r from-flame-50/50 to-orange-50/30">
                    {typingField === 'code' ? (
                      <span>{typingText}<span className="typing-cursor">▍</span></span>
                    ) : typingRow.code}
                  </td>
                  <td>
                    {typingField === 'trade' ? (
                      <span>{typingText}<span className="typing-cursor">▍</span></span>
                    ) : typingField === 'content' || typingField === 'code' ? (
                      typingRow.trade ? (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${tradeBadgeClass(typingRow.trade)}`}>
                          {typingRow.trade}
                        </span>
                      ) : null
                    ) : null}
                  </td>
                  <td>
                    {typingField === 'content' ? (
                      <span>{typingText}<span className="typing-cursor">▍</span></span>
                    ) : null}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        ) : isStreaming ? (
          <div className="p-5 flex items-center gap-3 text-[13px] text-slate-500">
            <span className="w-4 h-4 border-2 border-slate-200 border-t-flame-500 rounded-full animate-spin" />
            工艺正在生成...
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-[12px] text-slate-400 p-8">
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-slate-200 border-t-flame-500 rounded-full animate-spin" />
              等待工艺生成...
            </span>
          </div>
        )}
      </div>

      {showCommitModal && (
        <CommitToLibraryModal
          draft={commitDraft}
          onClose={() => setShowCommitModal(false)}
          onSuccess={() => setShowCommitModal(false)}
        />
      )}
    </div>
  )
}
