import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import type { TaskResult } from '../../types'
import { CommitToLibraryModal } from './CommitToLibraryModal'
import type { CommitDraft } from '../../api/client'
import { TypingRow } from './TypingRow'
import type { TypingRowHandle, TypewriterProgress } from './TypingRow'
import gsap from 'gsap'

export interface ProcessRow {
  code: string
  trade: string
  content: string
}

interface Props {
  result: TaskResult | null
  taskId: string | null
  runToken: number
  streamingChunks: string
  reviewText?: string
  onTypewriterComplete?: () => void
  onRowsChange?: (rows: ProcessRow[]) => void
  onTypewriterProgress?: (info: TypewriterProgress) => void  // new
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



// Trade badge color
function tradeBadgeClass(trade: string): string {
  if (trade === '热处理') return 'bg-emerald-100 text-emerald-700 border-emerald-200'
  if (trade === '检验') return 'bg-amber-100 text-amber-700 border-amber-200'
  return 'bg-blue-50 text-blue-600 border-blue-200'
}

export function ProcessPanel({ result, taskId, runToken, streamingChunks, reviewText, onTypewriterComplete, onRowsChange, onTypewriterProgress }: Props) {
  const tableRef = useRef<HTMLDivElement>(null)
  const emptyStateRef = useRef<HTMLDivElement>(null)
  const commitBtnRef = useRef<HTMLButtonElement>(null)

  // Streaming typewriter state
  const [displayedRows, setDisplayedRows] = useState<ProcessRow[]>([])
  const typingRef = useRef<TypingRowHandle>(null)
  const [isTyping, setIsTyping] = useState(false)
  const animatedCountRef = useRef(0)
  const userScrolledRef = useRef(false)

  // Editable rows & row management — initialize from result on re-mount to avoid empty flash
  const [editRows, setEditRows] = useState<ProcessRow[]>(() => {
    if (!result?.process_flow?.data) return []
    return result.process_flow.data.map((row: unknown) => {
      if (Array.isArray(row)) {
        return {
          code: String(row[0] || '').trim(),
          trade: row.length >= 3 ? String(row[1] || '').trim() : '',
          content: String(row[row.length >= 3 ? 2 : 1] || '').trim(),
        }
      }
      return { code: '', trade: '', content: String(row || '') }
    })
  })
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

    // Use edited reviewText if available, otherwise fall back to original
    const featureText = reviewText || result?.feature_report_text || ''
    const featSrc = featureText

    // Parse prefix from feature text (【零件名称】xxx)
    let prefix = ''
    let techRequirement = ''
    let productType = ''
    if (featSrc) {
      const m = featSrc.match(/【零件名称】\s*(.+)/)
      if (m) prefix = m[1].trim()
      const tr = featSrc.match(/【技术要求】\s*(.+)/)
      if (tr) techRequirement = tr[1].trim()
      const pt = featSrc.match(/【类型】\s*(.+)/)
      if (pt) productType = pt[1].trim()
    }
    if (!prefix && result?.source_name) prefix = result.source_name
    if (!prefix && result?.pdf_name) prefix = result.pdf_name.replace(/\.\w+$/, '')

    return {
      prefix,
      content,
      process_summary: processSummary,
      feature_report_text: featureText,
      preview_image_urls: result?.preview_image_urls || result?.preview_images || [],
      source_type: 'web_upload',
      source_task_id: result?.task_id || '',
      process_list: rows.map(r => ({ code: r.code, trade: r.trade, content: r.content })),
      tech_requirement: techRequirement,
      product_type: productType,
    }
  }, [editRows, finalRows, result, reviewText])

  // Sync editRows when result changes (skip on re-mount if result already exists to avoid empty-array flash)
  const editRowsInitRef = useRef(!!result)
  useEffect(() => {
    if (editRowsInitRef.current) { editRowsInitRef.current = false; return }
    if (finalRows.length > 0) {
      setEditRows(finalRows)
    }
  }, [finalRows])

  // Notify parent when rows change (for export sync)
  useEffect(() => {
    onRowsChange?.(editRows)
  }, [editRows, onRowsChange])

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

  // Track whether typewriter has been fed rows (prevents hasFinalResult flash)
  const rowsFedRef = useRef(false)
  // Track enqueued row codes to avoid re-parsing duplicates in streaming effect
  const enqueuedCodesRef = useRef(new Set<string>())

  // Reset streaming state when a new run starts (skip on mount — refs already initialized)
  const prevRunTokenRef = useRef(runToken)
  useEffect(() => {
    if (prevRunTokenRef.current === runToken) return
    prevRunTokenRef.current = runToken
    setDisplayedRows([])
    animatedCountRef.current = 0
    processedLinesRef.current = 0
    resultArrivedRef.current = false
    rowsFedRef.current = false
    enqueuedCodesRef.current.clear()
    skipOnMountRef.current = false
    typingRef.current?.reset()
    setIsTyping(false)
  }, [runToken])
  // Process streaming chunks — track processed line count to avoid re-parsing
  const processedLinesRef = useRef(0)
  const resultArrivedRef = useRef(false)

  // Skip result/streaming effects on re-mount when result already present (tab switch)
  // On re-mount, go straight to final display state
  const skipOnMountRef = useRef(!!result)
  if (skipOnMountRef.current) {
    rowsFedRef.current = true
    resultArrivedRef.current = true
  }

  // When result arrives: feed rows to typewriter if no streaming happened, then mark arrived
  useEffect(() => {
    if (!result || resultArrivedRef.current || skipOnMountRef.current) return
    // Feed final rows through typewriter if it never ran (no streaming)
    if (displayedRows.length === 0 && !isTyping && typingRef.current) {
      for (const row of finalRows) {
        typingRef.current.enqueue(row)
        enqueuedCodesRef.current.add(row.code)
      }
      // Set isTyping synchronously to prevent hasFinalResult flash on next render.
      // React batches this with the state updates from enqueue → typewriter starts.
      setIsTyping(true)
      rowsFedRef.current = true
    }
    // Mark AFTER feeding — so streaming effect won't block
    resultArrivedRef.current = true
  }, [result, finalRows, displayedRows.length, isTyping])

  // Process streaming chunks into typewriter queue
  useEffect(() => {
    if (!streamingChunks) return
    if (resultArrivedRef.current) return
    // Skip if result already arrived (e.g. tab switch re-mount)
    if (result) return

    const lines = streamingChunks.split(/\r?\n/)
    const completeCount = lines.length - 1

    for (let i = processedLinesRef.current; i < completeCount; i++) {
      const row = parseLine(lines[i])
      if (row && !enqueuedCodesRef.current.has(row.code)) {
        enqueuedCodesRef.current.add(row.code)
        typingRef.current?.enqueue(row)
        rowsFedRef.current = true
      }
    }
    processedLinesRef.current = completeCount
  }, [streamingChunks])

  // Reset user scroll flag when streaming starts
  useEffect(() => {
    if (streamingChunks) {
      userScrolledRef.current = false
    }
  }, [streamingChunks])

  // Bridge: TypingRow progress → parent callback
  // Only set isTyping = true here; isTyping = false is handled by onAllDone
  const handleTypingProgress = useCallback((info: TypewriterProgress) => {
    if (info.queued > 0 || info.currentChar < info.currentTotal) {
      setIsTyping(true)
    }
    onTypewriterProgress?.(info)
  }, [onTypewriterProgress])

  // Called when typewriter starts processing a row (synchronous, before render)
  const handleTypingStart = useCallback(() => {
    setIsTyping(true)
  }, [])

  // Called when typewriter queue is fully drained
  const handleAllDone = useCallback(() => {
    setIsTyping(false)
  }, [])

  // Auto-scroll after row complete
  const handleRowComplete = useCallback((row: ProcessRow) => {
    setDisplayedRows(prev => [...prev, row])
    if (!userScrolledRef.current && tableRef.current) {
      setTimeout(() => {
        if (tableRef.current) tableRef.current.scrollTop = tableRef.current.scrollHeight
      }, 50)
    }
  }, [])

  // GSAP: Table row animation (opacity only — transforms on <tr> cause layout bugs)
  useEffect(() => {
    if (!tableRef.current) return
    const rows = tableRef.current.querySelectorAll('tbody tr')
    if (rows.length <= animatedCountRef.current) return

    const newRows = Array.from(rows).slice(animatedCountRef.current)
    if (newRows.length === 0) return

    gsap.fromTo(newRows,
      { opacity: 0 },
      { opacity: 1, duration: 0.3, stagger: 0.04, ease: 'power2.out' }
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
  const typewriterActive = isTyping
  const hasFinalResult = finalRows.length > 0 && !typewriterActive && rowsFedRef.current

  // Notify parent when typewriter finishes (result arrived + all rows displayed)
  // Initialize to true on re-mount when result already exists to prevent duplicate callback
  const hasFiredCompleteRef = useRef(!!result)
  useEffect(() => {
    if (hasFinalResult && !hasFiredCompleteRef.current) {
      hasFiredCompleteRef.current = true
      onTypewriterComplete?.()
    }
  }, [hasFinalResult, onTypewriterComplete])

  // Reset the flag when task changes
  const prevRunTokenForCompleteRef = useRef(runToken)
  useEffect(() => {
    if (prevRunTokenForCompleteRef.current === runToken) return
    prevRunTokenForCompleteRef.current = runToken
    hasFiredCompleteRef.current = false
  }, [runToken])

  // GSAP: Entrance animation for commit button (skip on re-mount with result)
  const commitAnimInitRef = useRef(!!result)
  useEffect(() => {
    if (commitAnimInitRef.current) { commitAnimInitRef.current = false; return }
    if (hasFinalResult && commitBtnRef.current) {
      gsap.fromTo(commitBtnRef.current,
        { scale: 0.7, opacity: 0, y: 8 },
        { scale: 1, opacity: 1, y: 0, duration: 0.5, ease: 'back.out(2)' }
      )
    }
  }, [hasFinalResult])

  // GSAP: Breathing glow on commit button
  useEffect(() => {
    if (!hasFinalResult || !commitBtnRef.current) return
    const tl = gsap.timeline({ repeat: -1, yoyo: true, delay: 0.6 })
      .to(commitBtnRef.current, {
        boxShadow: '0 0 16px rgba(249,115,22,0.3), 0 4px 12px rgba(249,115,22,0.15)',
        duration: 2,
        ease: 'sine.inOut',
      })
    return () => { tl.kill() }
  }, [hasFinalResult])
  const isStreaming = !result || typewriterActive

  // Only show "upload first" when there's genuinely no task — not during rerun/continue
  if (!result && !streamingChunks && !taskId) {
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
            ref={commitBtnRef}
            onClick={() => setShowCommitModal(true)}
            className="btn btn-primary !text-[13px] !px-6 !py-2"
          >
            入库
          </button>
        )}
      </div>

      {/* Process table */}
      <div
        ref={tableRef}
        className="flex-1 min-h-0 max-h-[65vh] overflow-y-auto overflow-x-hidden bg-white data-table-wrap"
        style={{ overflowAnchor: 'none', scrollBehavior: 'smooth' }}
        onScroll={() => {
          const el = tableRef.current
          if (!el) return
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
          userScrolledRef.current = !atBottom
        }}
      >
        {taskId ? (
          <table className="data-table" style={{ tableLayout: 'fixed' }}>
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
                    {row.trade ? (
                      <span
                        contentEditable={hasFinalResult}
                        suppressContentEditableWarning
                        onBlur={(e) => hasFinalResult && handleCellEdit(i, 'trade', e.currentTarget.textContent || '')}
                        className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${tradeBadgeClass(row.trade)} ${hasFinalResult ? 'cursor-text' : ''}`}
                      >
                        {row.trade}
                      </span>
                    ) : hasFinalResult ? (
                      <span
                        contentEditable
                        suppressContentEditableWarning
                        onBlur={(e) => handleCellEdit(i, 'trade', e.currentTarget.textContent || '')}
                        className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] text-slate-400 border border-dashed border-slate-200 cursor-text"
                      >
                        工种
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
              {/* TypingRow — always mounted when taskId exists, self-manages visibility */}
              <TypingRow
                ref={typingRef}
                onRowComplete={handleRowComplete}
                onProgress={handleTypingProgress}
                onAllDone={handleAllDone}
                onStart={handleTypingStart}
              />
              {/* Hidden placeholder to maintain table height between typewriter rows */}
              {isTyping && (
                <tr aria-hidden="true" style={{ visibility: 'hidden' }}>
                  <td>&nbsp;</td><td /><td />
                </tr>
              )}
              {/* Placeholder row when table is empty and not typing */}
              {rows.length === 0 && !isTyping && (
                <tr>
                  <td colSpan={3} className="text-center py-8">
                    <span className="flex items-center justify-center gap-2 text-[12px] text-slate-400">
                      <span className="w-4 h-4 border-2 border-slate-200 border-t-flame-500 rounded-full animate-spin" />
                      工艺正在生成...
                    </span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
