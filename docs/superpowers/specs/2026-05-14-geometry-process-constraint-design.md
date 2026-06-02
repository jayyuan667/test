# 程序化几何分析约束工艺生成 — 设计文档

> **日期**: 2026-05-14

---

## 1. 目标

将 OpenCASCADE（via FreeCAD）几何分析的精确数字直接注入工艺生成约束层，防止 LLM 在备料规格、孔径、孔数量上产生幻觉。

具体目标：

1. **几何→备料规格**：根据形状分类（轴类/板类/盘类/箱体）自动推导正确的备料格式（`δT×L×W=1`、`φD×L=1` 等），作为 0010 备料工序的权威来源。
2. **几何→工艺约束**：在工艺生成前把精确几何数字写入硬约束，进入 LLM prompt。
3. **几何→后校验覆盖**：工艺生成后，对备料规格、孔数量做自动覆盖；对孔径做范围标记。

---

## 2. 范围

### 做

- `backend/pipeline/geometry_analyzer.py`：新增 `derive_blank_spec(geo_result) -> str`
- `backend/pipeline/process_gen.py`：`generate()` 加 `geo_data` 可选参数；扩展 `_extract_process_constraints`；扩展 `_post_check_process`
- `backend/api/upload.py`：在调用 `generate()` 前传入 `geo_data`

### 不做

- 不改 `vlm_feature.py`（特征提取层几何已接入）
- 不改前端展示结构
- 不做孔径的静默自动替换（孔径有加工余量，只做范围标记）

---

## 3. 数据流

```text
STEP 文件
  └─ analyze_step_geometry() → geo_data dict
        ├─ dimensions: {x, y, z}          # 包络尺寸，单位 mm
        ├─ shape_class                     # 轴类 / 盘类 / 板类 / 箱体 / 一般件
        ├─ hole_info: {count, min_diameter, max_diameter, thread_range}
        └─ faces: [{type_name, params:{radius}, area}, ...]
              │
              ▼
       derive_blank_spec(geo_data) → str
       例: "δ30×250×100=1" / "φ80×320=1"
              │
              ▼
  ProcessGenerator.generate(..., geo_data=geo_data)
              │
        ┌─────┴──────┐
        │             │
  约束提取           工艺生成
  (已有逻辑 +        LLM stream
   新增3类硬约束)            │
        │             ▼
        └──────> _post_check_process()
                  ① 0010备料 → 整行替换
                  ② 孔数量   → N覆盖
                  ③ 孔径     → 范围标记（不静默替换）
```

---

## 4. 核心改动

### 4.1 `geometry_analyzer.py` — `derive_blank_spec`

```python
def derive_blank_spec(geo_result: dict) -> str:
    """从几何分析结果推导备料规格字符串。

    形状判断规则：
      - 轴类：最大圆柱面外径 × 最长边 → φD×L=1
      - 盘类：最大圆柱面外径 × 最短边 → φD×H=1
      - 板类：包络最短边=厚度 → δT×L×W=1
      - 箱体/一般件：三边从大到小 → L×W×H=1

    注：不依赖 PRT 坐标轴方向；板类厚度始终取包络最小边。
    """
    shape = geo_result.get("shape_class", "一般件")
    dims  = geo_result.get("dimensions", {})
    x, y, z = dims.get("x", 0), dims.get("y", 0), dims.get("z", 0)
    sorted_dims = sorted([x, y, z])  # [min, mid, max]

    faces = geo_result.get("faces", [])
    cylinders = [f for f in faces if f.get("type_name") == "Cylinder"]
    max_r = max((f.get("params", {}).get("radius", 0) for f in cylinders), default=0)

    if shape == "轴类" and max_r > 0:
        D = round(max_r * 2, 1)
        L = sorted_dims[2]
        return f"φ{D}×{L}=1"
    elif shape == "盘类" and max_r > 0:
        D = round(max_r * 2, 1)
        H = sorted_dims[0]
        return f"φ{D}×{H}=1"
    elif shape == "板类":
        T, W, L = sorted_dims[0], sorted_dims[1], sorted_dims[2]
        return f"δ{T}×{L}×{W}=1"
    else:  # 箱体 / 一般件
        L, W, H = sorted_dims[2], sorted_dims[1], sorted_dims[0]
        return f"{L}×{W}×{H}=1"
```

### 4.2 `process_gen.py` — `generate()` 接口扩展

```python
def generate(
    self,
    descriptions: List[Dict[str, Any]],
    expert_judgment: str,
    prefix_hint: Optional[str] = None,
    log_callback=None,
    stream_callback=None,
    library_key: Optional[str] = None,
    geo_data: Optional[dict] = None,   # ← 新增
) -> tuple[str, list[list[str]], dict | None]:
```

`geo_data` 为 `analyze_step_geometry()` 的原始返回值；`None` 时退化为现有行为（向后兼容）。

### 4.3 `process_gen.py` — `_extract_process_constraints` 扩展

在现有 `hard` dict 里新增三个几何专属键：

```python
hard["geo_blank_spec"]  = ""   # derive_blank_spec 结果，如 "δ30×250×100=1"
hard["geo_hole_count"]  = 0    # hole_info.count
hard["geo_bore_range"]  = ""   # "min_diameter~max_diameter mm"，如 "8~12mm"
```

当 `geo_data` 不为 None 时填入；无几何数据时保持空/0（不影响现有逻辑）。

### 4.4 `process_gen.py` — `_post_check_process` 扩展

**① 备料规格校验（0010 行，覆盖已有逻辑）**

- 当 `geo_blank_spec` 非空时，使用新逻辑替换尺寸部分（保留 `=1` 数量）
- 原有 blank_size 字符串匹配逻辑保留作为 fallback（geo_data 不可用时）

```python
# 伪代码
if geo_blank_spec and is_blank_line(line):
    return replace_blank_spec(line, geo_blank_spec)
elif blank_size:        # 原有逻辑
    return replace_blank_dim(line, blank_size)
```

**② 孔数量校验（任何工序行）**

匹配模式：`(\d+)\s*[×x\*]\s*[Mφ]\d+` 或 `(\d+)\s*个\s*(?:螺纹孔|孔)`

当匹配到的孔数 N ≠ `geo_hole_count`（且 `geo_hole_count > 0`）时，将 N 替换为 `geo_hole_count`。

**③ 孔径范围标记（不静默替换）**

匹配 `[Φφ](\d+(?:\.\d+)?)` 中的数值 X：

- 若 X 在 `[min_diameter - 1mm, max_diameter + 1mm]` 范围内 → 不处理
- 若 X 明显超出范围 → 在该行末尾追加 `⚠几何孔径范围:{geo_bore_range}` 标记

原因：孔径有加工余量，自动替换风险高；标记供人工审核。

### 4.5 `upload.py` — 传入 geo_data

```python
# 在 generator.generate() 调用前
geo_data = None
step_path = task.get("step_path", "")
if step_path and os.path.exists(step_path):
    try:
        from ..pipeline.geometry_analyzer import analyze_step_geometry
        geo_data = analyze_step_geometry(step_path)
        if "error" in geo_data:
            geo_data = None
    except Exception:
        geo_data = None

process_flow_raw, process_data, rag_results = generator.generate(
    descriptions,
    expert_judgment,
    prefix_hint=prefix_hint,
    log_callback=rag_log_callback,
    stream_callback=stream_callback,
    library_key=library_key,
    geo_data=geo_data,           # ← 新增
)
```

---

## 5. 约束优先级

```
geo_data 精确数字（最高）
  > feature_text 中的几何字段（中）
  > LLM 自由生成（最低，被覆盖）
```

---

## 6. 备料格式规则汇总

| 形状分类 | 备料格式 | 示例 |
|---------|---------|------|
| 轴类 | `φD×L=1` | `φ80×320=1` |
| 盘类 | `φD×H=1` | `φ120×40=1` |
| 板类 | `δT×L×W=1` | `δ30×250×100=1` |
| 箱体/一般件 | `L×W×H=1` | `200×150×100=1` |

δ 方向判定：**始终取包络三边最小值**，不依赖 PRT 坐标轴方向。

---

## 7. 向后兼容

- `geo_data=None` 时，`generate()` 行为与当前完全一致
- 原有 blank_size 校验逻辑保留为 fallback
- 不改变任何返回值结构（`process_flow_raw`, `process_data`, `rag_results`）

---

## 8. 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/pipeline/geometry_analyzer.py` | 新增 `derive_blank_spec()` |
| `backend/pipeline/process_gen.py` | `generate()` 加参数；扩展约束提取和 post-check（3类） |
| `backend/api/upload.py` | 调用 `analyze_step_geometry`，传 `geo_data` |

---

## 9. 预期效果

| 校验类型 | Before | After |
|---------|--------|-------|
| 0010 备料规格 | LLM 可能幻觉任意尺寸 | 自动替换为几何推导的 δ/φ 格式 |
| 孔数量 | LLM 可能写错孔的个数 | 自动覆盖为 OpenCASCADE 计算值 |
| 孔径 | LLM 可能写错直径 | 超出范围时附加 ⚠ 标记 |
| 无几何数据 | 现有行为 | 完全退化为现有行为（无副作用） |
