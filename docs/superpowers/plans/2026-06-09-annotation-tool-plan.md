# 手工标注工具 — 实施计划

**对应设计**：`2026-06-09-annotation-tool-design.md`  
**分支**：2d  
**回退基点**：`29440ad`（设计文档提交）

---

## 执行顺序

```
步骤 1（后端 API）─► 步骤 2（前端核心模块）─► 步骤 3（HTML 布局）─► 步骤 4（JS 联动）─► 步骤 5（CSS）─► 步骤 6（验收）
```

---

## 步骤 1：后端 annotations API

**文件**：`backend/api/annotations.py`（新建）

### 1.1 创建文件，实现三个路由

```python
# -*- coding: utf-8 -*-
import os, json, zipfile, io
from flask import Blueprint, request, jsonify, send_file
from ..config import OUTPUT_FOLDER

annotations_bp = Blueprint("annotations", __name__)

LABEL_TO_ID = {"threaded_hole": 0, "circle_hole": 1, "chamfer": 2}

@annotations_bp.route("/annotations/<task_id>", methods=["GET"])
def get_annotations(task_id): ...

@annotations_bp.route("/annotations/<task_id>/save", methods=["POST"])
def save_annotations(task_id): ...

@annotations_bp.route("/annotations/<task_id>/export", methods=["GET"])
def export_annotations(task_id): ...
```

### 1.2 `get_annotations` 实现

```python
ann_dir = os.path.join(OUTPUT_FOLDER, task_id, "annotations")
if not os.path.isdir(ann_dir):
    return jsonify({"task_id": task_id, "pages": {}})
pages = {}
for f in os.listdir(ann_dir):
    if f.endswith(".json"):
        # 从文件名提取页码：stem_page_N.json
        parts = f.rsplit("_page_", 1)
        page_n = parts[1].replace(".json", "") if len(parts) == 2 else "1"
        with open(os.path.join(ann_dir, f), encoding="utf-8") as fh:
            pages[page_n] = json.load(fh)
return jsonify({"task_id": task_id, "pages": pages})
```

### 1.3 `save_annotations` 实现

请求体：`{page, shapes, imageWidth, imageHeight, imagePath}`

```python
data = request.get_json()
page = data.get("page", 1)
shapes = data.get("shapes", [])
img_w = data["imageWidth"]
img_h = data["imageHeight"]
img_path = data["imagePath"]           # e.g. "1F13469_P1_page_1.png"
stem = os.path.splitext(img_path)[0]   # "1F13469_P1_page_1"

ann_dir = os.path.join(OUTPUT_FOLDER, task_id, "annotations")
os.makedirs(ann_dir, exist_ok=True)

# 写 labelme JSON
labelme = {
    "version": "0.4.36", "flags": {}, "text": "",
    "imagePath": img_path, "imageData": None,
    "imageHeight": img_h, "imageWidth": img_w,
    "shapes": [
        {"label": s["label"], "text": "", "points": s["points"],
         "group_id": None, "shape_type": "rectangle", "flags": {}}
        for s in shapes
    ]
}
json_path = os.path.join(ann_dir, f"{stem}.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(labelme, f, ensure_ascii=False, indent=2)

# 写 YOLO TXT
txt_lines = []
for s in shapes:
    (x1, y1), (x2, y2) = s["points"]
    cx = (x1 + x2) / 2 / img_w
    cy = (y1 + y2) / 2 / img_h
    w  = abs(x2 - x1) / img_w
    h  = abs(y2 - y1) / img_h
    cls_id = LABEL_TO_ID.get(s["label"], len(LABEL_TO_ID))
    txt_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
txt_path = os.path.join(ann_dir, f"{stem}.txt")
with open(txt_path, "w", encoding="utf-8") as f:
    f.write("\n".join(txt_lines))

return jsonify({"ok": True, "json_path": json_path, "txt_path": txt_path})
```

### 1.4 `export_annotations` 实现

```python
ann_dir = os.path.join(OUTPUT_FOLDER, task_id, "annotations")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in os.listdir(ann_dir):
        zf.write(os.path.join(ann_dir, f), f)
buf.seek(0)
return send_file(buf, mimetype="application/zip",
                 as_attachment=True,
                 download_name=f"annotations_{task_id}.zip")
```

### 1.5 注册 Blueprint

**文件**：`backend/api/__init__.py`，在末尾追加：

```python
from .annotations import annotations_bp
app.register_blueprint(annotations_bp, url_prefix="/api")
```

**验证**：`curl http://localhost:5090/api/annotations/fake_id` 返回 `{"pages": {}, "task_id": "fake_id"}`

---

## 步骤 2：前端核心模块

**文件**：`updated_front/js/annotation-tool.js`（新建）

### 2.1 常量与配置

```js
const LABEL_CONFIG = {
  chamfer:       { id: 2, color: "#f59e0b", dash: null,  zh: "倒角"  },
  threaded_hole: { id: 0, color: "#6366f1", dash: "6,3", zh: "螺纹孔" },
  circle_hole:   { id: 1, color: "#10b981", dash: null,  zh: "光孔"  },
};
const EXTRA_COLORS = ["#ec4899","#14b8a6","#f97316","#8b5cf6"];
```

### 2.2 AnnotationTool 类

```js
class AnnotationTool {
  constructor(container, apiBase) { ... }

  // 初始化：接收 taskId、图片 URL、图片原始尺寸
  init(taskId, imageUrl, imageWidth, imageHeight, imageStem) { ... }

  // SVG 覆盖层
  _setupSvg() { ... }         // 绑定 mousedown/mousemove/mouseup
  _onMouseDown(e) { ... }
  _onMouseMove(e) { ... }
  _onMouseUp(e) { ... }

  // 坐标映射
  _toReal(x, y)    { return [x / this._scaleX, y / this._scaleY]; }
  _toDisplay(x, y) { return [x * this._scaleX, y * this._scaleY]; }
  _updateScale()   { /* 从 img.clientWidth/naturalWidth 计算 scaleX/Y */ }

  // 渲染
  renderAll() { ... }         // 清空 SVG，重绘所有 annotations
  _makeRect(ann) { ... }      // 创建 <rect> + <text> label

  // 标签管理
  setActiveLabel(key) { ... }
  addCustomLabel(zh, en) { ... }

  // 持久化
  autoSave() { ... }          // debounce 1s，POST /api/annotations/:taskId/save
  loadFromServer() { ... }    // GET /api/annotations/:taskId
  exportZip() { ... }         // GET /api/annotations/:taskId/export → download

  // 列表面板
  renderList() { ... }        // 更新右侧标注列表 DOM
  deleteAnnotation(id) { ... }
}

window.AnnotationTool = AnnotationTool;
```

### 2.3 SVG 鼠标事件关键逻辑

```js
_onMouseDown(e) {
  this._updateScale();
  const rect = this._svg.getBoundingClientRect();
  this._drawState = {
    isDrawing: true,
    startX: e.clientX - rect.left,
    startY: e.clientY - rect.top,
  };
  // 创建草稿 rect
  this._draftRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  this._svg.appendChild(this._draftRect);
}

_onMouseUp(e) {
  if (!this._drawState.isDrawing) return;
  const {startX, startY} = this._drawState;
  const rect = this._svg.getBoundingClientRect();
  const endX = e.clientX - rect.left;
  const endY = e.clientY - rect.top;
  if (Math.abs(endX - startX) < 5 || Math.abs(endY - startY) < 5) {
    this._svg.removeChild(this._draftRect);
    return; // 过小的框忽略
  }
  // 转换为原始像素坐标
  const [rx1, ry1] = this._toReal(Math.min(startX, endX), Math.min(startY, endY));
  const [rx2, ry2] = this._toReal(Math.max(startX, endX), Math.max(startY, endY));
  this.annotations.push({
    id: Date.now(), label: this.activeLabel,
    points: [[rx1, ry1], [rx2, ry2]],
  });
  this._drawState.isDrawing = false;
  this.renderAll();
  this.renderList();
  this.autoSave();
}
```

### 2.4 右键删除

```js
_makeRect(ann) {
  const rect = document.createElementNS(..., "rect");
  rect.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    this.deleteAnnotation(ann.id);
  });
  return rect;
}
```

---

## 步骤 3：HTML 布局

**文件**：`updated_front/demo-industrial-console.html`

### 3.1 标签栏追加第三个 tab（约第 93 行后）

```html
<button class="result-tab" data-result-view="view-annotate">✏ 标注工具</button>
```

### 3.2 追加 `#view-annotate` 视图（在 `#view-process` 之后）

```html
<div class="result-view" id="view-annotate">
  <!-- 工具栏 -->
  <div class="annotate-toolbar">
    <span class="annotate-label-row" id="annotateLabelRow">
      <!-- JS 动态渲染标签按钮 -->
    </span>
    <button class="button secondary" id="annotateAddTypeBtn">+ 添加类型</button>
    <div style="flex:1"></div>
    <button class="button secondary" id="annotateExportBtn">↓ 导出 ZIP</button>
  </div>
  <!-- 主体 -->
  <div class="annotate-body">
    <div class="annotate-canvas-wrap" id="annotateCanvasWrap">
      <img id="annotateImage" class="annotate-img" alt="标注图纸" />
      <svg id="annotateSvg" class="annotate-svg"></svg>
    </div>
    <div class="annotate-list-panel" id="annotateListPanel">
      <div class="annotate-list-head">
        标注列表 <span id="annotateCount" class="annotate-count"></span>
      </div>
      <div class="annotate-list-body" id="annotateListBody"></div>
      <div class="annotate-list-footer">
        <button class="button secondary task-preview-btn" id="annotatePagePrev">← 上页</button>
        <span id="annotatePageCounter"></span>
        <button class="button secondary task-preview-btn" id="annotatePageNext">下页 →</button>
      </div>
    </div>
  </div>
</div>
```

### 3.3 在 `</body>` 前引入新脚本

```html
<script src="js/annotation-tool.js"></script>
```

---

## 步骤 4：JS 联动

**文件**：`updated_front/js/demo-industrial-console.js`

### 4.1 初始化 AnnotationTool 实例（文件顶部变量区）

```js
let annotationTool = null;
```

### 4.2 tab 切换时初始化（找到现有的 tab 切换逻辑，约在 `data-result-view` 处理处追加）

```js
if (viewId === 'view-annotate') {
  const taskId = backendState.currentTaskId || backendState.currentProcessTaskId;
  const result = backendState.lastResult;
  if (taskId && result) {
    const imageUrl = result.image_url
      ? (API_BASE.replace(/\/api$/, '') + result.image_url)
      : '';
    if (!annotationTool) {
      annotationTool = new AnnotationTool(
        document.getElementById('view-annotate'),
        API_BASE
      );
    }
    // imageStem 从 preview_images[0] 去掉扩展名
    const imageStem = (result.preview_images?.[0] || 'page_1.png').replace(/\.[^.]+$/, '');
    annotationTool.init(
      taskId, imageUrl,
      /* 原始宽高在 result 中无直接字段，初始化后从 img.naturalWidth 取 */
      0, 0, imageStem
    );
  }
}
```

> 注意：`imageWidth/imageHeight` 在 img `onload` 后从 `img.naturalWidth/naturalHeight` 读取，`init()` 内部监听 `onload` 事件。

### 4.3 新任务完成时重置

```js
// 在现有 task complete 处理末尾追加
annotationTool = null;
```

---

## 步骤 5：CSS

**文件**：`updated_front/css/industrial-console.css`，在文件末尾追加

```css
/* ── 标注工具 ── */
.annotate-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.annotate-label-btn {
  padding: 3px 10px;
  border-radius: 4px;
  border: 2px solid;
  background: transparent;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.annotate-label-btn.active { opacity: 1; }
.annotate-label-btn:not(.active) { opacity: 0.45; }

.annotate-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
.annotate-canvas-wrap {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: var(--surface-2, #0f172a);
  cursor: crosshair;
}
.annotate-img {
  display: block;
  max-width: 100%;
  max-height: 100%;
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
  pointer-events: none;
}
.annotate-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.annotate-list-panel {
  width: 220px;
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  background: var(--surface-1, #1f2937);
}
.annotate-list-head {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.annotate-count {
  font-weight: 400;
  color: var(--text-muted);
  margin-left: 4px;
}
.annotate-list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.annotate-list-item {
  padding: 6px 8px;
  border-radius: 4px;
  border-left: 3px solid;
  margin-bottom: 6px;
  cursor: pointer;
  font-size: 12px;
}
.annotate-list-item:hover { filter: brightness(1.15); }
.annotate-list-item-coords {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}
.annotate-list-footer {
  padding: 8px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
}
```

---

## 步骤 6：验收检查清单

| 检查项 | 方法 |
|--------|------|
| 切换到「标注工具」tab，特征审阅/工艺规程不受影响 | 手动切换三个 tab |
| 图纸加载后 SVG 覆盖层对齐 | 上传图纸，切换到标注工具，观察 svg inset |
| 拖拽绘制框，松开后框出现在图纸正确位置 | 绘制后对比坐标与视觉位置 |
| 三类标签框颜色/线型正确区分 | 各选一个标签绘框，视觉确认 |
| 右键删除标注框有效 | 右键任一框，确认消失且列表同步 |
| 自动保存：绘框 1 秒后检查 `output/<task_id>/annotations/` 有 json+txt | 查看后端文件系统 |
| YOLO TXT 坐标值均在 [0,1] 区间 | 打开 txt 文件确认 |
| 导出 ZIP 包含对应页的 json+txt | 点击导出，解压确认 |
| 笔记本（1366px）下标注工具不溢出 | DevTools 调宽度确认 |

---

## 回退方式

```bash
git checkout HEAD -- updated_front/demo-industrial-console.html
git checkout HEAD -- updated_front/css/industrial-console.css
git checkout HEAD -- updated_front/js/demo-industrial-console.js
# 删除新增文件
git rm updated_front/js/annotation-tool.js
git rm backend/api/annotations.py
git checkout HEAD -- backend/api/__init__.py
```
