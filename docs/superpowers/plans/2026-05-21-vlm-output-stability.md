# VLM 图纸提取输出稳定性优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增输出规范化层与关键字段校验，改写工程图 prompt，消除 VLM 多次调用结果不一致的问题。

**Architecture:** 在 VLM 返回原始文本 → `_parse_structured_fields()` 解析之后、`_merge_geometry_creo_vlm_fields()` 合并之前，插入两个新函数：`_normalize_vlm_output()` 做字段补全/格式标准化/精度统一，`_validate_and_mark_dimensions()` 做外形尺寸合理性检查和跨调用防抖。

**Tech Stack:** Python 3, pytest, `backend/pipeline/vlm_feature.py`

**Spec:** `docs/superpowers/specs/2026-05-21-vlm-output-stability-design.md`

---

## 文件清单

| 文件 | 操作 |
|------|------|
| `backend/pipeline/vlm_feature.py` | Modify: 新增 `_normalize_vlm_output`、`_normalize_overall_dims`、`_validate_and_mark_dimensions`、`_make_cache_key`；改写 `_VLM_ENGINEERING_DRAWING_PROMPT`；在三个提取函数中接入流水线 |
| `backend/pipeline/test_vlm_feature.py` | Modify: 新增 `_normalize_vlm_output` 和 `_validate_and_mark_dimensions` 的单元测试；更新 prompt 断言 |

---

### Task 1: 为 `_normalize_vlm_output` 写失败测试

**Files:**
- Modify: `backend/pipeline/test_vlm_feature.py`

- [ ] **Step 1: 在 test_vlm_feature.py 末尾追加测试函数**

在文件末尾追加以下三个测试函数：

```python
# ============================================================
# _normalize_vlm_output tests
# ============================================================

def test_normalize_vlm_output_fills_missing_fields():
    from backend.pipeline.vlm_feature import _normalize_vlm_output
    result = _normalize_vlm_output({"零件名称": "轴"})
    assert result["零件名称"] == "轴"
    assert result["外形尺寸"] == "无"
    assert result["刻字"] == "无"
    assert result["通孔"] == "无"


def test_normalize_vlm_output_unifies_empty_variants():
    from backend.pipeline.vlm_feature import _normalize_vlm_output
    result = _normalize_vlm_output({
        "零件名称": "无。",
        "形态": "暂无",
        "类型": "N/A",
        "热处理与探伤": "",
        "其他特征": "None",
    })
    assert result["零件名称"] == "无"
    assert result["形态"] == "无"
    assert result["类型"] == "无"
    assert result["热处理与探伤"] == "无"
    assert result["其他特征"] == "无"


def test_normalize_vlm_output_standardizes_overall_dims():
    from backend.pipeline.vlm_feature import _normalize_vlm_output
    result = _normalize_vlm_output({"外形尺寸": "373 x 238*140"})
    assert "×" in result["外形尺寸"]
    assert "373" in result["外形尺寸"]
    assert "238" in result["外形尺寸"]
    assert "140" in result["外形尺寸"]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd F:\Work_Dir\new_3dversion\my_working
python -m pytest backend/pipeline/test_vlm_feature.py::test_normalize_vlm_output_fills_missing_fields -v
```

预期输出：`FAILED` — `ImportError: cannot import name '_normalize_vlm_output'`

---

### Task 2: 为 `_validate_and_mark_dimensions` 写失败测试

**Files:**
- Modify: `backend/pipeline/test_vlm_feature.py`

- [ ] **Step 1: 在文件末尾追加测试函数**

```python
# ============================================================
# _validate_and_mark_dimensions tests
# ============================================================

def test_validate_and_mark_dimensions_flags_implausible_thickness():
    from backend.pipeline.vlm_feature import _validate_and_mark_dimensions
    fields = {"外形尺寸": "长373mm×宽238mm×高140mm"}
    result = _validate_and_mark_dimensions(fields, "test_key_1")
    assert "[?]" in result["外形尺寸"], "140mm thickness should be flagged"


def test_validate_and_mark_dimensions_accepts_normal_thickness():
    from backend.pipeline.vlm_feature import _validate_and_mark_dimensions
    fields = {"外形尺寸": "长373mm×宽238mm×高14mm"}
    result = _validate_and_mark_dimensions(fields, "test_key_2")
    assert "[?]" not in result["外形尺寸"]


def test_validate_and_mark_dimensions_locks_on_fluctuation():
    from backend.pipeline.vlm_feature import _validate_and_mark_dimensions, _dimension_cache
    key = "test_fluctuation_key"
    _dimension_cache.clear()
    # First call — establishes baseline
    fields1 = {"外形尺寸": "长373mm×宽238mm×高14mm"}
    r1 = _validate_and_mark_dimensions(fields1, key)
    assert r1["外形尺寸"] == "长373mm×宽238mm×高14mm"
    # Second call — 20% deviation triggers lock, returns cached
    fields2 = {"外形尺寸": "长450mm×宽280mm×高18mm"}
    r2 = _validate_and_mark_dimensions(fields2, key)
    assert r2["外形尺寸"] == "长373mm×宽238mm×高14mm"
    _dimension_cache.clear()
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
python -m pytest backend/pipeline/test_vlm_feature.py::test_validate_and_mark_dimensions_flags_implausible_thickness -v
```

预期输出：`FAILED` — `ImportError: cannot import name '_validate_and_mark_dimensions'`

---

### Task 3: 实现 `_normalize_vlm_output` 和辅助函数

**Files:**
- Modify: `backend/pipeline/vlm_feature.py`

- [ ] **Step 1: 在 `_parse_structured_fields` 函数之后（约第115行）插入新函数**

```python
# ── Expected VLM output fields (from _SEMANTIC_FIELDS + _DRAWING_FIELDS) ──
_NORMALIZE_FIELDS = (
    "零件名称", "形态", "类型", "热处理与探伤", "其他特征",
    "外形尺寸", "通孔", "沉孔沉槽", "螺纹孔", "特殊孔",
    "尺寸公差", "形位公差", "表面粗糙度", "表面处理", "刻字",
)

_EMPTY_VARIANTS = frozenset({"无", "无。", "暂无", "N/A", "None", "none", ""})


def _normalize_overall_dims(val: str) -> str:
    """Normalize 外形尺寸 to standard format: 长Xmm×宽Ymm×高Zmm"""
    if not val or val == "无":
        return "无"
    # Unify separators: x, X, *, × → ×
    cleaned = re.sub(r'\s*[xX*×]\s*', '×', val)
    # Remove bare "长/宽/高" prefixes if present (will re-add)
    cleaned = re.sub(r'[长宽高]\s*', '', cleaned)
    cleaned = re.sub(r'mm', '', cleaned)
    # Extract numbers
    nums = re.findall(r'(\d+(?:\.\d+)?)', cleaned)
    if len(nums) >= 3:
        rounded = []
        for n in nums[:3]:
            v = float(n)
            rounded.append(_fmt_mm_value(round(v * 2) / 2))
        return f"长{rounded[0]}mm×宽{rounded[1]}mm×高{rounded[2]}mm"
    return val


def _normalize_vlm_output(fields: dict) -> dict:
    """Normalize VLM output fields for consistent format across calls."""
    result = {}
    for field in _NORMALIZE_FIELDS:
        val = (fields.get(field, "") or "").strip()
        val = re.sub(r'\s+', ' ', val)
        if val in _EMPTY_VARIANTS:
            val = "无"
        if field == "外形尺寸" and val != "无":
            val = _normalize_overall_dims(val)
        result[field] = val
    # Carry through extra fields not in standard list
    for k, v in fields.items():
        if k not in result:
            result[k] = v
    return result
```

- [ ] **Step 2: 运行 Task 1 三个测试，确认通过**

```powershell
python -m pytest backend/pipeline/test_vlm_feature.py::test_normalize_vlm_output_fills_missing_fields backend/pipeline/test_vlm_feature.py::test_normalize_vlm_output_unifies_empty_variants backend/pipeline/test_vlm_feature.py::test_normalize_vlm_output_standardizes_overall_dims -v
```

预期输出：3 passed

- [ ] **Step 3: 提交**

```bash
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: add _normalize_vlm_output for consistent VLM field format"
```

---

### Task 4: 实现 `_validate_and_mark_dimensions` 和缓存

**Files:**
- Modify: `backend/pipeline/vlm_feature.py`

- [ ] **Step 1: 在 `_normalize_vlm_output` 之后插入波动锁缓存和新函数**

```python
# Cross-call dimension stability cache (in-process only, resets on restart)
_dimension_cache: dict[str, dict] = {}


def _make_cache_key(image_paths: list) -> str:
    """Create a deterministic cache key from image paths."""
    h = hashlib.sha256()
    for p in sorted(image_paths, key=lambda x: str(x)):
        try:
            st = Path(p).stat()
            h.update(f"{Path(p).resolve()}|{st.st_mtime}|{st.st_size}\n".encode())
        except Exception:
            h.update(str(p).encode())
    return h.hexdigest()[:16]


def _validate_and_mark_dimensions(fields: dict, cache_key: str) -> dict:
    """Validate 外形尺寸 reasonableness and apply cross-call stability lock."""
    result = dict(fields)
    dim_str = result.get("外形尺寸", "无")
    if dim_str == "无":
        return result

    nums = re.findall(r'(\d+(?:\.\d+)?)', dim_str)
    if len(nums) < 3:
        return result

    values = [float(n) for n in nums[:3]]
    thickness = min(values)

    # Range check: flag implausible thickness
    if thickness > 100 or thickness < 2:
        result["外形尺寸"] = dim_str + " [?]"
        return result

    # Cross-call stability lock
    if cache_key in _dimension_cache:
        cached = _dimension_cache[cache_key]
        cached_vals = cached["values"]
        for cur, prev in zip(values, cached_vals):
            if prev > 0 and abs(cur - prev) / prev > 0.10:
                result["外形尺寸"] = cached["dim_str"]
                return result

    _dimension_cache[cache_key] = {"values": values, "dim_str": dim_str}
    return result
```

- [ ] **Step 2: 运行 Task 2 三个测试，确认通过**

```powershell
python -m pytest backend/pipeline/test_vlm_feature.py::test_validate_and_mark_dimensions_flags_implausible_thickness backend/pipeline/test_vlm_feature.py::test_validate_and_mark_dimensions_accepts_normal_thickness backend/pipeline/test_vlm_feature.py::test_validate_and_mark_dimensions_locks_on_fluctuation -v
```

预期输出：3 passed

- [ ] **Step 3: 提交**

```bash
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: add _validate_and_mark_dimensions with cross-call stability lock"
```

---

### Task 5: 改写 `_VLM_ENGINEERING_DRAWING_PROMPT` 并更新测试断言

**Files:**
- Modify: `backend/pipeline/vlm_feature.py` (第 59–84 行)
- Modify: `backend/pipeline/test_vlm_feature.py` (第 332–377 行)

- [ ] **Step 1: 替换 `_VLM_ENGINEERING_DRAWING_PROMPT`**

将第 59–84 行的 `_VLM_ENGINEERING_DRAWING_PROMPT = """..."""` 替换为：

```python
_VLM_ENGINEERING_DRAWING_PROMPT = """
你是专业机械工程师，正在阅读同一个零件的 Creo 工程视图截图。请先逐张扫描图片中的数字标注和文字标注，再按字段输出。

【外形尺寸】
第一步：识别每张图的视图类型（主视图/左视图/右视图/俯视图/剖视图/其他）
第二步：按视图类型提取轴向尺寸
  - 主视图 → 长方向和高方向的最大外轮廓标注值
  - 左视图/右视图 → 宽（厚度）方向和高方向的最大外轮廓标注值
  - 俯视图 → 长方向和宽方向的最大外轮廓标注值
第三步：取各方向最大整体外轮廓值，合并输出一个值，格式：长×宽×厚
规则：厚度取最薄方向整体通长尺寸，不取槽深/台阶高/局部特征深度；只抄图纸数字，不估算
【通孔】数量-直径，多种孔径用分号分隔
【沉孔沉槽】沉孔写直径×角度或直径×深度，沉槽写宽×深
【螺纹孔】数量-规格 孔深N 底孔深N，平底或通孔需注明
【特殊孔】钢丝螺套、销孔、铆孔等特殊孔型
【尺寸公差】逐张扫描以下位置：
  ① 每个尺寸数字旁的公差符号（如 ±0.05、+0.02/-0.01、H7、h6、JS6）
  ② 标题栏或技术要求区的"未注公差"说明（如"未注公差按GB/T 1804-m"）
  ③ 公差框格内的极限偏差数值
  格式：尺寸值 公差；未注公差说明；如确实无任何公差标注则填"无"
【形位公差】逐张扫描公差框格（矩形框+箭头引线），提取：类型符号（平面度/垂直度/位置度等）、公差值、基准代号；如确实无形位公差标注则填"无"
【表面粗糙度】Ra 或 Rz 值，含未注说明
【表面处理】阳极化、镀层、发黑、喷涂等
【热处理与探伤】硬度、热处理、探伤检测要求
【刻字】字高×深度×内容，逐处列出
【零件名称】根据外形推断，如无法判断填"无"
【形态】一句话描述整体几何形态
【类型】功能类别
【其他特征】凸台、加强筋、镂空、退刀槽、键槽、装配孔等结构描述

规则：
- 数字必须原样抄录，不得估算
- 识别不确定时在该值后加"[?]"
- 多视图同一字段有矛盾时用"|"分隔并注明来源
- 所有字段必须输出，无内容填"无"
- 不要输出字段之外的解释文字
""".strip()
```

- [ ] **Step 2: 更新测试断言**

在 `test_extract_creo_primary_features_builds_structured_prompt` 函数末尾（第 377 行 `assert captured["n_images"] == 1` 之后）追加新的 prompt 断言：

```python
    # 新提示词：外形尺寸三步推理
    assert "第一步" in captured["prompt"], "外形尺寸三步推理缺失"
    assert "视图类型" in captured["prompt"], "视图类型映射指令缺失"
    # 新提示词：公差扫描清单
    assert "公差符号" in captured["prompt"], "尺寸公差扫描清单缺失"
    assert "公差框格" in captured["prompt"], "形位公差框格扫描指令缺失"
```

保留原有 `assert "逐张扫描" in captured["prompt"]` —— 改后提示词首行仍含此短语，断言仍应通过。

- [ ] **Step 3: 运行测试确认通过**

```powershell
python -m pytest backend/pipeline/test_vlm_feature.py::test_extract_creo_primary_features_builds_structured_prompt -v
```

预期输出：PASSED

- [ ] **Step 4: 提交**

```bash
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: improve VLM engineering drawing prompt for multi-view dim synthesis and tolerance scan"
```

---

### Task 6: 在三个提取函数中接入规范化+校验流水线

**Files:**
- Modify: `backend/pipeline/vlm_feature.py` (`extract_creo_primary_features`, `extract_freecad_geo_constrained_features`, `extract_vlm_features`)

- [ ] **Step 1: 在 `extract_creo_primary_features` 中接入**

找到 `extract_creo_primary_features` 函数（约第 1020–1023 行）：

```python
    vlm_semantic = _extract_vlm_semantic_fields(creo_paths, creo_context_prompt)

    # Merge all three layers
    result = _merge_geometry_creo_vlm_fields(geometry_fields, creo_buckets, vlm_semantic)
```

改为：

```python
    vlm_semantic = _extract_vlm_semantic_fields(creo_paths, creo_context_prompt)

    # Normalize and validate VLM output
    vlm_semantic = _normalize_vlm_output(vlm_semantic)
    vlm_semantic = _validate_and_mark_dimensions(vlm_semantic, _make_cache_key(creo_paths))

    # Merge all three layers
    result = _merge_geometry_creo_vlm_fields(geometry_fields, creo_buckets, vlm_semantic)
```

- [ ] **Step 2: 在 `extract_freecad_geo_constrained_features` 中接入**

找到约第 1154–1157 行：

```python
    vlm_semantic = _extract_vlm_semantic_fields(image_paths, geo_context_prompt)

    # Merge (no Creo txt layer)
    result = _merge_geometry_creo_vlm_fields(geometry_fields, {}, vlm_semantic)
```

改为：

```python
    vlm_semantic = _extract_vlm_semantic_fields(image_paths, geo_context_prompt)

    # Normalize and validate VLM output
    vlm_semantic = _normalize_vlm_output(vlm_semantic)
    vlm_semantic = _validate_and_mark_dimensions(vlm_semantic, _make_cache_key(image_paths))

    # Merge (no Creo txt layer)
    result = _merge_geometry_creo_vlm_fields(geometry_fields, {}, vlm_semantic)
```

- [ ] **Step 3: 在 `extract_vlm_features` 中接入**

找到约第 1045–1048 行：

```python
    vlm_semantic = _extract_vlm_semantic_fields(image_paths, _VLM_SEMANTIC_FIELDS_PROMPT)

    # No geometry layer, no Creo txt layer — merge with empty buckets
    result = _merge_geometry_creo_vlm_fields({}, {}, vlm_semantic)
```

改为：

```python
    vlm_semantic = _extract_vlm_semantic_fields(image_paths, _VLM_SEMANTIC_FIELDS_PROMPT)

    # Normalize and validate VLM output
    vlm_semantic = _normalize_vlm_output(vlm_semantic)
    vlm_semantic = _validate_and_mark_dimensions(vlm_semantic, _make_cache_key(image_paths))

    # No geometry layer, no Creo txt layer — merge with empty buckets
    result = _merge_geometry_creo_vlm_fields({}, {}, vlm_semantic)
```

- [ ] **Step 4: 将 `_normalize_vlm_output`、`_validate_and_mark_dimensions`、`_make_cache_key`、`_dimension_cache` 加入测试文件的 import**

修改 `backend/pipeline/test_vlm_feature.py` 第 18–37 行的 import 块，追加：

```python
    _normalize_vlm_output,
    _validate_and_mark_dimensions,
    _make_cache_key,
    _dimension_cache,
```

- [ ] **Step 5: 运行全量测试**

```powershell
python -m pytest backend/pipeline/test_vlm_feature.py -v
```

预期输出：所有测试 PASSED，零 FAILED。

- [ ] **Step 6: 提交**

```bash
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: wire normalization and validation into all VLM extraction paths"
```

---

## 完成检查

全部 6 个 Task 完成后：

1. 运行全量测试确认零失败：
   ```powershell
   python -m pytest backend/pipeline/test_vlm_feature.py -v
   ```

2. 确认 git log 有 4 个提交：
   ```
   feat: add _normalize_vlm_output for consistent VLM field format
   feat: add _validate_and_mark_dimensions with cross-call stability lock
   feat: improve VLM engineering drawing prompt for multi-view dim synthesis and tolerance scan
   feat: wire normalization and validation into all VLM extraction paths
   ```
