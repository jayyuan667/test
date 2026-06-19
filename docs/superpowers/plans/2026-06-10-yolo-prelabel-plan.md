# YOLO 预标注集成 — 实施计划

**对应设计**：`2026-06-10-yolo-prelabel-design.md`
**分支**：2d
**回退基点**：`d931264`（设计文档提交）

> **命名校准**：设计文档用了 `annotation_pending` / `review_pending`，但现有 `upload.py` 实际用 `awaiting_review` 作为状态字符串、`review_required` 作为 SSE 事件名。为保持代码一致，本计划落地为：
> - 状态：`awaiting_annotation`
> - SSE：`annotation_required`
> - 恢复函数：`_resume_from_annotation()`（与 `_resume_from_review` 同文件）

---

## 执行顺序

```
1 准备 ─► 2 YOLO 层 ─► 3 转 labelme ─► 4 文本渲染 ─► 5 vision_analyzer 接收 ann_text
       ─► 6 pipeline 改造（关键）─► 7 finalize 路由 ─► 8 config ─► 9 前端 annotation-tool 视觉调整
       ─► 10 前端右侧面板状态分支 ─► 11 移除原 toggle ─► 12 验收
```

后端（步骤 2–8）可独立测试；前端（步骤 9–11）依赖后端完成。

---

## 步骤 1：依赖与权重确认

### 1.1 安装 ultralytics

`requirements.txt` 末尾追加：

```
ultralytics>=8.0
```

在 venv 里 `pip install -r requirements.txt`，验证 `import ultralytics` 不报错。

### 1.2 权重文件存在性检查

启动前手动确认 `F:/小桌面/yolo/v3_weight/best.pt` 存在。后端运行时由 `YOLODetector.get()` 懒检查，缺失时抛 `FileNotFoundError`，被上游捕获走"YOLO 不可用"分支。

### 1.3 烟雾测试

写一次性脚本 `scripts/smoke_yolo.py`：
```python
from ultralytics import YOLO
m = YOLO(r"F:/小桌面/yolo/v3_weight/best.pt")
r = m.predict(r"F:/小桌面/yolo/temp/flat_images/1F13469_P1_page_1.png", conf=0.25)
for box in r[0].boxes:
    print(int(box.cls), float(box.conf), box.xyxy[0].tolist())
```
跑通后删除该脚本，目的只是验证环境 + 权重健康。

---

## 步骤 2：YOLO 检测层

**文件**：`backend/pipeline/yolo_detector.py`（新建）

```python
# -*- coding: utf-8 -*-
"""YOLO 工艺特征检测器 — 单例懒加载。"""
import logging
import threading
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

ID_TO_LABEL = {0: "threaded_hole", 1: "circle_hole", 2: "chamfer"}

class YOLODetector:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, weight_path: str, conf: float, iou: float,
                 imgsz: int, device: str):
        from ultralytics import YOLO
        logger.info("[YOLO] loading %s (device=%s)", weight_path, device)
        self._model = YOLO(weight_path)
        self._conf = conf
        self._iou  = iou
        self._imgsz = imgsz
        self._device = device

    @classmethod
    def get(cls) -> "YOLODetector":
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is None:
                from ..config import (
                    YOLO_WEIGHT_PATH, YOLO_CONF, YOLO_IOU,
                    YOLO_IMG_SIZE, YOLO_DEVICE,
                )
                cls._instance = cls(
                    weight_path=YOLO_WEIGHT_PATH,
                    conf=YOLO_CONF, iou=YOLO_IOU,
                    imgsz=YOLO_IMG_SIZE, device=YOLO_DEVICE,
                )
        return cls._instance

    def detect(self, image_path: str) -> List[Dict[str, Any]]:
        """Returns list of detections, each with keys: cls_id, cls_name, conf, x1,y1,x2,y2 (int pixels)."""
        results = self._model.predict(
            image_path,
            conf=self._conf, iou=self._iou,
            imgsz=self._imgsz, device=self._device,
            verbose=False,
        )
        out = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls)
                xyxy = box.xyxy[0].tolist()
                out.append({
                    "cls_id":   cls_id,
                    "cls_name": ID_TO_LABEL.get(cls_id, f"cls_{cls_id}"),
                    "conf":     float(box.conf),
                    "x1": int(xyxy[0]), "y1": int(xyxy[1]),
                    "x2": int(xyxy[2]), "y2": int(xyxy[3]),
                })
        return out
```

**验收**：单元 `python -c "from backend.pipeline.yolo_detector import YOLODetector; d=YOLODetector.get(); print(d.detect(r'F:/小桌面/yolo/temp/flat_images/1F13469_P1_page_1.png'))"` 输出非空列表。

---

## 步骤 3：YOLO → labelme JSON 写入

**文件**：`backend/pipeline/yolo_to_labelme.py`（新建）

```python
# -*- coding: utf-8 -*-
"""把 YOLO 检测结果写入 labelme 0.4.36 JSON（与手动标注同格式）。"""
import json
import os
from PIL import Image

def write_labelme(image_path: str, detections: list, out_path: str):
    """detections: 来自 YOLODetector.detect()"""
    img = Image.open(image_path)
    w, h = img.size
    shapes = [
        {
            "label":     d["cls_name"],
            "text":      f"auto:{d['conf']:.2f}",
            "points":    [[d["x1"], d["y1"]], [d["x2"], d["y2"]]],
            "group_id":  None,
            "shape_type": "rectangle",
            "flags":     {},
        }
        for d in detections
    ]
    labelme = {
        "version": "0.4.36", "flags": {}, "shapes": shapes,
        "imagePath":  os.path.basename(image_path),
        "imageData":  None,
        "imageHeight": h, "imageWidth": w,
        "text": "",
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(labelme, f, ensure_ascii=False, indent=2)
```

文件名约定：`<png_stem>_page_<n>.json`，与手动标注路径完全一致（前端 `_loadFromServer()` 零改动）。

**验收**：手写一个 fake detections 列表跑 `write_labelme`，输出文件能被 `labelme` 软件打开（或至少 `json.load` 通过）。

---

## 步骤 4：标注 → VLM 中文文本渲染

**文件**：`backend/pipeline/annotation_renderer.py`（新建）

```python
# -*- coding: utf-8 -*-
"""把 annotations/*.json 渲染成给 VLM 的中文结构化文本。"""
import json
import os
from collections import defaultdict

LABEL_TO_ZH = {
    "chamfer":        "倒角",
    "threaded_hole":  "螺纹孔",
    "circle_hole":    "圆孔",
}

def _page_block(page_num: int, shapes: list) -> str:
    if not shapes:
        return f"=== 第 {page_num} 页 ===\n[此页无已知特征位置]\n"
    groups = defaultdict(list)
    for s in shapes:
        groups[s["label"]].append(s["points"])

    lines = [f"=== 第 {page_num} 页 ===",
             "[已人工核对的特征位置]"]
    for label, boxes in groups.items():
        zh = LABEL_TO_ZH.get(label, label)
        lines.append(f"- {zh} ({label})：{len(boxes)} 处")
        for i, ((x1, y1), (x2, y2)) in enumerate(boxes, 1):
            lines.append(f"  · 框 {i}: 左上 ({int(x1)}, {int(y1)}) 右下 ({int(x2)}, {int(y2)})")
    return "\n".join(lines) + "\n"

def render_annotation_text(ann_dir: str) -> str:
    """读 annotations/ 下所有 JSON，按页号排序拼一段中文文本。"""
    if not os.path.isdir(ann_dir):
        return ""
    pages = {}
    for fname in sorted(os.listdir(ann_dir)):
        if not fname.endswith(".json"):
            continue
        parts = fname.rsplit("_page_", 1)
        try:
            page_n = int(parts[1].replace(".json", "")) if len(parts) == 2 else 1
        except ValueError:
            page_n = 1
        with open(os.path.join(ann_dir, fname), encoding="utf-8") as f:
            try:
                data = json.load(f)
                pages[page_n] = data.get("shapes", [])
            except json.JSONDecodeError:
                continue
    if not pages:
        return ""
    blocks = [_page_block(n, pages[n]) for n in sorted(pages)]
    return "\n".join(blocks) + "\n请基于上述特征位置（图纸像素坐标），结合图纸本身进行精确分析。\n"
```

**验收**：构造 fake annotations 目录（含 2 页、混合类别），调用 `render_annotation_text()` 输出中文段落，肉眼检查格式。

---

## 步骤 5：vision_analyzer 接收 annotation_text

**文件**：`backend/pipeline/vision_analyzer.py`

修改 `analyze_drawing` 签名（向后兼容默认空字符串）：

```python
def analyze_drawing(self, image_paths: List[str],
                    annotation_text: str = "") -> Dict[str, Any]:
    ...
    # 拼前缀：annotation_text 不为空时插到视觉分析 prompt 前
    visual_prompt = _PROMPT_VISUAL_ANALYSIS
    if annotation_text.strip():
        visual_prompt = annotation_text + "\n\n" + _PROMPT_VISUAL_ANALYSIS

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_text   = ex.submit(self._call_vlm_batch, _PROMPT_TEXT_EXTRACTION, image_paths)
        f_visual = ex.submit(self._call_vlm_batch, visual_prompt, image_paths)
        ...
```

`_PROMPT_TEXT_EXTRACTION`（文字识别）不动 —— 文字识别不需要框信息。

**验收**：单元——空 `annotation_text` 时返回结果与原版一致；非空时检查日志/捕获 prompt 字符串里含 `[已人工核对的特征位置]`。

---

## 步骤 6：Pipeline 改造（核心）

**文件**：`backend/api/upload.py`

### 6.1 新增辅助：跑 YOLO + 写所有页 JSON

`_process_uploaded_file_task` 内、PNG 化完成后（约第 999 行 `task["progress"] = 25` 之后），插入：

```python
# Step 1.5: YOLO 预标注
emit_step_start(task_id, event_data, event_locks, 2, "YOLO 检测",
                "正在自动标注特征")
_run_yolo_prelabel(task_id, png_paths, output_dir)
task["progress"] = 35
```

新模块级函数：

```python
def _run_yolo_prelabel(task_id: str, png_paths: list, output_dir: str):
    """对所有 PNG 跑 YOLO，写 annotations/*.json，统计汇总，发 SSE。"""
    from ..pipeline.yolo_detector import YOLODetector
    from ..pipeline.yolo_to_labelme import write_labelme
    ann_dir = os.path.join(output_dir, "annotations")
    summary = {"threaded_hole": 0, "circle_hole": 0, "chamfer": 0}
    try:
        detector = YOLODetector.get()
    except Exception as e:
        logger.warning("[%s] YOLO 不可用: %s", task_id, e)
        emit_log(task_id, event_data, event_locks, 2,
                 f"YOLO 不可用 ({e})，请全手动标注")
        # 仍然写空 JSON 让前端正常加载
        for i, p in enumerate(png_paths, 1):
            stem = os.path.splitext(os.path.basename(p))[0]
            write_labelme(p, [],
                          os.path.join(ann_dir, f"{stem}_page_{i}.json"))
        return summary

    total = len(png_paths)
    for i, p in enumerate(png_paths, 1):
        try:
            dets = detector.detect(p)
        except Exception as e:
            logger.warning("[%s] YOLO 第 %d 页失败: %s", task_id, i, e)
            dets = []
        # 统计
        page_count = {"threaded_hole": 0, "circle_hole": 0, "chamfer": 0}
        for d in dets:
            page_count[d["cls_name"]] = page_count.get(d["cls_name"], 0) + 1
            summary[d["cls_name"]] = summary.get(d["cls_name"], 0) + 1
        stem = os.path.splitext(os.path.basename(p))[0]
        write_labelme(p, dets,
                      os.path.join(ann_dir, f"{stem}_page_{i}.json"))
        emit_custom(task_id, event_data, event_locks, "yolo_progress",
                    {"page": i, "total": total, "detections": page_count})
    emit_step_complete(task_id, event_data, event_locks, 2, "YOLO 检测",
                       f"{summary['chamfer']}倒角 / {summary['threaded_hole']}螺纹孔 / {summary['circle_hole']}圆孔")
    return summary
```

### 6.2 暂停进 `awaiting_annotation`

紧跟 6.1 之后（仍在 PNG 化之后、原 VLM 调用之前），插入：

```python
task["status"] = "awaiting_annotation"
update_task_status(task_id, "awaiting_annotation", 35)
persist_review_payload(task)   # 复用现有持久化（保留 png_paths, prefix_hint 等）
emit_custom(
    task_id, event_data, event_locks,
    "annotation_required",
    {
        "task_id": task_id,
        "summary": _last_yolo_summary,   # 见下方
        "pages":   len(png_paths),
    },
)
return    # ⬅ 关键：到此暂停，等用户 POST finalize
```

把 6.1 的 `_run_yolo_prelabel` 返回值赋给 `_last_yolo_summary`。

### 6.3 新增 `_resume_from_annotation`

放在 `_resume_from_review` 旁边：

```python
def _resume_from_annotation(task_id: str):
    """User finalized manual annotation. Resume VLM + downstream."""
    from ..pipeline.annotation_renderer import render_annotation_text
    task = tasks.get(task_id)
    if not task:
        return
    if task.get("status") == "cancelled":
        return
    output_dir = task.get("output_dir") or os.path.join(OUTPUT_FOLDER, task_id)
    png_paths  = task.get("png_paths", []) or []
    ann_dir    = os.path.join(output_dir, "annotations")
    ann_text   = render_annotation_text(ann_dir)

    task["status"] = "processing"
    task["progress"] = 40
    update_task_status(task_id, "processing", 40)
    emit_log(task_id, event_data, event_locks, 3, "标注已确认，开始 VLM 视觉分析")

    # === 把原 _process_uploaded_file_task 里 VLM + 特征报告 + review_pending 那段重构成 helper，这里调用 ===
    _vlm_and_feature_extract(
        task_id=task_id,
        png_paths=png_paths,
        annotation_text=ann_text,
        prefix_hint=task.get("prefix_hint", ""),
        filename=task.get("pdf_name", ""),
        file_hash=task.get("file_hash"),
        use_cache=task.get("use_cache", True),
    )
```

### 6.4 把现有 VLM + 特征报告段抽成 `_vlm_and_feature_extract`

把当前 `_process_uploaded_file_task` 内**从 cache check 到 `persist_review_payload(task)` + `emit_custom("review_required",...)`** 整段（约第 1004–1170 行）抽到模块级函数 `_vlm_and_feature_extract(task_id, png_paths, annotation_text, prefix_hint, filename, file_hash, use_cache)`。

- 内部把 `analyzer.analyze_drawing(png_paths)` 换成 `analyzer.analyze_drawing(png_paths, annotation_text)`
- 其余逻辑（OCR 厚度校验、缓存写入、feature_text 组装、`awaiting_review` 切换）保持不变
- 原 `_process_uploaded_file_task` 在 6.2 处 `return` 后不再到达这段；新 `_resume_from_annotation` 进入这段

这是本步骤最大的改动，**先抽函数 + 跑原流程回归测试**，再启用 6.1/6.2 改动，避免一次性改动太多。

**验收**：
- 上传一个 PDF，状态依次：`processing(0) → processing(25) → processing(35) → awaiting_annotation(35)`
- 此时 `output/<task_id>/annotations/` 已有 JSON 文件
- 通过 finalize 端点（步骤 7）触发后，继续 `processing(40) → … → awaiting_review(50)`

---

## 步骤 7：finalize 路由

**文件**：`backend/api/annotations.py`（已存在）

末尾追加：

```python
@annotations_bp.route("/annotations/<task_id>/finalize", methods=["POST"])
def finalize_annotations(task_id):
    """User confirmed manual annotation; resume the pipeline."""
    # 延迟导入避免循环
    from .upload import _resume_from_annotation, tasks

    task = tasks.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "task not found"}), 404
    if task.get("status") != "awaiting_annotation":
        return jsonify({"ok": False, "error": f"task in status {task.get('status')}, not awaiting_annotation"}), 409

    # 异步触发，避免长请求超时
    threading.Thread(
        target=_resume_from_annotation,
        args=(task_id,), daemon=True,
    ).start()
    return jsonify({"ok": True, "task_id": task_id})
```

注意 `annotations.py` 顶部加 `import threading`。

**验收**：用 curl 模拟 `POST /api/annotations/<id>/finalize`，状态非 `awaiting_annotation` 时返回 409；正常状态返回 200 + 状态切到 `processing`。

---

## 步骤 8：配置

**文件**：`backend/config.py`

新增（环境变量优先）：

```python
YOLO_WEIGHT_PATH = os.getenv("YOLO_WEIGHT_PATH", r"F:/小桌面/yolo/v3_weight/best.pt")
YOLO_CONF        = float(os.getenv("YOLO_CONF", "0.25"))
YOLO_IOU         = float(os.getenv("YOLO_IOU",  "0.45"))
YOLO_IMG_SIZE    = int(os.getenv("YOLO_IMG_SIZE", "1280"))
YOLO_DEVICE      = os.getenv("YOLO_DEVICE", "cpu")
```

**验收**：启动后 `from backend.config import YOLO_WEIGHT_PATH; print(YOLO_WEIGHT_PATH)` 正确。

---

## 步骤 9：前端 — annotation-tool.js 视觉调整

**文件**：`updated_front/js/annotation-tool.js`

### 9.1 改名：光孔 → 圆孔

```js
const LABEL_CONFIG = {
  chamfer:       { id: 2, color: '#f59e0b', dash: null,  zh: '倒角'  },
  threaded_hole: { id: 0, color: '#6366f1', dash: '6,3', zh: '螺纹孔' },
  circle_hole:   { id: 1, color: '#10b981', dash: null,  zh: '圆孔'  },  // ← was '光孔'
};
```

### 9.2 `renderAll()` 移除框旁 `<text>`，加 `<title>` 子元素

定位每个 ann 的渲染循环里：

```js
// 删除整段：const txt = document.createElementNS(NS, 'text'); ... appendChild(txt);

// 在 rect 创建后增加 native tooltip：
const title = document.createElementNS(NS, 'title');
title.textContent = cfg.zh;
rect.appendChild(title);
```

**验收**：标注框旁不再有文字；hover 框 0.5–1s 出现原生 tooltip "倒角"。

---

## 步骤 10：前端 — 右侧面板 `awaiting_annotation` 分支

**文件**：`updated_front/js/demo-industrial-console.js`

### 10.1 监听新 SSE 事件

在现有 SSE 路由里加：

```js
if (eventType === 'annotation_required') {
  backendState.annotationSummary = data.summary || {};
  backendState.annotationPages   = data.pages   || 0;
  renderAnnotationPendingPanel();
  activateResultView('view-review');
}
if (eventType === 'yolo_progress') {
  // 可选：在 workflow 控制台显示 "YOLO 第 i/N 页"
}
```

### 10.2 渲染面板

```js
function renderAnnotationPendingPanel() {
  const host = document.getElementById('reviewTableHost');
  const empty = document.getElementById('reviewEmptyState');
  if (empty) empty.style.display = 'none';
  if (!host) return;
  const s = backendState.annotationSummary || {};
  host.innerHTML = `
    <div class="annotation-pending-card">
      <div style="font-weight:600;margin-bottom:10px;">
        ⓘ YOLO 已完成初步标注，请人工核对并补全
      </div>
      <div style="line-height:1.8;font-size:13px;">
        ● 倒角     <b>${s.chamfer        || 0}</b> 处<br>
        ● 螺纹孔   <b>${s.threaded_hole  || 0}</b> 处<br>
        ● 圆孔     <b>${s.circle_hole    || 0}</b> 处
      </div>
      <div style="margin-top:14px;display:flex;gap:8px;">
        <button class="button primary" id="startAnnotateBtn">✏ 开始标注</button>
        <button class="button secondary" id="finalizeAnnotateBtn" disabled>✓ 完成标注 → 继续</button>
      </div>
    </div>`;
  document.getElementById('startAnnotateBtn').addEventListener('click', () => {
    backendState.annotateVisitedOnce = true;
    document.getElementById('finalizeAnnotateBtn').disabled = false;
    enterAnnotateMode();   // 复用现有全屏标注模态
  });
  document.getElementById('finalizeAnnotateBtn').addEventListener('click', finalizeAnnotation);
}

async function finalizeAnnotation() {
  const taskId = backendState.currentProcessTaskId || backendState.latestTaskId;
  const btn = document.getElementById('finalizeAnnotateBtn');
  if (btn) { btn.disabled = true; btn.textContent = '已确认，等待 VLM…'; }
  try {
    await fetch(`${window.__API_BASE__ || '/api'}/annotations/${taskId}/finalize`,
                { method: 'POST' });
  } catch (e) {
    console.error(e);
    if (btn) { btn.disabled = false; btn.textContent = '✓ 完成标注 → 继续（重试）'; }
  }
}
```

### 10.2 持久化判断（刷新页面恢复）

`pollTaskStatus` 或现有恢复任务的逻辑里，识别 `task.status === 'awaiting_annotation'`，重新调一次 `renderAnnotationPendingPanel()`。Summary 在原 SSE 没拿到的情况下，从 `/api/annotations/<id>` GET 重算每类总数即可。

### 10.3 CSS 微调

`updated_front/css/industrial-console.css` 追加：

```css
.annotation-pending-card {
  padding: 18px 20px;
  border-radius: 10px;
  border: 1px solid #d8e3ef;
  background: linear-gradient(135deg, #fefefe 0%, #f5f9fd 100%);
  margin: 12px;
}
```

**验收**：上传 PDF → 等 YOLO 跑完 → 右侧面板出现卡片；"开始标注"打开全屏；"完成标注"按钮在进入标注页前灰显，进过一次后亮起；点完成后接收 SSE 切回正常 review 流程。

---

## 步骤 11：移除原 toggle 按钮

**文件**：`updated_front/demo-industrial-console.html`、`updated_front/js/demo-industrial-console.js`

### 11.1 HTML

删除 `review-board-footer` 中的：

```html
<button class="button secondary" id="annotateToggleBtn">✏ 标注</button>
```

### 11.2 JS

删除 `annotateToggleBtn` 相关声明 + 事件绑定（保留 `enterAnnotateMode` / `exitAnnotateMode` 函数本身，被步骤 10 复用）。

**验收**：正常的 `awaiting_review` 状态下底部只有 [确认特征并继续] / [修改后重新生成]，不再有 ✏ 标注按钮。

---

## 步骤 12：端到端验收

| 用例 | 期望 |
|---|---|
| 上传含 chamfer + threaded_hole + circle_hole 的 PDF | 状态依次 25 → 35 → awaiting_annotation；annotations/*.json 已存在；前端右侧出现 YOLO 汇总卡片 |
| 点"开始标注"打开全屏 | 框已显示 YOLO 预标注（颜色正确、无文字遮挡、hover 出 tooltip） |
| 删除几个框 / 添加几个框 / 退出 | 自动保存生效；侧栏列表与图一致；侧栏类名"圆孔" |
| 点"完成标注 → 继续" | finalize 200；前端切 loading；几秒后进入 awaiting_review；VLM prompt 里能看到 `[已人工核对的特征位置]` 段（log/debug 抓） |
| 点"确认特征并继续" | 走原工艺规程流程，输出与无 YOLO 时相比，工艺路线对小特征覆盖更准 |
| YOLO 权重缺失模拟（重命名 best.pt） | 不阻断；状态进 awaiting_annotation；annotations/*.json 是空 shapes；前端显示全 0；用户手动标完照常走 |
| 关闭浏览器再打开 | 任务在历史里能恢复到 awaiting_annotation；annotations 还在；继续标注流程正常 |
| 下载 ZIP（在标注页里） | 包含 JSON+TXT+images/，images/ 与 annotations 内容对应 |

---

## 回退预案

| 步骤完成度 | 回退方法 |
|---|---|
| 步骤 1–8 后端做完前 | `git reset --hard d931264` |
| 步骤 6 上线后发现问题 | 把 `_run_yolo_prelabel` 调用 + `return` 注释掉，pipeline 恢复直跑 VLM；annotations.py 的 finalize 路由保留也无副作用 |
| 步骤 9–11 前端做完后想关 YOLO | 设置 `YOLO_WEIGHT_PATH=/non/existent` 让 detector 走"YOLO 不可用"分支，等同于纯手动标注流程 |
