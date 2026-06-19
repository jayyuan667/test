# 响应式布局重设计 Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为前端 4 个页面添加 Tailwind 响应式断点，修复窄屏布局问题

**Architecture:** 纯 CSS 响应式改动，使用 Tailwind `sm:`/`md:`/`lg:` 断点类。DbPage 筛选用 Disclosure 面板模式。不改组件结构，只改 className 和少量 inline style。

**Tech Stack:** React 18 + TypeScript + Tailwind CSS 3 + GSAP 3

---

## 文件变更总览

| 文件 | 改动 |
|------|------|
| `src/pages/HistoryPage.tsx` | H1 统计卡片, H2 弹窗, H3 表格→卡片, H4 hover |
| `src/pages/DbPage.tsx` | D1 筛选 Disclosure, D3 表单, D5 统计卡片 |
| `src/pages/ZipPage.tsx` | Z1 Hero, Z2 匹配卡片, Z3 未匹配项 |
| `src/pages/GeneratePage.tsx` | G5 最小宽度, G6 Tab 动画 |
| `src/index.css` | Disclosure 面板样式 |

---

### Task 1: HistoryPage — 统计卡片响应式 (H1)

**Files:**
- Modify: `src/pages/HistoryPage.tsx:336`

- [ ] **Step 1: 统计卡片 grid 加响应式断点**

将第 336 行：
```tsx
<div ref={statsRef} className="grid grid-cols-4 gap-3 shrink-0">
```
改为：
```tsx
<div ref={statsRef} className="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">
```

- [ ] **Step 2: 统计卡片内部布局加响应式**

将第 337-355 行的卡片渲染改为窄屏左右结构。找到 `statCards.map` 中的卡片 div（约第 338-355 行），将内部布局从固定上下结构改为响应式：

将：
```tsx
<div
  key={stat.label}
  ref={el => { statCardsRef.current[index] = el }}
  className={`stat-card card-solid !p-4 cursor-default transition-all duration-200 ${stat.bgColor}`}
  onMouseEnter={() => handleStatCardHover(index, true)}
  onMouseLeave={() => handleStatCardHover(index, false)}
>
  <div className="flex items-center justify-between mb-2">
    <span className="text-[20px]">{stat.icon}</span>
    <span className={`text-[11px] font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`}>
      {stat.label}
    </span>
  </div>
  <div className="text-[28px] font-extrabold text-slate-800 leading-none">
    {stat.value}
  </div>
</div>
```
改为：
```tsx
<div
  key={stat.label}
  ref={el => { statCardsRef.current[index] = el }}
  className={`stat-card card-solid !p-4 cursor-default transition-all duration-200 ${stat.bgColor} flex flex-row lg:flex-col items-center lg:items-stretch gap-3 lg:gap-0`}
  onMouseEnter={() => handleStatCardHover(index, true)}
  onMouseLeave={() => handleStatCardHover(index, false)}
>
  <div className="flex items-center justify-between mb-0 lg:mb-2 flex-1 lg:flex-none">
    <span className="text-[20px]">{stat.icon}</span>
    <span className={`text-[11px] font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent hidden lg:inline`}>
      {stat.label}
    </span>
  </div>
  <div className="text-[22px] lg:text-[28px] font-extrabold text-slate-800 leading-none">
    {stat.value}
  </div>
</div>
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 零错误

- [ ] **Step 4: Commit**

```bash
git add src/pages/HistoryPage.tsx
git commit -m "feat(history): 统计卡片响应式 grid-cols-4→2 + 窄屏左右布局"
```

---

### Task 2: HistoryPage — 快照弹窗窄屏适配 (H2)

**Files:**
- Modify: `src/pages/HistoryPage.tsx:493,533`

- [ ] **Step 1: 弹窗 body 改为响应式方向**

找到第 493 行的弹窗 body：
```tsx
<div className="flex-1 min-h-0 overflow-auto flex">
```
改为：
```tsx
<div className="flex-1 min-h-0 overflow-auto flex flex-col md:flex-row">
```

- [ ] **Step 2: 右侧详情面板加响应式宽度**

找到第 533 行：
```tsx
<div className="w-[320px] shrink-0 overflow-auto p-4 flex flex-col gap-4">
```
改为：
```tsx
<div className="w-full md:w-[320px] shrink-0 overflow-auto p-4 flex flex-col gap-4 border-t md:border-t-0 md:border-l border-slate-200">
```

- [ ] **Step 3: 左侧图片区域加响应式**

找到第 495 行：
```tsx
<div className="flex-1 min-w-0 border-r border-slate-200 flex flex-col items-center justify-center p-4 bg-slate-50">
```
改为：
```tsx
<div className="flex-1 min-w-0 md:border-r border-slate-200 flex flex-col items-center justify-center p-4 bg-slate-50">
```

- [ ] **Step 4: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add src/pages/HistoryPage.tsx
git commit -m "feat(history): 快照弹窗窄屏上下布局 flex-col md:flex-row"
```

---

### Task 3: HistoryPage — 表格窄屏转卡片列表 (H3)

**Files:**
- Modify: `src/pages/HistoryPage.tsx:387-460`

- [ ] **Step 1: 在表格 div 前添加卡片列表（窄屏可见）**

找到第 387 行 `<div className="flex-1 min-h-0 overflow-auto">`，在其内部、`<table>` 之前，添加卡片列表视图：

在 `<table>` 之前插入：
```tsx
{/* Mobile card list */}
<div className="md:hidden flex flex-col gap-2">
  {pageItems.map(h => {
    const isDone = h.progress >= 100
    return (
      <div
        key={h.task_id}
        className="rounded-xl border border-slate-200 bg-white p-3.5"
      >
        <div className="flex items-start justify-between mb-2">
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-semibold text-slate-800 truncate">{h.pdf_name || h.task_id}</div>
            <div className="text-[11px] text-slate-400 mt-0.5 font-mono">{h.task_id}</div>
          </div>
          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold shrink-0 ml-2 ${isDone ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
            {isDone ? '已完成' : '待审阅'}
          </span>
        </div>
        <div className="text-[11px] text-slate-500 mb-2">
          {formatDate(h.completed_at || h.created_at)}
          {h.file_count != null ? ` · 已输出 ${h.file_count} 条工序` : ''}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={selected.has(h.task_id)}
            onChange={() => toggleSelect(h.task_id)}
            className="rounded accent-flame-500"
          />
          <button
            className="btn btn-ghost !text-[11px] !py-1 !px-2.5 !text-blue-600"
            onClick={() => openSnapshot(h.task_id)}
          >
            查看快照
          </button>
          <button
            className="btn btn-ghost !text-[11px] !py-1 !px-2 !text-red-400 ml-auto"
            disabled={deleting === h.task_id}
            onClick={() => handleDelete(h.task_id)}
          >
            {deleting === h.task_id ? '删除中...' : '删除'}
          </button>
        </div>
      </div>
    )
  })}
</div>
```

- [ ] **Step 2: 表格加 hidden md:block**

找到第 387 行的表格容器 div 和 table：
将：
```tsx
          <div className="flex-1 min-h-0 overflow-auto">
            <table className="data-table">
```
改为：
```tsx
          <div className="hidden md:block flex-1 min-h-0 overflow-auto">
            <table className="data-table">
```

这样表格容器在窄屏隐藏（`hidden`），宽屏显示（`md:block`）。卡片列表（Step 1 添加的 `md:hidden`）在窄屏显示，宽屏隐藏。两者通过 `md:` 断点切换。

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add src/pages/HistoryPage.tsx
git commit -m "feat(history): 窄屏表格转卡片列表 md:block/hidden"
```

---

### Task 4: HistoryPage — GSAP hover 动画优化 (H4)

**Files:**
- Modify: `src/pages/HistoryPage.tsx:132-148`

- [ ] **Step 1: 移除 backgroundColor 动画**

将第 132-148 行：
```tsx
const handleRowHover = (e: React.MouseEvent<HTMLTableRowElement>, isEnter: boolean) => {
    const row = e.currentTarget
    if (isEnter) {
      gsap.to(row, {
        backgroundColor: '#f8fafc',
        scale: 1.005,
        duration: 0.2,
        ease: 'power1.out',
      })
    } else {
      gsap.to(row, {
        backgroundColor: '#ffffff',
        scale: 1,
        duration: 0.2,
        ease: 'power1.out',
      })
    }
  }
```
改为：
```tsx
const handleRowHover = (e: React.MouseEvent<HTMLTableRowElement>, isEnter: boolean) => {
    const row = e.currentTarget
    gsap.to(row, {
      scale: isEnter ? 1.005 : 1,
      duration: 0.2,
      ease: 'power1.out',
    })
  }
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/HistoryPage.tsx
git commit -m "fix(history): hover 动画移除 backgroundColor，只保留 transform"
```

---

### Task 5: DbPage — 筛选面板 Disclosure (D1)

**Files:**
- Modify: `src/pages/DbPage.tsx:413-462,485-540`

- [ ] **Step 1: 添加 Disclosure 状态**

在 DbPage 组件的 state 声明区域（约第 34 行附近）添加：
```tsx
const [filterOpen, setFilterOpen] = useState(false)
```

- [ ] **Step 2: 工具栏添加筛选按钮（窄屏可见）**

在工具栏的左侧按钮组（第 415-433 行）中，在"重置筛选"按钮之前添加：
```tsx
<button
  className="btn btn-ghost !text-[12px] lg:hidden"
  onClick={() => setFilterOpen(o => !o)}
>
  <span className="flex items-center gap-1.5">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" /></svg>
    筛选
  </span>
</button>
```

- [ ] **Step 3: 筛选面板加响应式类**

找到第 487 行的筛选面板：
```tsx
<div ref={filterRef} className="w-[220px] shrink-0 card-solid flex flex-col gap-3 overflow-auto">
```
改为：
```tsx
<div ref={filterRef} className="hidden lg:flex w-[220px] shrink-0 card-solid flex-col gap-3 overflow-auto">
```

- [ ] **Step 4: 添加 Disclosure 筛选面板（窄屏可见）**

在工具栏 div（第 462 行 `</div>`）之后、统计卡片 div 之前，添加：
```tsx
{/* Filter disclosure panel (mobile) */}
{filterOpen && (
  <div className="lg:hidden relative shrink-0">
    <div className="absolute inset-x-0 top-0 z-50 bg-white rounded-xl border border-slate-200 shadow-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="text-[12px] font-bold text-slate-500">筛选条件</div>
        <button className="btn btn-ghost !p-1 !text-[14px]" onClick={() => setFilterOpen(false)}>&times;</button>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[11px] font-semibold text-slate-500">模型编号/关键词</label>
        <input
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 focus:ring-1 focus:ring-flame-glow transition-all"
          placeholder="搜索模型编号、工艺内容、摘要"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { handleApplyFilter(); setFilterOpen(false) } }}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[11px] font-semibold text-slate-500">产品类型</label>
        <select
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[12px] text-slate-700 focus:outline-none focus:border-flame-400 transition-all"
          value={filterProductType}
          onChange={e => setFilterProductType(e.target.value)}
        >
          <option value="">全部</option>
          {productTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div className="flex gap-2 mt-1">
        <button className="btn btn-primary !text-[11px] !py-2 flex-1" onClick={() => { handleApplyFilter(); setFilterOpen(false) }}>应用筛选</button>
        <button className="btn btn-ghost !text-[11px] !py-2" onClick={() => { handleResetFilter(); setFilterOpen(false) }}>重置</button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 5: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add src/pages/DbPage.tsx
git commit -m "feat(db): 筛选面板响应式 — 窄屏 Disclosure + 宽屏侧栏"
```

---

### Task 6: DbPage — 编辑表单 + 统计卡片响应式 (D3, D5)

**Files:**
- Modify: `src/pages/DbPage.tsx:465,662,723`

- [ ] **Step 1: 统计卡片加响应式断点**

将第 465 行：
```tsx
<div ref={statsRef} className="grid grid-cols-3 gap-3 shrink-0">
```
改为：
```tsx
<div ref={statsRef} className="grid grid-cols-1 sm:grid-cols-3 gap-3 shrink-0">
```

- [ ] **Step 2: 详情模式 info grid 响应式**

将第 662 行：
```tsx
<div className="grid grid-cols-2 gap-3">
```
改为：
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
```

- [ ] **Step 3: 编辑模式表单响应式**

将第 723 行：
```tsx
<div className="grid grid-cols-2 gap-3">
```
改为：
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
```

- [ ] **Step 4: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add src/pages/DbPage.tsx
git commit -m "feat(db): 统计卡片 sm:grid-cols-3 + 表单 md:grid-cols-2 响应式"
```

---

### Task 7: ZipPage — Hero + 卡片响应式 (Z1, Z2, Z3)

**Files:**
- Modify: `src/pages/ZipPage.tsx:262,537,574`

- [ ] **Step 1: Hero 区域响应式**

将第 262 行：
```tsx
<div ref={heroRef} className="grid gap-4" style={{ gridTemplateColumns: 'minmax(320px, 1.1fr) minmax(320px, 0.9fr)' }}>
```
改为：
```tsx
<div ref={heroRef} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
```

- [ ] **Step 2: 匹配卡片响应式**

将第 537 行：
```tsx
<div className="grid grid-cols-2 gap-3 mb-3">
```
改为：
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
```

- [ ] **Step 3: 未匹配项响应式**

将第 574 行：
```tsx
<div className="grid grid-cols-2 gap-3">
```
改为：
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
```

- [ ] **Step 4: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add src/pages/ZipPage.tsx
git commit -m "feat(zip): Hero 单列 + 匹配/未匹配卡片响应式 grid-cols-1 md:grid-cols-2"
```

---

### Task 8: GeneratePage — 最小宽度 + Tab 动画 (G5, G6)

**Files:**
- Modify: `src/pages/GeneratePage.tsx:78-86,288`

- [ ] **Step 1: 工作台最小宽度减小**

将第 288 行：
```tsx
<div ref={workbenchRef} className="flex-1 min-h-0 grid gap-4 items-stretch" style={{ gridTemplateColumns: 'minmax(400px, 1fr) minmax(480px, 1.2fr)' }}>
```
改为：
```tsx
<div ref={workbenchRef} className="flex-1 min-h-0 grid gap-4 items-stretch" style={{ gridTemplateColumns: 'minmax(280px, 1fr) minmax(320px, 1.2fr)' }}>
```

- [ ] **Step 2: Tab 切换动画改用 CSS**

将第 78-86 行的 GSAP tab 动画：
```tsx
// GSAP: Tab switch animation
useEffect(() => {
    const panel = document.querySelector('.tab-panel-active')
    if (panel) {
      gsap.fromTo(panel,
        { opacity: 0, x: 10 },
        { opacity: 1, x: 0, duration: 0.3, ease: 'power2.out' }
      )
    }
  }, [activeTab])
```
改为：
```tsx
// Tab switch — CSS transition handles opacity via .tab-panel-active class
```

然后在 tab 内容区域添加 CSS transition。找到第 300-314 行的 tab 内容：
```tsx
<div className="flex-1 min-h-0 p-5 flex flex-col">
  {activeTab === 'review' ? (
    <ReviewPanel ... />
  ) : (
    <ProcessPanel ... />
  )}
</div>
```
改为：
```tsx
<div className="flex-1 min-h-0 p-5 flex flex-col transition-opacity duration-200">
  {activeTab === 'review' ? (
    <ReviewPanel ... />
  ) : (
    <ProcessPanel ... />
  )}
</div>
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add src/pages/GeneratePage.tsx
git commit -m "feat(generate): 工作台最小宽度 280/320 + Tab 动画改 CSS transition"
```

---

### Task 9: 最终验证 + 统一提交

- [ ] **Step 1: TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 零错误

- [ ] **Step 2: 检查所有改动**

```bash
git diff --stat
```

Expected: 只有 4 个页面文件改动

- [ ] **Step 3: 如有遗漏，补充提交**

```bash
git add -A && git commit -m "chore: 响应式布局重设计 — 全部完成"
```
