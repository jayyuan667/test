# 智能工艺系统 — 前端控制台

> 基于 2D 工艺图纸的 AI 特征提取、工艺规程自动生成、知识库管理一体化 Web 前端。

## 目录

- [项目概览](#项目概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [页面架构与模块说明](#页面架构与模块说明)
- [核心前端实现逻辑](#核心前端实现逻辑)
- [后端 API 联动详解](#后端-api-联动详解)
- [数据流全链路](#数据流全链路)
- [启动方式](#启动方式)

---

## 项目概览

本项目是一个**工业工艺规程自动生成系统**的前端控制台。用户上传 2D 工艺图纸（PDF/PNG/JPG）或 PRT 三维模型，系统通过 AI（VLM 视觉语言模型 + RAG 检索增强生成）自动提取零件特征并生成加工工艺规程。前端提供完整的工艺入库、特征审阅、工艺生成、历史记录回看和数据库浏览功能。

**核心业务流程：**

```
上传图纸/模型 → AI 特征提取 → 人工审阅确认 → 工艺规程生成 → 导出/入库
```

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 页面结构 | 原生 HTML5，单文件 `demo-industrial-console.html` |
| 样式 | 原生 CSS（`industrial-console.css`，约 5000 行工业风设计系统） |
| 交互逻辑 | 原生 JavaScript（`demo-industrial-console.js`，约 5000+ 行） |
| 3D 预览 | Three.js + GLTFLoader（模块化引入） |
| 标注工具 | 自研 SVG BoundingBox 标注模块（`annotation-tool.js`） |
| PDF 导出 | Vue 3 组件 `export-file-modal.vue`，使用 jsPDF + OPPOSans 字体 |
| 后端通信 | Fetch API + SSE（Server-Sent Events）长连接 |
| 后端 | Python Flask，端口 5090，SQLite 数据库 |

---

## 项目结构

```
updated_front/
├── demo-industrial-console.html    # 主 HTML（所有页面结构与弹窗）
├── css/
│   └── industrial-console.css      # 全量样式（工业风设计系统）
├── js/
│   ├── demo-industrial-console.js  # 核心业务逻辑（状态管理、API 调用、DOM 渲染）
│   ├── annotation-tool.js          # SVG 标注工具（BoundingBox 标注类）
│   ├── three-init.js               # Three.js 初始化与 GLTFLoader 挂载
│   ├── three.module.min.js         # Three.js 库文件
│   ├── GLTFLoader.js               # Three.js GLTF 加载器
│   └── BufferGeometryUtils.js      # Three.js 几何工具
├── export-file-modal.vue           # Vue 3 PDF 导出组件（独立于主应用）
├── start_flask_demo.bat            # 一键启动脚本（启动后端 + 打开浏览器）
├── stop_flask_demo.bat             # 一键停止脚本
├── kb_import_selftest.zip          # 知识库导入自测用示例 ZIP
└── system/                         # 系统资源目录（当前为空）
```

---

## 页面架构与模块说明

系统采用**侧栏导航 + 单页切换**架构，共 4 个主页面：

### 1. 工艺入库（`page-zip`）

**功能：** 通过上传 ZIP 工艺包批量导入工艺知识到数据库。

- **入库目标选择：** 支持选择已有库或新建私有工艺库，可选复制公共库基线
- **冲突模式：** 替换入库 / 保留旧版
- **状态区：** 空闲 → 上传中 → 解析中 → 入库中 → 完成，带进度条和实时阶段提示
- **结果区：** 已匹配记录卡片、未匹配项列表、批次日志三个 Tab

### 2. 工艺生成（`page-generate`）

**功能：** 上传单个图纸/模型，AI 自动提取特征并生成工艺规程。

- **左侧上传面板：** 拖拽上传区域，上传后切换为图纸预览（支持多页翻页、缩放、全屏）
- **右侧结果面板：**
  - **特征审阅 Tab：** 表格化展示 AI 提取的工艺特征（尺寸公差、粗糙度、形位公差等），支持 `contenteditable` 原位编辑
  - **工艺规程 Tab：** 打字机动画逐行输出工序表（工序号、工种、工序内容），支持编辑
- **顶部 HUD：** 统一进度条 + 阶段提示（带呼吸灯动画），可折叠
- **工具栏：** 上传文件、选择检索知识库、特征缓存开关、重置工作区

### 3. 历史记录（`page-list`）

**功能：** 浏览所有历史工艺生成任务。

- **统计卡片：** 总数、已完成、待审阅、总工序数
- **表格：** 任务名/模型、状态、完成时间、工序数、快照查看、删除
- **分页：** 支持按完成日期筛选，批量选择删除
- **快照弹窗：** 分栏预览（左图右文），支持图片缩放/翻页、3D 模型预览（GLTF）、特征审阅和工艺规程详情

### 4. 数据库浏览（`page-db`）

**功能：** 浏览和编辑知识库中的工艺记录。

- **访问控制：** 默认锁定，需先完成一次 ZIP 入库才解锁编辑功能；支持只读浏览公共库/个人库
- **三栏布局：** 左侧筛选面板（关键词、产品类型、来源、状态）、中间记录列表、右侧详情面板
- **详情面板：** 记录元数据、模型快照查看、工艺内容编辑、特征报告按页编辑
- **操作：** 编辑记录、删除废表、删除整个用户库（公共库只读保护）

---

## 核心前端实现逻辑

### 状态管理（`backendState` 对象）

整个应用使用一个全局 `backendState` 对象管理所有状态，包括：

```javascript
backendState = {
  history: [],                    // 历史任务列表
  records: [],                    // 数据库记录
  taskMap: {},                    // 任务槽位 → 任务卡片数据映射
  latestTaskId: '',               // 最新任务 ID
  latestResult: null,             // 最新任务结果
  latestZipReport: null,          // 最新 ZIP 入库报告
  activeLibraryKey: 'public',     // 当前活跃知识库 key
  retrievalLibraryKey: 'public',  // 当前检索库 key
  canBrowseDb: false,             // 数据库是否可浏览
  dbBrowseOnly: false,            // 是否只读模式
  taskBusy: false,                // 任务是否进行中
  taskProgress: 0,                // 任务进度百分比
  previewImages: [],              // 预览图片 URL 列表
  previewIndex: 0,                // 当前预览图片索引
  previewZoom: 1,                 // 预览缩放比
  processStreamText: '',          // SSE 流式工艺文本累积
  processStreamRows: [],          // 解析后的工艺行
  twRowQueue: [],                 // 打字机动画队列
  twIsTyping: false,              // 打字机是否正在输出
  featureCacheEnabled: false,     // 特征缓存开关
  // ...
}
```

### DOM 引用模式

所有 DOM 元素在脚本顶部通过 `document.getElementById` 获取并缓存为常量（约 150+ 个引用），后续操作直接使用这些引用，避免重复查询。

### 页面切换

通过 `activatePage(pageId)` 函数控制：隐藏所有 `.page`，显示目标页面，更新侧栏 `.nav-item.active` 状态。导航时会检查是否有进行中的任务（ZIP 导入或工艺生成），有则锁定其他页面。

### 打字机动画引擎（`tw*` 系列函数）

工艺规程的流式输出采用自研打字机引擎：

1. **`queueProcessStreamChunk(taskId, chunk)`** — 接收 SSE 推送的文本块，逐字符喂入 `twFeedChar`
2. **`twFeedChar(ch)`** — 逐字符累积到行缓冲区，遇到 `\n` 时解析为工序行（`0010@工种@内容` 格式）
3. **`twStartNextRow()`** — 从队列取出一行，创建 `<tr>` DOM，调用 `twTypeFieldSequence` 逐字段打字
4. **`twTypeField(el, text, speed, onDone)`** — 逐字符输出到 DOM 元素，中文/标点/数字使用不同延迟模拟真人打字节奏
5. **`twFinishRow(tr, row)`** — 行完成动画（`row-new` CSS 动画），暂停 320-600ms 后开始下一行
6. **`twOnAllRowsDone()`** — 全部行完成后触发最终渲染、状态同步和历史记录更新

### 标注工具（`annotation-tool.js`）

`AnnotationTool` 类提供基于 SVG 的矢量矩形标注功能，用于在 2D 图纸上人工标记工艺特征区域（倒角、螺纹孔、圆孔等），为后续 AI 特征提取提供训练数据。

#### 标签系统

内建三类标签，各有独立的 `id`、颜色、虚线样式：

| 键名 | id | 颜色 | 虚线 | 中文 |
|------|----|------|------|------|
| `chamfer` | 2 | `#f59e0b` | 无 | 倒角 |
| `threaded_hole` | 0 | `#6366f1` | `6,3` | 螺纹孔 |
| `circle_hole` | 1 | `#10b981` | 无 | 圆孔 |

- **自定义标签：** 用户可通过 `prompt` 输入中文名称新增标签，从 5 色循环池（`#ec4899`, `#14b8a6`, `#f97316`, `#8b5cf6`, `#06b6d4`）自动取色
- **持久化：** 自定义标签存储在 `localStorage` key `annotate.customLabels.v1`，页面刷新后保留
- **安全删除：** 删除自定义标签前会扫描所有页面的标注数据，若仍有引用则拒绝删除并提示页数
- **全局暴露：** `getAnnotationLabelMeta()` 挂载到 `window`，供主应用（`demo-industrial-console.js`）渲染标注汇总卡片时获取颜色和中文名

#### 坐标系统

SVG 通过 `position: absolute; inset: 0` 覆盖在 `<img>` 上，两者处于同一个 `inline-block` 容器内：

- **`_imgOffset()`：** 用 `getBoundingClientRect()` 分别获取 `<img>` 和 `<svg>` 的矩形，计算偏移量 `(dx, dy)` 和缩放比 `(sx, sy)`。使用 `getBoundingClientRect` 而非 `clientWidth` 是为了兼容祖先元素上的 CSS transform
- **`_toReal(svgX, svgY)`：** SVG 像素坐标 → 图片自然坐标（减偏移、除缩放比）
- **`_toDisplay(realX, realY)`：** 图片自然坐标 → SVG 像素坐标（乘缩放比、加偏移）
- 所有标注的 `points` 字段存储的是**图片自然坐标** `[[x1,y1], [x2,y2]]`，渲染时实时换算为显示坐标，因此缩放不影响标注精度

#### 绘制流程

1. `mousedown`（左键）：记录起始点，创建 `<rect>` 草稿矩形（半透明填充 + 当前标签颜色描边，`pointer-events: none`）
2. `mousemove`：实时更新草稿矩形的 `x/y/width/height`（取 `Math.min` 处理反向拖拽）
3. `mouseup`：移除草稿矩形，若拖拽距离 ≥ 6px 则将起止点通过 `_toReal` 转为自然坐标，push 到 `_annotations` 数组，触发 `renderAll()` + `_renderList()` + `_scheduleSave()`
4. 右键点击已有标注框 → 删除该标注

#### 多页支持

- `_allPages` 对象以页码字符串（`"1"`, `"2"`, ...）为键，存储每页的标注数组
- 切换页面时（`_goPage`）自动保存当前页到 `_allPages`，再加载目标页的标注
- `_loadPage(idx)` 设置 `<img>` 的 `src`，图片加载完成后自动调用 `fitToViewport()` 适配视口

#### 选中态渲染

`renderAll()` 按选中状态排序，选中框最后绘制（保证在最上层）：

- **光晕效果：** 选中标注外层渲染白色描边（`stroke: #ffffff, width: 6`）+ 黑色虚线环（`stroke: #111827, dash: 6 4`），圆角 `rx=4`
- **浮动标签：** 仅选中时在框上方显示药丸形标签（如"螺纹孔 3"），背景色取标签色，白色文字，避免未选中框的标签遮挡
- **独立编号：** 按标签类型独立递增序号（倒角 1、倒角 2、螺纹孔 1…），SVG 标签文字与右侧列表序号严格一致

#### 双向联动选中

`_selectAnnotation(id, opts)` 支持三个来源：

| 来源 | `opts` | 滚动行为 |
|------|--------|----------|
| 画布点击 | `{ fromCanvas: true }` | 列表滚动到对应项 |
| 列表点击 | `{ fromList: true }` | 画布滚动到对应矩形中心 |
| 程序调用 | `{}` | 两侧都滚动 |

- 画布滚动通过 `_scrollCanvasToAnnotation()` 计算标注中心的显示坐标 → 转为 scroll 容器坐标 → `scrollTo({ behavior: 'smooth' })`
- 列表滚动通过 `_scrollListToAnnotation()` 用 `querySelector` 按 `data-ann-id` 找到 DOM 元素 → `scrollIntoView({ block: 'nearest' })`

#### 缩放

- **状态：** `_zoom`（当前缩放比）、`_fitZoom`（最近一次 fit-to-viewport 计算的缩放比）
- **范围：** 0.05x ~ 8.0x
- **`_applyZoom()`：** 直接设置 `<img>` 的 `style.width/height` 为 `naturalWidth * _zoom`，同时覆盖 `max-width: none; max-height: none` 取消 CSS 限制
- **Ctrl+滚轮缩放：** 以光标为中心 — 缩放前记录光标下的图片自然坐标 `(pxNat, pyNat)`，缩放后反算 scroll 偏移使该点保持在光标屏幕位置
- **工具栏按钮：** 放大（×1.25）、缩小（÷1.25）、适应视口（`fitToViewport`）、100%（`setZoom(1.0)`）
- **`fitToViewport()`：** 根据 scroll 容器可用宽高（减去 28px padding）和图片自然尺寸计算 `Math.min(sx, sy)` 作为 fit 缩放比

#### 持久化机制

- **自动保存：** 标注变更后 `_scheduleSave()` 启动 1s 防抖定时器，触发 `_autoSaveNow()` POST 到 `/api/annotations/{taskId}/save`
- **保存 payload：** `{ page, shapes: [{label, points}], imageWidth, imageHeight, imagePath }`
- **页面关闭兜底：** `sendBeaconSave()` 使用 `navigator.sendBeacon()` 发送 Blob JSON，浏览器保证在页面卸载后仍能发送
- **服务端加载：** `_loadFromServer()` GET `/api/annotations/{taskId}`，返回 `{ pages: { "1": { shapes: [...] }, ... } }`，合并到 `_allPages`
- **生命周期：** `activate()` 注册所有事件 → `deactivate()` 返回 Promise（可 await 最终保存完成）→ 清理 SVG 和事件监听
- **`flushSave()`：** 公开方法，供外部调用方等待保存结束后再执行后续操作（如关闭标注面板）
- **`getSummary()`：** 返回跨所有页面的标注汇总 `{ chamfer: N, threaded_hole: N, circle_hole: N, pages: N }`，主应用用于刷新待标注状态卡片

#### 导出

`_exportZip()` 先触发 `_autoSaveNow()` 确保服务端有最新数据，600ms 后创建临时 `<a>` 标签触发 `/api/annotations/{taskId}/export` 下载，文件名为 `annotations_{taskId}.zip`

### 3D 预览（`three-init.js`）

通过 `importmap` 引入 Three.js 模块，`GLTFLoader` 挂载到 `window.THREE`。`make3DViewer()` 工厂函数创建 3D 查看器实例，支持 GLTF 模型加载、OrbitControls 交互（拖拽旋转/缩放）。在历史快照和数据库预览中用于展示 PRT 模型的三维视图。

### 导出功能（`export-file-modal.vue`）

独立的 Vue 3 组件，使用 jsPDF 生成 A4 工艺规程卡片 PDF：

- 左侧嵌入图纸预览图，右侧展示模型信息属性表
- 下方为工艺规程表格（工序号、工种、工序名称及内容、设备型号、工时）
- 支持多行自动换行、跨页续表、斑马条纹
- 使用自研 `OPPOSans-L` 中文字体嵌入

---

## 后端 API 联动详解

### API 基础

```javascript
const API_BASE = window.__API_BASE__ || 'http://localhost:5090/api';
```

所有请求通过统一的 `apiFetch(path, options)` 封装，自动处理 JSON Content-Type 和错误响应。

### 完整 API 端点清单

#### 1. 任务生命周期

| 端点 | 方法 | 用途 | 触发时机 |
|------|------|------|----------|
| `/api/upload` | POST | 上传单个 PRT 模型 | 用户在工艺生成页上传 PRT 文件 |
| `/api/upload_drawing` | POST | 上传 2D 图纸（PDF/PNG/JPG） | 用户上传 2D 图纸，附带 `library_key` 和 `use_cache` |
| `/api/batch_upload` | POST | 批量上传 PRT 模型 | 用户选择多个 PRT 文件 |
| `/api/result/{taskId}` | GET | 获取任务结果（含工艺规程、特征报告、预览图） | 轮询任务进度 + 获取最终结果 |
| `/api/review/{taskId}` | POST | 提交特征审阅确认/修改后重新生成 | 用户在特征审阅面板确认或修改后重新生成 |
| `/api/events/{taskId}` | SSE | 实时事件流（进度更新、流式工艺输出） | 任务开始后建立 EventSource 连接 |
| `/api/export/{taskId}` | POST | 导出工艺文件（PDF/Excel） | 用户点击导出按钮，附带当前编辑后的 `rows` |

#### 2. 知识库管理

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/kb/import_zip` | POST | 上传 ZIP 工艺包批量入库 |
| `/api/kb/sample_zip` | GET | 下载示例 ZIP 工艺包 |
| `/api/library/status` | GET | 获取知识库状态（是否就绪、可浏览、库列表） |
| `/api/library/scopes` | GET | 获取所有知识库作用域（公共/私有库列表） |
| `/api/library/scopes/{key}` | DELETE | 删除整个用户库 |
| `/api/library/records` | GET | 分页获取知识库记录（支持筛选） |
| `/api/library/records/{id}` | PUT | 更新知识库记录（产品类型、工艺内容、特征报告） |
| `/api/library/records/{id}` | DELETE | 删除单条知识库记录 |

#### 3. 历史与标注

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/history` | GET | 获取历史任务列表 |
| `/api/history/{taskId}` | DELETE | 删除历史任务 |
| `/api/annotations/{taskId}` | GET | 获取标注数据 |
| `/api/annotations/{taskId}/save` | POST | 保存标注数据（JSON body） |
| `/api/annotations/{taskId}/finalize` | POST | 标注完成，触发后续工艺生成 |
| `/api/annotations/{taskId}/export` | GET | 导出标注数据为 ZIP |

#### 4. 系统

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/health` | GET | 后端健康检查（启动脚本用） |
| `/api/startup_token` | GET | 获取启动令牌（检测后端重启） |

### 前后端交互时序图

#### 2D 图纸工艺生成完整流程

```
前端                           后端
 │                              │
 │  POST /upload_drawing        │
 │  (file + library_key)        │
 │─────────────────────────────→│
 │  ← { task_id }               │
 │                              │
 │  GET /events/{taskId}  (SSE) │
 │─────────────────────────────→│
 │  ← event: progress {10%}     │
 │  ← event: log "图纸分析中"    │
 │  ← event: progress {30%}     │
 │  ← event: feature_report     │
 │     { review_text, ... }     │
 │  ← event: status "awaiting_review"
 │                              │
 │  [用户审阅特征，点击确认]       │
 │  POST /review/{taskId}       │
 │  { confirmed: true, ... }    │
 │─────────────────────────────→│
 │  ← event: progress {50%}     │
 │  ← event: process_chunk      │
 │     "0010@料@备料：..."       │
 │  ← event: process_chunk      │
 │     "0020@铣@铣方六面..."     │
 │  ← ... (流式输出)             │
 │  ← event: progress {100%}    │
 │  ← event: status "completed" │
 │                              │
 │  GET /result/{taskId}        │
 │  (最终完整结果)               │
 │─────────────────────────────→│
 │  ← { process_flow,           │
 │     feature_report_text,     │
 │     preview_image_urls, ... }│
```

#### ZIP 知识库入库流程

```
前端                           后端
 │                              │
 │  POST /kb/import_zip         │
 │  (zip_file + conflict_mode   │
 │   + library_mode)            │
 │─────────────────────────────→│
 │  ← { batch_id, summary,      │
 │     matched_pairs,           │
 │     target_library }         │
 │                              │
 │  GET /library/status         │
 │  (刷新库状态)                 │
 │─────────────────────────────→│
 │                              │
 │  GET /library/records        │
 │  (刷新记录列表)               │
 │─────────────────────────────→│
```

### SSE 事件类型

通过 `EventSource` 连接 `/api/events/{taskId}`，后端推送以下事件：

| 事件名 | 数据结构 | 说明 |
|--------|----------|------|
| `progress` | `{ progress: number }` | 任务进度更新（0-100） |
| `log` | `{ tag: string, text: string }` | 实时日志（显示在 HUD 阶段提示） |
| `feature_report` | `{ review_text, ... }` | 特征提取报告（触发审阅面板渲染） |
| `status` | `{ status: string }` | 状态变更（`awaiting_review` / `completed` / `error`） |
| `process_chunk` | `{ text: string }` | 工艺规程流式文本块（喂入打字机引擎） |
| `gltf_url` | `{ url: string }` | PRT 模型 3D 预览 URL |
| `preview_image` | `{ url: string }` | 预览图片 URL |

### 特征缓存机制

前端提供 `⚡ 特征缓存` 开关（`backendState.featureCacheEnabled`）。开启后，上传图纸时在 FormData 中附加 `use_cache=1`。后端对同一份图纸（按文件 hash 判断）跳过 VLM 特征提取，直接返回上次的分析结果，加快重复上传场景的响应速度。

### 知识库多库架构

系统支持**多知识库隔离**：

- **公共工艺库（public）：** 全局共享，只读
- **用户私有库：** 通过 ZIP 入库创建，可编辑/删除
- **检索库选择：** 工艺生成时可选择用哪个库做 RAG 检索（`retrievalLibraryKey`），默认公共库
- **入库目标选择：** ZIP 入库时可选择目标库，支持新建（可选复制公共基线）

库状态通过 `sessionStorage` 持久化（`ZIP_UNLOCK_SESSION_KEY` / `ZIP_SCOPE_SESSION_KEY` / `RETRIEVAL_SCOPE_SESSION_KEY`），页面刷新后恢复。

---

## 数据流全链路

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   用户上传    │────→│  Flask 后端   │────→│  VLM 视觉模型 │
│  PDF/PRT/ZIP │     │  /api/upload  │     │  特征提取     │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    SSE 推送 │ 进度/日志/特征
                           │
                    ┌──────▼───────┐
                    │  前端 HUD     │
                    │  实时更新进度  │
                    └──────┬───────┘
                           │
              特征报告到达   │
                    ┌──────▼───────┐
                    │  特征审阅面板  │ ← 用户编辑/确认
                    │  表格化展示    │
                    └──────┬───────┘
                           │
              POST /review  │ 确认特征
                           │
                    ┌──────▼───────┐     ┌──────────────┐
                    │  Flask 后端   │────→│  RAG 检索     │
                    │  工艺生成管线  │     │  知识库匹配    │
                    └──────┬───────┘     └──────────────┘
                           │
                    SSE 流式推送 │ 工艺规程文本
                           │
                    ┌──────▼───────┐
                    │  打字机引擎   │
                    │  逐行动画输出  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  工艺规程面板  │ ← 用户编辑/导出
                    │  contenteditable │
                    └──────────────┘
```

---

## 启动方式

### 一键启动（推荐）

```bat
start_flask_demo.bat
```

脚本自动检测 Python 环境（`.venv` > `py` > `python`），释放 5090 端口，启动后端，等待健康检查通过后打开浏览器。

### 手动启动

```bash
# 1. 启动后端
cd F:\Work_Dir\2D-v
python -m backend.run

# 2. 浏览器打开
# http://localhost:5090/dev/demo-industrial-console
```

### 停止

```bat
stop_flask_demo.bat
```

---

## 设计系统

- **配色：** 蓝色品牌色（`#1a56db`）、橙色强调色（`#ff6528`）、语义色（绿/黄/红）
- **圆角：** 大卡片 18-20px，小元素 10-12px，药丸 999px
- **字体：** PingFang SC / Microsoft YaHei，等宽使用 Cascadia Code / Fira Code
- **动画：** 按钮光泽扫过（`button-sheen`）、进度条呼吸（`workflow-pulse`）、行入场（`processRowIn`）、打字光标闪烁（`cursorBlink`）
- **响应式：** 1260px 断点折叠网格布局，980px 断点隐藏侧栏
- **无障碍：** `skip-link`、`focus-visible` 样式、`aria-live` 区域、`aria-expanded` 状态
