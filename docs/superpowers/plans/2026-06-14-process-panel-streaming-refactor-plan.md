# ProcessPanel 流式输出重构 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 typewriter 逻辑从 ProcessPanel (588行) 拆分到独立 TypingRow 组件，配合 CSS contain 布局隔离和 onTypewriterProgress 回调，消除流式输出割裂感并实现渐进式进度条。

**Architecture:** TypingRow 通过 forwardRef + imperative handle 暴露 enqueue/reset 方法，内部用 useRef 管理队列（不触发父组件 render）。ProcessPanel 通过 onTypewriterProgress 回调将打字进度传递给 GeneratePage 驱动进度条和 PhaseHint。

**Tech Stack:** React 18 + TypeScript + Tailwind CSS + GSAP 3.14

---

## 文件映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/components/generate/TypingRow.tsx` | **新建** | 独立打字行组件 — 队列管理 + typeField/typeRow/kickTyping |
| `frontend/src/components/generate/ProcessPanel.tsx` | **修改** | 移除打字逻辑，集成 TypingRow，新增 onTypewriterProgress |
| `frontend/src/pages/GeneratePage.tsx` | **修改** | 新增 onTypewriterProgress 回调，动态 phaseHint |
| `frontend/src/index.css` | **修改** | contain 样式、placeholder 结构、呼吸动画 keyframes |

---

### Task 1: 创建 TypingRow 组件

**Files:**
- Create: `frontend/src/components/generate/TypingRow.tsx`

- [ ] **Step 1: 创建 TypingRow.tsx**

```typescript
import { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef, memo } from 'react'
import type { ProcessRow } from './ProcessPanel'

export interface TypewriterProgress {
  displayed: number      // 已完成的 row 数 (由父组件传入)
  queued: number         // 排队中的 row 数
  currentChar: number    // 当前行已打字符数
  currentTotal: number   // 当前行总字符数
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
}

export const TypingRow = memo(forwardRef<TypingRowHandle, Props>(
  function TypingRow({ onRowComplete, onProgress }, ref) {
    // ── State ──
    const [currentRow, setCurrentRow] = useState<ProcessRow | null>(null)
    const [field, setField] = useState<'code' | 'trade' | 'content'>('code')
    const [typedText, setTypedText] = useState('')
    const [status, setStatus] = useState<'idle' | 'typing' | 'completing'>('idle')

    // ── Refs ──
    const queueRef = useRef<ProcessRow[]>([])
    const isActiveRef = useRef(false)
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const completedCountRef = useRef(0)

    // ── Cleanup timer on unmount ──
    useEffect(() => {
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current)
      }
    }, [])

    // ── Imperative handle ──
    useImperativeHandle(ref, () => ({
      enqueue(row: ProcessRow) {
        queueRef.current.push(row)
        if (!isActiveRef.current) {
          processNext()
        }
      },
      reset() {
        if (timerRef.current) clearTimeout(timerRef.current)
        timerRef.current = null
        queueRef.current = []
        isActiveRef.current = false
        completedCountRef.current = 0
        setCurrentRow(null)
        setField('code')
        setTypedText('')
        setStatus('idle')
      },
      getQueueLength() {
        return queueRef.current.length
      },
      isActive() {
        return isActiveRef.current
      },
    }), [])

    // ── Type a single field ──
    const typeField = useCallback((text: string, speed: 'fast' | 'slow', onDone: () => void) => {
      if (!text) { onDone(); return }
      let i = 0
      const tick = () => {
        if (i >= text.length) { onDone(); return }
        i++
        setTypedText(text.slice(0, i))

        // Progress callback
        onProgress?.({
          displayed: completedCountRef.current,
          queued: queueRef.current.length,
          currentChar: i,
          currentTotal: text.length,
        })

        const ch = text[i - 1]
        let delay: number
        // Content field: fast for first 30 chars, slow after
        const isContentSlow = speed === 'slow' && i > 30
        const effectiveSpeed = isContentSlow ? 'slow' : 'fast'

        if (effectiveSpeed === 'fast') {
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

    // ── Type a whole row: code → trade → content ──
    const typeRow = useCallback((row: ProcessRow) => {
      isActiveRef.current = true
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
            // Row complete — start completing transition
            setStatus('completing')
            completedCountRef.current++
            onRowComplete(row)

            // After transition, check queue
            timerRef.current = setTimeout(() => {
              setCurrentRow(null)
              setTypedText('')
              setStatus('idle')
              isActiveRef.current = false
              // Pause between rows then process next
              timerRef.current = setTimeout(() => {
                processNext()
              }, 320 + Math.random() * 280)
            }, 300)
          })
        })
      })
    }, [typeField, onRowComplete])

    // ── Process next row from queue ──
    function processNext() {
      const next = queueRef.current.shift()
      if (next) {
        typeRow(next)
      }
    }

    // Trade badge color (duplicated from ProcessPanel to keep TypingRow self-contained)
    function tradeBadgeClass(trade: string): string {
      if (trade === '热处理') return 'bg-emerald-100 text-emerald-700 border-emerald-200'
      if (trade === '检验') return 'bg-amber-100 text-amber-700 border-amber-200'
      return 'bg-blue-50 text-blue-600 border-blue-200'
    }

    // ── Render ──
    if (status === 'idle' || !currentRow) return null

    return (
      <tr className={`tw-typing-row${status === 'completing' ? ' completing' : ''}`}>
        {/* Code cell */}
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

        {/* Trade cell */}
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

        {/* Content cell */}
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
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `npx tsc --noEmit --pretty`
Expected: 零错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/generate/TypingRow.tsx
git commit -m "feat: add TypingRow component — isolated typewriter with queue management"
```

---

### Task 2: 重构 ProcessPanel，集成 TypingRow

**Files:**
- Modify: `frontend/src/components/generate/ProcessPanel.tsx`

- [ ] **Step 1: 更新 Props 接口，新增 onTypewriterProgress**

在 ProcessPanel.tsx 顶部，更新 Props 接口：

```typescript
import { useRef, useState, useCallback, useMemo, useEffect } from 'react'
import type { TaskResult } from '../../types'
import { CommitToLibraryModal } from './CommitToLibraryModal'
import type { CommitDraft } from '../../api/client'
import { TypingRow } from './TypingRow'
import type { TypingRowHandle, TypewriterProgress } from './TypingRow'
import gsap from 'gsap'

// ... ProcessRow interface, parseLine, parseStreamingRows, tradeBadgeClass stay the same ...

interface Props {
  result: TaskResult | null
  taskId: string | null
  runToken: number
  streamingChunks: string
  reviewText?: string
  onTypewriterComplete?: () => void
  onTypewriterProgress?: (info: TypewriterProgress) => void  // ← 新增
  onRowsChange?: (rows: ProcessRow[]) => void
}
```

- [ ] **Step 2: 替换内部 state 和 refs — 移除打字相关，新增 typingRef**

将原来的 5 个类型相关 state+ref 替换为：

```typescript
export function ProcessPanel({ result, taskId, runToken, streamingChunks, reviewText, onTypewriterComplete, onTypewriterProgress, onRowsChange }: Props) {
  const tableRef = useRef<HTMLDivElement>(null)
  const emptyStateRef = useRef<HTMLDivElement>(null)
  const commitBtnRef = useRef<HTMLButtonElement>(null)
  const typingRef = useRef<TypingRowHandle>(null)  // ← 新增

  // Streaming state (仅保留 displayedRows)
  const [displayedRows, setDisplayedRows] = useState<ProcessRow[]>([])

  // 移除: typingRow, typingField, typingText, typingTimerRef
  // 移除: rowQueueRef, isTypingRef
  // 保留: animatedCountRef, userScrolledRef, processedLinesRef, resultArrivedRef
  const animatedCountRef = useRef(0)
  const userScrolledRef = useRef(false)
  const processedLinesRef = useRef(0)
  const resultArrivedRef = useRef(false)

  // Editable rows & row management (不变)
  const [editRows, setEditRows] = useState<ProcessRow[]>([])
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)
  const [showCommitModal, setShowCommitModal] = useState(false)
```

- [ ] **Step 3: 更新 reset effect**

```typescript
// Reset streaming state when a new run starts
useEffect(() => {
  setDisplayedRows([])
  animatedCountRef.current = 0
  processedLinesRef.current = 0
  resultArrivedRef.current = false
  typingRef.current?.reset()
}, [runToken])
```

- [ ] **Step 4: 更新 streaming chunk 处理 — 改为通过 typingRef.enqueue 入队**

替换原来的 streaming chunks useEffect（约 L282-303）：

```typescript
// Mark when result arrives
useEffect(() => {
  if (result && !resultArrivedRef.current) {
    resultArrivedRef.current = true
  }
}, [result])

useEffect(() => {
  if (!streamingChunks) return
  if (resultArrivedRef.current) return

  const lines = streamingChunks.split(/\r?\n/)
  const completeCount = lines.length - 1

  for (let i = processedLinesRef.current; i < completeCount; i++) {
    const row = parseLine(lines[i])
    if (row) {
      // De-duplicate check against displayed rows only (queue dedup in TypingRow)
      const inDisplayed = displayedRows.some(r => r.code === row.code)
      if (!inDisplayed) {
        typingRef.current?.enqueue(row)
      }
    }
  }
  processedLinesRef.current = completeCount
}, [streamingChunks, displayedRows])
```

- [ ] **Step 5: 添加 onTypewriterProgress 回调桥接**

```typescript
// Bridge: TypingRow progress → parent callback
const handleTypingProgress = useCallback((info: TypewriterProgress) => {
  onTypewriterProgress?.(info)
}, [onTypewriterProgress])
```

- [ ] **Step 6: 更新渲染分支中的 typing row JSX**

替换原来的 `{showTyping && typingRow && (...)` 块（约 L518-551）：

```typescript
{/* TypingRow — always mounted, self-manages visibility */}
<TypingRow
  ref={typingRef}
  onRowComplete={(row) => {
    setDisplayedRows(prev => [...prev, row])
    // Auto-scroll
    if (!userScrolledRef.current && tableRef.current) {
      setTimeout(() => {
        if (tableRef.current) tableRef.current.scrollTop = tableRef.current.scrollHeight
      }, 50)
    }
  }}
  onProgress={handleTypingProgress}
/>
```

- [ ] **Step 7: 更新 isStreaming / hasFinalResult 判断逻辑**

```typescript
// Determine what to show
const typewriterActive = typingRef.current?.isActive() ?? false
const hasQueuedRows = (typingRef.current?.getQueueLength() ?? 0) > 0
const hasFinalResult = finalRows.length > 0 && !typewriterActive && !hasQueuedRows
const hasStreamingContent = displayedRows.length > 0 || typewriterActive
```

注意：`isStreaming` 需要通过 state 来追踪，因为 ref 的变化不触发重渲染。添加一个 state：

```typescript
const [isTyping, setIsTyping] = useState(false)
```

并在 onRowComplete 和 reset 中更新：

```typescript
// 在 handleTypingProgress 中根据 info 更新
const handleTypingProgress = useCallback((info: TypewriterProgress) => {
  setIsTyping(info.queued > 0 || info.currentChar < info.currentTotal)
  onTypewriterProgress?.(info)
}, [onTypewriterProgress])
```

这样 `isStreaming` 判断：

```typescript
const isStreaming = !result || isTyping || hasQueuedRows
```

- [ ] **Step 8: 移除旧的 typewriter 函数**

删除以下不再需要的函数和 ref：
- `typeField` 函数 (L209-231)
- `typeRow` 函数 (L234-260)
- `kickTyping` 函数 (L263-269)
- `scrollToBottom` 函数 (L201-206) — 改为内联
- `typingTimerRef` ref
- `rowQueueRef` ref
- `isTypingRef` ref
- `typingRow` state
- `typingField` state
- `typingText` state

- [ ] **Step 9: 验证 TypeScript 编译**

Run: `npx tsc --noEmit --pretty`
Expected: 零错误

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/generate/ProcessPanel.tsx
git commit -m "refactor: extract typewriter to TypingRow, add onTypewriterProgress"
```

---

### Task 3: 添加 CSS contain 布局隔离和呼吸动画

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 增强 typing row 的 contain 样式**

在 index.css 末尾添加/更新：

```css
/* ── Typing Row Layout Isolation ── */
.tw-typing-row {
  contain: layout style;
}
.tw-typing-row td {
  contain: layout;
  overflow-anchor: none;
  background: rgba(249, 115, 22, 0.03) !important;
}

/* Completing transition — cursor fade out + bg transition */
.tw-typing-row.completing .typing-cursor {
  opacity: 0;
  transition: opacity 150ms ease;
}
.tw-typing-row.completing td {
  transition: background-color 300ms ease;
}

/* ── Phase Hint Breathing Glow ── */
@keyframes phaseHintBreathe {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50%      { opacity: 0.6; transform: scale(1.05); }
}

@keyframes phaseHintDotPulse {
  0%, 100% { transform: scale(1);   opacity: 0.5; }
  50%      { transform: scale(1.3); opacity: 0.9; }
}

.phase-hint-container {
  position: relative;
}

.phase-hint-glow {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(249,115,22,0.08) 0%, rgba(251,146,60,0.04) 100%);
  animation: phaseHintBreathe 4s ease-in-out infinite;
  pointer-events: none;
}

.phase-hint-counter {
  display: inline-block;
  font-weight: 600;
  color: #f97316;
}

.phase-hint-counter.pop {
  animation: counterPop 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes counterPop {
  0%   { transform: scale(1.3); color: #f59e0b; }
  100% { transform: scale(1);   color: #f97316; }
}
```

- [ ] **Step 2: 验证 CSS 无语法错误**

Run: `npx tailwindcss -i frontend/src/index.css --dry-run 2>&1 | head -5` (仅检查语法)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: add contain layout isolation and breathing keyframes for phase hint"
```

---

### Task 4: 在 GeneratePage 中接入 onTypewriterProgress

**Files:**
- Modify: `frontend/src/pages/GeneratePage.tsx`

- [ ] **Step 1: 添加 onTypewriterProgress 回调函数（带节流）**

在 GeneratePage 中 ProcessPanel 的调用处，添加 `onTypewriterProgress` prop：

```typescript
// 在 component 函数内部，handleReset 之前添加:
const progressThrottleRef = useRef(0)

const handleTypewriterProgress = useCallback((info: { displayed: number; queued: number; currentChar: number; currentTotal: number }) => {
  const active = (info.currentChar < info.currentTotal) ? 1 : 0
  const total = info.displayed + info.queued + active

  // Throttle: update progress every ~200ms, phaseHint every ~800ms
  const now = Date.now()

  if (total > 0 && now - progressThrottleRef.current > 200) {
    progressThrottleRef.current = now
    const pct = info.displayed / total
    setProgress(60 + Math.round(pct * 25))
  }

  // Phase hint — slower updates to maintain breathing rhythm
  if (info.queued > 0 || info.currentChar < info.currentTotal) {
    setPhaseHint(`正在生成工艺规程... 已完成 ${info.displayed} 道工序，共 ${total} 道`)
  } else if (info.displayed > 0) {
    setPhaseHint(`工艺内容生成完成，共 ${info.displayed} 道工序`)
  }
}, [])
```

- [ ] **Step 2: 将回调传给 ProcessPanel**

更新 ProcessPanel 的 JSX 调用：

```typescript
<ProcessPanel
  result={result}
  taskId={taskId}
  runToken={runToken}
  streamingChunks={streamingChunks}
  reviewText={reviewText}
  onTypewriterComplete={() => {
    setProgress(100)
    setPhaseHint(`工艺生成完成，共 ${editedRows.length || 0} 道工序`)
  }}
  onTypewriterProgress={handleTypewriterProgress}
  onRowsChange={setEditedRows}
/>
```

- [ ] **Step 3: 更新 handleConfirmReview 的 phaseHint**

```typescript
const handleConfirmReview = useCallback(async () => {
  // ... 前面的校验不变 ...
  try {
    setReviewFeedback(undefined)
    setStatus('processing')
    setProgress(60)
    setPhaseHint('特征已确认，等待后端响应...')  // ← 更新文案
    // ... 其余不变 ...
  }
}, [taskId, reviewText])
```

- [ ] **Step 4: 验证 TypeScript 编译**

Run: `npx tsc --noEmit --pretty`
Expected: 零错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/GeneratePage.tsx
git commit -m "feat: wire onTypewriterProgress for incremental progress bar and phase hint"
```

---

### Task 5: 为 PhaseHint 文字添加呼吸感过渡

**Files:**
- Modify: `frontend/src/components/generate/WorkflowHUD.tsx`

- [ ] **Step 1: 添加数字跳动动画**

在 WorkflowHUD 中，将 phaseHint 渲染改为支持动态计数高亮。在 phaseRef 的渲染处增加计数器动画逻辑：

```typescript
// 新增 ref 用于追踪上一次的工序数
const lastCountRef = useRef<number | null>(null)

// 新增 effect：检测 phaseHint 中的数字变化并触发 pop 动画
useEffect(() => {
  // Extract count from phaseHint like "已完成 3 道工序" or "共 12 道工序"
  const match = phaseHint.match(/(\d+)\s*道/)
  if (!match) return
  const count = parseInt(match[1], 10)
  if (lastCountRef.current !== null && count !== lastCountRef.current && phaseRef.current) {
    // Trigger scale pop on the phase text
    gsap.fromTo(phaseRef.current,
      { scale: 1.03, color: '#f97316' },
      { scale: 1, color: '#334155', duration: 0.4, ease: 'back.out(1.7)' }
    )
  }
  lastCountRef.current = count
}, [phaseHint])
```

- [ ] **Step 2: 将 phase-hint-container 结构应用到渲染**

更新 phase hint 区域的 JSX（L353-368），添加呼吸光圈 layer：

```tsx
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
```

- [ ] **Step 3: 验证 TypeScript 编译**

Run: `npx tsc --noEmit --pretty`
Expected: 零错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/generate/WorkflowHUD.tsx
git commit -m "feat: add breathing glow and counter pop animation to phase hint"
```

---

### Task 6: 端到端验证

**Files:**
- Verify: all modified files

- [ ] **Step 1: 完整 TypeScript 编译检查**

```bash
npx tsc --noEmit --pretty
```
Expected: 零错误

- [ ] **Step 2: 启动开发服务器并手动测试**

```bash
npm run dev
```

验证场景：
1. **首次上传** — 文件上传后，进度条 0→50→60，流式阶段进度 60→85 逐步增长，PhaseHint 显示 "已完成 N 道工序，共 M 道"
2. **确认继续** — tab 自动切换到 process，typing row 开始打字，进度从 60 开始
3. **重新生成** — 进度回退到 40，然后走完完整流程
4. **呼吸动画** — PhaseHint 区域的呼吸光圈在 busy 状态下持续 4s 周期涨落
5. **数字跳动** — 工序计数变化时数字有 scale pop 效果

- [ ] **Step 3: 检查 CSS contain 效果**

在浏览器 DevTools 中：
- 检查 `.tw-typing-row` 是否有 `contain: layout style`
- 检查 `.tw-typing-row td` 是否有 `contain: layout`
- 确认打字过程中已完成行不跳动

- [ ] **Step 4: Commit 最终调整**

```bash
git add -A
git commit -m "chore: final adjustments after e2e verification"
```
