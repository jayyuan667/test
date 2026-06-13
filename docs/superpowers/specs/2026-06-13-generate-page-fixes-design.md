# GeneratePage 四项修复设计

> 工艺生成页第二轮修复设计文档
> 日期：2026-06-13

---

## 1. 问题概览

| # | 问题 | 根因 | 修复方向 |
|---|------|------|---------|
| 1 | Ctrl+滚轮触发浏览器整体缩放 | wheel 事件 passive，无法 preventDefault | 原生 addEventListener + passive: false |
| 2 | 标注页面细节与 H5 差距大 | 缺少自定义类型、侧栏拖拽/折叠、分类折叠 | 逐步对齐 H5 功能 |
| 3 | 审阅面板关键字段显示空白 | NOISE_LABELS 误杀零件名称等字段 | 改为白名单过滤 |
| 4 | 流式输出闪烁 + 不自动滚动 | GSAP 对所有行重复触发 + 无 auto-scroll | GSAP 仅作用新行 + scrollIntoView |

---

## 2. 修复 1：Ctrl+滚轮缩放

### 2.1 根因分析

React 版通过 `onWheel` 合成事件绑定 handleWheel，React 合成事件默认 passive，调用 `e.preventDefault()` 无法阻止浏览器默认的 Ctrl+滚轮页面缩放行为。

### 2.2 修复方案

**wheel 事件绑定改为原生 addEventListener：**

```tsx
useEffect(() => {
  const el = scrollContainerRef.current
  if (!el) return
  const handler = (e: WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    // 现有的乘法 ×1.15 + 光标锚定逻辑
  }
  el.addEventListener('wheel', handler, { passive: false })
  return () => el.removeEventListener('wheel', handler)
}, [zoom])
```

**边界保护：**
- scroll 恢复时添加 `Math.max(0, targetLeft/Top)`
- 移除 fitToViewport 的 `Math.min(..., 1)` 限制，允许放大超过 100%

### 2.3 拖拽平移

**状态管理：**
```tsx
const [isPanning, setIsPanning] = useState(false)
const panStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })
```

**交互逻辑：**
1. mousedown（非 Ctrl）→ 记录起始位置，设 `isPanning = true`，cursor 改为 `grabbing`
2. mousemove → 计算偏移量，更新 `scrollLeft` / `scrollTop`
3. mouseup → 结束拖拽，cursor 恢复 `grab`
4. 拖拽期间禁用图片默认拖拽行为（`e.preventDefault()`）

**cursor 样式：**
- 默认：`grab`
- 拖拽中：`grabbing`
- Ctrl 按下时：`zoom-in`

---

## 3. 修复 2：标注页面增强

### 3.1 自定义添加标注类型

**交互流程：**
1. 标注工具栏末尾显示"+"按钮（添加标注）
2. 点击弹出 Modal：
   - 输入类型名称（必填）
   - 选择颜色（预设调色板 12 色 + 自定义 hex 输入）
   - 可选虚线样式（实线/虚线/点线）
3. 确认后新类型出现在工具栏
4. 内置类型（螺纹孔、铆钉孔等 10 种）不可删除
5. 自定义类型可通过长按/右键菜单删除

**数据结构：**
```typescript
interface CustomLabel {
  id: string          // uuid
  name: string        // 显示名，如 "特殊孔"
  color: string       // hex 颜色，如 "#3b82f6"
  dash?: string       // 可选：'solid' | 'dashed' | 'dotted'
  isCustom: true      // 区分内置和自定义
}
```

**持久化：** 保存到 `localStorage`，key 为 `annotation-custom-labels`

### 3.2 右侧栏拖拽 + 折叠

**拖拽调整宽度：**
- 右侧栏左边框添加 6px 宽的拖拽手柄区域
- mousedown 开始拖拽，mousemove 更新宽度，mouseup 结束
- 宽度限制：min 200px，max 500px
- cursor: `col-resize`

**折叠/展开：**
- 侧栏顶部标题栏添加折叠按钮（`<` / `>` 图标）
- 折叠后侧栏宽度为 0，只保留一个展开按钮悬浮在右边缘
- 展开时恢复上次宽度

**持久化：** 宽度和折叠状态保存到 `localStorage`

### 3.3 分类折叠/展开

- 右侧栏中每个标注类型是一个分组（Disclosure）
- 分组标题行显示：类型名 + 颜色指示 + 数量 badge + 折叠箭头
- 点击标题行切换折叠/展开
- 折叠状态下只显示标题行，展开显示该类型下的所有标注列表
- 默认全部展开，折叠状态持久化到 `localStorage`

---

## 4. 修复 3：审阅字段丢失

### 4.1 根因分析

`featureParser.ts` 的 `NOISE_LABELS` 是黑名单机制，包含 `零件名称`、`毛坯类型`、`图号`、`图号保留`，导致这些关键字段被静默过滤。

### 4.2 修复方案：改为白名单过滤

```typescript
// 之前（黑名单）
const NOISE_LABELS = new Set([
  '报告名称', '页数', '图号', '图号保留', '零件名称', '毛坯类型',
])

// 之后（只隐藏真正的元数据）
const HIDDEN_LABELS = new Set([
  '报告名称', '页数',
])
```

- 移除 `零件名称`、`毛坯类型`、`图号`、`图号保留` 的过滤
- 保留 `报告名称`、`页数` 的过滤（这些是文档元数据，不是零件特征）
- 保留页摘要正则过滤 `/^第\d+页摘要$/`
- 后续新增字段默认可见

### 4.3 边缘情况

字段值中包含 `【xxx】` 模式可能破坏解析。添加防护：
- 在正则匹配前，检查当前行是否已匹配到字段开头
- 如果值中包含 `【】`，将其转义后再解析

---

## 5. 修复 4：流式闪烁 + 自动滚动

### 5.1 修复闪烁

**根因：** 每次 `displayedRows` 变化，GSAP `fromTo` 作用于 `querySelectorAll('tbody tr')` 中的所有行，已有行被重复触发 opacity 0→1 动画。

**修复：**
```tsx
const animatedCountRef = useRef(0)

useEffect(() => {
  const rows = tableRef.current?.querySelectorAll('tbody tr')
  if (!rows || rows.length <= animatedCountRef.current) return

  // 只选择新增的行
  const newRows = Array.from(rows).slice(animatedCountRef.current)
  gsap.fromTo(newRows,
    { opacity: 0, y: 10 },
    { opacity: 1, y: 0, duration: 0.3, stagger: 0.05 }
  )
  animatedCountRef.current = rows.length
}, [displayedRows])
```

### 5.2 自动滚动到底部

**实现：**
```tsx
const scrollContainerRef = useRef<HTMLDivElement>(null)
const userScrolledRef = useRef(false)

// 监听用户手动滚动
const handleScroll = () => {
  const el = scrollContainerRef.current
  if (!el) return
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
  userScrolledRef.current = !atBottom
}

// 打字机完成一行后自动滚动
const scrollToBottom = () => {
  if (userScrolledRef.current) return
  scrollContainerRef.current?.scrollTo({
    top: scrollContainerRef.current.scrollHeight,
    behavior: 'smooth'
  })
}
```

**触发时机：**
1. 打字机完成一行 → `scrollToBottom()`
2. typing row 输入字符 → `scrollToBottom()`（仅在用户未手动滚动时）
3. 用户滚动到距离底部 50px 以内 → 重新启用自动滚动

---

## 6. 涉及文件清单

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/annotate/AnnotationPanel.tsx` | 原生 wheel 事件、拖拽平移、自定义类型工具栏 |
| `frontend/src/components/annotate/AnnotationSidebar.tsx` | 新建：右侧栏组件（拖拽、折叠、分类折叠） |
| `frontend/src/components/annotate/AddLabelModal.tsx` | 新建：添加标注类型弹窗 |
| `frontend/src/index.css` | 标注相关样式更新 |
| `frontend/src/utils/featureParser.ts` | NOISE_LABELS → HIDDEN_LABELS |
| `frontend/src/components/generate/ProcessPanel.tsx` | GSAP 仅新行动画 + auto-scroll |
| `frontend/src/components/generate/ReviewPanel.tsx` | 适配字段显示 |

---

## 7. 验证清单

- [ ] 标注页：Ctrl+滚轮仅缩放图片，工具栏和侧栏不受影响
- [ ] 标注页：拖拽图片可平移
- [ ] 标注页：点击"+"弹窗添加自定义标注类型
- [ ] 标注页：自定义类型出现在工具栏，可选中使用
- [ ] 标注页：右侧栏可拖拽调整宽度
- [ ] 标注页：右侧栏可折叠/展开
- [ ] 标注页：右侧栏中分类可折叠/展开
- [ ] 审阅页：零件名称、毛坯类型、图号正常显示
- [ ] 审阅页：编辑后序列化不丢失字段
- [ ] 工艺规程：流式输出已有行不闪烁
- [ ] 工艺规程：新行出现时自动滚动到底部
- [ ] 工艺规程：用户手动向上滚动后停止自动滚动
