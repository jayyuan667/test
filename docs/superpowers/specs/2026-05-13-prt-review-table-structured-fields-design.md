# PRT 审阅特征表结构化 + 日志视图移除 — 设计文档

> **日期**: 2026-05-13

---

## 1. 目标

1. **特征表结构化**：PRT 上传后，审阅特征表从"仅 PRT 名称有内容"改为 12 个有意义字段全部填充。txt 来源字段（关键尺寸、倒角等）直接从 CREO_TASK.txt 解析结果映射，不经 VLM；VLM 只负责视觉可见的 7 个字段。
2. **移除生成日志 tab**：删除单文件 PRT 上传流程中的"生成日志"标签页及其容器。ZIP 批次日志（`#zipLogList`）保持不变。

---

## 2. 范围

### 做

- `backend/pipeline/vlm_feature.py`：新增 `_assemble_prt_fields`、新常量 `_VLM_VISUAL_FIELDS_PROMPT`；修改三个 extractor 函数
- `backend/feature_report.py`：`REPORT_FIELD_ORDER` 精简为 12 个 PRT 字段
- `updated_front/demo-industrial-console.html`：删除"生成日志" tab 按钮和 `#view-log` 容器
- `updated_front/js/demo-industrial-console.js`：`log` SSE 事件处理器改为空函数

### 不做

- 不改 `upload_pipeline.py`、`kb_import.py`、`library.py`（调用方签名不变）
- 不改后端 SSE 日志发射（`emit_log` 保留）
- 不动 ZIP 批处理流程和 `#zipLogList`
- 不改 Qdrant 存储结构（review_text / feature_text 同一字段，只是内容变为结构化）

---

## 3. 字段定义（12 个）

| # | 字段名 | 来源 | 路径适用 |
|---|--------|------|----------|
| 1 | 图号 | 调用方（文件名 stem） | 全部 |
| 2 | 零件名称 | VLM 视觉 | 全部 |
| 3 | 形态 | VLM 视觉 | 全部 |
| 4 | 类型 | VLM 视觉 | 全部 |
| 5 | 技术要求 | CREO_TASK.txt `[3D NOTE]` 块 | creo-primary |
| 6 | 关键尺寸 | CREO_TASK.txt 主要外形尺寸桶 + 特征尺寸桶 | creo-primary |
| 7 | 外圆与内孔 | VLM 视觉 | 全部 |
| 8 | 螺纹与螺孔 | VLM 视觉 | 全部 |
| 9 | 倒角 | CREO_TASK.txt 倒角圆角桶（非 R 前缀） | creo-primary |
| 10 | 热处理与探伤 | VLM 视觉 | 全部 |
| 11 | 过渡特征 | CREO_TASK.txt 倒角圆角桶（R 前缀） | creo-primary |
| 12 | 其他特征 | VLM 视觉 | 全部 |

freecad-geo / freecad 路径下，txt 来源字段（#5、#6、#9、#11）填"无"。

---

## 4. 架构

### 4.1 数据流

```
CREO_TASK.txt
  parse_creo_task_txt() → txt_buckets
      技术要求   → 【技术要求】
      主要外形+特征尺寸 → 【关键尺寸】
      倒角圆角非R → 【倒角】
      倒角圆角R   → 【过渡特征】

VLM（新 prompt _VLM_VISUAL_FIELDS_PROMPT）
  → 【零件名称】【形态】【类型】【外圆与内孔】
    【螺纹与螺孔】【热处理与探伤】【其他特征】

_assemble_prt_fields(txt_buckets, vlm_visual_text)
  → 11字段结构化文本

调用方（不变）:
  full_feature_text = vlm_text + "\n【图号】" + stem
  → 12字段完整文本 → review_text + RAG feature_text
```

### 4.2 VLM 新 prompt（`_VLM_VISUAL_FIELDS_PROMPT`）

```
以下图片是该零件的截图。请仅根据图片可见内容，按以下格式逐字段输出：

【零件名称】（根据外形推断，如无法判断填"无"）
【形态】（一句话描述整体几何形态）
【类型】（功能类别，如：轴套类-配合件）
【外圆与内孔】（外圆直径及公差；内孔直径及公差；如无填"无"）
【螺纹与螺孔】（螺纹规格、数量；如无填"无"）
【热处理与探伤】（硬度要求或热处理工艺；如无填"无"）
【其他特征】（键槽、退刀槽等特殊结构；如无填"无"）

要求：
- 只描述图片中明确可见的特征
- 不推测未标注的数值
- 每字段多条内容用分号（；）分隔
```

creo-primary 路径在此 prompt 前追加 CREO_TASK.txt 的权威数值段（与现有逻辑一致），作为视觉字段的参考约束，但不要求 VLM 重复这些数值。

### 4.3 `_assemble_prt_fields(txt_buckets, vlm_visual_text) → str`

```python
def _assemble_prt_fields(txt_buckets: dict, vlm_visual_text: str) -> str:
    """
    合并 CREO_TASK.txt 桶数据与 VLM 视觉字段，输出 11 字段结构化文本。
    图号由调用方追加，此处不包含。
    """
    # 解析 VLM 视觉字段（从 vlm_visual_text 中提取 【字段】值）
    vlm_fields = _parse_structured_fields(vlm_visual_text)

    def _get(key, fallback="无"):
        return vlm_fields.get(key, fallback) or fallback

    # txt 来源字段
    tech_req = "；".join(txt_buckets.get("技术要求", [])) or "无"
    major_dims = "；".join(txt_buckets.get("主要外形尺寸", []))
    feature_dims = "；".join(txt_buckets.get("特征尺寸", []))
    key_dims = "；".join(filter(None, [major_dims, feature_dims])) or "无"
    chamfers = "；".join(
        v for v in txt_buckets.get("倒角圆角", []) if not v.startswith("R")
    ) or "无"
    fillets = "；".join(
        v for v in txt_buckets.get("倒角圆角", []) if v.startswith("R")
    ) or "无"

    lines = [
        f"【零件名称】{_get('零件名称')}",
        f"【形态】{_get('形态')}",
        f"【类型】{_get('类型')}",
        f"【技术要求】{tech_req}",
        f"【关键尺寸】{key_dims}",
        f"【外圆与内孔】{_get('外圆与内孔')}",
        f"【螺纹与螺孔】{_get('螺纹与螺孔')}",
        f"【倒角】{chamfers}",
        f"【热处理与探伤】{_get('热处理与探伤')}",
        f"【过渡特征】{fillets}",
        f"【其他特征】{_get('其他特征')}",
    ]
    return "\n".join(lines)
```

### 4.4 `_parse_structured_fields(text) → dict`

辅助函数，从 `【字段名】值` 格式文本中提取字典：

```python
import re

def _parse_structured_fields(text: str) -> dict:
    result = {}
    for m in re.finditer(r'【([^】]+)】([^\n【]*)', text):
        key, val = m.group(1).strip(), m.group(2).strip()
        if key:
            result[key] = val
    return result
```

### 4.5 修改三个 extractor

**`extract_creo_primary_features(creo_dir, txt_path) → str`**

现有 prompt 结构保持（权威数值段作为约束前缀），在末尾**追加** `_VLM_VISUAL_FIELDS_PROMPT` 的格式要求段，明确告知 VLM 只输出 7 个视觉字段、不重复权威数值。VLM 返回后组装：

```python
txt_buckets = parse_creo_task_txt(txt_path)
authority_prefix = _build_authority_prefix(txt_buckets)   # 现有逻辑，不变
prompt = authority_prefix + "\n---\n" + _VLM_VISUAL_FIELDS_PROMPT
vlm_visual = _call_vlm_with_images(image_paths, prompt)
return _assemble_prt_fields(txt_buckets, vlm_visual)
```

**`extract_freecad_geo_constrained_features(views_dir, step_path) → str`**

现有几何约束前缀保持（`【零件几何参数·权威来源】…`），末尾追加 `_VLM_VISUAL_FIELDS_PROMPT` 格式要求。txt_buckets 传空字典：

```python
geo_prefix = _build_geo_prefix(geo_text)   # 现有逻辑，不变；geo 失败时为空串
prompt = (geo_prefix + "\n---\n" + _VLM_VISUAL_FIELDS_PROMPT) if geo_prefix else _VLM_VISUAL_FIELDS_PROMPT
vlm_visual = _call_vlm_with_images(image_paths, prompt)
return _assemble_prt_fields({}, vlm_visual)
```

**`extract_vlm_features(views_dir) → str`**

```python
vlm_visual = _call_vlm_with_images(image_paths, _VLM_VISUAL_FIELDS_PROMPT)
return _assemble_prt_fields({}, vlm_visual)
```

---

## 5. `feature_report.py` 字段顺序

```python
REPORT_FIELD_ORDER = [
    "图号",
    "零件名称",
    "形态",
    "类型",
    "技术要求",
    "关键尺寸",
    "外圆与内孔",
    "螺纹与螺孔",
    "倒角",
    "热处理与探伤",
    "过渡特征",
    "其他特征",
]
```

---

## 6. 前端改动

### 6.1 `demo-industrial-console.html`

删除：
```html
<!-- 删除 tab 按钮（line 96） -->
<button class="result-tab" data-result-view="view-log">生成日志</button>

<!-- 删除 view 容器（lines 180-184） -->
<div class="result-view" id="view-log">
  <div class="log-list" id="generateLogList">
    <div class="log-line"><span class="log-time">09:28:14</span><span>等待上传 PRT 模型文件。</span></div>
  </div>
</div>
```

### 6.2 `demo-industrial-console.js`

`log` SSE 事件处理器改为空函数（保留注册避免 SSE 报错）：

```javascript
// 原有 log 事件处理器替换为：
source.addEventListener('log', () => {});
```

如有对 `demoLogList` 的直接写入调用（`setLogLines` 等），一并改为空函数体或移除对应代码块。

---

## 7. 错误处理

| 情形 | 处理 |
|------|------|
| CREO_TASK.txt 缺失/空 | `parse_creo_task_txt` 返回 `{}`；txt 字段值为"无"；VLM 仍运行 |
| VLM API 失败 | `_call_vlm_with_images` 返回 `""`；`_parse_structured_fields("")` 返回 `{}`；VLM 字段值为"无" |
| VLM 输出格式不符（无【字段】标记） | `_parse_structured_fields` 返回 `{}`，字段降级为"无"，不崩溃 |
| freecad-geo / freecad 路径 | 传入空 `txt_buckets`，txt 字段全"无"，VLM 字段正常 |
| 全部失败（mode=none） | 调用方兜底：`full_feature_text = "【图号】{stem}"` |
| 图号含扩展名（`.prt.3`） | 调用方 stem 提取：循环 `os.path.splitext` 直到无已知扩展 |

---

## 8. 测试

在现有 `backend/pipeline/test_vlm_feature.py` 中新增：

| 测试名 | 覆盖内容 |
|--------|----------|
| `test_assemble_prt_fields_full` | txt 桶 + VLM 输出 → 11 字段格式正确，值不为"无" |
| `test_assemble_prt_fields_empty_txt` | 空 txt_buckets → txt 字段为"无"，VLM 字段正常 |
| `test_assemble_prt_fields_no_vlm` | VLM 返回空串 → VLM 字段为"无"，txt 字段正常 |
| `test_creo_primary_returns_structured` | `extract_creo_primary_features` 输出含全部 11 个 `【字段名】` 标签 |
| `test_parse_structured_fields` | 正常解析、空串、无标记文本三种输入 |

前端验收（手动）：上传含 CREO_TASK.txt 的 PRT 文件，确认：
1. 审阅特征表显示 12 行，关键尺寸/倒角/过渡特征/技术要求有真实数据
2. "生成日志" tab 不出现

---

## 9. 涉及文件清单

| 文件 | 操作 |
|------|------|
| `backend/pipeline/vlm_feature.py` | 新增 `_assemble_prt_fields`、`_parse_structured_fields`、`_VLM_VISUAL_FIELDS_PROMPT`；修改三个 extractor |
| `backend/pipeline/test_vlm_feature.py` | 新增 5 个测试 |
| `backend/feature_report.py` | `REPORT_FIELD_ORDER` 改为 12 字段 |
| `updated_front/demo-industrial-console.html` | 删除 tab 按钮和 `#view-log` 容器 |
| `updated_front/js/demo-industrial-console.js` | `log` 事件处理器改为空函数；移除 `demoLogList` 写入调用 |
