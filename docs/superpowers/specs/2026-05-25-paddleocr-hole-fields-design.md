# PaddleOCR 孔特征字段补全 — 设计文档

**日期：** 2026-05-25  
**分支：** `3d-version-modify`  
**状态：** 已批准，待实施

---

## 一、背景与目标

VLM（视觉语言模型）在提取 `【通孔】`、`【沉孔沉槽】`、`【螺纹孔】`、`【特殊孔】` 四个字段时不稳定，部分零件图纸（如多孔安装基板）的孔标注密集、字符小，VLM 容易漏识别或返回"无"。

目标：在不改变 VLM 主流程的前提下，用 PaddleOCR 对同一批 Creo 视图图片做文字识别，提取孔标注，**追加**到 VLM 已有值中（B 策略），并对重复项去重。

---

## 二、整体架构

```
creo_views/*.jpg
      │
      ▼
ocr_feature.py
  run_ocr_on_images(image_paths)     ← PaddleOCR，返回文本行列表
      │
  classify_ocr_tokens(lines)         ← 正则分类到4个桶
      │
  extract_hole_fields_from_ocr(creo_dir) → dict[str, list[str]]
      │
      ▼
vlm_feature.py  extract_creo_primary_features()
  ├─ (已有) VLM → drawing_fields
  ├─ (新增) ocr_fields = extract_hole_fields_from_ocr(creo_dir)
  └─ _merge_geometry_creo_vlm_fields(..., ocr_fields=ocr_fields)
           └─ 对4个字段: VLM值 + OCR追加 → 去重合并
```

---

## 三、文件变动清单

| 文件 | 变动类型 | 内容 |
|------|---------|------|
| `backend/pipeline/ocr_feature.py` | 新建 | OCR 运行、分类、入口函数 |
| `backend/pipeline/vlm_feature.py` | 修改 | `extract_creo_primary_features` 调用 OCR；`_merge_geometry_creo_vlm_fields` 新增 `ocr_fields` 参数和合并逻辑 |
| `backend/pipeline/test_ocr_feature.py` | 新建 | 分类规则测试、去重测试 |

---

## 四、`ocr_feature.py` 详细设计

### 4.1 PaddleOCR 懒加载

```python
_ocr_instance = None

def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return _ocr_instance
```

首次调用时加载模型，后续复用，避免每次请求重新初始化（约 2-3s 开销）。

### 4.2 `run_ocr_on_images(image_paths: list[Path]) -> list[str]`

- 遍历图片列表，对每张调用 `ocr.ocr(str(path), cls=True)`
- 提取每个识别框的文本（`line[1][0]`），过滤置信度 < 0.6 的结果
- 合并所有图片的文本行，返回 `list[str]`
- 单图异常时 `logger.warning` 后跳过，不中断

### 4.3 `classify_ocr_tokens(lines: list[str]) -> dict[str, list[str]]`

返回 `{"通孔": [...], "沉孔沉槽": [...], "螺纹孔": [...], "特殊孔": [...]}`

**分类优先级（高→低）：**

| 优先级 | 字段 | 正则条件 |
|--------|------|---------|
| 1 | 沉孔沉槽 | `[Øφ∅]\d+(\.\d+)?\s*×\s*\d+°` 或含"沉孔"/"沉槽"/"埋头" |
| 2 | 螺纹孔 | `M\d+(\.\d+)?` 且含"孔深"/"底孔"/"螺纹孔" |
| 3 | 通孔 | `\d*-?[Øφ∅]\d+(\.\d+)?` 且不含深度词，或含"通孔" |
| 4 | 特殊孔 | 含"锥孔"/"异形孔"/"定位孔"/"销孔"，或 Ø > 50mm |

每条文本只归入一个桶，最高优先级命中即停。

### 4.4 `extract_hole_fields_from_ocr(creo_dir: str) -> dict[str, list[str]]`

主入口：
1. 用 `_select_creo_images(Path(creo_dir))` 复用已有的图片筛选逻辑
2. 调 `run_ocr_on_images` → `classify_ocr_tokens`
3. 任何异常返回空 dict，记 `logger.warning`

---

## 五、`_merge_geometry_creo_vlm_fields` 修改

### 5.1 签名变更

```python
def _merge_geometry_creo_vlm_fields(
    geometry_fields: dict,
    creo_txt_buckets: dict,
    vlm_semantic_fields: dict,
    ocr_fields: dict | None = None,   # 新增，默认 None
) -> str:
```

调用方（3 处）不需要改，`ocr_fields` 默认为 `None` 向后兼容。

### 5.2 合并逻辑（4 个目标字段）

在 `drawing_fields` 从 VLM 取值并做 Creo txt fallback 之后，插入：

```python
if ocr_fields:
    for _f in ("通孔", "沉孔沉槽", "螺纹孔", "特殊孔"):
        _ocr_items = ocr_fields.get(_f, [])
        if _ocr_items:
            drawing_fields[_f] = _merge_ocr_into_field(
                drawing_fields.get(_f, "无"), _ocr_items
            )
```

### 5.3 `_merge_ocr_into_field(vlm_val: str, ocr_items: list[str]) -> str`

去重合并辅助函数：

1. `vlm_val` 按 `；` 拆成列表（过滤"无"）
2. 对每条 `ocr_item`：
   - 规范化：`φ/∅` → `Ø`，全角空格 → 半角，去首尾空格
   - 与 vlm 列表逐项对比规范化字符串，有包含关系则视为重复跳过
3. 将不重复的 OCR 项追加到 vlm 列表末尾
4. 用 `；` 拼回，若最终列表为空返回 `"无"`

---

## 六、开关

环境变量 `OCR_HOLE_FIELDS`（默认 `"1"`）：

```python
import os
_OCR_ENABLED = os.getenv("OCR_HOLE_FIELDS", "1") != "0"
```

`extract_hole_fields_from_ocr` 开头检查，`0` 时直接返回 `{}`。

---

## 七、错误处理

| 场景 | 处理 |
|------|------|
| PaddleOCR 模块未安装 | `ImportError` 捕获，`logger.warning`，返回 `{}` |
| 单图识别异常 | 跳过该图，记 warning，继续 |
| creo_dir 不存在/无图 | 返回 `{}`，不报错 |
| 全部异常 | 最外层 try/except，返回 `{}`，主流程不受影响 |

---

## 八、测试计划

`test_ocr_feature.py`：

| 测试 | 验证场景 |
|------|---------|
| `test_classify_tongkong_plain_phi` | `24-Ø2.8` → 通孔 |
| `test_classify_tongkong_with_keyword` | `4-M3通孔` → 通孔 |
| `test_classify_chen_kong` | `∅5.6×90°` → 沉孔沉槽 |
| `test_classify_luowen_with_depth` | `24-M3孔深6 底孔深7` → 螺纹孔 |
| `test_classify_special_taper` | `∅80锥孔` → 特殊孔 |
| `test_classify_priority_chen_over_luowen` | 沉孔沉槽优先于螺纹孔 |
| `test_merge_dedup_same_spec` | VLM 已有 `24-Ø2.8`，OCR 也识别到 → 不重复追加 |
| `test_merge_appends_new_ocr_item` | VLM 有值，OCR 识别到新条目 → 追加 |
| `test_merge_vlm_wu_replaced_by_ocr` | VLM="无"，OCR 有值 → 用 OCR 值 |
| `test_merge_ocr_empty_no_change` | OCR 空 → VLM 值不变 |
