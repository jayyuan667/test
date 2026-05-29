# PaddleOCR 孔特征字段补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `ocr_feature.py` 模块，用 PaddleOCR 识别 Creo 视图图片中的孔标注，补全 VLM 提取的 `【通孔】`/`【沉孔沉槽】`/`【螺纹孔】`/`【特殊孔】` 四个字段，重复项去重后追加。

**Architecture:** 新建独立模块 `ocr_feature.py` 负责 OCR 运行和正则分类；在 `vlm_feature.py` 的 `extract_creo_primary_features` 末尾调用 OCR 入口，结果通过新增 `ocr_fields` 参数传入 `_merge_geometry_creo_vlm_fields`，在 VLM 字段赋值后追加去重。

**Tech Stack:** `paddleocr 3.5.0`（已安装），`paddlepaddle 3.3.1`（已安装），Python `re`，`pathlib`

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/pipeline/ocr_feature.py` | 新建 | PaddleOCR 懒加载、文本识别、正则分类、公开入口 |
| `backend/pipeline/test_ocr_feature.py` | 新建 | 分类规则测试、去重合并测试（不依赖真实 OCR） |
| `backend/pipeline/vlm_feature.py` | 修改 | 新增 `_merge_ocr_into_field`；`_merge_geometry_creo_vlm_fields` 加 `ocr_fields` 参数；`extract_creo_primary_features` 调用 OCR |
| `backend/pipeline/test_vlm_feature.py` | 修改 | 新增 `ocr_fields` 合并行为测试（2 个） |

---

## Task 1: 创建 `ocr_feature.py` — 分类逻辑（TDD）

**Files:**
- Create: `backend/pipeline/ocr_feature.py`
- Create: `backend/pipeline/test_ocr_feature.py`

- [ ] **Step 1: 写分类函数的失败测试**

新建 `backend/pipeline/test_ocr_feature.py`：

```python
import pytest
from backend.pipeline.ocr_feature import classify_ocr_tokens


def test_classify_tongkong_plain_phi():
    result = classify_ocr_tokens(["24-Ø2.8", "20-Ø3"])
    assert result["通孔"] == ["24-Ø2.8", "20-Ø3"]
    assert result["螺纹孔"] == []
    assert result["沉孔沉槽"] == []


def test_classify_tongkong_with_keyword():
    result = classify_ocr_tokens(["4-M3通孔"])
    assert result["通孔"] == ["4-M3通孔"]
    assert result["螺纹孔"] == []


def test_classify_chenkong_angle():
    result = classify_ocr_tokens(["∅5.6×90°"])
    assert result["沉孔沉槽"] == ["∅5.6×90°"]


def test_classify_chenkong_keyword():
    result = classify_ocr_tokens(["沉孔深3"])
    assert result["沉孔沉槽"] == ["沉孔深3"]


def test_classify_luowen_with_depth():
    result = classify_ocr_tokens(["24-M3孔深6 底孔深7"])
    assert result["螺纹孔"] == ["24-M3孔深6 底孔深7"]
    assert result["通孔"] == []


def test_classify_luowen_螺纹孔_keyword():
    result = classify_ocr_tokens(["26-M2.5螺纹孔深8.1 底孔深9.1"])
    assert result["螺纹孔"] == ["26-M2.5螺纹孔深8.1 底孔深9.1"]


def test_classify_special_taper():
    result = classify_ocr_tokens(["∅80锥孔"])
    assert result["特殊孔"] == ["∅80锥孔"]


def test_classify_special_keywords():
    for kw in ["异形孔深4", "定位孔∅6", "销孔H7"]:
        result = classify_ocr_tokens([kw])
        assert result["特殊孔"] == [kw], f"expected 特殊孔 for: {kw}"


def test_classify_priority_chen_over_luowen():
    # ∅5.6×90° 是沉孔沉槽，即使包含可能像螺纹的符号也优先沉孔
    result = classify_ocr_tokens(["∅5.6×90°"])
    assert result["沉孔沉槽"] == ["∅5.6×90°"]
    assert result["螺纹孔"] == []


def test_classify_empty_lines_ignored():
    result = classify_ocr_tokens(["", "  ", "abc"])
    assert result["通孔"] == []
    assert result["螺纹孔"] == []
    assert result["沉孔沉槽"] == []
    assert result["特殊孔"] == []


def test_classify_phi_variants_normalized():
    # φ 和 ∅ 都识别为通孔
    result = classify_ocr_tokens(["12-φ3.2", "8-∅4"])
    assert len(result["通孔"]) == 2
```

- [ ] **Step 2: 运行测试确认失败**

```
cd F:\Work_Dir\new_3dversion\my_working
python -m pytest backend/pipeline/test_ocr_feature.py -v 2>&1 | head -30
```

预期：`ModuleNotFoundError: No module named 'backend.pipeline.ocr_feature'`

- [ ] **Step 3: 实现 `classify_ocr_tokens`**

新建 `backend/pipeline/ocr_feature.py`：

```python
# -*- coding: utf-8 -*-
"""PaddleOCR-based hole annotation extractor for Creo view images."""

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_OCR_ENABLED = os.getenv("OCR_HOLE_FIELDS", "1") != "0"

# ── Regex patterns ──────────────────────────────────────────────
_PHI = r"[Øφ∅]"
_NUM = r"\d+(?:\.\d+)?"

# 沉孔沉槽: φN×角度° 或 含"沉孔"/"沉槽"/"埋头"
_RE_CHEN = re.compile(
    rf"({_PHI}{_NUM}\s*[×x]\s*{_NUM}°|沉孔|沉槽|埋头)", re.IGNORECASE
)

# 螺纹孔: MN + 含"孔深"/"底孔"/"螺纹孔" (通孔除外)
_RE_LUOWEN = re.compile(
    rf"M{_NUM}.*?(?:孔深|底孔|螺纹孔)", re.IGNORECASE
)

# 通孔: N-φN 或 含"通孔" (无深度词)
_RE_TONGKONG_PHI = re.compile(rf"\d*-?{_PHI}{_NUM}")
_RE_TONGKONG_KW = re.compile(r"通孔")
_RE_DEPTH_WORD = re.compile(r"孔深|底孔|螺纹孔")

# 特殊孔
_RE_SPECIAL = re.compile(r"锥孔|异形孔|定位孔|销孔")
_RE_SPECIAL_LARGE = re.compile(rf"{_PHI}(\d+(?:\.\d+)?)")  # Ø>50


def classify_ocr_tokens(lines: list[str]) -> dict[str, list[str]]:
    """将 OCR 识别文本行分类到4个孔字段桶。

    优先级: 沉孔沉槽 > 螺纹孔 > 通孔 > 特殊孔
    每条文本只归入一个桶。
    """
    buckets: dict[str, list[str]] = {
        "通孔": [], "沉孔沉槽": [], "螺纹孔": [], "特殊孔": []
    }
    for raw in lines:
        line = raw.strip()
        if not line or not re.search(r"[\dMØφ∅沉槽锥孔通孔螺纹]", line):
            continue

        if _RE_CHEN.search(line):
            buckets["沉孔沉槽"].append(line)
        elif _RE_LUOWEN.search(line):
            buckets["螺纹孔"].append(line)
        elif _RE_TONGKONG_KW.search(line) or (
            _RE_TONGKONG_PHI.search(line) and not _RE_DEPTH_WORD.search(line)
        ):
            buckets["通孔"].append(line)
        elif _RE_SPECIAL.search(line):
            buckets["特殊孔"].append(line)
        else:
            m = _RE_SPECIAL_LARGE.search(line)
            if m and float(m.group(1)) > 50:
                buckets["特殊孔"].append(line)
    return buckets
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest backend/pipeline/test_ocr_feature.py -v
```

预期：`11 passed`

- [ ] **Step 5: 提交**

```
git add backend/pipeline/ocr_feature.py backend/pipeline/test_ocr_feature.py
git commit -m "feat: add ocr_feature.py with classify_ocr_tokens"
```

---

## Task 2: 添加去重合并测试并实现 `_merge_ocr_into_field`

**Files:**
- Modify: `backend/pipeline/test_ocr_feature.py`
- Modify: `backend/pipeline/ocr_feature.py`

- [ ] **Step 1: 写去重合并的失败测试**

在 `test_ocr_feature.py` 末尾追加：

```python
from backend.pipeline.ocr_feature import merge_ocr_into_field


def test_merge_appends_new_ocr_item():
    result = merge_ocr_into_field("24-Ø2.8；20-Ø3", ["8-Ø4"])
    assert "8-Ø4" in result
    assert "24-Ø2.8" in result


def test_merge_dedup_same_spec():
    # OCR 识别到与 VLM 完全相同的条目，不重复追加
    result = merge_ocr_into_field("24-Ø2.8；20-Ø3", ["24-Ø2.8"])
    assert result.count("24-Ø2.8") == 1


def test_merge_dedup_phi_variant():
    # VLM 有 "24-Ø2.8"，OCR 识别到 "24-φ2.8"（phi变体），规范化后相同不追加
    result = merge_ocr_into_field("24-Ø2.8", ["24-φ2.8"])
    assert result.count("2.8") == 1


def test_merge_vlm_wu_replaced_by_ocr():
    result = merge_ocr_into_field("无", ["24-Ø2.8", "20-Ø3"])
    assert "24-Ø2.8" in result
    assert "20-Ø3" in result
    assert "无" not in result


def test_merge_ocr_empty_no_change():
    result = merge_ocr_into_field("24-Ø2.8", [])
    assert result == "24-Ø2.8"


def test_merge_both_empty_returns_wu():
    result = merge_ocr_into_field("无", [])
    assert result == "无"
```

- [ ] **Step 2: 运行确认失败**

```
python -m pytest backend/pipeline/test_ocr_feature.py::test_merge_appends_new_ocr_item -v
```

预期：`ImportError` 或 `AttributeError`（`merge_ocr_into_field` 不存在）

- [ ] **Step 3: 实现 `merge_ocr_into_field`**

在 `ocr_feature.py` 末尾（`classify_ocr_tokens` 之后）追加：

```python
def _normalize_spec(s: str) -> str:
    """规范化孔规格字符串用于去重比较。"""
    s = s.strip()
    s = re.sub(r"[φ∅]", "Ø", s)          # 统一 phi 符号
    s = re.sub(r"\s+", " ", s)            # 合并空白
    s = s.replace("　", " ")              # 全角空格
    return s


def merge_ocr_into_field(vlm_val: str, ocr_items: list[str]) -> str:
    """将 OCR 识别项追加到 VLM 字段值，重复项去重。

    Args:
        vlm_val: VLM 输出的字段值，用 ；分隔，或 "无"
        ocr_items: OCR 识别到的同字段条目列表

    Returns:
        合并去重后的字段值字符串
    """
    if not ocr_items:
        return vlm_val

    # 拆分 VLM 值
    vlm_parts = [p.strip() for p in vlm_val.split("；") if p.strip() and p.strip() != "无"]
    vlm_norms = [_normalize_spec(p) for p in vlm_parts]

    # 追加不重复的 OCR 项
    for item in ocr_items:
        norm = _normalize_spec(item)
        # 若规范化后字符串完全相同或已有项包含此项则跳过
        if any(norm == v or norm in v or v in norm for v in vlm_norms):
            continue
        vlm_parts.append(item.strip())
        vlm_norms.append(norm)

    return "；".join(vlm_parts) if vlm_parts else "无"
```

- [ ] **Step 4: 运行全部测试确认通过**

```
python -m pytest backend/pipeline/test_ocr_feature.py -v
```

预期：`17 passed`

- [ ] **Step 5: 提交**

```
git add backend/pipeline/ocr_feature.py backend/pipeline/test_ocr_feature.py
git commit -m "feat: add merge_ocr_into_field with deduplication"
```

---

## Task 3: 添加 OCR 运行和入口函数

**Files:**
- Modify: `backend/pipeline/ocr_feature.py`

- [ ] **Step 1: 实现 OCR 运行和入口**

在 `ocr_feature.py` 顶部 import 区域之后（`_OCR_ENABLED` 常量之后）插入：

```python
# ── PaddleOCR 懒加载 ────────────────────────────────────────────
_ocr_instance = None


def _get_ocr():
    """懒加载 PaddleOCR 实例，首次调用时初始化，后续复用。"""
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR  # noqa: import inside function for lazy load
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return _ocr_instance


def run_ocr_on_images(image_paths: list[Path]) -> list[str]:
    """对图片列表跑 PaddleOCR，返回所有识别文本行（置信度>=0.6）。"""
    lines: list[str] = []
    ocr = _get_ocr()
    for path in image_paths:
        try:
            result = ocr.ocr(str(path), cls=True)
            if not result:
                continue
            for page in result:
                if not page:
                    continue
                for item in page:
                    # item: [[bbox], [text, confidence]]
                    text, conf = item[1][0], item[1][1]
                    if conf >= 0.6 and text.strip():
                        lines.append(text.strip())
        except Exception:
            logger.warning("[ocr_feature] OCR failed on %s", path, exc_info=True)
    return lines


def extract_hole_fields_from_ocr(creo_dir: str) -> dict[str, list[str]]:
    """从 creo_views 目录的图片中提取孔标注，返回分类后的字段桶。

    若 OCR 未启用、目录不存在、或任何异常，返回空 dict。
    """
    if not _OCR_ENABLED:
        return {}
    try:
        from backend.pipeline.vlm_feature import _select_creo_images  # avoid circular at module level
        dir_path = Path(creo_dir)
        if not dir_path.exists():
            return {}
        image_paths = _select_creo_images(dir_path, max_n=6)
        if not image_paths:
            return {}
        lines = run_ocr_on_images(image_paths)
        return classify_ocr_tokens(lines)
    except Exception:
        logger.warning("[ocr_feature] extract_hole_fields_from_ocr failed", exc_info=True)
        return {}
```

- [ ] **Step 2: 运行已有测试确认无回归**

```
python -m pytest backend/pipeline/test_ocr_feature.py -v
```

预期：`17 passed`

- [ ] **Step 3: 提交**

```
git add backend/pipeline/ocr_feature.py
git commit -m "feat: add run_ocr_on_images and extract_hole_fields_from_ocr"
```

---

## Task 4: 修改 `_merge_geometry_creo_vlm_fields` 接入 OCR 字段

**Files:**
- Modify: `backend/pipeline/vlm_feature.py` (lines 952-1142)
- Modify: `backend/pipeline/test_vlm_feature.py`

- [ ] **Step 1: 写 merge 函数 ocr_fields 行为的失败测试**

在 `test_vlm_feature.py` 末尾追加（找到现有 test 文件末尾）：

```python
def test_merge_ocr_fields_appends_to_vlm_tongkong():
    """ocr_fields 中的通孔新条目追加到 VLM 已有值后面。"""
    geo = {}
    creo = {"技术要求": [], "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": []}
    vlm = {
        "通孔": "24-Ø2.8",
        "沉孔沉槽": "无", "螺纹孔": "无", "特殊孔": "无",
        "外形尺寸": "无", "尺寸公差": "无", "形位公差": "无",
        "表面粗糙度": "无", "表面处理": "无", "刻字": "无",
        "零件名称": "无", "形态": "无", "类型": "无",
        "热处理与探伤": "无", "其他特征": "无",
    }
    ocr = {"通孔": ["20-Ø3"], "沉孔沉槽": [], "螺纹孔": [], "特殊孔": []}
    result = _merge_geometry_creo_vlm_fields(geo, creo, vlm, ocr_fields=ocr)
    assert "20-Ø3" in result
    assert "24-Ø2.8" in result


def test_merge_ocr_fields_dedup_does_not_double_append():
    """ocr_fields 中与 VLM 重复的条目不再追加。"""
    geo = {}
    creo = {"技术要求": [], "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": []}
    vlm = {
        "通孔": "24-Ø2.8；20-Ø3",
        "沉孔沉槽": "无", "螺纹孔": "无", "特殊孔": "无",
        "外形尺寸": "无", "尺寸公差": "无", "形位公差": "无",
        "表面粗糙度": "无", "表面处理": "无", "刻字": "无",
        "零件名称": "无", "形态": "无", "类型": "无",
        "热处理与探伤": "无", "其他特征": "无",
    }
    ocr = {"通孔": ["24-Ø2.8"], "沉孔沉槽": [], "螺纹孔": [], "特殊孔": []}
    result = _merge_geometry_creo_vlm_fields(geo, creo, vlm, ocr_fields=ocr)
    assert result.count("24-Ø2.8") == 1
```

确认 test_vlm_feature.py 顶部有这个 import（如果没有则追加）：

```python
from backend.pipeline.vlm_feature import _merge_geometry_creo_vlm_fields
```

- [ ] **Step 2: 运行确认失败**

```
python -m pytest backend/pipeline/test_vlm_feature.py::test_merge_ocr_fields_appends_to_vlm_tongkong -v
```

预期：`TypeError: _merge_geometry_creo_vlm_fields() got an unexpected keyword argument 'ocr_fields'`

- [ ] **Step 3: 修改 `_merge_geometry_creo_vlm_fields` 签名和合并逻辑**

找到 `vlm_feature.py` 第 952 行的函数定义，修改签名：

```python
def _merge_geometry_creo_vlm_fields(
    geometry_fields: dict,
    creo_txt_buckets: dict,
    vlm_semantic_fields: dict,
    ocr_fields: dict | None = None,
) -> str:
```

在第 1009 行（`# ── Merge each 12-field ──` 注释）**之前**，即 Creo txt fallback 代码块之后，插入 OCR 合并块：

```python
    # ── Layer D: OCR 孔字段补全（追加去重）──
    if ocr_fields:
        from backend.pipeline.ocr_feature import merge_ocr_into_field
        for _ocr_field in ("通孔", "沉孔沉槽", "螺纹孔", "特殊孔"):
            _ocr_items = ocr_fields.get(_ocr_field, [])
            if _ocr_items:
                drawing_fields[_ocr_field] = merge_ocr_into_field(
                    drawing_fields.get(_ocr_field, "无"), _ocr_items
                )
```

插入位置：紧接在第 1009 行 `drawing_fields["表面处理"] = surface` 的 if 块结束之后，`# ── Merge each 12-field ──` 注释之前。

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest backend/pipeline/test_vlm_feature.py -v 2>&1 | tail -5
```

预期：`132 passed`（原 130 + 新增 2）

- [ ] **Step 5: 提交**

```
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: wire ocr_fields into _merge_geometry_creo_vlm_fields"
```

---

## Task 5: 在 `extract_creo_primary_features` 中调用 OCR 入口

**Files:**
- Modify: `backend/pipeline/vlm_feature.py` (lines 1444-1446)

- [ ] **Step 1: 修改 `extract_creo_primary_features`**

找到 `vlm_feature.py` 第 1445 行（`# Merge all three layers`），将：

```python
    # Merge all three layers
    result = _merge_geometry_creo_vlm_fields(geometry_fields, creo_buckets, vlm_semantic)
```

替换为：

```python
    # Merge all layers (geometry + Creo txt + VLM + OCR)
    from backend.pipeline.ocr_feature import extract_hole_fields_from_ocr
    _ocr_fields = extract_hole_fields_from_ocr(creo_dir)
    result = _merge_geometry_creo_vlm_fields(
        geometry_fields, creo_buckets, vlm_semantic, ocr_fields=_ocr_fields
    )
```

- [ ] **Step 2: 运行全部相关测试**

```
python -m pytest backend/pipeline/test_vlm_feature.py backend/pipeline/test_ocr_feature.py backend/pipeline/test_process_gen_geo.py -v 2>&1 | tail -8
```

预期：`132 + 17 + 69 = 218 passed`，无 FAIL

- [ ] **Step 3: 提交**

```
git add backend/pipeline/vlm_feature.py
git commit -m "feat: call PaddleOCR hole extraction in extract_creo_primary_features"
```

---

## Task 6: 全套测试 + 快速冒烟验证

**Files:** 无新文件

- [ ] **Step 1: 跑全套测试**

```
python -m pytest backend/pipeline/ -v 2>&1 | tail -10
```

预期：全部通过，无回归

- [ ] **Step 2: 冒烟验证 OCR 分类（不需要真实图片）**

```python
# 在项目目录运行 python
from backend.pipeline.ocr_feature import classify_ocr_tokens, merge_ocr_into_field

lines = ["24-Ø2.8", "20-Ø3", "4-M3通孔", "∅5.6×90°", "24-M3孔深6 底孔深7"]
print(classify_ocr_tokens(lines))
# 预期: 通孔=['24-Ø2.8','20-Ø3','4-M3通孔'], 沉孔沉槽=['∅5.6×90°'], 螺纹孔=['24-M3孔深6 底孔深7']

print(merge_ocr_into_field("24-Ø2.8；20-Ø3", ["8-Ø4", "24-Ø2.8"]))
# 预期: "24-Ø2.8；20-Ø3；8-Ø4"  (重复的24-Ø2.8不追加)
```

- [ ] **Step 3: 最终提交（如有未提交的改动）**

```
git status
# 确认无遗漏改动
```
