# YOLO 预标注集成设计

**日期**：2026-06-10
**作者**：jay + Claude
**目的**：在 PDF 处理 pipeline 中插入 YOLO 自动预标注步骤，由人工补全后再喂给 VLM，提升特征提取与工艺推演的准确性。

---

## 1. 背景与目标

### 现状
当前 pipeline：`PDF → PNG → VLM 视觉分析 → 特征提取 → [特征审阅 gate] → 工艺规程`。
VLM 直接对原始图纸做特征提取，对密集小特征（倒角、螺纹孔、圆孔等）的位置识别精度有限。

### 目标
- 在 PNG 化之后、VLM 之前插入 YOLO 自动检测，对图纸上的 3 类工艺特征（倒角 / 螺纹孔 / 圆孔）打出预标注框
- 在 VLM 前增加一个强制 gating step：用户必须人工核对并补全标注后才能继续
- 把核对后的标注（类别 + 像素坐标）以结构化中文文本形式注入 VLM prompt，作为"已知特征位置"的辅助上下文
- 不影响现有的"特征审阅" gate 和工艺生成逻辑

### 非目标
- 不替换 VLM 视觉分析（标注是辅助上下文，不是替代）
- 不为旧任务做迁移（只对新上传生效）
- 不在此项目中训练新的 YOLO 模型（使用已有的 `v3_weight/best.pt`）

---

## 2. 高层架构

```
upload → PNG 化 → YOLO 推理 → [annotation_pending 暂停] ⏸
                                ↓ POST /api/annotations/<id>/finalize
                              _resume_from_annotation()
                                ↓
                              加载标注 → 渲染中文文本 → vision_analyzer.analyze_drawing(paths, ann_text)
                                ↓
                              特征提取 → [review_pending 暂停] ⏸    （现有）
                                ↓ POST /api/review/<id>/submit
                              _resume_from_review() → 工艺规程 → done
```

镜像现有 `review_pending → _resume_from_review` 模式，在它前面插一个 `annotation_pending → _resume_from_annotation` 循环。状态机、SSE、前端右侧面板都对称扩展。

---

## 3. 模块变更清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| **`backend/pipeline/yolo_detector.py`** | 新增 | 封装 ultralytics 推理：`YOLODetector` 单例类，懒加载权重；`detect(image_path) -> list[Detection]` 返回 `[(cls_id, conf, x1, y1, x2, y2), ...]` |
| **`backend/pipeline/yolo_to_labelme.py`** | 新增 | 把 YOLO 检测结果转成 labelme JSON（与手动标注同格式），写入 `output/<task_id>/annotations/<stem>.json` |
| **`backend/pipeline/annotation_renderer.py`** | 新增 | 把 `annotations/*.json` 渲染成中文结构化文本（详见第 6 节） |
| **`backend/api/upload.py`** | 改 | PNG 化后调用 YOLO；新增 `_resume_from_annotation()` 函数（与现有 `_resume_from_review` 同文件、同模式）；初次进入暂停时不再直接跑 VLM |
| **`backend/api/annotations.py`** | 改 | 新增 `POST /annotations/<task_id>/finalize` 端点，调用 `upload._resume_from_annotation(task_id)` |
| **`backend/pipeline/vision_analyzer.py`** | 改 | `analyze_drawing(image_paths, annotation_text="")` 新增第二个可选参数，拼接到现有 `_PROMPT_VISUAL_ANALYSIS` 之前 |
| **`backend/config.py`** | 改 | 新增 `YOLO_WEIGHT_PATH` / `YOLO_CONF` / `YOLO_IOU` / `YOLO_IMG_SIZE` / `YOLO_DEVICE` |
| **`requirements.txt`** | 改 | 新增 `ultralytics>=8.0`（含 torch、torchvision） |
| **`updated_front/js/demo-industrial-console.js`** | 改 | 处理新 SSE 状态 `annotation_pending`；右侧面板新增"标注待补全"分支，显示汇总 + "开始标注" + "完成标注 → 继续"按钮；移除底部"✏ 标注"toggle（这条路径只在 gate 里出现） |
| **`updated_front/js/annotation-tool.js`** | 改 | `renderAll()` 移除框旁 `<text>` 文字元素（避免遮挡图纸）；保留颜色 + 侧栏；`LABEL_CONFIG.circle_hole.zh` 改成 `'圆孔'` |
| **`backend/api/events.py`** | 改 | 新增 SSE 事件类型：`yolo_progress`、`annotation_pending`、`annotation_finalized` |

---

## 4. YOLO 检测层（`yolo_detector.py`）

### 接口
```python
class YOLODetector:
    _instance = None

    @classmethod
    def get(cls) -> "YOLODetector":
        """懒加载单例，避免每次任务重新载权重。"""

    def detect(self, image_path: str) -> list[dict]:
        """返回 [{'cls_id': int, 'cls_name': str, 'conf': float,
                  'x1': int, 'y1': int, 'x2': int, 'y2': int}, ...]"""
```

### 实现细节
- 使用 `ultralytics.YOLO(weight_path).predict(image_path, conf=..., iou=..., imgsz=...)`
- 单例懒加载：第一次 `get()` 才加载权重，后续任务复用同一模型对象，避免每次 ~200MB 的载入开销
- 进程级单例（不跨进程共享），多进程场景下每个 worker 独占一份
- 设备：默认 `cpu`，可通过 `YOLO_DEVICE=cuda:0` 切换

### 类映射（写死，与 `augmented_v2/data.yaml` 对齐）
```python
ID_TO_LABEL = {0: "threaded_hole", 1: "circle_hole", 2: "chamfer"}
LABEL_TO_ZH = {"threaded_hole": "螺纹孔", "circle_hole": "圆孔", "chamfer": "倒角"}
```

---

## 5. YOLO → labelme 映射（`yolo_to_labelme.py`）

每张 PNG 一份 JSON，文件名 `<stem>_page_<n>.json`（与手动标注同模式），写入 `output/<task_id>/annotations/`。

```json
{
  "version": "0.4.36",
  "flags": {},
  "shapes": [
    {
      "label": "chamfer",
      "text": "auto:0.87",       ← 来源标记 + 置信度（仅 JSON，不画在 SVG）
      "points": [[1234, 567], [1456, 678]],
      "group_id": null,
      "shape_type": "rectangle",
      "flags": {}
    }
  ],
  "imagePath": "page_1.png",
  "imageData": null,
  "imageHeight": 4678,
  "imageWidth": 6623,
  "text": ""
}
```

关键点：
- 现有 `annotation-tool.js _loadFromServer()` 直接复用，**无格式改动**
- `text` 字段：YOLO 写 `"auto:<conf>"`，手动新增框时为空字符串（现有行为）。labelme 打开时一眼看出来源
- SVG 渲染时不解析 `text` 字段——框上**不画文字**

---

## 6. 标注 → VLM 文本渲染（`annotation_renderer.py`）

输入：`annotations/` 目录下所有 JSON
输出：单段中文文本，拼到 `_PROMPT_VISUAL_ANALYSIS` 之前

### 渲染格式
```
[已人工核对的特征位置 — 共 3 类]
- 倒角 (chamfer)：5 处
  · 框 1: 左上 (1234, 567) 右下 (1456, 678)
  · 框 2: 左上 (2300, 800) 右下 (2480, 920)
  · 框 3: ...
- 螺纹孔 (threaded_hole)：8 处
  · 框 1: ...
- 圆孔 (circle_hole)：3 处
  · 框 1: ...

请基于上述特征位置（图纸像素坐标），结合图纸本身进行精确分析。
```

设计选择：
- **坐标用原始像素**：VLM 同时拿到原图，像素坐标天然对齐
- **包含手工与自动**：`text` 字段不参与渲染（VLM 不需要知道来源）
- **按类聚合**：减少 prompt 冗余
- **多页**：每页一段，前面加 `=== 第 N 页 ===` 分隔
- **0 检测**：该类不出现在文本中；全 0 时整段文本为 `[此页无已知特征位置]`

---

## 7. 状态机 + SSE 事件

### 状态扩展
现有：`uploading → vision_analysis → feature_extract → review_pending → process_gen → completed`
新增：`uploading → yolo_inference → annotation_pending → vision_analysis → ...`

`backend/task_store.py` 的 `update_task_status()` 接受新状态字符串，无表结构改动。

### SSE 事件

| 事件类型 | 何时触发 | payload |
|---|---|---|
| `yolo_progress` | 每页 YOLO 完成 | `{page: N, total: M, detections: {chamfer: 5, ...}}` |
| `annotation_pending` | YOLO 全部完成、暂停时 | `{task_id, summary: {chamfer: 12, threaded_hole: 19, circle_hole: 8}, pages: 3}` |
| 后续事件 | finalize 端点返回 HTTP 200 后，前端等待现有 `vision_analysis_start` 等事件，无需新增 finalize SSE | |

---

## 8. 前端 — 右侧面板新分支

`#view-review` 内的 `#reviewEmptyState` / `#reviewTableHost` 受 `task.status` 控制：

```
status === 'annotation_pending':
  ┌────────────────────────────────────────────┐
  │ ⓘ YOLO 已完成初步标注，请人工核对并补全     │
  │                                            │
  │ 本次检测到：                                │
  │   ● 倒角     5 处                          │
  │   ● 螺纹孔   8 处                          │
  │   ● 圆孔     3 处                          │
  │                                            │
  │ [✏ 开始标注]                                │
  │ ──────────────────────────────────────     │
  │ [✓ 完成标注 → 继续视觉分析]                 │
  │ （灰显，用户至少进过一次标注页后才亮起）     │
  └────────────────────────────────────────────┘

status === 'review_pending'（现有）:
  特征审阅表格 + [确认特征并继续] / [修改后重新生成]
```

- "开始标注"复用现有 `enterAnnotateMode()`（直接打开全屏标注模态）
- 全屏模态里的"✕ 退出"返回此页，不推进 pipeline
- "完成标注 → 继续"POST `/api/annotations/<id>/finalize` 触发后端 resume，前端切到 loading 状态等待 `vision_analysis_start` 事件
- 底部原"✏ 标注"toggle 按钮**移除**——这条路径只在 gate 里出现，避免在非标注阶段误触

---

## 9. 标注工具视觉调整

`annotation-tool.js renderAll()`：
- ✗ 移除 SVG `<text>` 元素（原本在每个框旁画"● 倒角"等文字，会遮挡图纸数字尺寸/公差等内容）
- ✓ 保留 `<rect>` 框（颜色 + 描边 + 淡填充）
- ✓ 给每个 `<rect>` 加 `<title>` 子元素：`<title>倒角</title>`，浏览器原生 tooltip，零遮挡
- ✓ 右侧"标注列表"侧栏继续按当前格式显示每个框的标签 + 坐标（不在图上）

`LABEL_CONFIG` 改动：
```js
circle_hole: { id: 1, color: '#10b981', dash: null, zh: '圆孔' }  // 原 '光孔'
```

---

## 10. 错误处理 / 边界情况

| 场景 | 处理 |
|---|---|
| YOLO 模型权重缺失 / 加载失败 | log error；状态进入 `annotation_pending`，每页 JSON 写 `shapes:[]`；前端汇总显示"YOLO 不可用，请全手动标注"；不阻断流程 |
| 某页 0 个检测 | 该页 JSON 写空 `shapes`，正常进 `annotation_pending`；汇总按 0 显示 |
| 单页 YOLO 推理崩溃 | 该页 `shapes:[]` + log；其他页继续；状态仍进 `annotation_pending` |
| 用户进了标注页但 0 改动直接退出 + 完成标注 | 允许；送给 VLM 的就是 YOLO 原始结果（包括 0 检测情况下空文本） |
| 用户关闭浏览器后回来 | 任务停在 `annotation_pending`；通过现有历史列表恢复任务上下文（含已存的 YOLO 预标注）继续标注 |
| 并发：用户在 finalize 之前继续编辑标注 | finalize 端点是幂等触发，重复 POST 返回相同结果；前端按钮 POST 后立即禁用避免双击 |
| 老任务回放（无 annotations 目录） | `_resume_from_annotation()` 不触发；老任务保持旧流程；新逻辑只对新上传生效 |
| 标注 finalize 成功后 VLM 失败 | 走现有 VLM 失败处理（记入 `vision_failures`）；任务状态进 `review_pending` 时附带失败信息；不需要回到 `annotation_pending` |

---

## 11. 配置

`backend/config.py` 新增（均可 env 覆盖）：

```python
YOLO_WEIGHT_PATH = os.getenv("YOLO_WEIGHT_PATH", r"F:/小桌面/yolo/v3_weight/best.pt")
YOLO_CONF        = float(os.getenv("YOLO_CONF", "0.25"))
YOLO_IOU         = float(os.getenv("YOLO_IOU",  "0.45"))
YOLO_IMG_SIZE    = int(os.getenv("YOLO_IMG_SIZE", "1280"))  # 工业图纸高分辨率友好
YOLO_DEVICE      = os.getenv("YOLO_DEVICE", "cpu")
```

`requirements.txt` 新增 `ultralytics>=8.0`（含 torch、torchvision）。

---

## 12. 测试要点

| 范围 | 用例 |
|---|---|
| `yolo_detector` | 加载已有 v3 权重；对 `temp/flat_images/1F13469_P1_page_1.png` 输出非空检测；权重路径错误时优雅降级 |
| `yolo_to_labelme` | 输出 JSON 通过 labelme 0.4.36 schema 校验；像素坐标在 `[0, naturalWidth/Height]` 范围 |
| `annotation_renderer` | 空 annotations 目录返回 `[此页无已知特征位置]`；混合类别正确分组聚合；多页带 `=== 第 N 页 ===` |
| upload 端到端 | 上传 PDF → 状态依次经过 `yolo_inference → annotation_pending`，前端能收到 SSE；POST finalize 后继续 VLM；最终 `completed` |
| 前端 | `annotation_pending` 状态正确渲染右侧面板；"开始标注"打开全屏；"完成标注"按钮在进过一次标注页后亮起；finalize 后切 loading |
| 标注工具视觉 | 框旁不再出现 `<text>` 文字；hover 时显示原生 tooltip；侧栏标签为"圆孔"而非"光孔" |

---

## 13. 范围外（后续工作）

- 在 VLM prompt 中嵌入标注框的视觉缩略图（如直接画框后的图）
- 标注质量评分 / 不确定度提示（哪些 YOLO 检测置信度低需要人工重点核对）
- 自动以 YOLO 检测做候选框，鼠标 hover 候选框可"一键采纳"的辅助交互
- 老任务批量补跑 YOLO + 重生成特征报告
