# 响应式布局重设计 Spec

> 前端 4 页面 + 4 子组件的布局审阅与改进方案

---

## 1. 概述

| 项 | 值 |
|---|---|
| 范围 | HistoryPage, DbPage, ZipPage, GeneratePage + 4 子组件 |
| 目标 | 添加响应式断点，修复窄屏布局问题 |
| 技术 | Tailwind CSS 响应式类（`sm:`/`md:`/`lg:`）+ CSS transition |
| 不做 | 不改字体、不换图标、不改配色、不重构 querySelector |

---

## 2. HistoryPage 改动

### 2.1 统计卡片响应式 (H1)

**当前**: `grid grid-cols-4 gap-3`
**改为**: `grid grid-cols-2 lg:grid-cols-4 gap-3`

同时改进卡片内部布局：
- 宽屏保持当前上下结构（图标+标签在上，数字在下）
- 窄屏改为左右结构（图标在左，文字在右），用 `flex-row` + `items-center`

### 2.2 快照弹窗窄屏适配 (H2)

**当前**: 左侧 `flex-1` + 右侧固定 `w-[320px]`，flex-row
**改为**:
- 宽屏保持 `flex-row` + `w-[320px]`
- 窄屏（`<768px`）改为 `flex-col`，详情面板移到图片下方
- 弹窗 max-width 和 padding 加响应式

### 2.3 表格窄屏转卡片列表 (H3)

**当前**: 固定列宽 `th style={{ width: ... }}`
**改为**:
- 宽屏保持表格
- 窄屏隐藏表格，改为卡片列表布局（每条记录一张卡片，信息垂直排列）
- 用 `hidden md:block`（表格）和 `md:hidden`（卡片）切换

### 2.4 GSAP hover 动画优化 (H4)

**当前**: `handleRowHover` 用 GSAP 动画 `backgroundColor`
**改为**: 移除 `backgroundColor` 动画，只保留 `scale: 1.005` 的 transform 动画

---

## 3. DbPage 改动

### 3.1 三栏布局窄屏适配 (D1)

**当前**: 左栏 `w-[220px]` + 中栏 `w-[35%]` 或 `flex-1` + 右栏 `flex-1`
**改为**:
- 宽屏（`lg:`）保持三栏不变
- 窄屏（`<lg`）：筛选面板整体移到工具栏的 Disclosure 面板中
  - 工具栏新增"筛选"按钮，点击展开/收起筛选表单
  - 展开时筛选表单在工具栏下方绝对定位，带白色背景 + shadow + 圆角
  - 点击外部或再次点击按钮关闭
  - 用 `useState` 控制展开状态，不需要第三方库
- 窄屏主体变为两栏：中栏列表 + 右栏详情
- 中栏在无详情时 `flex-1`，有详情时 `w-[35%]`（与当前逻辑一致）

### 3.2 编辑表单响应式 (D3)

**当前**: `grid grid-cols-2 gap-3`
**改为**: `grid grid-cols-1 md:grid-cols-2 gap-3`

### 3.3 统计卡片响应式 (D5)

**当前**: `grid grid-cols-3 gap-3`
**改为**: `grid grid-cols-1 sm:grid-cols-3 gap-3`

---

## 4. ZipPage 改动

### 4.1 Hero 区域响应式 (Z1)

**当前**: `gridTemplateColumns: 'minmax(320px, 1.1fr) minmax(320px, 0.9fr)'`
**改为**: Tailwind 响应式类 `grid grid-cols-1 lg:grid-cols-2 gap-4`

### 4.2 匹配卡片响应式 (Z2)

**当前**: `grid grid-cols-2 gap-3`（已有记录 vs 本次导入）
**改为**: `grid grid-cols-1 md:grid-cols-2 gap-3`

### 4.3 未匹配项响应式 (Z3)

**当前**: `grid grid-cols-2 gap-3`（其他文件 vs 未匹配 PDF）
**改为**: `grid grid-cols-1 md:grid-cols-2 gap-3`

---

## 5. GeneratePage 改动

### 5.1 工作台最小宽度 (G5)

**当前**: `gridTemplateColumns: 'minmax(400px, 1fr) minmax(480px, 1.2fr)'`
**改为**: `gridTemplateColumns: 'minmax(280px, 1fr) minmax(320px, 1.2fr)'`

保持双栏，但允许更窄的最小宽度。

### 5.2 Tab 切换动画 (G6)

**当前**: `document.querySelector('.tab-panel-active')` + GSAP `fromTo`（class 不存在，动画不生效）
**改为**: 移除 GSAP 动画，用 CSS transition 处理 tab 切换的 opacity 变化

---

## 6. 不改动项

| 项 | 原因 |
|---|------|
| querySelector 反模式 (G2/W1) | 每个页面只有一个实例，不会冲突 |
| UploadPanel 工具栏 (U1) | flex-wrap 自动换行已够用 |
| 字体/配色/图标 | 不在本次范围 |
| ReviewPanel/ProcessPanel 列宽 | 使用频率低，不需要响应式 |

---

## 7. 断点规范

统一使用 Tailwind 默认断点：

| 断点 | 宽度 | 用途 |
|------|------|------|
| 默认 | <640px | 手机 — 单列布局 |
| `sm:` | ≥640px | 大手机/小平板 |
| `md:` | ≥768px | 平板 — 表格可见、双栏开始 |
| `lg:` | ≥1024px | 笔记本 — 三栏布局、完整工具栏 |
| `xl:` | ≥1280px | 桌面 — 默认布局 |

关键切换点：
- **表格 ↔ 卡片**: `md:` (768px)
- **双栏 ↔ 单栏**: `lg:` (1024px)
- **三栏 ↔ 两栏**: `lg:` (1024px)

---

## 8. 文件变更清单

| 文件 | 改动 |
|------|------|
| `src/pages/HistoryPage.tsx` | H1 统计卡片响应式, H2 弹窗响应式, H3 表格→卡片, H4 hover 动画 |
| `src/pages/DbPage.tsx` | D1 筛选弹出层, D3 表单响应式, D5 统计卡片响应式 |
| `src/pages/ZipPage.tsx` | Z1 Hero 响应式, Z2 匹配卡片响应式, Z3 未匹配项响应式 |
| `src/pages/GeneratePage.tsx` | G5 工作台最小宽度, G6 Tab 动画改 CSS |
| `src/index.css` | 可能需要添加筛选弹出层的样式 |

---

*最后更新：2026-06-13*
