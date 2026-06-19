# 手工标注工具 — 设计文档

**分支**：2d  
**日期**：2026-06-09  
**背景**：后续接入 YOLO 模型自动标注，YOLO 存在漏标，需在审阅页内补充手工标注并导出与现有训练数据格式一致的文件。

---

## 目标

在现有"审阅页"（`demo-industrial-console.html`）新增一个**标注工具标签页**，不改动"特征审阅"和"工艺规程"两个现有标签页，允许用户：

1. 在图纸图片上拖拽绘制矩形标注框
2. 为每个框指定类别标签（倒角 / 螺纹孔 / 光孔，可追加自定义类型）
3. 不同标签的框用不同颜色和线型区分
4. 保存后导出 AnyLabeling JSON + YOLO TXT 双格式文件

---

## 类别定义

| 类别 ID | JSON label（英文） | UI 显示（中文） | SVG 框样式 |
|--------|-------------------|--------------|-----------|
| 0 | threaded_hole | 螺纹孔 | 紫色 `#6366f1` 虚线 `stroke-dasharray="6,3"` |
| 1 | circle_hole | 光孔 | 绿色 `#10b981` 实线 |
| 2 | chamfer | 倒角 | 橙色 `#f59e0b` 实线 |

类别顺序与 `F:\小桌面\yolo\temp\augmented_v2\data.yaml` 一致。  
用户追加的自定义类型从 ID 3 起递增，颜色循环取预设色板。

---

## 整体架构

```
前端（纯增量，不改现有代码）
├── demo-industrial-console.html
│     ├── 标签栏新增 <button data-result-view="view-annotate">✏ 标注工具</button>
│     └── 新增 <div id="view-annotate">（与 view-review / view-process 并列）
│           ├── 工具栏：标签选择 / + 添加类型 / 导出 ZIP 按钮
│           ├── 左侧：图纸容器
│           │     ├── <img>（复用 task_id 的 preview_image_url）
│           │     └── <svg>（绝对定位覆盖层，绘制/显示标注框）
│           └── 右侧：标注列表面板（标签 / 坐标 / 删除）
└── annotation-tool.js（新文件，独立模块）

后端（新增，不改现有路由）
└── backend/api/annotations.py
      ├── GET  /api/annotations/<task_id>          读取已有标注
      ├── POST /api/annotations/<task_id>/save     保存标注
      └── GET  /api/annotations/<task_id>/export   导出 ZIP
```

---

## 前端组件设计

### annotation-tool.js

```
AnnotationTool
  ├── init(taskId, imageUrl, imageWidth, imageHeight)
  ├── 状态
  │     ├── annotations[]  — {id, label, points: [[x1,y1],[x2,y2]], pageIndex}
  │     ├── activeLabel    — 当前选中标签的英文 key
  │     └── drawState      — {isDrawing, startX, startY}
  ├── SVG 交互
  │     ├── mousedown → 记录起点，进入绘制状态
  │     ├── mousemove → 实时更新草稿 <rect>
  │     ├── mouseup  → 确认框，写入 annotations[]，调用 autoSave()
  │     └── 每个已保存 <rect> 右键菜单 → 删除
  ├── 坐标映射（显示坐标 ↔ 原始像素）
  │     ├── scaleX = img.clientWidth  / img.naturalWidth
  │     ├── scaleY = img.clientHeight / img.naturalHeight
  │     ├── toReal(x, y) → [x/scaleX, y/scaleY]
  │     └── toDisplay(x, y) → [x*scaleX, y*scaleY]
  └── renderAll() — 遍历 annotations[]，按 LABEL_CONFIG 取色/线型渲染

LABEL_CONFIG = {
  chamfer:       { id: 2, color: "#f59e0b", dash: null,  zh: "倒角"  },
  threaded_hole: { id: 0, color: "#6366f1", dash: "6,3", zh: "螺纹孔" },
  circle_hole:   { id: 1, color: "#10b981", dash: null,  zh: "光孔"  },
}
```

### 布局结构

```
[ 特征审阅 ]  [ 工艺规程 ]  [ ✏ 标注工具 ]   ← 标签栏（新增第三个 tab）

┌─ 工具栏 ───────────────────────────────────────────────────────────┐
│  当前标签：[● 倒角] [● 螺纹孔] [● 光孔]  [+ 添加类型]  [↓ 导出 ZIP] │
└────────────────────────────────────────────────────────────────────┘
┌─ 图纸画布（flex: 1）─────────┐  ┌─ 标注列表（220px）──────────────┐
│  <img> + <svg overlay>       │  │  倒角 #1   x:248 y:73 ...  [×] │
│  cursor: crosshair           │  │  螺纹孔 #1 x:54  y:54 ...  [×] │
│  拖拽绘制框选 · 右键删除     │  │  光孔 #1   x:44 y:148 ... [×]  │
│                              │  │  ──────────────────────────    │
│                              │  │  页面 1 / N  [← 上页] [下页 →] │
└──────────────────────────────┘  └──────────────────────────────────┘
```

### 多页图纸支持

- 切换页面时，SVG 标注框随之切换，数据按 `pageIndex` 分组存储
- 自动保存：每次 mouseup 触发 debounced POST，延迟 1 秒

---

## 后端 API 设计

### 文件：`backend/api/annotations.py`

#### `GET /api/annotations/<task_id>`

从 `output/<task_id>/annotations/` 读取所有 JSON 文件，按页码分组返回。

```json
{
  "task_id": "abc123",
  "pages": {
    "1": { ...labelme json... },
    "2": { ...labelme json... }
  }
}
```

#### `POST /api/annotations/<task_id>/save`

请求体：
```json
{
  "page": 1,
  "shapes": [
    { "label": "chamfer", "points": [[248.0, 73.0], [320.0, 125.0]] }
  ],
  "imageWidth": 6623,
  "imageHeight": 4678,
  "imagePath": "1F13469_P1_page_1.png"
}
```

服务端：
1. 写 `output/<task_id>/annotations/{stem}_page_{n}.json`（AnyLabeling 0.4.36 格式）
2. 写 `output/<task_id>/annotations/{stem}_page_{n}.txt`（YOLO 归一化坐标）
3. YOLO 换算在 Python 端完成（避免浏览器浮点误差）

#### `GET /api/annotations/<task_id>/export`

打包 `output/<task_id>/annotations/` 目录为 ZIP，触发浏览器下载。

---

## 数据格式

### AnyLabeling JSON（与现有文件完全一致）

```json
{
  "version": "0.4.36",
  "flags": {},
  "shapes": [
    {
      "label": "chamfer",
      "text": "",
      "points": [[248.0, 73.0], [320.0, 125.0]],
      "group_id": null,
      "shape_type": "rectangle",
      "flags": {}
    }
  ],
  "imagePath": "1F13469_P1_page_1.png",
  "imageData": null,
  "imageHeight": 4678,
  "imageWidth": 6623,
  "text": ""
}
```

### YOLO TXT

```
2 0.462 0.028 0.073 0.015
```

公式：`cx = (x1+x2)/2/W`, `cy = (y1+y2)/2/H`, `w = (x2-x1)/W`, `h = (y2-y1)/H`

### 文件命名规则

`{pdf_stem}_page_{n}.json` / `{pdf_stem}_page_{n}.txt`

与 `F:\小桌面\yolo\temp\flat_images\` 现有文件命名完全一致，导出后可直接放入训练目录使用。

---

## 不改动的现有代码

- `updated_front/css/industrial-console.css` — 仅追加标注工具专用样式
- `updated_front/demo-industrial-console.html` — 仅追加 tab button 和 `#view-annotate` div
- `updated_front/js/demo-industrial-console.js` — 仅追加 tab 切换时调用 `AnnotationTool.init()`
- 所有现有后端路由 — 不改动

---

## 关键文件索引

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `updated_front/js/annotation-tool.js` | 新建 | 标注工具核心模块 |
| `updated_front/demo-industrial-console.html` | 追加 | 第三个 tab + `#view-annotate` 布局 |
| `updated_front/css/industrial-console.css` | 追加 | 标注工具样式 |
| `updated_front/js/demo-industrial-console.js` | 追加 | tab 切换联动 init |
| `backend/api/annotations.py` | 新建 | 3 个 API 路由 |
| `backend/api/__init__.py` | 追加 | 注册 annotations_bp |
