# 前端核心流程详解 — YOLO 标注页 & 流式工艺输出

> 本文档深入梳理前端两大核心流程的完整实现逻辑：YOLO 预标注后的人工审阅流程，以及工艺规程的流式打字机输出引擎。

---

## 目录

- [一、YOLO 标注页面流程](#一yolo-标注页面流程)
  - [1.1 状态变量](#11-状态变量)
  - [1.2 进入标注模式](#12-进入标注模式)
  - [1.3 标注全屏覆盖层](#13-标注全屏覆盖层)
  - [1.4 标注工具核心（AnnotationTool）](#14-标注工具核心annotationtool)
  - [1.5 退出标注模式](#15-退出标注模式)
  - [1.6 完成标注并继续](#16-完成标注并继续)
  - [1.7 标注汇总卡片渲染](#17-标注汇总卡片渲染)
  - [1.8 完整时序图](#18-完整时序图)
  - [1.9 功能界限与能力边界](#19-功能界限与能力边界)
- [二、流式工艺输出引擎](#二流式工艺输出引擎)
  - [2.1 状态变量](#21-状态变量)
  - [2.2 SSE 事件接收](#22-sse-事件接收)
  - [2.3 流式文本入口](#23-流式文本入口)
  - [2.4 打字机引擎完整流程](#24-打字机引擎完整流程)
  - [2.5 工序行解析](#25-工序行解析)
  - [2.6 SSE complete 事件与收尾](#26-sse-complete-事件与收尾)
  - [2.7 最终工艺表格渲染](#27-最终工艺表格渲染)
  - [2.8 进度条与阶段提示](#28-进度条与阶段提示)
  - [2.9 完整数据流图](#29-完整数据流图)
  - [2.10 功能界限与能力边界](#210-功能界限与能力边界)
- [三、两模块的协作边界](#三两模块的协作边界)

---

## 一、YOLO 标注页面流程

### 1.1 状态变量

主应用 `demo-industrial-console.js` 顶部维护两个模块级变量：

```javascript
let _annotateTool = null;       // AnnotationTool 单例
let _annotateActive = false;    // 全屏标注页是否打开
```

`backendState` 上的相关字段（初始化于 ~line 528）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `annotationAnalyzed` | boolean | YOLO 分析完成后设为 `true` |
| `annotationSummary` | object | 各标签类型的计数，如 `{chamfer:3, threaded_hole:5}` |
| `annotationPages` | number | 有标注的页数 |
| `annotateVisitedOnce` | boolean | 用户是否进入过标注全屏（用于控制"完成标注"按钮状态） |
| `currentReviewTaskId` | string | 当前正在标注的任务 ID |

### 1.2 进入标注模式

#### 触发源一：SSE `annotation_required` 事件（~line 2877）

后端 YOLO 预标注完成后推送此事件。前端处理流程：

1. 解析 payload，存储 `summary` 和 `pages` 到 `backendState`
2. 重置 `annotateVisitedOnce = false`
3. 清除上一个任务的审阅状态
4. 更新工作流 HUD → "等待人工补全标注"，进度 35%
5. 更新状态标签 → "等待标注" / "YOLO 已预标注"
6. 写入工作流日志（显示 YOLO 检出总数）
7. 渲染上传预览图
8. 调用 `renderAnnotationPendingPanel()` → 在 `#reviewTableHost` 中渲染标注汇总卡片（含"开始标注"和"完成标注"按钮）
9. 设置 `annotationAnalyzed = true`
10. 调用 `renderReviewAnnotationSummary()` → 在审阅表格上方渲染只读汇总
11. 激活 `view-review` 视图

#### 触发源二：轮询恢复（~line 3490）

当轮询发现任务状态为 `awaiting_annotation` 时，从 `/annotations/{taskId}` 拉取已有标注数据，统计各类型计数后渲染汇总卡片。

#### 用户点击"开始标注"（`renderAnnotationPendingPanel` 内部，~line 4773）

```javascript
startBtn.addEventListener('click', () => {
    backendState.annotateVisitedOnce = true;
    finBtn.disabled = false;
    enterAnnotateMode();
});
```

#### `enterAnnotateMode()` 函数（~line 4622）

1. 防重入检查（`_annotateActive`）
2. 调用 `ensureAnnotateFullscreen()` 惰性创建全屏 DOM
3. 获取 `#annotateFsImage`、`#annotateFsSvg`、`#annotateFsSidebar` 引用
4. 添加 `open` class → CSS 控制全屏可见
5. 锁定 `body` 滚动
6. 创建或复用 `AnnotationTool` 单例，调用 `activate(taskId, urls, imgEl, svgEl)`

### 1.3 标注全屏覆盖层

`ensureAnnotateFullscreen()` 函数（~line 4563）惰性创建 DOM 结构：

```
<div id="annotateFullscreen" class="annotate-fullscreen">
  └─ .annotate-fs-layout (flex 容器)
     ├─ #annotateFsScroll (.annotate-fs-scroll) — 可滚动区域
     │  └─ #annotateFsImgWrap (.annotate-fs-img-wrap) — inline-block 包裹
     │     ├─ <img id="annotateFsImage"> — 图纸页面图片
     │     └─ <svg id="annotateFsSvg"> — SVG 标注覆盖层（position:absolute）
     └─ #annotateFsSidebar (.annotate-fs-sidebar) — 右侧工具栏
        ├─ 退出按钮 → exitAnnotateMode()
        ├─ 提示文字："右键框删除 · 自动保存 · Ctrl+滚轮缩放"
        ├─ 缩放工具栏：缩小/百分比/放大/适应/100%
        ├─ 标签工具栏：#annotateFsLabelRow + 新增类型按钮
        ├─ 标注列表：#annotateFsCount + #annotateFsListBody
        └─ 底部：上一页/页码/下一页/导出按钮
```

页面关闭安全网（~line 4616）：`beforeunload` 事件触发 `sendBeaconSave()`，使用 `navigator.sendBeacon()` 确保数据发送。

### 1.4 标注工具核心（AnnotationTool）

`annotation-tool.js` 中的 `AnnotationTool` 类是标注功能的核心。

#### 1.4.1 标签系统

```javascript
const LABEL_CONFIG = {
    chamfer:       { id: 2, color: '#f59e0b', dash: null,  zh: '倒角'   },
    threaded_hole: { id: 0, color: '#6366f1', dash: '6,3', zh: '螺纹孔' },
    circle_hole:   { id: 1, color: '#10b981', dash: null,  zh: '圆孔'   },
};
```

- 自定义标签存储于 `localStorage` key `annotate.customLabels.v1`
- 从 5 色循环池自动取色：`#ec4899`, `#14b8a6`, `#f97316`, `#8b5cf6`, `#06b6d4`
- 删除前检查所有页面是否有引用，有则拒绝
- `getAnnotationLabelMeta()` 挂载到 `window`，供主应用获取颜色和中文名

#### 1.4.2 坐标系统

SVG 通过 `position: absolute; inset: 0` 覆盖在 `<img>` 上。

```
_imgOffset()  →  getBoundingClientRect() 计算 (dx, dy, sx, sy)
_toReal()     →  SVG 像素坐标 → 图片自然坐标（减偏移、除缩放比）
_toDisplay()  →  图片自然坐标 → SVG 像素坐标（乘缩放比、加偏移）
```

标注的 `points` 存储**图片自然坐标** `[[x1,y1],[x2,y2]]`，渲染时实时换算，缩放不影响精度。

#### 1.4.3 绘制流程

| 步骤 | 事件 | 行为 |
|------|------|------|
| 1 | `mousedown`（左键） | 记录起始点，创建草稿 `<rect>`（半透明 + 标签色描边） |
| 2 | `mousemove` | 实时更新草稿矩形的 x/y/width/height |
| 3 | `mouseup` | 移除草稿，若拖拽 ≥ 6px 则转为自然坐标存入 `_annotations` |
| 4 | 右键已有框 | 删除该标注 |

#### 1.4.4 多页支持

- `_allPages` 对象以页码字符串 `"1"`,`"2"`,... 为键存储每页标注
- `_loadPage(idx)` 切换页面时自动保存当前页、加载目标页
- `_loadFromServer()` 从 GET `/api/annotations/{taskId}` 加载已有标注合并到 `_allPages`

#### 1.4.5 缩放

- 范围 0.05x ~ 8.0x
- `_applyZoom()` 直接设置 `<img>` 的 `style.width/height`
- Ctrl+滚轮以光标为中心缩放：先记录光标下自然坐标，缩放后反算 scroll 偏移保持该点不动
- `fitToViewport()` 根据容器可用空间计算自适应缩放比

#### 1.4.6 选中态与双向联动

- 选中框叠加白色光晕 + 黑色虚线环
- 浮动标签（如"螺纹孔 3"）始终显示，选中时加大加亮
- 按标签类型独立编号
- 画布点击 → 列表滚动；列表点击 → 画布滚动

#### 1.4.7 持久化

| 方法 | 时机 | 行为 |
|------|------|------|
| `_scheduleSave()` | 标注变更后 | 1s 防抖 → `_autoSaveNow()` |
| `_autoSaveNow()` | 防抖触发 | POST 当前页到 `/api/annotations/{taskId}/save` |
| `sendBeaconSave()` | 页面关闭 | `navigator.sendBeacon()` 发送当前页 |
| `deactivate()` | 退出标注 | 遍历 `_allPages`，保存**所有页**，`Promise.all` 等待完成 |
| `flushSave()` | 完成标注前 | 公开方法，等待最后一次保存完成 |

保存 payload：
```json
{
    "page": 1,
    "shapes": [{ "label": "chamfer", "points": [[x1,y1],[x2,y2]] }],
    "imageWidth": 2480,
    "imageHeight": 3508,
    "imagePath": "page_1.png"
}
```

#### 1.4.8 getSummary()

遍历 `_allPages` 统计各标签计数，内建三类即使为 0 也保留占位：

```javascript
getSummary() {
    this._allPages[this._pageKey()] = this._annotations.slice();
    const sum = {};
    Object.values(this._allPages).forEach((shapes) => {
        (shapes || []).forEach((s) => {
            sum[s.label] = (sum[s.label] || 0) + 1;
        });
    });
    if (sum.chamfer === undefined)       sum.chamfer = 0;
    if (sum.threaded_hole === undefined) sum.threaded_hole = 0;
    if (sum.circle_hole === undefined)   sum.circle_hole = 0;
    return { ...sum, pages };
}
```

### 1.5 退出标注模式

`exitAnnotateMode()` 函数（~line 4644）：

1. 防重入检查
2. 禁用退出按钮，文字改为"保存中…"
3. 创建最小 350ms 延迟（让用户看到保存状态）
4. `await _annotateTool.deactivate()` — 保存所有页 + 清理事件监听 + 清空 SVG
5. 移除 `open` class → 隐藏全屏覆盖层
6. 恢复 `body` 滚动
7. 从 `_annotateTool.getSummary()` 获取最新计数
8. 更新 `backendState.annotationSummary` / `annotationPages`
9. 刷新两个汇总卡片

### 1.6 完成标注并继续

`finalizeAnnotation()` 函数（~line 4781）：

1. 禁用按钮，文字改为"保存最新标注…"
2. `await _annotateTool.flushSave()` — 确保后端有最新数据
3. 文字改为"已确认，等待视觉分析…"
4. POST `/api/annotations/{taskId}/finalize` — 触发后端下一流程阶段
5. 成功 → 更新工作流状态为"视觉分析中" 45%
6. 失败 → 重新启用按钮，添加"(重试)"后缀

### 1.7 标注汇总卡片渲染

#### `renderAnnotationPendingPanel()`（~line 4720）

渲染到 `#reviewTableHost`（审阅表格区域），替代审阅表格：

- 隐藏空状态
- 禁用"确认特征并继续"/"修改后重新生成"按钮（需先完成标注）
- 渲染标注汇总卡片：标题 + 标签 tab 行（彩色圆点 + 计数） + "开始标注"/"完成标注"按钮
- 根据 `annotateVisitedOnce` 控制"完成标注"按钮是否可用

#### `renderReviewAnnotationSummary()`（~line 4686）

渲染到 `#reviewAnnotationSummary`（审阅表格上方的专用 div）：

- **显示条件**：`annotationAnalyzed === true` 且审阅表格已渲染
- 不满足条件时清空容器、不渲染
- 渲染只读汇总：标题 + 标签 tab 行（无按钮）

### 1.8 完整时序图

```
用户上传图纸
    │
    ▼
后端 YOLO 预标注
    │
    ▼ SSE: annotation_required
前端解析 summary/pages
    │
    ├─ 渲染 renderAnnotationPendingPanel()  ← 带"开始标注"/"完成标注"按钮
    ├─ 设置 annotationAnalyzed = true
    ├─ 渲染 renderReviewAnnotationSummary()  ← 需等表格出来才显示
    └─ 激活 view-review 视图
    │
    ▼ 用户点击"开始标注"
enterAnnotateMode()
    │
    ├─ ensureAnnotateFullscreen() 创建 DOM
    ├─ CSS open → 全屏显示
    └─ AnnotationTool.activate()
        ├─ 加载图片 + 服务端已有标注
        ├─ 绑定绘制事件
        └─ 用户交互：画框/选中/删除/缩放/翻页
            │ (自动保存：1s 防抖 POST)
            │
    ▼ 用户点击"退出"
exitAnnotateMode()
    │
    ├─ deactivate() → 保存所有页
    ├─ 更新 annotationSummary
    └─ 刷新两个汇总卡片
    │
    ▼ 用户点击"完成标注 → 继续"
finalizeAnnotation()
    │
    ├─ flushSave() → 确保后端最新
    └─ POST /finalize → 触发视觉分析
    │
    ▼ 后端继续处理 → 特征审阅
```

### 1.9 功能界限与能力边界

#### 能做什么

| 能力 | 说明 |
|------|------|
| 矩形框标注 | 在任意图片页面上拖拽绘制矩形区域，标记工艺特征 |
| 多页标注 | 支持 PDF 多页图纸，每页独立标注，翻页自动保存/加载 |
| 标签分类 | 3 个内建标签（倒角/螺纹孔/圆孔）+ 用户自定义标签（localStorage 持久化） |
| 自动保存 | 1s 防抖自动 POST 到后端，页面关闭时 sendBeacon 兜底 |
| 全页保存 | `deactivate()` 遍历所有页并行保存，不丢失多页数据 |
| 缩放平移 | 0.05x ~ 8.0x 缩放，Ctrl+滚轮以光标为中心，fit-to-viewport 自适应 |
| 双向联动 | 画布点击 ↔ 列表滚动，选中高亮（白色光晕 + 虚线环 + 浮动标签） |
| 标签管理 | 新增自定义标签（prompt 输入中文），右键删除（有引用时拒绝） |
| 导出 | 通过 `/api/annotations/{taskId}/export` 下载 ZIP 格式标注数据 |
| 汇总统计 | `getSummary()` 跨所有页按标签类型统计计数，支持自定义类型 |

#### 不能做什么 / 已知限制

| 边界 | 具体限制 | 原因 |
|------|----------|------|
| **仅支持矩形** | 不支持多边形、圆形、自由曲线等形状 | `_onMouseDown/Move/Up` 只创建 `<rect>`，无其他形状的绘制逻辑 |
| **无拖拽移动** | 画好的框不能拖拽调整位置或大小 | 没有实现 rect 的 drag/move/resize 事件处理 |
| **无撤销/重做** | 误操作无法 Ctrl+Z 回退 | 未维护操作历史栈 |
| **无多选** | 不能框选多个标注批量操作 | `_selectedId` 是单值，无选区逻辑 |
| **标注不跨页** | 每页标注独立，不能关联跨页特征 | `_allPages` 按页码隔离存储 |
| **自定义标签无 class_id** | 自定义标签只有前端显示映射，无后端 class_id | 注释明确说明："不写后端 class_id 映射，纯前端缓存" |
| **保存粒度** | `_autoSaveNow` 只保存当前页；`deactivate` 保存所有页 | 设计权衡：频繁保存所有页会产生大量请求 |
| **坐标精度** | `getBoundingClientRect()` 在 CSS transform 场景下可能有亚像素偏差 | 浏览器 API 限制，不影响实际使用 |
| **无离线模式** | 标注数据依赖后端存储，断网后只能靠 localStorage 的自定义标签 | 标注 shapes 未做 localStorage 备份 |
| **单用户单任务** | 不支持多人协作标注同一任务 | 无冲突检测或乐观锁机制 |
| **图片格式** | 仅支持浏览器原生渲染的图片格式（PNG/JPG/PDF 页面截图） | `<img>` 标签限制，不支持 DICOM 等医学影像格式 |
| **缩放无平滑动画** | `setZoom` 直接设置 width/height，无 CSS transition | `renderAll()` 在缩放后立即重绘，动画会冲突 |
| **标签名不可修改** | 创建后的标签名不能编辑，只能删除重建 | 无 rename 逻辑 |
| **导出格式单一** | 只支持 ZIP 导出，无 COCO/VOC/YOLO 等标准格式 | `_exportZip()` 直接调后端 `/export` 端点 |

---

## 二、流式工艺输出引擎

### 2.1 状态变量

所有打字机状态存储在 `backendState` 上（~line 509）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `processStreamText` | string | SSE 流式文本累积（完整文本） |
| `processStreamRows` | array | 解析后的工序行数组 |
| `processStreamTaskId` | string | 当前流式任务 ID |
| `twRowQueue` | array | 已解析等待打字的行队列 |
| `twLineBuffer` | string | 当前行的字符缓冲区（遇 `\n` 解析） |
| `twIsTyping` | boolean | 是否正在逐字输出一行 |
| `twFieldTimer` | number | 当前 setTimeout 句柄 |
| `twCurrentTr` | HTMLTableRowElement | 当前正在打字的 `<tr>` |
| `twDoneFlag` | boolean | SSE `complete` 事件已触发 |
| `twAllDoneHandled` | boolean | 防止 `twOnAllRowsDone` 执行两次 |
| `streamingDone` | boolean | 流式传输结束标记 |

### 2.2 SSE 事件接收

`connectTaskEvents(taskId)` 函数（~line 2840）建立 EventSource 连接：

```javascript
const source = new EventSource(`${API_BASE}/events/${taskId}`);
```

工艺流式输出通过 `process_stream` 事件接收（~line 2962）：

```javascript
source.addEventListener('process_stream', (event) => {
    const payload = JSON.parse(event.data || '{}');
    const chunk = String(payload.chunk || '');
    queueProcessStreamChunk(taskId, chunk);
});
```

其他相关 SSE 事件：

| 事件 | 说明 |
|------|------|
| `progress` | 更新进度条百分比 |
| `log` | 实时日志 → 更新阶段提示 |
| `feature_report` | 特征提取报告 → 渲染审阅表格 |
| `status` | 状态变更（`awaiting_review` / `completed` / `error`） |
| `process_stream` | 工艺规程流式文本块 |
| `complete` | 流式传输结束 |
| `gltf_url` | 3D 模型预览 URL |
| `preview_image` | 预览图片 URL |

### 2.3 流式文本入口

`queueProcessStreamChunk(taskId, chunk)` 函数（~line 2066）：

1. 防空 chunk / `streamingDone` 守卫
2. 若 taskId 变更 → `resetProcessStreamState(taskId)` 清除所有流式/打字机状态
3. 若流式区域未显示 → `showStreamingZone()` 注入 `<table>` 骨架（三列：工序号、工种、内容）
4. **追加** chunk 到 `backendState.processStreamText`
5. **逐字符**喂入 `twFeedChar(ch)`

### 2.4 打字机引擎完整流程

#### 2.4.1 `twFeedChar(ch)` — 逐字符接收（~line 1817）

```
ch !== '\n'  →  追加到 twLineBuffer
ch === '\n'  →  取出 twLineBuffer → twParseLine(line)
                   ├─ 有效行 → 去重检查 → push 到 twRowQueue → twKick()
                   └─ 无效行 → 丢弃
```

#### 2.4.2 `twParseLine(line)` — 行解析（~line 1802）

输入一行文本，输出 `{ code, tradeType, content }`：

1. 去除前导 `- ` / `* ` 标记
2. 过滤空行、`#` 注释、`---`/`===` 分隔线
3. **三段式**：`/^(\d{4})@([^@]*)@(.+)$/` → `0010@铣@铣方六面`
4. **两段式回退**：`/^(\d{4})\s*[@:：\-|,，;；\s]*\s*(.+)$/` → `0010@铣方六面`
5. 若工种为空 → `_splitTradeFromContent(content)` 尝试从内容中提取

#### 2.4.3 `twKick()` — 调度器（~line 1840）

```
twIsTyping === true   →  不做任何事（当前行正在输出）
队列非空              →  twStartNextRow()
队列空 && twDoneFlag  →  twOnAllRowsDone()
```

#### 2.4.4 `twStartNextRow()` — 开始输出下一行（~line 1849）

1. 从 `twRowQueue` shift 一行，设置 `twIsTyping = true`
2. 创建 `<tr class="tw-typing-tr" data-process-row="CODE">`
3. 三个 `<td>`：`.step-no`（工序号）、`.step-trade`（工种）、`.step-content-cell > div[contenteditable]`（内容）
4. 追加到 `<tbody>`，滚动到底部
5. 调用 `twTypeFieldSequence(tr, fields, 0, row)`

#### 2.4.5 `twTypeFieldSequence(tr, fields, idx, row)` — 字段序列化输出（~line 1884）

递归调用，逐字段打字：

```
fields = [
    { el: codeTd,    value: row.code,      speed: 'fast' },
    { el: tradeTd,   value: row.tradeType,  speed: 'fast' },
    { el: contentEl, value: row.content,    speed: 'slow' },
]
```

每个字段完成后添加 `tw-cell-active` CSS 类，字段间随机延迟 50-105ms。

#### 2.4.6 `twTypeField(el, text, speed, onDone)` — 逐字符输出（~line 1899）

通过 `setTimeout` 链逐字符更新 `el.textContent`：

| 速度档 | 适用 | 字符类型 | 延迟 |
|--------|------|----------|------|
| `fast` | 工序号/工种 | 数字 | 14-28ms |
| `fast` | 工序号/工种 | 其他 | 9-18ms |
| `slow` | 工序内容 | 中文标点 | 55-130ms |
| `slow` | 工序内容 | CJK 字符 | 20-40ms |
| `slow` | 工序内容 | 数字 | 16-32ms |
| `slow` | 工序内容 | 其他 | 11-22ms |

每次输出后自动滚动表格容器，确保当前字符可见。

#### 2.4.7 `twFinishRow(tr, row)` — 行完成（~line 1924）

1. 移除 `tw-typing-tr`，添加 `row-new`（入场动画）和 `tw-row-completing`（600ms 闪光）
2. 对内容应用 `processContentForDisplay` 格式化：在子步骤标记（`-2.`、`3）`、`N.`）前插入换行，分号后换行
3. 更新阶段提示："正在输出第 0010 道工序"
4. 更新步骤计数器
5. 随机暂停 320-600ms → `twIsTyping = false` → `twKick()`（处理下一行或触发完成）

#### 2.4.8 `twDrainAll()` — 紧急停止（~line 1952）

清除所有定时器、清空队列和行缓冲、移除打字中的 `<tr>`、重置 `twIsTyping`。当轮询结果先于打字机完成到达时调用。

### 2.5 工序行解析

#### 实时解析：`twParseLine(line)`（~line 1802）

流式过程中逐行解析，格式同上。

#### 批量解析：`parseStreamingProcessRows(text)`（~line 2083）

流式结束后用于最终对账。将完整 `processStreamText` 按行拆分，跳过噪声行，用相同正则提取，按 `code::value` 去重。

#### 工种提取：`_splitTradeFromContent(content)`（~line 1337）

三种嵌套工种格式：

| 格式 | 示例 | 正则 |
|------|------|------|
| 后缀 | `工序内容 （工种：料）` | `/^(.*?)\s*[（(]工种[：:]\s*([一-龥\-]{1,6})\s*[）)]\s*$/` |
| @ 分隔 | `料@备料...` | `/^([^\d\s@（）【】\[\]()]{1,6})@(.+)/s` |
| 括号 | `料（备料...）` | `/^([一-龥\-]{1,6})\s*（([\s\S]+)/` |

#### 归一化：`normalizeProcessRow(row)`（~line 1356）

处理所有输入形状（数组、对象、字符串），归一化为 `{ code, tradeType, content }`。用于流式去重和最终渲染。

### 2.6 SSE complete 事件与收尾

#### `complete` 事件处理（~line 2972）

1. 停止轮询定时器，设置 `streamingDone = true`
2. 断开 EventSource
3. 设置 `twDoneFlag = true`
4. 若打字机空闲且队列为空 → 立即 `twOnAllRowsDone()`
5. 否则自然的 `twKick` 循环会在最后一行完成后触发

#### `twOnAllRowsDone()` 函数（~line 1969）

受 `twAllDoneHandled` 保护，只执行一次：

1. 隐藏流式区域（移除打字中标记）
2. 设置工作流状态 → "工艺生成完成" 100%
3. **若 `pendingPollResult` 存在**（轮询先于打字机完成）→ 直接用该结果调用 `renderProcessFromResult(r)`，避免重复工作
4. **否则** → `parseStreamingProcessRows(processStreamText)` 获取最终行列表
   - 若无解析结果 → 回退到 `/result/{taskId}` 拉取
   - 若有结果 → 计算 `missingRows`（已在流式中输出但 DOM 中缺失的行），以 80ms 间隔逐行补入
5. 所有行补完后 → `twSyncCompletion()`

#### `twSyncCompletion()` 函数（~line 2040）

1. 填充编辑器文本框（markdown 格式）
2. 刷新编辑器预览和导出按钮状态
3. 从 `/result/{taskId}` 拉取最终结果，缓存并渲染审阅表格

### 2.7 最终工艺表格渲染

`renderProcessFromResult(result)`（~line 2259）：

1. 提取 `processFlow.data`（行数组）
2. 调用 `renderProcessRowsSurface(rows, { result, markdown, live: false })`

`renderProcessRowsSurface(rows, opts)`（~line 2177）：

- `live: false`（最终渲染）：替换整个 `#processStepsList` innerHTML 为干净的 `<table>`
- 三列：工序号（`.step-no`）、工种（`.step-trade`）、工序名称及内容（`.step-content`）
- 内容单元格 `contenteditable="true"` 支持内联编辑
- 同时填充 `editorTextarea` 的 markdown 表示

### 2.8 进度条与阶段提示

#### HTML 结构（demo-industrial-console.html ~line 68）

```
#workflowHudCard          — HUD 容器
├─ #workflowPercent       — 百分比文字（如"65%"）
├─ #workflowProgressBar   — 进度条（width 内联样式）
└─ #workflowPhaseHint     — 阶段提示文字（带呼吸灯动画）
```

#### `setWorkflowState(phase, progress, busy)` 函数（~line 788）

1. 更新 `backendState.taskPhase` / `taskProgress` / `taskBusy`
2. 设置百分比文字和进度条宽度
3. 切换 HUD 卡片的 CSS class：`busy` / `completed` / `collapsed`
4. 通过正则映射表将 `phase` 转为用户友好的中文提示

#### 流式期间的进度更新来源

| 来源 | 更新方式 |
|------|----------|
| 轮询 `followTaskProgress` | 每轮调用 `setWorkflowState(result.progress, phase)` |
| 打字机每行完成 | `setWorkflowThinkingLine("正在输出第 0010 道工序")` |
| SSE `log` 事件 | `appendWorkflowLiveEntry(tag, text)` → `formatWorkflowThinkingText()` 转为中文 |
| 完成 | `twOnAllRowsDone()` → 100% + "工艺生成完成" |

#### `formatWorkflowThinkingText(tag, text)` 函数（~line 126）

将原始日志转为用户友好的中文提示，通过关键词匹配：

| 关键词 | 输出 |
|--------|------|
| 视觉分析 | "视觉特征分析中…" |
| 专家判断 | "专家规则判断中…" |
| 生成完成 | "工艺规程生成完成" |
| review | "等待人工审阅" |
| zip / 知识库 | "知识库入库中…" |
| 其他 | 原样输出 |

### 2.9 完整数据流图

```
后端 SSE "process_stream" { chunk: "..." }
    │
    ▼
connectTaskEvents() 处理器
    │
    ▼
queueProcessStreamChunk(taskId, chunk)
    ├─ 追加到 processStreamText
    ├─ 首次 → showStreamingZone() 注入 <table>
    └─ 逐字符 → twFeedChar(ch)
         │
         ▼
       twFeedChar(ch)
         ├─ 非换行 → 追加到 twLineBuffer
         └─ 换行 → twParseLine(line)
              ├─ 有效 → 去重 → push twRowQueue → twKick()
              └─ 无效 → 丢弃
                   │
                   ▼
                 twKick()
                   ├─ 正在打字 → 无操作
                   ├─ 队列非空 → twStartNextRow()
                   │    ├─ 创建 <tr>
                   │    └─ twTypeFieldSequence(tr, fields, 0)
                   │         ├─ twTypeField(el, text, speed) ← 逐字符
                   │         ├─ 字段完成 → 下一字段
                   │         └─ 全部完成 → twFinishRow(tr, row)
                   │              ├─ 格式化内容
                   │              ├─ 更新阶段提示
                   │              ├─ 随机暂停 320-600ms
                   │              └─ twKick() ← 循环
                   │
                   └─ 队列空 && twDoneFlag → twOnAllRowsDone()
                        ├─ pendingPollResult? → renderProcessFromResult()
                        ├─ 否则 → parseStreamingProcessRows() → 补缺行
                        └─ twSyncCompletion() → 拉最终结果 → 渲染审阅

SSE "complete" 事件
    ├─ twDoneFlag = true
    └─ twKick() → 最终触发 twOnAllRowsDone()
```

### 2.10 功能界限与能力边界

#### 能做什么

| 能力 | 说明 |
|------|------|
| 流式接收 | 通过 SSE `process_stream` 事件实时接收后端工艺文本 |
| 逐字动画 | 中文/标点/数字使用不同延迟模拟真人打字节奏 |
| 实时解析 | 逐字符累积 → 遇换行即解析 → 即时入队打字 |
| 自动去重 | 同一工序号在 DOM 和队列中都做去重检查，防止重复输出 |
| 多格式兼容 | 三段式 `0010@工种@内容`、两段式 `0010@内容`、嵌套工种 `料@备料...` 均可解析 |
| 工种智能提取 | `_splitTradeFromContent` 从内容中识别后缀/ @分隔/ 括号三种嵌套工种格式 |
| 进度反馈 | 每行完成后更新阶段提示（"正在输出第 0010 道工序"）和步骤计数器 |
| 内容格式化 | `processContentForDisplay` 在子步骤标记前插入换行，提升可读性 |
| 中断恢复 | `twDrainAll()` 紧急停止打字机，用轮询结果直接渲染最终表格 |
| 最终对账 | 流式结束后 `parseStreamingProcessRows` 批量解析完整文本，补入缺失行 |
| 可编辑输出 | 最终表格所有单元格 `contenteditable`，支持内联编辑后导出 |
| SSE 断线处理 | `complete` 事件触发后主动断开 EventSource，避免重连风暴 |

#### 不能做什么 / 已知限制

| 边界 | 具体限制 | 原因 |
|------|----------|------|
| **固定三列格式** | 只支持工序号 + 工种 + 内容的三列表格 | `twStartNextRow` 硬编码三个 `<td>` |
| **工序号必须四位数字** | 正则 `^\d{4}` 要求四位数字，如 `0010` | `twParseLine` 的正则限制 |
| **单行不支持富文本** | 打字过程是纯 `textContent`，完成后再格式化为 `<br>` | `twTypeField` 用 `textContent` 逐字输出，不支持内联样式 |
| **无暂停/继续** | 打字机一旦启动无法暂停，只能 `twDrainAll` 强制终止 | 无暂停状态机，只有 typing/done 两态 |
| **无速度调节** | 打字速度由硬编码的随机区间控制，用户无法调整 | 无 UI 控件或配置项 |
| **延迟精度受限** | `setTimeout` 在浏览器后台标签页会被节流（最小 1000ms） | 浏览器 API 限制，切到后台时打字会明显变慢 |
| **队列无界** | `twRowQueue` 无长度上限，极端情况下可能积压大量行 | 未设上限，但实际场景中工序数有限（通常 < 100 行） |
| **行间暂停不可预测** | 行间随机 320-600ms 暂停，每次刷新时序不同 | `Math.random()` 设计为模拟真人节奏 |
| **解析容错有限** | 格式不匹配的行直接丢弃，不会回退到后端重试 | `twParseLine` 返回 null 后无 fallback |
| **最终渲染双路径** | `twOnAllRowsDone` 有两条路径（pendingPollResult vs parseStreamingProcessRows），逻辑复杂 | 设计为兼容"轮询先完成"和"打字先完成"两种时序 |
| **无段落/章节概念** | 不支持工序分组（如"粗加工段"、"精加工段"） | 行级别渲染，无分组折叠逻辑 |
| **导出依赖编辑态** | 导出时读取的是 `readProcessTable()` 从 DOM 读取的当前状态，不是原始流式文本 | 设计为"所见即所得"，但如果 DOM 被意外修改会丢失数据 |
| **流式文本累积在内存** | `processStreamText` 累积完整文本，极大文本（>1MB）可能影响性能 | 未做分页或流式丢弃 |
| **无重播功能** | 不能重放一次打字机动画效果 | 一旦 `twOnAllRowsDone` 执行，动画状态被清理 |

---

## 三、两模块的协作边界

### 3.1 数据流边界

```
标注模块                          后端                           流式输出模块
    │                              │                                │
    │  POST /annotations/save      │                                │
    │  POST /annotations/finalize  │                                │
    │─────────────────────────────→│                                │
    │                              │  视觉分析 + RAG + 生成          │
    │                              │                                │
    │                              │  SSE process_stream            │
    │                              │───────────────────────────────→│
    │                              │                                │
    │                              │  SSE complete                  │
    │                              │───────────────────────────────→│
    │                              │                                │
    │  GET /result/{taskId}        │                                │
    │  ← 用于刷新审阅表格           │                                │
    │←─────────────────────────────│                                │
```

### 3.2 状态隔离

| 状态 | 归属 | 说明 |
|------|------|------|
| `_annotateTool` / `_annotateActive` | 标注模块 | 标注工具单例和激活标记 |
| `annotationSummary` / `annotationPages` / `annotationAnalyzed` | 标注模块 | 汇总数据，供审阅面板使用 |
| `annotateVisitedOnce` | 标注模块 | 控制"完成标注"按钮是否可用 |
| `processStreamText` / `processStreamRows` | 流式输出模块 | 流式文本累积和解析结果 |
| `twRowQueue` / `twIsTyping` / `twDoneFlag` 等 | 流式输出模块 | 打字机状态机 |
| `currentReviewTaskId` / `currentProcessTaskId` | 共享 | 两个模块通过 taskId 关联到同一任务 |
| `latestResult` | 共享 | 最终结果缓存，两个模块都会读取 |

### 3.3 时序依赖

标注模块和流式输出模块**不会并行运行**，存在严格的先后关系：

1. **上传图纸** → 后端 YOLO 分析 → `annotation_required` SSE → **标注模块激活**
2. 用户完成标注 → POST `/finalize` → 后端视觉分析 + RAG 生成
3. 后端开始流式输出 → `process_stream` SSE → **流式输出模块激活**
4. 流式完成 → `complete` SSE → 打字机收尾 → 最终渲染

两个模块共享同一个 `#reviewTableHost` DOM 容器：
- 标注阶段：`renderAnnotationPendingPanel()` 占据该容器，显示标注汇总卡片
- 流式阶段：审阅表格渲染到同一容器，标注汇总卡片被替换

### 3.4 共同的脆弱点

| 场景 | 风险 | 现有缓解 |
|------|------|----------|
| 标注未完成就触发 `finalize` | `flushSave` 可能保存不完整数据 | 按钮在 `annotateVisitedOnce` 前保持禁用 |
| 流式输出期间用户切换页面 | 打字机定时器继续运行但 DOM 不可见 | `twDrainAll` 在重置工作区时清理 |
| SSE 断线 | 标注阶段依赖 `annotation_required` 事件；流式阶段依赖 `process_stream` | 轮询 `followTaskProgress` 作为兜底恢复 |
| 后端重启 | 前端 EventSource 断开，`startup_token` 变化 | 重连逻辑 + 页面刷新提示 |
| 标注数据量极大 | `_allPages` 全部在内存，`getSummary()` 每次遍历全部 | 当前规模（< 1000 框）无性能问题 |

---

## 关键函数索引

| 函数 | 文件 | 行号 | 说明 |
|------|------|------|------|
| `enterAnnotateMode()` | demo-industrial-console.js | ~4622 | 进入标注全屏 |
| `exitAnnotateMode()` | demo-industrial-console.js | ~4644 | 退出标注全屏 |
| `finalizeAnnotation()` | demo-industrial-console.js | ~4781 | 完成标注触发后续 |
| `ensureAnnotateFullscreen()` | demo-industrial-console.js | ~4563 | 惰性创建全屏 DOM |
| `renderAnnotationPendingPanel()` | demo-industrial-console.js | ~4720 | 渲染标注汇总（带按钮） |
| `renderReviewAnnotationSummary()` | demo-industrial-console.js | ~4686 | 渲染标注汇总（只读） |
| `AnnotationTool` | annotation-tool.js | ~39 | 标注工具类 |
| `AnnotationTool.activate()` | annotation-tool.js | ~83 | 初始化标注页 |
| `AnnotationTool.deactivate()` | annotation-tool.js | ~135 | 保存所有页并清理 |
| `AnnotationTool.getSummary()` | annotation-tool.js | ~186 | 跨页汇总计数 |
| `queueProcessStreamChunk()` | demo-industrial-console.js | ~2066 | 流式文本入口 |
| `twFeedChar()` | demo-industrial-console.js | ~1817 | 逐字符喂入 |
| `twParseLine()` | demo-industrial-console.js | ~1802 | 行解析 |
| `twKick()` | demo-industrial-console.js | ~1840 | 打字机调度器 |
| `twStartNextRow()` | demo-industrial-console.js | ~1849 | 创建行 DOM 开始打字 |
| `twTypeFieldSequence()` | demo-industrial-console.js | ~1884 | 字段序列递归 |
| `twTypeField()` | demo-industrial-console.js | ~1899 | 逐字符输出 |
| `twFinishRow()` | demo-industrial-console.js | ~1924 | 行完成动画 |
| `twOnAllRowsDone()` | demo-industrial-console.js | ~1969 | 全部完成收尾 |
| `twSyncCompletion()` | demo-industrial-console.js | ~2040 | 同步最终结果 |
| `parseStreamingProcessRows()` | demo-industrial-console.js | ~2083 | 批量解析 |
| `normalizeProcessRow()` | demo-industrial-console.js | ~1356 | 行归一化 |
| `_splitTradeFromContent()` | demo-industrial-console.js | ~1337 | 工种提取 |
| `setWorkflowState()` | demo-industrial-console.js | ~788 | 进度条更新 |
| `formatWorkflowThinkingText()` | demo-industrial-console.js | ~126 | 日志转中文提示 |
