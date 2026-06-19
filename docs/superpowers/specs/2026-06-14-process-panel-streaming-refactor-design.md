# ProcessPanel 流式输出重构 — 消除割裂感 & 进度条优化

**日期**: 2026-06-14
**状态**: 设计中
**关联**: GeneratePage.tsx, ProcessPanel.tsx

---

## 问题清单

| # | 问题 | 根因 |
|---|------|------|
| A | 行高跳变 — 打字行消失→completed row 出现时高度瞬变 | typing row 与 regular row DOM/样式不同，同一 render 内 remove+insert |
| B | 文字闪烁 — 每字符 setTypingText 触发全表重渲染 | React reconciliation 可能重建 DOM 节点而非复用 |
| C | 长内容炸开 — content 字段多行时周围行视觉位置浮动 | tableLayout:fixed 只固定列宽不固定行高，无布局隔离 |
| D | 进度跳跃 — 60→90 之间无增量 | typewriter 阶段无进度回调，只有 onComplete 才跳变 |
| E | PhaseHint 静态 — 流式阶段文字长时间不变 | 仅 setPhaseHint 设置一次，无后续更新 |

---

## 方案概述

**方案 1: React.memo 隔离 + CSS contain**（选定）

核心思路：把 typewriter 逻辑抽成独立 `TypingRow` 组件，React 重渲染只影响这一行。配合 CSS `contain: layout` 隔离布局，invisible placeholder 预占空间，`onTypewriterProgress` 回调驱动进度条。

## 组件拆分

### 拆分前

```
ProcessPanel.tsx  588 lines
├── parseLine / parseStreamingRows (utils)
├── tradeBadgeClass (utils)
├── ProcessPanel component
│   ├── Props: result, taskId, runToken, streamingChunks, reviewText
│   ├── 15 useRef, 5 useState, 2 useMemo, 4 useEffect
│   ├── typeField / typeRow / kickTyping (打字逻辑混在父组件)
│   ├── 编辑回调 (add/insert/delete/cellEdit)
│   └── JSX: header + table + typing row
```

### 拆分后

```
ProcessPanel.tsx  ~350 lines
├── parseLine / parseStreamingRows
├── tradeBadgeClass
├── TypingRow component  ← 新文件 (~180 lines)
│
├── ProcessPanel component
│   ├── Props: result, taskId, runToken, streamingChunks, reviewText
│   │         onTypewriterProgress  ← 新增
│   ├── displayedRows 管理
│   ├── 编辑回调
│   ├── 渲染分支
│   └── JSX: <TypingRow ref={typingRef} onComplete={...} onProgress={...} />
```

### TypingRow 接口

```typescript
interface TypewriterProgress {
  displayed: number
  queued: number
  currentRow?: { code: string; trade: string; content: string }
  currentChar: number
  currentTotal: number
}

interface TypingRowHandle {
  enqueue: (row: ProcessRow) => void
  reset: () => void
}

interface TypingRowProps {
  onComplete: (row: ProcessRow) => void
  onProgress?: (info: TypewriterProgress) => void
}

// React.forwardRef + useImperativeHandle + React.memo
const TypingRow = React.memo(React.forwardRef<TypingRowHandle, TypingRowProps>(...))
```

### 关键设计决策

| 决策 | 说明 |
|------|------|
| TypingRow 是独立文件 | `TypingRow.tsx`，ProcessPanel 同级目录。所有打字逻辑内聚 |
| forwardRef + imperative handle | 父组件通过 `typingRef.current.enqueue(row)` 入队，不触发父组件 render |
| 队列用内部 Ref 管理 | `queueRef`、`isActiveRef` 完全在 TypingRow 内部，父组件不关心 |
| React.memo 包裹 | 新 row 入队时才触发 useEffect 开始打字链 |
| 打字完成不移除 DOM | TypingRow 始终挂载，完成时添加 `.completing` class 过渡后清空内容等待下一行 |

---

## TypingRow 内部状态机

```
idle ──(enqueue)──▶ typing_code ──▶ typing_trade ──▶ typing_content ──▶ done ──(队列非空)──▶ typing_code
                       │                │                  │                │
                    setField          setField           setField         onComplete(row)
                    typeField()       typeField()        typeField()      检查队列
```

### typeField 打字核心

```
typeField(text, speed, onDone):
  - fast:  8-26ms/char (code, trade, content前30字符)
  - slow: 30-80ms/char (content 30字符之后)
  - 递归 setTimeout，每字符 setTypingText
  - 到末尾调用 onDone
```

### 分段速度策略

content 字段前 30 字符用 fast 速度，之后切换到 slow。避免长内容时用户等太久。

### Cleanup

| 场景 | 动作 |
|------|------|
| 组件卸载 | useEffect cleanup: clearTimeout + isActiveRef = false |
| runToken 变化 | 父组件调用 `typingRef.current.reset()` → 清空队列 + 清除定时器 + 重置 state |
| 正常流程 | 当前行自然完成 → onComplete → 队列取下一行 |

---

## CSS 修复方案

### 修复矩阵

| 问题 | CSS 手段 | 位置 |
|------|---------|------|
| A: 行高跳变 | `tableLayout: fixed` + `contain: layout` | `<table>` + `<tr>` |
| B: 文字闪烁 | invisible placeholder + `will-change: transform` | 每个 `<td>` 内 span |
| C: 长内容炸开 | placeholder 预占全部文本空间 + `contain: layout` | content 列 |

### tableLayout: fixed

```html
<table style="tableLayout: fixed; width: 100%">
  <colgroup>
    <col style="width: 60px" />   <!-- 序号 -->
    <col style="width: 100px" />  <!-- 工序代码 -->
    <col style="width: 100px" />  <!-- 工种 -->
    <col style="width: auto" />   <!-- 内容 (弹性) -->
  </colgroup>
</table>
```

### contain: layout

```css
.tw-typing-row {
  contain: layout style;
}
.tw-typing-row td {
  contain: layout;
  overflow-anchor: none;
}
```

创建布局围栏：此 tr 内部变化不触发兄弟 tr 的重新布局计算。

### Invisible Placeholder

```html
<td style="contain: layout">
  <span style="position: relative; display: block;">
    <!-- Layer 1: 隐形占位 (预占最终空间) -->
    <span style="visibility: hidden; white-space: pre-wrap; word-break: break-word;">
      {fullText}
    </span>
    <!-- Layer 2: 可见打字文本 (absolute 覆盖) -->
    <span style="position: absolute; left: 0; top: 0; will-change: transform;">
      {typedText}<span class="typing-cursor">▍</span>
    </span>
  </span>
</td>
```

placeholder 确保 td 高度从第一帧就是最终高度，打字过程行高不变。

### 行完成过渡

```css
.tw-typing-row.completing .typing-cursor { opacity: 0; transition: opacity 150ms; }
.tw-typing-row.completing { transition: background-color 300ms ease; }
```

### 已知风险

- `contain: layout` 在 `<tr>` 上的浏览器兼容性 (Chrome 良好，Firefox/Safari 需验证)
- invisible placeholder 中英混排时宽度预占可能有偏差
- 如果 CSS 方案在实测中效果不佳，备选：completed row 用 CSS transition 从 typing 样式渐变到正常样式，避免 remove+insert

---

## 进度条设计

### 进度映射

```
0 ──→ 50 ──→ 60 ──→ ──→ 85 ──→ 90 ──→ 100
上传   后端   确认   流式   SSE    收尾
      处理   锚点   输出   complete 动画
```

| 区间 | 触发者 | 说明 |
|------|--------|------|
| 0→50 | SSE onStepStart/onStepComplete | 上传+后端处理 |
| 50→60 | SSE onReviewRequired | 特征审阅阶段 |
| 60 | handleConfirmReview / handleRerun | 确认锚点 |
| 60→85 | onTypewriterProgress | `60 + displayed/total * 25` |
| 85→90 | SSE onComplete | 后端处理完成 |
| 90→100 | setTimeout / GSAP | Typewriter 收尾动画 |

### onTypewriterProgress 集成

```typescript
<ProcessPanel
  onTypewriterProgress={(info) => {
    const { displayed, queued, currentRow } = info
    const total = displayed + queued + (currentRow ? 1 : 0)
    if (total > 0) {
      setProgress(60 + Math.round((displayed / total) * 25))
    }
    // PhaseHint 更新在此处
  }}
/>
```

`onProcessStream` 不再直接设 progress，完全交给 typewriter 回调驱动。

### GeneratePage 各 handler 进度设置

| Handler | progress |
|---------|----------|
| onStepStart | `step/totalSteps * 50` |
| onReviewRequired | 50 |
| handleConfirmReview | 60 |
| handleRerun | 40 (回退) |
| onProcessStream | 不设 progress |
| onComplete | 90 |

### 边界情况

| 场景 | 处理 |
|------|------|
| 行数少 (1-2行) | 每行占比大，60→85 跳变明显但可接受 |
| SSE complete 先于 typewriter | progress 已在 85+，onComplete 设 90 |
| typewriter 先于 SSE complete | progress 在 85，等待 onComplete |
| rerun | 40 → onReviewRequired(50) → handleRerun(60) → 流式 → 正常收尾 |

---

## PhaseHint 思维链 & 呼吸感

### 文案序列

| 阶段 | 静态文字 | 动态部分 |
|------|---------|---------|
| 上传 | 正在解析图纸特征 | — |
| 审阅 | 请审阅识别结果，确认后继续 | — |
| 确认后等待 | 特征已确认，等待后端响应 | 呼吸光圈表示等待中 |
| 流式生成 | 正在生成工艺规程 | 已完成 **N** 道，待生成 **M** 道 |
| 流式收尾 | 工艺内容生成完成 | 共 **N** 道工序 |
| 完成 | 工艺生成完成 | 共 **N** 道工序 |

### 三层呼吸结构

| 层 | 内容 | 动画 |
|---|------|------|
| 光圈背景 | 渐变色光圈 | GSAP, 4s 周期涨落, sine.inOut |
| 状态圆点 | ● 指示点 | 与光圈同步，0.2s 偏移 |
| 文字 | 静态文字 + 动态数字 | 数字 scale pop (1→1.3→1, 300ms, back.out)，阶段切换 crossfade 400ms |

### 设计决策

| 决策 | 原因 |
|------|------|
| **不做**当前打字行提示 | 表格里已在逐字打字，phaseHint 再做是信息冗余，切换太快破坏呼吸节奏 |
| 数字用 scale pop | 与呼吸光圈的涨落形成呼应，视觉语言统一 |
| 阶段切换用 crossfade | 整句替换用 scale 太剧烈，crossfade 更安静 |
| 呼吸周期 4s | 接近成人静息呼吸频率 (12-20次/分)。太快像警报，太慢像卡死 |

### 已知风险

- GSAP timeline 在 streaming 高频 React render 下可能被冲掉。备选：CSS animation 替代，用 `animation-play-state` 控制
- PhaseHint 更新在 onTypewriterProgress 回调中，每字符触发，需节流到 500ms 避免过度渲染

---

## 防卡死策略

1. **行内字符级进度**：`onTypewriterProgress` 增加 `currentChar/currentTotal`，每打几个字符就更新进度条，不等整行完成
2. **Tab 队列深度**：标签显示 "工艺规程 (3/12)"，用户直接看到排队数量增长
3. **分段速度**：content 前 30 字符 fast，之后 slow
4. **不做假进度**：真实反映比虚假前进更可信

---

## 影响范围

| 文件 | 变更 |
|------|------|
| `frontend/src/components/generate/TypingRow.tsx` | **新建** — 独立打字行组件 (~180 lines) |
| `frontend/src/components/generate/ProcessPanel.tsx` | 移除打字逻辑，引入 TypingRow，新增 onTypewriterProgress (~350 lines) |
| `frontend/src/pages/GeneratePage.tsx` | 新增 onTypewriterProgress 回调，phaseHint 动态更新逻辑 |
| `frontend/src/index.css` | 新增 `.tw-typing-row` contain 样式、呼吸动画 keyframes、`.phase-hint-*` 样式 |

---

## 实施顺序

1. 创建 TypingRow 组件（纯逻辑，无 CSS）
2. ProcessPanel 集成 TypingRow，验证 typewriter 功能正常
3. 添加 CSS contain + tableLayout:fixed + invisible placeholder
4. 添加 onTypewriterProgress → 进度条渐进
5. 添加 PhaseHint 呼吸动画
6. 端到端测试：首次上传、确认继续、重新生成
