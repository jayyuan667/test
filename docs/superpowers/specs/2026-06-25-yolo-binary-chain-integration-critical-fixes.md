# YOLO 7 类二分类链式模型集成：关键修改建议

> 日期：2026-06-25
> 关联设计：`2026-06-25-yolo-binary-chain-integration-design.md`
> 目的：在方案已进入实施阶段时，只列出可能导致上线失败、推理不稳定或前后端契约不一致的关键问题。

---

## 结论

当前方案的总体方向可继续：后端通过 HTTP 调独立 GPU 服务，GPU 服务常驻加载 7 个二分类模型，返回统一检测结果。

但必须补齐以下关键点，否则容易出现：

- 多任务并发导致 GPU OOM 或模型对象并发不安全。
- 多页图纸一次性批量请求超时。
- 前端等待期间无 YOLO 进度反馈。
- 新 7 类只在部分链路生效，VLM 标注文本和标注图仍按旧 3 类处理。
- GPU 服务端口暴露后可被任意内网调用。
- 现有 capability / 安装契约测试与新架构冲突。

---

## 1. GPU 服务必须串行化推理

### 问题

原设计写到：

```text
批量接口：一次传所有页面，服务端串行处理每页（GPU 已独占，并行无益）
FastAPI 默认线程池处理请求即可，不需要异步/队列
```

这两句存在冲突。FastAPI 默认会并发处理多个请求。如果两个用户同时上传图纸，GPU 服务可能同时执行多条 `detect_batch`，每条又会调用 7 个模型。

风险：

- GPU 显存峰值不可控。
- ultralytics 模型对象并发调用可能不稳定。
- 单机 GPU 服务吞吐反而下降。
- 多任务互相拖慢，后端请求超时。

### 修改建议

GPU 服务中必须加全局推理锁，或者实现单 worker 队列。

最低实现：

```python
import threading

infer_lock = threading.Lock()

@app.post("/detect_batch")
def detect_batch(req: DetectBatchRequest):
    with infer_lock:
        return detector.detect_batch(req.images)
```

如果后续需要排队状态，再升级为任务队列：

```text
POST /detect_batch_async -> {job_id}
GET  /detect_batch_async/{job_id} -> progress/result
```

一期不一定要做异步队列，但必须保证 GPU 推理同一时间只有一个请求进入。

---

## 2. 不建议一次性上传所有页面并固定 30s 超时

### 问题

当前设计：

```text
后端收集所有 PNG → 一次 POST /detect_batch
默认 30s 超时
```

多页 PDF 或高分辨率图纸会执行：

```text
页数 × 7 个模型
```

例如 8 页图纸就是 56 次模型推理。30s 很容易超时。一次性 base64 传所有图片也会放大内存和网络开销。

### 修改建议

推荐改为按页调用：

```text
for page in png_paths:
    POST /detect_page
    写该页 LabelMe
    发 yolo_progress SSE
```

如果保留 `/detect_batch`，也至少要改超时策略：

```python
timeout = base_timeout + per_page_timeout * len(image_paths)
```

建议配置：

```python
YOLO_SERVICE_TIMEOUT_BASE = 10
YOLO_SERVICE_TIMEOUT_PER_PAGE = 20
```

并限制单次请求页面数，例如：

```text
MAX_YOLO_BATCH_PAGES = 8
```

超过后后端自动分批。

---

## 3. `yolo_progress` 不能等整批完成后才发

### 问题

设计要求：

```text
yolo_progress SSE 事件格式保持现有结构，前端无感
```

但如果后端一次性调用 `/detect_batch`，只有 GPU 服务返回后才能逐页遍历 `pages` 并发 `yolo_progress`。这会导致长时间无进度事件，用户看到页面卡在“YOLO 检测”。

这不一定破坏协议，但会破坏当前交互预期和可观测性。

### 修改建议

优先采用按页调用 GPU 服务，每页完成后立即发：

```python
emit_custom(
    task_id,
    event_data,
    event_locks,
    "yolo_progress",
    {"page": i, "total": total, "detections": page_count},
)
```

如果坚持批量接口，则 GPU 服务需要支持进度回传或任务式查询；否则不要宣称“进度体验不变”。

---

## 4. 7 类标签要覆盖完整链路，不只是 annotations.py

### 问题

设计只提到：

```text
backend/api/annotations.py 的 LABEL_TO_ID 改为从 yolo_labels import
frontend ReviewPanel 色板扩展到 7 色
```

但当前后端还有一条关键链路：

```text
backend/pipeline/annotation_renderer.py
```

这里负责：

- 将 labelme 标注转成中文结构化文本给 VLM。
- 将标注框画到图片上给后续视觉分析。

当前只支持旧 3 类：

```python
LABEL_TO_ZH = {
    "chamfer": "倒角",
    "threaded_hole": "螺纹孔",
    "circle_hole": "圆孔",
}
```

如果不改，新 7 类会出现：

- VLM 提示词中直接出现英文 label。
- 标注框颜色走默认灰色。
- 虚线/实线语义不一致。

### 修改建议

新增 `backend/pipeline/yolo_labels.py` 不应只包含 ID，也应包含展示元数据：

```python
YOLO_LABELS = [
    {"name": "code_hole", "id": 0, "zh": "编码孔", "color": (16, 185, 129), "dash": False},
    {"name": "through_hole", "id": 1, "zh": "通孔", "color": (59, 130, 246), "dash": False},
    {"name": "blind_hole", "id": 2, "zh": "盲孔", "color": (14, 165, 233), "dash": False},
    {"name": "threaded_hole", "id": 3, "zh": "螺纹孔", "color": (99, 102, 241), "dash": True},
    {"name": "chamfer", "id": 4, "zh": "倒角", "color": (245, 158, 11), "dash": False},
    {"name": "counterbore", "id": 5, "zh": "沉头孔", "color": (249, 115, 22), "dash": True},
    {"name": "countersink", "id": 6, "zh": "锥口孔", "color": (139, 92, 246), "dash": True},
]
```

然后由它生成：

```python
YOLO_CLASSES
LABEL_TO_ID
ID_TO_LABEL
LABEL_TO_ZH
LABEL_TO_RGB
LABEL_DASHED
```

`annotations.py`、`annotation_renderer.py`、`yolo_detector.py` 都从这里 import。

---

## 5. 前端标签源应改 `types/annotate.ts`，不是只改 ReviewPanel

### 问题

当前前端内置标签并不是 3 个，而是在：

```text
frontend-react/src/types/annotate.ts
```

并且已经有 11 个内置标签。`ReviewPanel.tsx` 只是消费这些标签，不是标签源。

如果只改 `ReviewPanel.tsx`，会造成：

- AnnotationPanel 工具栏仍显示旧标签。
- UploadPanel / FullscreenPreview 颜色仍按旧配置。
- `circle_hole` 仍保留为内置标签。
- 新的 `counterbore` / `countersink` / `blind_hole` 可能没有中文名或颜色。

### 修改建议

前端应修改统一源：

```text
frontend-react/src/types/annotate.ts
```

建议将内置标签改为 7 类：

```typescript
export const BUILT_IN_LABELS = [
  { name: 'code_hole',      color: '#10b981', borderStyle: 'solid', isCustom: false },
  { name: 'through_hole',   color: '#3b82f6', borderStyle: 'solid', isCustom: false },
  { name: 'blind_hole',     color: '#0ea5e9', borderStyle: 'solid', isCustom: false },
  { name: 'threaded_hole',  color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'chamfer',        color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'counterbore',    color: '#f97316', borderStyle: '6,3',   isCustom: false },
  { name: 'countersink',    color: '#8b5cf6', borderStyle: '6,3',   isCustom: false },
]
```

并同步：

```typescript
export const LABEL_DISPLAY_NAMES = {
  code_hole: '编码孔',
  through_hole: '通孔',
  blind_hole: '盲孔',
  threaded_hole: '螺纹孔',
  chamfer: '倒角',
  counterbore: '沉头孔',
  countersink: '锥口孔',
}
```

旧标注中的 `circle_hole` 可以继续通过 fallback 显示，不建议继续作为新建内置标签。

---

## 6. GPU 服务需要模型路径配置和访问限制

### 问题

部署方案只写：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

缺少：

- 模型目录配置。
- 服务访问控制。
- 请求体大小限制。
- 健康检查与推理接口的边界。

如果在内网直接暴露 `0.0.0.0:8000`，任何能访问该端口的人都可以提交图片触发 GPU 推理。

### 修改建议

补充环境变量：

```bash
YOLO_MODEL_DIR=/opt/yolo-binary-models
YOLO_DEVICE=cuda:0
YOLO_MAX_IMAGES=8
YOLO_MAX_IMAGE_MB=20
YOLO_API_TOKEN=...
```

后端调用时带 token：

```http
Authorization: Bearer <YOLO_API_TOKEN>
```

GPU 服务校验 token：

```python
def require_token(request: Request):
    expected = os.getenv("YOLO_API_TOKEN", "")
    if expected and request.headers.get("Authorization") != f"Bearer {expected}":
        raise HTTPException(status_code=401)
```

部署侧至少使用防火墙或反向代理限制只允许 Flask 后端访问 `/detect_batch`。

---

## 7. capability / 安装契约需要同步调整

### 问题

当前项目已有能力检查和安装契约：

```text
backend/services/capabilities.py
backend/test_capabilities.py
backend/test_dependency_manifest.py
backend/test_installation_contract.py
README.md / INSTALL.md / START.md
```

现有逻辑假设：

- 本地存在 `best.onnx` 或 `best.pt`。
- 本地安装 `onnxruntime` 或 `ultralytics/torch`。
- 文档说明通过 `uv sync --extra yolo` 启用本地 YOLO。

新方案改为远程 GPU 服务后，这些契约需要重写，否则测试和文档会与实现冲突。

### 修改建议

`inspect_yolo_capability()` 返回建议：

```python
{
    "available": True,
    "provider": "gpu_service",
    "reason": "",
    "service_url": "...",
    "models_loaded": 7,
    "gpu_available": True,
}
```

不可用时：

```python
{
    "available": False,
    "provider": "gpu_service",
    "reason": "YOLO GPU 服务不可用或模型未加载完成"
}
```

测试也要改成 mock `YOLOServiceClient.health()`，不再检查本地模型文件。

安装文档也应改口径：

```text
后端默认通过 YOLO_SERVICE_URL 调用 GPU 服务。
本地 best.onnx / best.pt 仅作为 legacy fallback，不是默认路径。
```

---

## 8. 降级策略要明确是否仍写空 LabelMe

### 问题

当前 `_run_yolo_prelabel` 在 YOLO 不可用时会给每页写空 LabelMe JSON，前端仍可进入人工标注。

新设计只写：

```text
返回 {"yolo_available": false} → 用户全手动标注
```

但没有明确是否仍写空标注文件。

如果不写空 LabelMe，前端加载标注时可能出现空状态差异，后续 `finalize` 和渲染链路也可能找不到对应页 JSON。

### 修改建议

保持旧行为：

```text
YOLO 服务不可用、单页推理失败、超时：
  - 仍为每一页写空 LabelMe JSON
  - 仍允许进入 YOLO 审阅/人工标注
  - summary 全 0
```

这样前端和后续 annotation renderer 不需要额外分支。

---

## 最低限度落地清单

如果当前没有时间完整重构，至少完成：

- [ ] GPU 服务加全局推理锁，避免并发推理。
- [ ] 后端不要固定 30s 处理所有页面；超时按页数放大，或改为逐页调用。
- [ ] 每页完成后发 `yolo_progress`，不要等整批完成才发。
- [ ] `annotation_renderer.py` 同步支持 7 类中文名、颜色、虚线规则。
- [ ] `frontend-react/src/types/annotate.ts` 改为 7 类统一标签源。
- [ ] GPU 服务增加 `YOLO_MODEL_DIR` 配置。
- [ ] `/detect_batch` 增加访问限制，至少 token 或内网防火墙。
- [ ] `inspect_yolo_capability()`、相关 pytest、安装文档同步改为 GPU service 语义。
- [ ] YOLO 不可用时继续写空 LabelMe JSON，保持人工标注流程稳定。

---

## 建议优先级

P0，必须立刻修：

1. GPU 推理串行化。
2. 超时/批量策略不能固定 30s 全页请求。
3. `annotation_renderer.py` 支持 7 类。
4. 前端统一标签源改成 7 类。

P1，建议本期同步修：

1. GPU 服务访问限制。
2. capability / 安装文档 / 测试契约同步。
3. YOLO 不可用时空 LabelMe 行为写入设计。
