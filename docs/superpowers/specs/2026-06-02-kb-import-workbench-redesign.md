# 工艺入库页工作台重设计

> 日期：2026-06-02
> 状态：已审批

## 背景

工艺入库页（`#page-zip`）的 Hero 区（顶部两张卡片）用户认为清晰，无需改动。问题集中在 Hero 下方的**工作台区域**：

- **布局混乱**：原有左右两个面板并排，空屏时两侧都是空占位，视觉浪费严重
- **状态反馈弱**：进度/阶段信息埋在左面板内，不醒目；成功/失败无明确视觉信号
- **工具栏拥挤**：冲突模式按钮和结果 tabs 挤在同一行

## 设计目标

1. 空屏时无废空间，有明确的操作引导
2. 处理过程中，进度和阶段信息占据视觉焦点
3. 完成后，结果汇总清晰，可直接浏览明细

## 不改动范围

- Hero 区完全保留（左：介绍文案 + 按钮；右：目标库选择器）
- "上传工艺包"按钮依然是主要上传触发入口
- 后端 API 接口不变

---

## 新工作台布局

### 结构层级

```
工艺入库工作台（workspace-card）
├── 工具栏（workspace-toolbar）
│   ├── 标题：工艺入库工作台
│   └── 冲突模式按钮（右对齐，secondary 样式）
├── 状态区（zip-status-zone）          ← 新增，全宽，三态切换
├── 结果 Tabs（result-tabs）           ← 移到状态区下方独立一行
└── 结果列表（browser-shell）          ← 全宽
```

### 三种状态

#### 状态①：待上传（初始）

- 状态区显示全宽虚线拖拽框（`dashed border`），**兼具视觉引导和功能拖拽区**（替代原 `#zipDropzone`，绑定相同的 drag/drop 事件）
- 内容：大图标 ⌁ + "拖拽 ZIP 工艺包到此处" + 小提示文字
- 引导文字指向 Hero 区的"上传工艺包"按钮（两种方式均触发同一文件选择流程）
- 结果 Tabs 置灰（`opacity: 0.4`，`pointer-events: none`）
- 结果列表区显示静默占位文字"上传后此处显示结果"

#### 状态②：处理中（上传 → 解析 → 入库）

状态区切换为进度面板，包含：

| 元素 | 说明 |
|------|------|
| 阶段指示点 + 文字 | 蓝色脉冲点 + "正在解析文件对..." 等阶段描述 |
| 百分比数字 | 右对齐，14px，粗体 |
| 进度条 | 蓝色，`height: 8px`，圆角，渐变色 |
| 实时统计行 | 总文件 / 配对✓ / 未匹配⚠ / 错误 — 四项内联，实时更新 |

进度阶段文字映射（对应 `chipText` 逻辑）：

| 后端阶段 | 显示文字 |
|---------|---------|
| uploading | 正在上传文件... |
| parsing | 正在解析文件对... |
| importing | 正在写入数据库... |
| done | 入库完成 |
| error | 入库失败 |

结果 Tabs 中**批次日志 tab 自动激活**，实时滚动展示日志（含真实时间戳）。

#### 状态③：完成

状态区切换为横幅，两种变体：

**成功横幅**（绿色）：
- 背景 `#052e16`，左边框 `#16a34a`
- ✓ 图标 + "入库完成 — [目标库名]" + "配对 N 组 · 未匹配 M 项 · K 错误"
- 右侧"再次上传"按钮：清空当前批次结果 + 重置统计 + 回到 idle 态，然后立即触发文件选择器

**失败横幅**（红色）：
- 背景 `#450a0a`，左边框 `#dc2626`
- ✗ 图标 + "入库失败" + 错误摘要
- 右侧"重试"按钮：同"再次上传"行为（清空 + 回 idle + 触发文件选择）

结果 Tabs 恢复可点击，**已匹配**和**未匹配** tab 显示数字角标。

---

## 状态切换逻辑

```
初始态
  │ 触发上传（按钮或拖拽）
  ▼
处理中
  │ 后端返回 done / error
  ▼
完成态（成功 or 失败）
  │ 点击"再次上传"或"重试"
  ▼
初始态（清空结果，重置统计）
```

状态切换通过 CSS class 控制（`zip-status-zone` 上加 `state-idle / state-running / state-done / state-error`），避免 JS 直接操作多个 DOM 节点。

---

## JS 改动范围

| 位置 | 改动 |
|------|------|
| `updateZipProgress(phase, pct)` | 更新阶段文字 + 进度条 + 百分比 |
| `updateZipStats(total, matched, unmatched, errors)` | 更新实时统计行 |
| `setZipState(state)` | 切换 `zip-status-zone` 的 class |
| `finishZip(success, summary)` | 渲染成功/失败横幅，更新 tab 角标 |
| `resetZip()` | 清空状态，回到 idle |
| 日志时间戳 | 改为 `new Date().toLocaleTimeString()` 真实时间 |

---

## CSS 改动范围

| 新增 class | 说明 |
|-----------|------|
| `.zip-status-zone` | 状态区容器，`border-radius: 10px`，内边距 16px |
| `.zip-status-zone.state-idle` | 显示拖拽框 |
| `.zip-status-zone.state-running` | 显示进度面板 |
| `.zip-status-zone.state-done` | 显示成功横幅 |
| `.zip-status-zone.state-error` | 显示失败横幅 |
| `.zip-progress-bar` | 进度条，高度 8px，渐变蓝 |
| `.zip-stats-row` | 实时统计行，flex，gap 16px |
| `.zip-result-banner` | 成功/失败横幅基础样式 |
| `.zip-result-banner.success` | 绿色变体 |
| `.zip-result-banner.error` | 红色变体 |

**删除 class**：`.zip-workbench`、`.zip-import-hud`、`.zip-import-rail`、`.zip-import-bar`（由新 class 替代）

---

## 移除/简化的元素

- 左右分栏面板（`workbench-panel upload-panel` + `workbench-panel result-panel`）→ 全部移除
- 分隔拖拽条（`#zipResizer`）→ 移除
- `workbench-panel-head` 中的 `panel-lib-label`（目标库已在 Hero 右卡片显示）→ 移除
- 工具栏中的 result tabs → 移到独立一行，位于状态区下方

---

## 文件影响

| 文件 | 改动类型 |
|------|---------|
| `updated_front/demo-industrial-console.html` | 重构 `#page-zip` 内的工作台 HTML 结构 |
| `updated_front/js/demo-industrial-console.js` | 修改 zip 相关状态更新函数 |
| `updated_front/css/industrial-console.css` | 删除旧 zip 面板样式，新增状态区样式 |
