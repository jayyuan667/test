# 工艺生成页 UX 优化设计文档

**日期**：2026-06-02  
**范围**：`updated_front/demo-industrial-console.html` · `updated_front/css/industrial-console.css` · `updated_front/js/demo-industrial-console.js`

---

## 一、代码清理（无视觉变化）

### 1.1 HTML 数据错误修复

| 位置 | 问题 | 修复 |
|------|------|------|
| `page-zip` 区域 chip，`SQLite：vector_map_new.db` | 旧库名残留 | 改为 `SQLite：2d-v.db` |
| `#processStepsList` 内 5 条 `.step-row` | 硬编码假工艺数据写死在 HTML 中 | 清空，保留空容器由 JS 填充 |
| `#editorTextarea` 内硬编码文本 | 同上 | 清空 |
| `#closeDbPreviewModal` 按钮上的 `onclick="..."` | 内联事件处理器 | 删除 `onclick`，改在 JS 中用 `addEventListener` 统一管理 |

### 1.2 JS 死代码清理

删除以下变量和函数（所引用的 DOM 元素均不存在于 HTML，始终为 `null`）：

**死变量**
- `demoStatusValue` / `demoHitValue` / `demoStepValue` / `demoResultChip`（`getElementById` 返回 null）
- `workflowLiveBadge = null`
- `workflowLiveStream = null`
- `workflowPhase`（HTML 中不存在）
- `taskPreviewImage` / `taskPreviewEmpty` / `taskPreviewCounter` / `taskPreviewZoomLabel` / `taskPreviewFullscreenImage` / `taskPreviewFullscreenCounter` / `taskPreviewFullscreenPrevBtn` / `taskPreviewFullscreenNextBtn`（HTML 中不存在）

**死函数**
- `setDemoStatusText(value)` — 调用 null 元素，空执行
- `setDemoHitText(value)` — 同上
- `setDemoStepText(value)` — 同上
- `setDemoResultChipText(value)` — 同上
- `renderWorkflowLiveStream()` — 首行 `if (!workflowLiveStream) return`，永远提前返回

---

## 二、工艺生成页 UI 改进

### 2.1 整体布局：顶栏融合工具与进度

**当前结构**：工具栏（`workspace-toolbar`）与进度 HUD（`workflowHudCard`）上下分离两块卡片。

**新结构**：合并为一条全宽顶栏，白色背景，单层高度。

**顶栏内容（从左到右）**：
```
[⤴ 上传文件] [◉ 检索库：xxx] [⚡ 缓存：关] [↺ 重置]    [阶段描述文字]  [百分比 xx%] [收起]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 橙色进度条（全宽）━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[状态细节文字，如：正在识别标题栏与尺寸标注，预计剩余 12 秒]
```

**样式规格**：
- 背景：`#fff`，底部 `border-bottom: 1px solid var(--line)`，`box-shadow: 0 2px 8px rgba(24,38,58,.06)`
- 进度条：高度 5px，颜色 `linear-gradient(90deg, #ff6528, #ff4d1f)`，圆角 `999px`，背景轨道 `var(--panel-soft)`
- 百分比：`font-size: 18px`，`font-weight: 800`，`color: var(--accent)`
- 阶段文字：`font-size: 13px`，`font-weight: 700`，`color: var(--text)`
- 状态细节：`font-size: 11px`，`color: var(--text-soft)`，进度条下方

**交互**：
- "收起"按钮折叠进度条和状态细节行，只保留按钮行
- 进度为 0 时（未开始）隐藏进度条行，仅显示按钮行
- 进度为 100% 且任务完成时，进度条变为绿色（`var(--green)`），状态文字显示"生成完成"

### 2.2 特征审阅区：紧凑行表格微调

**保留现有结构**，仅做以下改进：

- 奇偶行交替底色：奇行 `#fff`，偶行 `var(--panel-soft)`
- 字段名列固定宽度 `120px`，`color: var(--text-soft)`，`font-weight: 600`
- 值列支持点击内联编辑：点击值区域切换为 `<input>` 或 `<textarea>`，失焦自动保存
- 编辑中的行左侧显示 `3px solid var(--accent)` 高亮边框

### 2.3 工艺规程展示：行表格 + 行内编辑 + 工种列

#### 结构变更

- **删除** `#editorShell`（底部文本编辑器 + 工艺预览两栏）
- **保留** `#processStepsList` 工序列表，改为 `<table>` 结构

#### 表格列定义

| 列 | 宽度 | 内容 |
|----|------|------|
| 工序号 | 68px | `font-family: monospace`，`color: var(--brand)`，`font-weight: 800` |
| 工种 | 108px | badge 展示；编辑态变为下拉 + 可选自定义输入 |
| 工序名称及内容 | flex:1 | 文本展示；编辑态变为 `<textarea>` |
| 操作 | 72px | "编辑"按钮，右对齐 |

#### 工种下拉预设选项

`划线工 / 车工 / 铣工 / 钻工 / 镗工 / 磨工 / 钳工 / 热处理 / 检验 / 其他`

选择"其他"时，下拉下方即时出现文本输入框，用户输入自定义工种名称；保存后以该名称作为 badge 显示。

#### 行内编辑交互

- 点击"编辑"→ 该行展开为编辑态（工种下拉 + 自定义输入（按需） + 内容 textarea + 保存/取消按钮）
- 编辑行左侧 `border-left: 3px solid var(--accent)`，背景 `var(--accent-soft)`
- 点击"保存"→ 行折叠，显示更新后内容
- 点击"取消"→ 行折叠，恢复原内容
- 同一时刻只允许一行处于编辑态

#### 工种 badge 配色

| 工种 | badge 颜色 |
|------|-----------|
| 热处理 | `var(--green-soft)` + `var(--green)` |
| 检验 | `var(--orange-soft)` + `var(--accent)` |
| 其他所有工种 | `var(--blue-soft)` + `var(--brand)` |

---

## 三、不在本次范围内

- 历史记录页、数据库浏览页、工艺入库页的 UI 改动
- CSS 全局冗余规则清理（独立任务）
- 51 处内联 `style=""` 属性迁移（独立任务）
