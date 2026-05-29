# VLM 三视图特征集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 PRT 上传流程中，用 VLM 分析已有的三视图截图生成语义特征文本，与程序化 geo_text 合并后送入 RAG，提升工序检索质量。

**Architecture:** 新建 `backend/pipeline/vlm_feature.py` 暴露 `extract_vlm_features(views_dir) -> str`，复用 `VISION_API_KEY`/`VISION_API_BASE`/`VISION_MODEL_ID` 环境变量和 `openai` 包，API 失败时静默返回 `""`。`upload.py` 在拿到 `geo_text` 之后调用该函数，两段文本按固定格式拼接后送 RAG，RAG 及其之后的流程不变。

**Tech Stack:** Python 3.11, openai SDK, Flask (现有), FreeCAD 三视图 PNG (现有)

---

## File Structure

| 文件 | 变更 | 职责 |
|------|------|------|
| `backend/pipeline/vlm_feature.py` | 新建 | VLM multimodal 调用，返回语义特征文本 |
| `backend/pipeline/test_vlm_feature.py` | 新建 | 烟雾测试：error paths + 可选真实 API 验证 |
| `backend/api/upload.py` | 修改第 812–834 行 | 调用 VLM，合并 geo+vlm 文本 |

---

## Task 1: 写烟雾测试（TDD first）

**Files:**
- Create: `backend/pipeline/test_vlm_feature.py`

- [ ] **Step 1: 创建测试文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Smoke test for vlm_feature.py

Usage:
    python backend/pipeline/test_vlm_feature.py              # error-path tests only
    python backend/pipeline/test_vlm_feature.py <views_dir>  # also calls real VLM
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.pipeline.vlm_feature import extract_vlm_features


def test_missing_env():
    """Returns "" when API env vars are not set."""
    saved = {k: os.environ.pop(k, None) for k in ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")}
    try:
        result = extract_vlm_features("/tmp/nonexistent")
        assert result == "", f"Expected '', got: {repr(result)}"
        print("PASS: missing env → ''")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_missing_images():
    """Returns "" when view PNGs are missing from an otherwise valid views_dir."""
    os.environ.setdefault("VISION_API_KEY", "dummy")
    os.environ.setdefault("VISION_API_BASE", "http://dummy")
    os.environ.setdefault("VISION_MODEL_ID", "dummy-model")
    with tempfile.TemporaryDirectory() as tmp:
        result = extract_vlm_features(tmp)
        assert result == "", f"Expected '', got: {repr(result)}"
        print("PASS: missing images → ''")


def test_real_vlm(views_dir: str):
    """Calls real VLM API with actual view images. Requires .env configured."""
    from dotenv import load_dotenv
    load_dotenv()
    result = extract_vlm_features(views_dir)
    print(f"\n--- VLM Output ({len(result)} chars) ---")
    print(result or "(empty — check API config and image paths)")
    print("---")


if __name__ == "__main__":
    test_missing_env()
    test_missing_images()
    if len(sys.argv) > 1:
        test_real_vlm(sys.argv[1])
    else:
        print("\nTip: pass <views_dir> to also test real VLM call")
    print("\nAll error-path tests passed.")
```

- [ ] **Step 2: 运行测试，确认它失败（模块还不存在）**

```bash
python backend/pipeline/test_vlm_feature.py
```

预期输出：`ModuleNotFoundError: No module named 'backend.pipeline.vlm_feature'`

---

## Task 2: 实现 `vlm_feature.py`

**Files:**
- Create: `backend/pipeline/vlm_feature.py`

- [ ] **Step 1: 创建模块**

```python
# -*- coding: utf-8 -*-
import base64
import os
from pathlib import Path

from openai import OpenAI

_FACES = ("front", "right", "top")

_SYSTEM_PROMPT = """你将看到同一个机械零件的三视图图片（正视图、右视图、俯视图）。

请综合所有图片提取零件的机械加工特征，重点识别：
平面、台阶、槽、型腔、孔、沉孔、埋头孔、螺纹孔、凸台、肋板、倒角、圆角、旋转体、自由曲面等。

输出格式：每条特征一行，格式为"特征类型：描述（含数量或典型尺寸，若可从图中判断）"。
示例：
旋转体：主体为轴类零件，带多级外圆台阶
螺纹孔：端面分布 4 个螺纹孔
内孔：中心通孔
倒角：各棱边均有倒角"""


def extract_vlm_features(views_dir: str) -> str:
    """
    读取 views_dir 下的 front/right/top.png，发 VLM multimodal 请求，
    返回语义特征文本。图片缺失或 API 失败时返回空字符串。
    """
    api_key = os.getenv("VISION_API_KEY", "")
    api_base = os.getenv("VISION_API_BASE", "").rstrip("/")
    model_id = os.getenv("VISION_MODEL_ID", "")

    if not api_key or not api_base or not model_id:
        print("[vlm_feature] VISION_API_KEY/VISION_API_BASE/VISION_MODEL_ID not configured, skipping")
        return ""

    views_path = Path(views_dir)
    image_paths = [views_path / f"{face}.png" for face in _FACES]
    missing = [str(p) for p in image_paths if not p.exists()]
    if missing:
        print(f"[vlm_feature] missing view images: {missing}, skipping")
        return ""

    try:
        content = []
        for path in image_paths:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        content.append({"type": "text", "text": "请识别图中零件的机械加工特征。"})

        client = OpenAI(api_key=api_key, base_url=api_base)
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=1024,
            timeout=120,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[vlm_feature] VLM call failed: {exc}")
        return ""
```

- [ ] **Step 2: 运行测试，确认 error-path 测试全部通过**

```bash
python backend/pipeline/test_vlm_feature.py
```

预期输出：
```
PASS: missing env → ''
PASS: missing images → ''

Tip: pass <views_dir> to also test real VLM call
All error-path tests passed.
```

- [ ] **Step 3: （可选）用真实三视图验证 VLM 输出质量**

如果手边有已生成的三视图目录（通常在 `output/<task_id>/` 下，含 front.png/right.png/top.png）：

```bash
python backend/pipeline/test_vlm_feature.py output/<task_id>
```

检查 VLM 输出是否包含有意义的机械特征词（孔、台阶、旋转体等）。

- [ ] **Step 4: 提交**

```bash
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: add vlm_feature module for three-view semantic extraction"
```

---

## Task 3: 集成到 `upload.py`

**Files:**
- Modify: `backend/api/upload.py:19`（import 行）
- Modify: `backend/api/upload.py:812-834`（特征提取 + 合并逻辑）

- [ ] **Step 1: 在 `upload.py` 顶部添加 import**

找到第 19 行：
```python
from ..prt_pipeline import prepare_prt_artifacts, export_gltf, extract_geometry_features
```

在其下方新增一行：
```python
from ..pipeline.vlm_feature import extract_vlm_features
```

- [ ] **Step 2: 替换特征提取 + 合并逻辑**

找到这段代码（约 825–832 行）：
```python
            full_feature_text = f"【图号】{prefix_hint or os.path.basename(file.filename)}"
            if geo_text and "Error" not in geo_text:
                full_feature_text = geo_text + "\n" + full_feature_text
            
            task["review_text"] = full_feature_text
            task["vision_descriptions"] = [{"description": full_feature_text}]
            task["feature_report_json"] = {"report_text": full_feature_text, "pages": []}
            task["feature_report_text"] = full_feature_text
```

替换为：
```python
            # VLM three-view semantic feature extraction
            vlm_text = ""
            if artifacts.get("views_generated") and artifacts.get("views_dir"):
                emit_log(task_id, event_data, event_locks, 2, "正在调用VLM提取三视图视觉特征...")
                vlm_text = extract_vlm_features(artifacts["views_dir"])
                if vlm_text:
                    emit_log(task_id, event_data, event_locks, 2, f"VLM视觉特征提取完成: {vlm_text[:80]}...")
                else:
                    emit_log(task_id, event_data, event_locks, 2, "VLM特征提取跳过（无图或API失败）", level="warn")

            # Merge: geo (precise numbers) + vlm (semantic) + drawing number
            parts = []
            if geo_text and "Error" not in geo_text:
                parts.append(geo_text)
            if vlm_text:
                parts.append(f"【VLM视觉特征】\n{vlm_text}")
            parts.append(f"【图号】{prefix_hint or os.path.basename(file.filename)}")
            full_feature_text = "\n".join(parts)

            task["review_text"] = full_feature_text
            task["vision_descriptions"] = [{"description": full_feature_text}]
            task["feature_report_json"] = {"report_text": full_feature_text, "pages": []}
            task["feature_report_text"] = full_feature_text
```

- [ ] **Step 3: 验证 `artifacts["views_dir"]` 路径**

在同一函数中搜索 `prepare_prt_artifacts` 的调用，确认返回值 `artifacts` 中存在 `views_dir` 和 `views_generated` 字段。

预期：`prepare_prt_artifacts()` 在 `prt_pipeline.py:392` 定义，返回：
```python
{
    "source_name": ...,
    "step_path": ...,
    "zip_path": ...,
    "views_dir": views_dir,      # ← str 路径
    "view_paths": view_paths,
    "views_generated": True/False,
}
```

两个字段均存在，条件判断正确。

- [ ] **Step 4: 启动后端，上传一个 PRT 文件，观察日志**

```bash
python backend/app.py
```

上传 PRT 后在控制台观察：
- `[vlm_feature] ...` 开头的日志（说明模块被调用）
- SSE 日志里出现 `"正在调用VLM提取三视图视觉特征..."` 和 `"VLM视觉特征提取完成"` 
- 在特征审阅界面，`full_feature_text` 中应包含 `【VLM视觉特征】` 段落

若 `VISION_API_KEY` 未配置：日志打印 `skipping`，审阅界面只有 geo_text，行为与现在完全一致。

- [ ] **Step 5: 提交**

```bash
git add backend/api/upload.py
git commit -m "feat: integrate VLM three-view features into PRT upload pipeline"
```
