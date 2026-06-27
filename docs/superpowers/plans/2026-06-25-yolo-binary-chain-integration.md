# YOLO 7 类二分类链式模型集成 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 7 个训练好的 yolo11n 二分类模型通过独立 GPU 推理服务集成到二维工艺系统的上传流水线中，替换当前单模型占位代码。

**Architecture:** 后端通过逐页 HTTP 调 GPU 服务（FastAPI + threading.Lock 串行推理），GPU 服务常驻加载 7 个 binary_*.pt 并执行链式检测（检出→涂黑→下一步）。标签映射抽取为 `yolo_labels.py` 统一定义源，前后端颜色/中文名/虚线共享。

**Tech Stack:** Python 3.11+ (Flask, httpx) / FastAPI + ultralytics (GPU service) / React 18 + TypeScript (前端标签)

## Global Constraints

- Python ≥ 3.11（系统 Python 3.9 不可用，必须 `.venv/bin/python3`）
- 后端不引入新 Python 依赖（httpx 已有）
- GPU 服务单页超时 15s
- GPU 推理同一时刻仅一个请求（`threading.Lock`）
- `/health` 无需鉴权，`/detect` 强制 `Authorization: Bearer` 校验
- YOLO 不可用时必须写空 LabelMe JSON（保持手动标注流程不断）
- 类别 ID 按工程语义分组（孔类 0-3，加工特征 4-6），链检测顺序与之不同
- 前端 `BUILT_IN_LABELS` 改为 7 类，颜色与后端 `LABEL_TO_RGB` 一致
- 旧 `circle_hole` 从所有映射中移除

---

### Task 1: 创建 7 类标签统一源 `yolo_labels.py`

**依赖:** 无（Phase 1 起点）

**Files:**
- Create: `backend/pipeline/yolo_labels.py`
- Modify: `backend/pipeline/annotation_renderer.py:13-25`
- Modify: `backend/api/annotations.py:20`
- Modify: `backend/pipeline/yolo_detector.py:129`

**Interfaces:**
- Produces:
  - `YOLO_CLASSES: list[str]` — 7 类按语义分组排序
  - `LABEL_TO_ID: dict[str, int]` — {name → id}
  - `ID_TO_LABEL: dict[int, str]` — {id → name}
  - `LABEL_TO_ZH: dict[str, str]` — {name → 中文名}
  - `LABEL_TO_RGB: dict[str, tuple[int,int,int]]` — {name → RGB}
  - `LABEL_DASHED: set[str]` — 虚线边框类集合

- Consumes: 无

---

- [ ] **Step 1: 创建 `backend/pipeline/yolo_labels.py`**

```python
# -*- coding: utf-8 -*-
"""7 类工程特征标签 — 统一定义源。

annotation_renderer.py / annotations.py / yolo_detector.py 均从此 import。
"""

# 按工程语义分组排序（孔类 0-3，加工特征 4-6）
YOLO_CLASSES = [
    "code_hole",       # 0  编码孔/基准孔
    "through_hole",    # 1  通孔
    "blind_hole",      # 2  盲孔
    "threaded_hole",   # 3  螺纹孔
    "chamfer",         # 4  倒角
    "counterbore",     # 5  沉头孔
    "countersink",     # 6  锥口孔
]

LABEL_TO_ID = {name: i for i, name in enumerate(YOLO_CLASSES)}
ID_TO_LABEL = {i: name for name, i in LABEL_TO_ID.items()}

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

# 虚线边框类（螺纹孔用虚线区分于直孔）
LABEL_DASHED = {"threaded_hole"}
```

- [ ] **Step 2: 验证 `yolo_labels.py` 导入无语法错误**

```bash
cd /Users/caojiayuan/Projects/work/test
.venv/bin/python3 -c "from backend.pipeline.yolo_labels import YOLO_CLASSES, LABEL_TO_ID, LABEL_TO_ZH, LABEL_TO_RGB, LABEL_DASHED; print(len(YOLO_CLASSES), LABEL_TO_ID)"
```
Expected: `7 {'code_hole': 0, 'through_hole': 1, 'blind_hole': 2, 'threaded_hole': 3, 'chamfer': 4, 'counterbore': 5, 'countersink': 6}`

- [ ] **Step 3: 修改 `backend/pipeline/annotation_renderer.py` — 删除旧硬编码，改为 import**

旧代码（第 13-25 行）：
```python
LABEL_TO_ZH = {
    "chamfer":       "倒角",
    "threaded_hole": "螺纹孔",
    "circle_hole":   "圆孔",
}

# RGB colors matching the frontend SVG palette
LABEL_TO_RGB: Dict[str, Tuple[int, int, int]] = {
    "chamfer":       (245, 158, 11),   # #f59e0b orange
    "threaded_hole": (99,  102, 241),  # #6366f1 indigo
    "circle_hole":   (16,  185, 129),  # #10b981 green
}
LABEL_DASHED = {"threaded_hole"}
```

替换为：
```python
from backend.pipeline.yolo_labels import LABEL_TO_ZH, LABEL_TO_RGB, LABEL_DASHED  # noqa: F401
```

同时更新注释（第 114 行附近）：
旧：`# - Solid border for chamfer / circle_hole, dashed for threaded_hole`
新：`# - Solid border for most classes; dashed for threaded_hole (see LABEL_DASHED)`

- [ ] **Step 4: 修改 `backend/api/annotations.py` — LABEL_TO_ID 改为 import**

旧代码（第 20 行）：
```python
LABEL_TO_ID = {"threaded_hole": 0, "circle_hole": 1, "chamfer": 2}
```

替换为：
```python
from backend.pipeline.yolo_labels import LABEL_TO_ID
```

- [ ] **Step 5: 修改 `backend/pipeline/yolo_detector.py` — 默认 class_names 更新**

旧代码（第 129 行附近）：
```python
self.class_names = class_names or {0: "threaded_hole", 1: "circle_hole"}
```

替换为：
```python
if class_names is None:
    from backend.pipeline.yolo_labels import ID_TO_LABEL
    class_names = dict(ID_TO_LABEL)  # {0: "code_hole", 1: "through_hole", ...}
self.class_names = class_names
```

- [ ] **Step 6: 运行现有测试验证标签改动不破坏现有逻辑**

```bash
cd /Users/caojiayuan/Projects/work/test
.venv/bin/python3 -m pytest backend/test_capabilities.py -v 2>&1 | tail -20
```
Expected: 所有原有测试继续通过（yolo 相关的可能因路径变化 fail，这会在 Task 5 修复）

- [ ] **Step 7: Commit**

```bash
git add backend/pipeline/yolo_labels.py backend/pipeline/annotation_renderer.py backend/api/annotations.py backend/pipeline/yolo_detector.py
git commit -m "feat: add 7-class yolo_labels unified source, update renderer/annotations/detector"
```

---

### Task 2: GPU 服务 — BinaryChainDetector + FastAPI `/detect`

**依赖:** Task 1（类别名常量可对照参考，但不强依赖）

**Files:**
- Create: `gpu_service/chain_detector.py`
- Create: `gpu_service/main.py`
- Create: `gpu_service/requirements.txt`

**Interfaces:**
- Produces:
  - `BinaryChainDetector(model_dir, device)` — 构造时加载 7 个模型到显存
  - `BinaryChainDetector.detect(image: np.ndarray) -> list[dict]` — 线程安全的链式推理
  - `GET /health → {ok, models_loaded, gpu_available, device}`
  - `POST /detect → {name, detections: [{class, conf, x1, y1, x2, y2}]}`

- Consumes: 无

---

- [ ] **Step 1: 创建 `gpu_service/requirements.txt`**

```
ultralytics>=8.0.0
fastapi>=0.100.0
uvicorn>=0.20.0
pillow>=10.0.0
```

- [ ] **Step 2: 创建 `gpu_service/chain_detector.py`**

```python
"""BinaryChainDetector — 7 模型链式推理 + 全局锁。

Detection order (empirically optimal):
  code_hole → threaded_hole → chamfer → through_hole →
  counterbore → countersink → blind_hole

After each class is detected, regions are blacked out before the next model.
"""
import threading
import numpy as np

CLASS_ORDER = [
    "code_hole",       # high-frequency first — block out early
    "threaded_hole",
    "chamfer",
    "through_hole",
    "counterbore",
    "countersink",
    "blind_hole",      # rarest last, highest confidence threshold
]

CLASS_CONF = {
    "code_hole": 0.25, "threaded_hole": 0.25, "chamfer": 0.25,
    "through_hole": 0.25, "counterbore": 0.30, "countersink": 0.30,
    "blind_hole": 0.50,
}


class BinaryChainDetector:
    """Loads 7 binary YOLO models, provides thread-safe chain detection."""

    def __init__(self, model_dir: str, device: str = "cuda:0"):
        from ultralytics import YOLO

        self.device = device
        self._lock = threading.Lock()
        self.models: dict[str, "YOLO"] = {}

        for name in CLASS_ORDER:
            path = f"{model_dir}/binary_{name}.pt"
            model = YOLO(path)
            model.to(device)
            self.models[name] = model

    def detect(self, image: np.ndarray) -> list[dict]:
        """Run full chain on a single image. Thread-safe via internal lock.

        Returns list of detections, each:
          {"class": str, "conf": float, "x1": float, "y1": float,
           "x2": float, "y2": float}
        """
        with self._lock:
            img = image.copy()
            all_dets: list[dict] = []

            for cls_name in CLASS_ORDER:
                results = self.models[cls_name](
                    img, conf=CLASS_CONF[cls_name], verbose=False
                )
                boxes: list[tuple[float, float, float, float]] = []

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

                # Blackout detected regions for next model
                for (x1, y1, x2, y2) in boxes:
                    y1i, y2i = max(0, int(y1)), max(0, int(y2))
                    x1i, x2i = max(0, int(x1)), max(0, int(x2))
                    if y2i > y1i and x2i > x1i:
                        img[y1i:y2i, x1i:x2i] = 0

            return all_dets
```

- [ ] **Step 3: 创建 `gpu_service/main.py`**

```python
"""GPU YOLO detection service — FastAPI.

Environment:
  YOLO_MODEL_DIR      path to binary_*.pt files (default ./models_binary)
  YOLO_DEVICE         torch device (default cuda:0)
  YOLO_SERVICE_TOKEN  shared secret for /detect auth (required — refuses startup if empty)
  YOLO_MAX_IMAGE_MB   max single image size in MB (default 20)
"""
import base64
import io
import os

import numpy as np
from fastapi import FastAPI, Header, HTTPException
from PIL import Image

from chain_detector import BinaryChainDetector

MODEL_DIR  = os.getenv("YOLO_MODEL_DIR", "./models_binary")
DEVICE     = os.getenv("YOLO_DEVICE", "cuda:0")
TOKEN      = os.getenv("YOLO_SERVICE_TOKEN", "")
if not TOKEN:
    raise RuntimeError("YOLO_SERVICE_TOKEN must be set — refusing to start without auth")

MAX_IMG_MB = int(os.getenv("YOLO_MAX_IMAGE_MB", "20"))

app = FastAPI(title="YOLO Binary Chain Detector")

# Load all 7 models at startup (blocking; takes ~10-30s)
detector = BinaryChainDetector(MODEL_DIR, DEVICE)


@app.get("/health")
def health():
    gpu_ok = False
    if DEVICE.startswith("cuda"):
        try:
            import torch
            gpu_ok = torch.cuda.is_available()
        except ImportError:
            pass
    return {
        "ok": True,
        "models_loaded": len(detector.models),
        "gpu_available": gpu_ok,
        "device": DEVICE,
    }


@app.post("/detect")
def detect(body: dict, authorization: str = Header(None)):
    # Auth — TOKEN is guaranteed non-empty (checked at startup)
    expected = f"Bearer {TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authorization token",
        )

    name = body.get("name", "unknown.png")
    raw = base64.b64decode(body["data"])

    # Size limit
    if len(raw) > MAX_IMG_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {MAX_IMG_MB}MB limit",
        )

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    detections = detector.detect(np.array(img))
    return {"name": name, "detections": detections}
```

- [ ] **Step 4: 验证 GPU 服务可以启动（在 liu4th 或本地有 ultralytics 的环境）**

```bash
cd /Users/caojiayuan/Projects/work/test/gpu_service
# 使用本地测试模型目录（如果二进制模型不在本地，此步骤在 liu4th 上执行）
pip install -r requirements.txt
YOLO_DEVICE=cpu python -c "
from chain_detector import BinaryChainDetector
import numpy as np
d = BinaryChainDetector('./models_binary', 'cpu')
print(f'Loaded {len(d.models)} models')
result = d.detect(np.zeros((640, 640, 3), dtype=np.uint8))
print(f'Blank image detections: {len(result)} (expected 0)')
"
```
Expected: `Loaded 7 models` / `Blank image detections: 0 (expected 0)`

- [ ] **Step 5: Commit**

```bash
git add gpu_service/chain_detector.py gpu_service/main.py gpu_service/requirements.txt
git commit -m "feat: add GPU detection service with BinaryChainDetector + /detect endpoint"
```

---

### Task 3: 后端 `YOLOServiceClient` + `config.py` 配置

**依赖:** Task 2（GPU 服务接口契约 `POST /detect` 已确定）

**Files:**
- Create: `backend/pipeline/yolo_service_client.py`
- Modify: `backend/config.py:207-212`

**Interfaces:**
- Produces:
  - `YOLOServiceClient(base_url, token, timeout)` — HTTP 客户端
  - `YOLOServiceClient.health() -> dict` — GET /health
  - `YOLOServiceClient.detect(image_path: str) -> dict` — POST /detect，返回 `{name, detections}`
- Consumes:
  - GPU 服务 `POST /detect` 接口（Task 2）
  - `backend/config.py` 的 YOLO_SERVICE_* 配置项（本 task 添加）

---

- [ ] **Step 1: 修改 `backend/config.py` — 新增 GPU 服务配置**

在现有 YOLO 配置块（第 207 行附近 `YOLO_DEVICE` 之后）追加：

```python
# ============ YOLO GPU 服务配置 ============
YOLO_SERVICE_URL       = os.getenv("YOLO_SERVICE_URL", "http://127.0.0.1:8000")
YOLO_SERVICE_TOKEN     = os.getenv("YOLO_SERVICE_TOKEN", "")
YOLO_SERVICE_TIMEOUT   = float(os.getenv("YOLO_SERVICE_TIMEOUT", "15"))
```

旧的 `YOLO_WEIGHT_PATH` / `YOLO_ONNX_PATH` 保留不删。

- [ ] **Step 2: 创建 `backend/pipeline/yolo_service_client.py`**

```python
# -*- coding: utf-8 -*-
"""GPU YOLO 服务 HTTP 客户端 — 逐页调用 /detect 端点。
"""
import base64
from pathlib import Path

import httpx


class YOLOServiceClient:
    """Thin HTTP wrapper around GPU YOLO detection service."""

    def __init__(self, base_url: str, token: str, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def health(self) -> dict:
        """GET /health — check service availability."""
        r = httpx.get(f"{self.base_url}/health", timeout=5)
        r.raise_for_status()
        return r.json()

    def detect(self, image_path: str) -> dict:
        """POST /detect — single-page chain inference.

        Returns: {"name": "page_1.png", "detections": [...]}
        """
        name = Path(image_path).name
        data = Path(image_path).read_bytes()

        r = httpx.post(
            f"{self.base_url}/detect",
            json={
                "name": name,
                "data": base64.b64encode(data).decode(),
            },
            headers=self._headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 3: 编写并运行客户端单元测试**

```bash
cd /Users/caojiayuan/Projects/work/test
cat > /tmp/test_yolo_client.py << 'PYEOF'
import json, tempfile, os
from unittest.mock import patch, MagicMock
from backend.pipeline.yolo_service_client import YOLOServiceClient

def test_health_makes_correct_request():
    client = YOLOServiceClient("http://gpu:8000", "secret", timeout=15)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "models_loaded": 7}
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        result = client.health()
        mock_get.assert_called_once_with("http://gpu:8000/health", timeout=5)
        assert result["models_loaded"] == 7

def test_detect_sends_auth_header():
    client = YOLOServiceClient("http://gpu:8000", "tok123", timeout=15)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"name": "p1.png", "detections": []}
    mock_resp.raise_for_status = MagicMock()

    # Use a real temp file — avoid patching pathlib.Path properties
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(b"fake_png_data")
    tmp.close()

    try:
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = client.detect(tmp.name)
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["headers"]["Authorization"] == "Bearer tok123"
            assert result["name"] == os.path.basename(tmp.name)
    finally:
        os.unlink(tmp.name)

test_health_makes_correct_request()
test_detect_sends_auth_header()
print("PASS")
PYEOF
.venv/bin/python3 /tmp/test_yolo_client.py
```
Expected: `PASS`

- [ ] **Step 4: Commit**

```bash
git add backend/config.py backend/pipeline/yolo_service_client.py
git commit -m "feat: add YOLOServiceClient for per-page GPU service calls"
```

---

### Task 4: `_run_yolo_prelabel` 改为逐页调用 + 实时 SSE + 空 LabelMe 降级

**依赖:** Task 1（yolo_labels），Task 3（YOLOServiceClient）

**Files:**
- Modify: `backend/api/upload.py:364-430`

**Interfaces:**
- Consumes:
  - `YOLOServiceClient.detect(image_path)` (Task 3)
  - `yolo_to_labelme.write_labelme(png_path, dets, out_json_path)` (现有)
  - `emit_custom(task_id, event_data, event_locks, "yolo_progress", {...})` (现有)
- Produces: `task["yolo_summary"]` — count dict per class

---

- [ ] **Step 1: 找到 `_run_yolo_prelabel` 函数（`backend/api/upload.py:364`）并替换**

```python
def _run_yolo_prelabel(task_id: str, png_paths: list, output_dir: str) -> dict:
    """Run YOLO via GPU service on each page, write labelme JSON, emit per-page SSE.

    When GPU service is unavailable, writes empty LabelMe JSONs so manual
    annotation fallback works without frontend changes.

    Returns aggregate detection counts {class_name: count}.
    """
    import logging
    from backend.config import YOLO_SERVICE_URL, YOLO_SERVICE_TOKEN, YOLO_SERVICE_TIMEOUT
    from backend.pipeline.yolo_service_client import YOLOServiceClient
    from backend.pipeline.yolo_to_labelme import write_labelme

    logger = logging.getLogger(__name__)
    ann_dir = os.path.join(output_dir, "annotations")
    summary: dict[str, int] = {}

    client = None
    try:
        client = YOLOServiceClient(YOLO_SERVICE_URL, YOLO_SERVICE_TOKEN, YOLO_SERVICE_TIMEOUT)
        client.health()  # fast check
    except Exception as e:
        logger.warning("[%s] YOLO GPU 服务不可用: %s", task_id, e)

    from backend.pipeline.yolo_labels import YOLO_CLASSES

    total = len(png_paths)
    for i, png_path in enumerate(png_paths, 1):
        dets: list[dict] = []

        if client is not None:
            try:
                result = client.detect(png_path)
                dets = result.get("detections", [])
                # GPU service returns key "class"; write_labelme expects "cls_name"
                for d in dets:
                    d["cls_name"] = d.pop("class")
            except Exception as e:
                logger.warning("[%s] 第 %d 页 YOLO 推理失败: %s", task_id, i, e)
                # Fall through — write empty LabelMe for this page
                dets = []

        # Per-class count dict (match old yolo_progress format)
        page_count = {cls: 0 for cls in YOLO_CLASSES}
        for d in dets:
            cls_name = d["cls_name"]
            if cls_name in page_count:
                page_count[cls_name] += 1
            summary[cls_name] = summary.get(cls_name, 0) + 1

        stem = os.path.splitext(os.path.basename(png_path))[0]
        json_path = os.path.join(ann_dir, f"{stem}_page_{i}.json")
        write_labelme(png_path, dets, json_path)

        emit_custom(task_id, event_data, event_locks, "yolo_progress",
                    {"page": i, "total": total, "detections": page_count})

    # Emit step completion with summary for frontend/logger
    summary_lines = [f"{cls}: {summary.get(cls, 0)}" for cls in YOLO_CLASSES if summary.get(cls, 0)]
    summary_text = "YOLO 检测完成：" + ("；".join(summary_lines) if summary_lines else "未检测到特征")
    emit_step_complete(
        task_id, event_data, event_locks, 2, "YOLO 检测", summary_text
    )

    return summary
```

**关键改动点 vs 旧代码：**
- 不再 import `get_yolo_detector` / `YOLODetector`—改为 `YOLOServiceClient`
- 不再 `detector.detect(img)` 逐页加载 cv2→改为 `client.detect(png_path)` HTTP 调用
- 每页完成立即 `write_labelme` + `emit_custom`（不等到全部完成）
- 每页失败写空 LabelMe（`dets = []`），不中断循环
- `class` → `cls_name` 键映射
- `detections` 保持为 `{class_name: count}` 字典格式（与旧协议一致）
- 循环结束后发 `emit_step_complete` 汇总（保持前端步骤状态正确更新）

- [ ] **Step 2: 验证 `_run_yolo_prelabel` 导入路径无语法错误**

```bash
cd /Users/caojiayuan/Projects/work/test
.venv/bin/python3 -c "
import ast, sys
with open('backend/api/upload.py') as f:
    tree = ast.parse(f.read())
print('upload.py syntax OK')
"
```
Expected: `upload.py syntax OK`

- [ ] **Step 3: 运行现有流程测试确认不引入回归**

```bash
cd /Users/caojiayuan/Projects/work/test
.venv/bin/python3 -m pytest backend/test_upload_capability_gate.py -v --timeout=30 2>&1 | tail -10
```
Expected: 通过（YOLO 相关测试在 Task 5 更新，此处确认非 YOLO 流程不受影响）

- [ ] **Step 4: Commit**

```bash
git add backend/api/upload.py
git commit -m "feat: _run_yolo_prelabel uses per-page GPU service calls with real-time SSE"
```

---

### Task 5: capability / tests / docs 同步

**依赖:** Task 1, Task 3, Task 4

**Files:**
- Modify: `backend/services/capabilities.py:50-79`
- Modify: `backend/test_capabilities.py:30-50`
- Modify: `README.md` / `INSTALL.md` / `START.md` — 更新 YOLO 依赖说明
- Modify: `backend/test_installation_contract.py` — 更新 YOLO 相关断言
- Modify: `backend/test_dependency_manifest.py` — 同上

**Interfaces:**
- Consumes:
  - `YOLOServiceClient.health()` (Task 3)
  - `backend/config.py` 的 YOLO_SERVICE_URL/TOKEN (Task 3 添加)
- Produces: `inspect_yolo_capability()` 返回 remote-first 结果

---

- [ ] **Step 1: 修改 `backend/services/capabilities.py` — `inspect_yolo_capability`**

旧函数（第 50-79 行）替换为：

```python
def inspect_yolo_capability() -> dict:
    """Check YOLO availability — remote GPU service first, local models as fallback."""
    from backend.config import YOLO_SERVICE_URL, YOLO_SERVICE_TOKEN

    # 1. Try remote GPU service (skip if token not configured — would 401)
    if not YOLO_SERVICE_TOKEN:
        # Token missing → /detect would fail; don't report available
        pass
    else:
        try:
            from backend.pipeline.yolo_service_client import YOLOServiceClient
            client = YOLOServiceClient(YOLO_SERVICE_URL, YOLO_SERVICE_TOKEN)
            info = client.health()
            if info.get("ok") and info.get("models_loaded", 0) == 7:
                return {
                    "available": True,
                    "provider": "gpu_service",
                    "reason": "",
                    "service_url": YOLO_SERVICE_URL,
                    "models_loaded": 7,
                    "gpu_available": info.get("gpu_available", True),
                    "device": info.get("device", ""),
                }
            else:
                return {
                    "available": False,
                    "provider": "gpu_service",
                    "reason": f"GPU 服务模型未就绪 (loaded={info.get('models_loaded', 0)})",
                }
        except Exception:
            pass

    # 2. Fallback: local model files (legacy) — preserve manifest check
    onnx = Path(YOLO_ONNX_PATH)
    pt = Path(YOLO_WEIGHT_PATH)
    manifest_path = Path(__file__).resolve().parents[2] / "db_data" / "model-manifest.json"

    if manifest_path.is_file():
        try:
            from backend.services.model_manifest import load_model_manifest, verify_model_file

            manifest = load_model_manifest(manifest_path)
            selected_path = onnx if manifest.get("format") == "onnx" else pt
            ok, reason = verify_model_file(selected_path, manifest)
            if not ok:
                return {"available": False, "provider": None, "reason": reason}
        except (ValueError, OSError) as exc:
            return {"available": False, "provider": None, "reason": f"模型清单错误：{exc}"}

    if onnx.is_file() and _module_available("onnxruntime"):
        return {"available": True, "provider": "onnx", "reason": ""}
    if pt.is_file() and _module_available("ultralytics") and _module_available("torch"):
        return {"available": True, "provider": "ultralytics", "reason": ""}

    missing_parts = []
    if not onnx.is_file() and not pt.is_file():
        missing_parts.append("本地模型文件不存在")
    return {
        "available": False,
        "provider": None,
        "reason": "GPU 服务不可用；" + ("；".join(missing_parts) if missing_parts else "本地模型亦不可用"),
    }
```

- [ ] **Step 2: 修改 `backend/test_capabilities.py` — YOLO 测试改为 mock remote health**

旧的 yolo 测试（第 30-50 行）替换为：

```python
def test_yolo_remote_health_ok(monkeypatch):
    """When GPU service health returns ok, inspect reports available."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient

    def mock_health(self):
        return {"ok": True, "models_loaded": 7, "gpu_available": True, "device": "cuda:0"}

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health)
    result = capabilities.inspect_yolo_capability()
    assert result["available"] is True
    assert result["provider"] == "gpu_service"
    assert result["models_loaded"] == 7


def test_yolo_remote_health_fail_falls_back(monkeypatch, tmp_path):
    """When GPU service is unreachable, falls back to local model check."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient

    def mock_health_fail(self):
        raise ConnectionError("timeout")

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health_fail)
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(tmp_path / "best.onnx"))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))

    result = capabilities.inspect_yolo_capability()
    # When no local models exist either, should be unavailable
    assert result["available"] is False
    assert "GPU 服务不可用" in result["reason"]


def test_yolo_remote_models_not_ready(monkeypatch):
    """When health returns but models_loaded < 7, report unavailable."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient

    def mock_health_partial(self):
        return {"ok": True, "models_loaded": 3, "gpu_available": True, "device": "cuda:0"}

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health_partial)
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", "/nonexistent")
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", "/nonexistent")

    result = capabilities.inspect_yolo_capability()
    assert result["available"] is False
    assert "模型未就绪" in result["reason"]
```

删除旧测试：
- `test_yolo_prefers_onnx_without_importing_ultralytics`
- `test_yolo_missing_models_is_non_blocking`

- [ ] **Step 3: 运行更新后的测试**

```bash
cd /Users/caojiayuan/Projects/work/test
.venv/bin/python3 -m pytest backend/test_capabilities.py -v 2>&1 | tail -20
```
Expected: 3 个 yolo 测试 PASS + 原有非 yolo 测试 PASS

- [ ] **Step 4: 更新安装文档**

`README.md` / `INSTALL.md` / `START.md` 中 YOLO 相关说明改为：

```markdown
## YOLO 预标注

系统通过独立 GPU 推理服务提供 YOLO 预标注。后端默认通过 `YOLO_SERVICE_URL` 调用 GPU 服务。

- 本地 `best.onnx` / `best.pt` 仅作为 legacy fallback，不是默认路径
- `uv sync --extra yolo` 仅 GPU 服务端需要；后端不需要安装 ultralytics/torch
```

`backend/test_installation_contract.py` 和 `backend/test_dependency_manifest.py` 中 YOLO 相关断言同步更新为 remote-first 语义。

- [ ] **Step 5: Commit**

```bash
git add backend/services/capabilities.py backend/test_capabilities.py README.md backend/test_installation_contract.py backend/test_dependency_manifest.py
git commit -m "feat: update capability detection to remote GPU service first, sync docs & tests"
```

---

### Task 6: 前端 `annotate.ts` 重构为 7 类 + GeneratePage 文案

**依赖:** Task 1（yolo_labels 颜色/类名已确定）

**Files:**
- Modify: `frontend-react/src/types/annotate.ts:25-53`
- Modify: `frontend-react/src/pages/GeneratePage.tsx:688,761,785,789`

**Interfaces:**
- Consumes: 前端 `AnnotationPanel`, `UploadPanel`, `FullscreenPreview`, `ReviewPanel` 从 `annotate.ts` import `BUILT_IN_LABELS` / `LABEL_DISPLAY_NAMES`
- Produces: 7 类标签色板 + 中文名

---

- [ ] **Step 1: 修改 `frontend-react/src/types/annotate.ts` — BUILT_IN_LABELS 重构**

旧代码（第 25-37 行）替换为：

```typescript
export const BUILT_IN_LABELS: AnnotationLabel[] = [
  { name: 'code_hole',      color: '#3b82f6', borderStyle: 'solid', isCustom: false },
  { name: 'through_hole',   color: '#22c55e', borderStyle: 'solid', isCustom: false },
  { name: 'blind_hole',     color: '#ef4444', borderStyle: 'solid', isCustom: false },
  { name: 'threaded_hole',  color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'chamfer',        color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'counterbore',    color: '#f97316', borderStyle: 'solid', isCustom: false },
  { name: 'countersink',    color: '#8b5cf6', borderStyle: 'solid', isCustom: false },
]
```

旧代码（第 41-53 行）替换为：

```typescript
export const LABEL_DISPLAY_NAMES: Record<string, string> = {
  code_hole: '编码孔',
  through_hole: '通孔',
  blind_hole: '盲孔',
  threaded_hole: '螺纹孔',
  chamfer: '倒角',
  counterbore: '沉头孔',
  countersink: '锥口孔',
}
```

删除旧标签：`circle_hole`, `rivet_hole`, `pin_hole`, `countersunk_hole`, `thread_through`, `emboss`, `flanged_hole`, `deep_draw`。

保留 `CUSTOM_LABEL_COLORS` 数组不变（供用户自定义标签使用）。

- [ ] **Step 2: 修改 `frontend-react/src/pages/GeneratePage.tsx` — 文案更新**

旧文案（第 761 行附近）：
```
YOLO 已预标注以下特征，请审阅或补充
```

改为：
```
YOLO 已预标注 7 类工程特征（编码孔/通孔/盲孔/螺纹孔/倒角/沉头孔/锥口孔），请审阅或补充
```

旧按钮文案（第 785 行附近）：
```
跳过 YOLO 审阅
```

改为：
```
跳过 YOLO 审阅
```
（保持不变，仅上下文提示更新）

- [ ] **Step 3: 运行 TypeScript 编译验证**

```bash
cd /Users/caojiayuan/Projects/work/test/frontend-react
npx tsc --noEmit 2>&1 | head -20
```
Expected: 无类型错误

- [ ] **Step 4: 验证标注 UI 组件引用新标签无运行时错误**

```bash
cd /Users/caojiayuan/Projects/work/test/frontend-react
npx vite build 2>&1 | tail -5
```
Expected: 构建成功

- [ ] **Step 5: Commit**

```bash
git add frontend-react/src/types/annotate.ts frontend-react/src/pages/GeneratePage.tsx
git commit -m "feat: refactor frontend labels to 7-class YOLO set, update GeneratePage copy"
```

---

## 验证清单（所有 Task 完成后执行）

- [ ] **后端启动验证**
```bash
cd /Users/caojiayuan/Projects/work/test
.venv/bin/python3 -c "from backend.pipeline.yolo_labels import *; from backend.pipeline.yolo_service_client import YOLOServiceClient; from backend.services.capabilities import inspect_yolo_capability; print('All imports OK')"
```
Expected: `All imports OK`

- [ ] **完整测试套件**
```bash
.venv/bin/python3 -m pytest backend/ -v --ignore=backend/test_auth_store.py --timeout=60 2>&1 | tail -30
```
Expected: 除 yolo remote 相关测试需要 GPU 服务在线（本地会 fallback），其余全部 PASS

- [ ] **GPU 服务部署**（在 liu4th 上）
```bash
cd gpu_service
export YOLO_MODEL_DIR=/path/to/models_binary
export YOLO_DEVICE=cuda:0
export YOLO_SERVICE_TOKEN=$(openssl rand -hex 32)
uvicorn main:app --host 127.0.0.1 --port 8000

# 验证（另一终端）
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/detect \
  -H "Authorization: Bearer $YOLO_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test.png","data":"'$(base64 -i /path/to/test.png)'"}'
```

- [ ] **前端构建验证**
```bash
cd frontend-react && npx vite build
```
Expected: 构建成功，无 TS 错误

---

## 文件改动总结

| 操作 | 文件 | Task |
|------|------|------|
| 🆕 | `backend/pipeline/yolo_labels.py` | 1 |
| 🆕 | `backend/pipeline/yolo_service_client.py` | 3 |
| 🆕 | `gpu_service/main.py` | 2 |
| 🆕 | `gpu_service/chain_detector.py` | 2 |
| 🆕 | `gpu_service/requirements.txt` | 2 |
| 🔧 | `backend/config.py` | 3 |
| 🔧 | `backend/pipeline/annotation_renderer.py` | 1 |
| 🔧 | `backend/pipeline/yolo_detector.py` | 1 |
| 🔧 | `backend/api/annotations.py` | 1 |
| 🔧 | `backend/api/upload.py` | 4 |
| 🔧 | `backend/services/capabilities.py` | 5 |
| 🔧 | `backend/test_capabilities.py` | 5 |
| 🔧 | `frontend-react/src/types/annotate.ts` | 6 |
| 🔧 | `frontend-react/src/pages/GeneratePage.tsx` | 6 |
