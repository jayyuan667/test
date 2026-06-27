# YOLO 7 类二分类链式模型集成 — 设计文档

> Date: 2026-06-25
> Branch: `yolo-react`
> 原始模型训练：`/Users/caojiayuan/Projects/experiments/test/`

## 1. 背景 & 现状

### 1.1 项目 YOLO 占位现状

当前 `backend/pipeline/yolo_detector.py` 实现了单模型 `YOLODetector`：

- 加载一个 `best.pt`（ONNX 优先，ultralytics 兜底）
- 类别映射硬编码 `{0: "threaded_hole", 1: "circle_hole"}` — 仅 2 类
- `backend/api/annotations.py` 的 `LABEL_TO_ID` 也仅 3 类：`threaded_hole`, `circle_hole`, `chamfer`
- 实际训练数据中不存在 `circle_hole`，该类为占位假类

### 1.2 已有 7 类二分类模型

在独立实验项目（`liu4th` 服务器，8× RTX 3090）中训练了 7 个 yolo11n 二分类模型：

| 模型文件 | 类别 | 大小 |
|----------|------|------|
| `binary_code_hole.pt` | code_hole | ~5.4MB |
| `binary_threaded_hole.pt` | threaded_hole | ~5.4MB |
| `binary_chamfer.pt` | chamfer | ~5.4MB |
| `binary_through_hole.pt` | through_hole | ~5.4MB |
| `binary_counterbore.pt` | counterbore | ~5.4MB |
| `binary_countersink.pt` | countersink | ~5.4MB |
| `binary_blind_hole.pt` | blind_hole | ~5.4MB |

链式推理策略：按 `code_hole → threaded_hole → chamfer → through_hole → counterbore → countersink → blind_hole` 顺序，每步检出后在图上涂黑该区域再喂给下一模型。最终整体召回率 87.4%，threaded_hole 召回 49.5%，through_hole 召回 23.5%。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  GeneratePage → "YOLO审阅" tab → 不变                   │
│  SSE: yolo_progress 逐页事件 → 格式不变                 │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /api/upload
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend (Flask)                        │
│                                                         │
│  upload.py: _run_yolo_prelabel()                        │
│    for each page:                                       │
│      ┌──────────────────────────────────────┐           │
│      │ YOLOServiceClient (新)              │           │
│      │  - detect(page_path) → detections    │           │
│      │  - POST {name, data: base64}         │           │
│      │  - Authorization: Bearer <token>     │           │
│      └──────────────┬───────────────────────┘           │
│      → write LabelMe JSON (yolo_to_labelme)             │
│      → emit yolo_progress SSE                           │
│                   │ HTTP (内网)                          │
│  annotations.py: LABEL_TO_ID ← yolo_labels              │
│  capabilities.py: inspect_yolo → 调 /health             │
└───────────────────┼─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│           GPU Service (FastAPI, liu4th:8000)             │
│                                                         │
│  POST /detect  (Authorization required)                 │
│    ┌──────────────────────────────────────┐             │
│    │ BinaryChainDetector                  │             │
│    │  - threading.Lock 全局推理锁         │             │
│    │  - 启动加载 7× binary_*.pt           │             │
│    │  - 检测顺序（实验最优）:             │             │
│    │    code→threaded→chamfer→through→    │             │
│    │    counterbore→countersink→blind     │             │
│    │  - 每步检出 → 涂黑 → 下一步          │             │
│    │  - device: CUDA (YOLO_DEVICE env)    │             │
│    └──────────────────────────────────────┘             │
│                                                         │
│  GET /health  (no auth)                                 │
│    → {ok, models_loaded, gpu_available, device}         │
└─────────────────────────────────────────────────────────┘
```

**关键设计决策：**

- 链检测顺序≠语义 ID 顺序。链顺序由实验数据决定（高频先检出涂黑），ID 顺序由工程语义分组
- GPU 服务启动时加载 7 个模型到显存（~38MB 权重，推理时约 1-2GB 显存），常驻内存
- **逐页调用**：后端每页单独 `POST /detect`，收到结果后立即写 LabelMe + 发 SSE 事件 → 前端获得逐页进度感
- **GPU 推理锁**：`BinaryChainDetector.detect()` 内部用 `threading.Lock` 保护，多个并发请求串行化，避免 GPU 抖动 / OOM / ultralytics 线程安全问题
- 后端用 `httpx` 调 GPU 服务，单页超时 15s（覆盖 7 模型链式推理）
- `/health` 无需鉴权，`/detect` 需要 `Authorization: Bearer <token>` 共享密钥

---

## 3. API 契约

### 3.1 GPU 服务

#### `GET /health`（无需鉴权）

```json
{
  "ok": true,
  "models_loaded": 7,
  "gpu_available": true,
  "device": "cuda:0"
}
```

#### `POST /detect`（需要鉴权）

Request header：`Authorization: Bearer <YOLO_SERVICE_TOKEN>`

Request body：
```json
{
  "name": "page_1.png",
  "data": "<base64 encoded PNG>"
}
```

Response：
```json
{
  "name": "page_1.png",
  "detections": [
    {"class": "code_hole",     "conf": 0.92, "x1": 100.0, "y1": 200.0, "x2": 180.0, "y2": 280.0},
    {"class": "threaded_hole", "conf": 0.73, "x1": 300.0, "y1": 150.0, "x2": 380.0, "y2": 230.0}
  ]
}
```

401 响应（token 错误/缺失）：
```json
{"detail": "Invalid or missing authorization token"}
```

### 3.2 后端变化

- `YOLOServiceClient` 封装 HTTP 调用，自动携带 `Authorization` header
- `_run_yolo_prelabel` 改为：**逐页循环** `png_paths` → 每页 `POST /detect` → 收到即写 LabelMe JSON → 发 `yolo_progress` SSE 事件 → 进入下一页
- 超时按单页配置：`YOLO_SERVICE_TIMEOUT = 15s`（单页 7 模型链推理在 GPU 上应 < 5s）
- `inspect_yolo_capability()` 改为调 `/health`，连接失败/超时 → 不可用

### 3.3 降级策略

同机房部署，GPU 服务不可用视为异常。HTTP 调用抛出异常 → `_run_yolo_prelabel` 捕获 → **仍为每一页写空 LabelMe JSON**（`shapes: []`）→ 返回 `{"yolo_available": false}` → 用户进入全手动标注。

**关键：即使 YOLO 不可用，也必须写空 LabelMe 文件**。理由：
- 前端标注加载逻辑按页查找 JSON，找不到会差异对待
- `finalize` 和 `annotation_renderer` 链路假定每页都有对应 JSON
- 写空 JSON 意味着前端标注工具正常启动，只是没有预标注框

这保持了与现有降级逻辑完全一致的行为。

---

## 4. 类别映射重构

### 4.1 统一定义源

新增 `backend/pipeline/yolo_labels.py`，作为**唯一的类别定义源**，覆盖 ID 映射、中文名、颜色、虚线样式（同时服务于 `annotations.py` 和 `annotation_renderer.py`）：

```python
# 7 类工程特征 — 按工程语义分组
YOLO_CLASSES = [
    "code_hole",       # 0  孔类 — 编码孔/基准孔
    "through_hole",    # 1  孔类 — 通孔
    "blind_hole",      # 2  孔类 — 盲孔
    "threaded_hole",   # 3  孔类 — 螺纹孔
    "chamfer",         # 4  加工特征 — 倒角
    "counterbore",     # 5  加工特征 — 沉头孔
    "countersink",     # 6  加工特征 — 锥口孔
]

LABEL_TO_ID = {name: i for i, name in enumerate(YOLO_CLASSES)}
ID_TO_LABEL = {i: name for i, name in enumerate(YOLO_CLASSES)}

# ── 渲染用映射（annotation_renderer.py 从此 import）──
LABEL_TO_ZH = {
    "code_hole":     "编码孔",
    "through_hole":  "通孔",
    "blind_hole":    "盲孔",
    "threaded_hole": "螺纹孔",
    "chamfer":       "倒角",
    "counterbore":   "沉头孔",
    "countersink":   "锥口孔",
}

# RGB colors — 与前端 annotate.ts BUILT_IN_LABELS 色板一致
LABEL_TO_RGB = {
    "code_hole":     (59,  130, 246),   # #3b82f6 blue
    "through_hole":  (34,  197, 94),    # #22c55e green
    "blind_hole":    (239, 68,  68),    # #ef4444 red
    "threaded_hole": (99,  102, 241),   # #6366f1 indigo
    "chamfer":       (245, 158, 11),    # #f59e0b amber
    "counterbore":   (249, 115, 22),    # #f97316 orange
    "countersink":   (139, 92,  246),   # #8b5cf6 violet
}

# 虚线边框类（螺纹孔类用虚线区分）
LABEL_DASHED = {"threaded_hole"}
```

### 4.2 涉及文件

| 文件 | 变更 |
|------|------|
| `backend/pipeline/yolo_labels.py` | 🆕 新增 — ID/中文/颜色/虚线 统一定义 |
| `backend/pipeline/annotation_renderer.py` | `LABEL_TO_ZH`/`LABEL_TO_RGB`/`LABEL_DASHED` 改为从 `yolo_labels` import，删除文件内硬编码 |
| `backend/api/annotations.py` | `LABEL_TO_ID` 改为从 `yolo_labels` import |
| `backend/pipeline/yolo_detector.py` | 默认 `class_names` 更新为 7 类映射 |
| `backend/pipeline/yolo_to_labelme.py` | 不变 — 已通过 `cls_name` 字段写入 |

### 4.3 移除 `circle_hole`

`circle_hole` 不属于 7 类体系，训练数据中不存在。向前兼容：已保存标注中如有 `circle_hole`，标注加载时保留原样不报错，但 YOLO 预标注不再产出该类。`annotation_renderer.py` 中对 `circle_hole` 的映射一并移除。

---

## 5. GPU 服务实现

### 5.1 文件结构

```
gpu_service/
  main.py              # FastAPI app, 启动加载模型
  chain_detector.py    # BinaryChainDetector 核心类
  requirements.txt     # ultralytics, fastapi, uvicorn, pillow
```

### 5.2 BinaryChainDetector（含全局推理锁）

```python
import threading
import numpy as np

CLASS_ORDER = [
    "code_hole",       # 高频优先检出涂黑
    "threaded_hole",
    "chamfer",
    "through_hole",
    "counterbore",
    "countersink",
    "blind_hole",      # 稀有类最后，置信度最高
]
CLASS_CONF = {
    "code_hole": 0.25, "threaded_hole": 0.25, "chamfer": 0.25,
    "through_hole": 0.25, "counterbore": 0.30, "countersink": 0.30,
    "blind_hole": 0.50,
}

class BinaryChainDetector:
    def __init__(self, model_dir: str, device: str = "cuda:0"):
        from ultralytics import YOLO
        self.device = device
        self._lock = threading.Lock()  # 全局推理锁 — 防止并发 GPU 访问
        self.models = {}
        for name in CLASS_ORDER:
            model = YOLO(f"{model_dir}/binary_{name}.pt")
            model.to(device)
            self.models[name] = model

    def detect(self, image: np.ndarray) -> list[dict]:
        """单张图链式推理（线程安全），返回所有 detection"""
        with self._lock:  # 同一时刻仅一个请求使用 GPU
            img = image.copy()
            all_dets = []
            for cls_name in CLASS_ORDER:
                results = self.models[cls_name](
                    img, conf=CLASS_CONF[cls_name], verbose=False
                )
                boxes = []
                if results[0].boxes is not None:
                    for b in results[0].boxes:
                        x1, y1, x2, y2 = b.xyxy[0].cpu().tolist()
                        boxes.append((x1, y1, x2, y2))
                        all_dets.append({
                            "class": cls_name,
                            "conf": round(float(b.conf[0]), 4),
                            "x1": round(x1, 1), "y1": round(y1, 1),
                            "x2": round(x2, 1), "y2": round(y2, 1),
                        })
                # 涂黑检测区域
                for (x1, y1, x2, y2) in boxes:
                    img[max(0, int(y1)):max(0, int(y2)),
                        max(0, int(x1)):max(0, int(x2))] = 0
            return all_dets
```

### 5.3 FastAPI 入口（鉴权 + 配置）

```python
# main.py
import os
from fastapi import FastAPI, HTTPException, Header
from chain_detector import BinaryChainDetector

MODEL_DIR  = os.getenv("YOLO_MODEL_DIR", "./models_binary")
DEVICE     = os.getenv("YOLO_DEVICE", "cuda:0")
TOKEN      = os.getenv("YOLO_SERVICE_TOKEN", "")
MAX_IMG_MB = int(os.getenv("YOLO_MAX_IMAGE_MB", "20"))

app = FastAPI()
detector = BinaryChainDetector(MODEL_DIR, DEVICE)

@app.get("/health")
def health():
    return {
        "ok": True,
        "models_loaded": len(detector.models),
        "gpu_available": True,
        "device": DEVICE,
    }

@app.post("/detect")
def detect(body: dict, authorization: str = Header(None)):
    # 鉴权
    expected = f"Bearer {TOKEN}"
    if not TOKEN or authorization != expected:
        raise HTTPException(status_code=401,
            detail="Invalid or missing authorization token")

    import base64
    from PIL import Image
    import io

    name = body["name"]
    raw = base64.b64decode(body["data"])
    # 请求体大小限制
    if len(raw) > MAX_IMG_MB * 1024 * 1024:
        raise HTTPException(status_code=413,
            detail=f"Image exceeds {MAX_IMG_MB}MB limit")

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    detections = detector.detect(np.array(img))
    return {"name": name, "detections": detections}
```

### 5.4 部署 & 安全

```bash
# liu4th 服务器 — 环境变量
export YOLO_MODEL_DIR=/data/models/yolo_binary
export YOLO_DEVICE=cuda:0
export YOLO_SERVICE_TOKEN="<随机生成 64 字符>"
export YOLO_MAX_IMAGE_MB=20

cd gpu_service
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

**安全约束：**
- `YOLO_SERVICE_TOKEN`：共享密钥，后端通过 `Authorization: Bearer <token>` 携带
- `YOLO_MAX_IMAGE_MB`：单张图片上限 20MB，防止内存耗尽
- `/health` 无需鉴权（供能力检测轮询），`/detect` 强制 Bearer 校验
- GPU 服务仅监听 `127.0.0.1`，由 nginx 反向代理暴露，限制来源 IP 为后端服务器

**nginx 最小配置**（仅允许 Flask 后端 `192.168.1.x` 访问 `/detect`）：
```nginx
server {
    listen 8000;
    server_name _;
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
    location /detect {
        allow 192.168.1.0/24;   # Flask 后端所在子网
        deny all;
        proxy_pass http://127.0.0.1:8000;
        client_max_body_size 20m;
    }
}
```

不做公网端口暴露；如确需跨机器，走内网 VPN 或 mTLS。

---

## 6. 后端改动

### 6.1 新增 `YOLOServiceClient`（逐页调用 + 鉴权）

```python
# backend/pipeline/yolo_service_client.py
import base64
import httpx
from pathlib import Path

class YOLOServiceClient:
    def __init__(self, base_url: str, token: str, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {token}"}

    def health(self) -> dict:
        r = httpx.get(f"{self.base_url}/health", timeout=5)
        r.raise_for_status()
        return r.json()

    def detect(self, image_path: str) -> dict:
        """单页检测，返回 {"name": ..., "detections": [...]}"""
        data = Path(image_path).read_bytes()
        r = httpx.post(
            f"{self.base_url}/detect",
            json={
                "name": Path(image_path).name,
                "data": base64.b64encode(data).decode(),
            },
            headers=self._headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()
```

### 6.2 修改 `_run_yolo_prelabel`（逐页循环 + 实时 SSE）

原逻辑：逐页加载图片 → `detector.detect(img)` → 写 LabelMe JSON → 发 SSE 事件。

改为：

```python
for i, png_path in enumerate(png_paths, 1):
    result = client.detect(png_path)                    # POST /detect
    dets = result["detections"]
    # GPU 服务返回键是 "class"，write_labelme 期望 "cls_name"
    for d in dets:
        d["cls_name"] = d.pop("class")
    write_labelme(png_path, dets, out_json_path)
    emit_custom(task_id, event_data, event_locks, "yolo_progress",
                {"page": i, "total": len(png_paths),
                 "detections": len(dets)})
```

前端在每个 `yolo_progress` 事件中看到 `page/total` 进度，获得逐页推进感。SSE 事件格式不变。

### 6.3 修改 `config.py`

```python
YOLO_SERVICE_URL       = os.getenv("YOLO_SERVICE_URL", "http://127.0.0.1:8000")
YOLO_SERVICE_TOKEN     = os.getenv("YOLO_SERVICE_TOKEN", "")
YOLO_SERVICE_TIMEOUT   = float(os.getenv("YOLO_SERVICE_TIMEOUT", "15"))
YOLO_MAX_IMAGE_MB      = int(os.getenv("YOLO_MAX_IMAGE_MB", "20"))
```

旧的 `YOLO_WEIGHT_PATH` / `YOLO_ONNX_PATH` 保留不删（向后兼容），`YOLODetector` 保留但不在流水线中默认使用。

### 6.4 修改 `inspect_yolo_capability`

改为调 GPU 服务 `/health`：`ok=true` 且 `models_loaded==7` → 可用。连接失败/超时 → 不可用。本地模型文件检查逻辑保留作为 fallback。

### 6.5 修改 `annotations.py`

`LABEL_TO_ID` 改从 `yolo_labels` import，删除文件内硬编码。

### 6.6 同步更新 `annotation_renderer.py`

`LABEL_TO_ZH` / `LABEL_TO_RGB` / `LABEL_DASHED` 改从 `yolo_labels` import，删除文件内 3 类硬编码。对 `circle_hole` 的映射一并移除。

### 6.7 同步更新测试

- `backend/test_capabilities.py`：`test_yolo_prefers_onnx_*` / `test_yolo_missing_models_*` 改为验证 `inspect_yolo_capability()` 的远程调用路径（mock `/health` 响应）。新增 `test_yolo_remote_health_ok` 和 `test_yolo_remote_health_fail` 用例。
- `backend/test_installation_contract.py` / `backend/test_dependency_manifest.py`：更新 YOLO 相关断言——后端不再依赖本地 `ultralytics`/`torch`，`uv sync --extra yolo` 说明改为 GPU 服务端需要。

---

## 7. 前端改动

### 7.1 `types/annotate.ts` — 标签定义重构

`BUILT_IN_LABELS` 当前有 11 个标签，其中 `circle_hole`, `rivet_hole`, `pin_hole`, `countersunk_hole`, `thread_through`, `emboss`, `flanged_hole`, `deep_draw` 不在 YOLO 7 类体系中。改为只保留与 YOLO 7 类精确匹配的内置标签，其余移除或标记为用户自定义标签：

| 7 类标签 | 颜色 | 边框样式 |
|----------|------|----------|
| `code_hole` | `#3b82f6` | solid |
| `through_hole` | `#22c55e` | solid |
| `blind_hole` | `#ef4444` | solid |
| `threaded_hole` | `#6366f1` | `6,3`（虚线） |
| `chamfer` | `#f59e0b` | solid |
| `counterbore` | `#f97316` | solid |
| `countersink` | `#8b5cf6` | solid |

`LABEL_DISPLAY_NAMES` 同步更新为 7 类中文名。颜色与 `yolo_labels.py` 的 `LABEL_TO_RGB` 保持一致。

### 7.2 `GeneratePage.tsx`

- "YOLO审阅" 标签页提示文案更新：从旧类别说明改为 7 类

### 7.3 波及组件

`BUILT_IN_LABELS` 被以下组件引用，修改 `annotate.ts` 后自动生效：
- `AnnotationPanel.tsx`
- `UploadPanel.tsx`
- `FullscreenPreview.tsx`
- `ReviewPanel.tsx`

---

## 8. 涉及文件清单

| 操作 | 文件 |
|------|------|
| 🆕 新增 | `backend/pipeline/yolo_labels.py` — 7 类 ID/中文/颜色/虚线统一定义 |
| 🆕 新增 | `backend/pipeline/yolo_service_client.py` — GPU 服务 HTTP 客户端 |
| 🆕 新增 | `gpu_service/main.py` — FastAPI 入口（鉴权 + /health + /detect） |
| 🆕 新增 | `gpu_service/chain_detector.py` — BinaryChainDetector（含推理锁） |
| 🆕 新增 | `gpu_service/requirements.txt` — ultralytics, fastapi, uvicorn, pillow |
| 🔧 修改 | `backend/config.py` — 新增 YOLO_SERVICE_URL/TOKEN/TIMEOUT |
| 🔧 修改 | `backend/pipeline/yolo_detector.py` — 默认 class_names 更新为 7 类 |
| 🔧 修改 | `backend/pipeline/annotation_renderer.py` — 标签映射改为 import yolo_labels |
| 🔧 修改 | `backend/api/upload.py` — _run_yolo_prelabel 改为逐页调用 |
| 🔧 修改 | `backend/api/annotations.py` — LABEL_TO_ID 改为 import yolo_labels |
| 🔧 修改 | `backend/services/capabilities.py` — inspect_yolo 优先调 /health |
| 🔧 修改 | `backend/test_capabilities.py` — YOLO 测试改为 remote health mock |
| 🔧 修改 | `backend/test_installation_contract.py` — 更新依赖文档说明 |
| 🔧 修改 | `backend/test_dependency_manifest.py` — 同上 |
| 🔧 修改 | `frontend-react/src/types/annotate.ts` — 标签定义重构为 7 类 |
| 🔧 修改 | `frontend-react/src/pages/GeneratePage.tsx` — 文案更新 |

---

## 9. 不涉及的部分

- ❌ 不修改 YOLO 模型权重或训练流程
- ❌ 不修改前端标注工具交互逻辑（画框/拖拽/删除）
- ❌ 不修改 SSE 事件协议（格式不变，逐页推送代替一次性）
- ❌ 不修改知识库 / 工序生成模块
- ❌ 后端不引入新 Python 依赖（httpx 已有）
- ❌ 不修改用户认证 / 权限体系
