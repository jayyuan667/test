# 几何特征加回 + Creo 特征双源提取 — 设计文档

> **日期**: 2026-05-13

---

## 1. 目标

将当前 PRT 特征提取链路从“VLM 主导”调整为 **“几何硬数据优先 + Creo/VLM 语义补充”** 的双源结构。

目标如下：

1. **凡是几何分析能稳定算出的尺寸类字段**，优先直接写入审阅特征表，不再交给模型自由生成。
2. **Creo txt 若提供更明确的公差 / 孔深 / 螺纹规格等标注细节**，作为补充增强对应字段，而不是替代几何主尺寸。
3. **VLM 只负责纯语义字段**，如零件名称、形态、类型、工艺性结构描述。
4. **最终仍输出一张统一的审阅特征表**，保持前端结构不变，不做双列来源展示。

---

## 2. 范围

### 做

- `backend/pipeline/vlm_feature.py`：重构特征装配逻辑，新增几何 + Creo + VLM 三层合并
- `backend/prt_pipeline.py` / 现有几何分析输出映射：重新接回几何特征在特征提取层的使用
- `backend/feature_report.py`：如字段映射需要，调整兼容逻辑
- `backend/pipeline/test_vlm_feature.py`：补充新装配逻辑测试

### 不做

- 不改前端审阅表结构
- 不改工艺生成主流程（这一轮只改特征提取层）
- 不改 ZIP / PDF / Excel 入口的额外逻辑范围
- 不做双来源两列表格展示

---

## 3. 总体架构

### 3.1 数据流

```text
PRT
  ├─ Creo 路径
  │   ├─ Creo 截图
  │   └─ CREO_TASK.txt
  │
  ├─ STEP / Onshape 几何分析
  │   └─ 几何硬特征（尺寸、体积、孔、外形等）
  │
  └─ Feature Assembler
       ├─ Geometry layer（优先）
       ├─ Creo txt supplement layer（补公差/孔深/螺纹）
       ├─ VLM semantic layer（零件名称/形态/类型/其他）
       └─ 输出统一结构化审阅特征表
```

### 3.2 三层装配逻辑

#### A. Geometry layer（最高优先级）

只要几何分析能稳定给出，就直接写入字段，例如：
- 外形尺寸
- 包络尺寸
- 孔统计
- 内外轮廓尺寸
- 可稳定识别的槽 / 孔 / 台阶类尺寸

这些字段不再依赖 VLM 复述。

#### B. Creo txt supplement layer

如果 `CREO_TASK.txt` 里有更明确的信息，则补充进对应字段：
- 公差
- 孔深
- 螺纹规格
- 技术要求文本
- 倒角 / 过渡特征中带明确标注的内容

规则：
- 只补充，不推翻几何主尺寸
- 用于把几何结果写得更完整

#### C. VLM semantic layer

VLM 只负责纯语义字段：
- 零件名称
- 形态
- 类型
- 其他特征中的工艺语义描述

---

## 4. 字段归属

### 4.1 几何直出字段

几何层优先写入：

- `【关键尺寸】`
- `【外圆与内孔】`
- `【螺纹与螺孔】`（仅限几何能稳定识别的孔 / 通孔 / 内孔类，不含螺纹规格）
- `【过渡特征】`（仅限几何可识别的圆角 / R 过渡）
- `【其他特征】` 中可稳定识别的槽 / 孔 / 凸台 / 台阶类结构摘要

### 4.2 Creo txt 补充字段

Creo txt 用于补充 / 增强：

- `【技术要求】`
- `【倒角】`
- `【过渡特征】` 中带明确标注值的项
- `【螺纹与螺孔】` 中：
  - 螺纹规格
  - 孔深
  - 攻丝说明
- `【外圆与内孔】` 中：
  - 公差
  - 配合等级
- `【关键尺寸】` 中：
  - 明确公差标注
  - 标注性尺寸补充

规则：
- 几何给主尺寸
- Creo 给标注细节

### 4.3 VLM 语义字段

主要由 VLM 输出：

- `【零件名称】`
- `【形态】`
- `【类型】`
- `【其他特征】` 中工艺语义描述部分

---

## 5. 冲突处理

### 情况 A：几何尺寸 vs Creo txt 数值冲突

- 主尺寸以几何为准
- 若 Creo txt 带公差 / 规格更完整，则作为补充文字保留
- 不允许 VLM 在冲突时决定谁对谁错

### 情况 B：几何无该字段，Creo txt 有

- 直接采用 Creo txt

### 情况 C：几何和 Creo 都没有，VLM 识别到了

- 仅限语义字段采用
- 尺寸字段不允许 VLM 凭图补主数值

### 情况 D：三者都没有

- 填 `"无"`

---

## 6. `vlm_feature.py` 设计改动

### 6.1 新增 `_extract_geometry_structured_fields(step_path: str) -> dict`

职责：
- 调用现有 `extract_geometry_features(step_path)` 或几何分析器
- 将输出映射为结构化字段字典，而不是自由文本

目标返回结构：

```python
{
  "关键尺寸": "...",
  "外圆与内孔": "...",
  "螺纹与螺孔": "...",
  "过渡特征": "...",
  "其他特征": "...",
}
```

说明：
- 如果现有 `extract_geometry_features()` 只能返回自由文本，则在本函数中增加解析层
- 若当前几何分析器不支持某字段，则返回空值，不用 VLM 补主尺寸

### 6.2 新增 `_extract_vlm_semantic_fields(...) -> dict`

替代当前“让 VLM 输出整张表”的模式，VLM 只返回语义字段：

```python
{
  "零件名称": "...",
  "形态": "...",
  "类型": "...",
  "其他特征": "...",
}
```

如需保留 `外圆与内孔` / `螺纹与螺孔` 的 VLM 输出，也只能作为补充候选，不得直接覆盖几何层。

### 6.3 新增 `_merge_geometry_creo_vlm_fields(...) -> str`

建议新增统一装配函数：

```python
def _merge_geometry_creo_vlm_fields(
    geometry_fields: dict,
    creo_txt_buckets: dict,
    vlm_semantic_fields: dict,
) -> str:
    ...
```

职责：
- 按字段优先级合并三层数据
- 输出 `【字段】值` 的结构化文本
- 图号仍由调用方追加

### 6.4 调整 `extract_creo_primary_features()`

现有逻辑：
- Creo 截图 + txt → VLM → `_assemble_prt_fields`

新逻辑：
- `geometry_fields = _extract_geometry_structured_fields(step_path)`
- `creo_txt_buckets = parse_creo_task_txt(txt_path)`
- `vlm_semantic = _extract_vlm_semantic_fields(creo_paths, prompt)`
- `return _merge_geometry_creo_vlm_fields(geometry_fields, creo_txt_buckets, vlm_semantic)`

### 6.5 调整 `extract_freecad_geo_constrained_features()` / `extract_vlm_features()`

- `freecad-geo`：几何层 + VLM 语义层
- `freecad`：若无 step/几何信息，则只输出语义字段 + 能从现有字段确定的最小结果

说明：
- 如果当前路由仍要求在 `freecad-geo` 下输出完整表，几何字段缺失项必须填 `"无"`
- 不允许退回到“让 VLM 补尺寸”

---

## 7. Prompt 调整

### 7.1 新 VLM prompt 只问语义字段

```text
以下图片是该零件的截图。请仅根据图片可见内容，按以下格式逐字段输出：

【零件名称】（根据外形推断，如无法判断填"无"）
【形态】（一句话描述整体几何形态）
【类型】（功能类别，如：轴套类-配合件）
【其他特征】（描述槽、凸台、台阶、布置关系等语义信息；如无填"无"）

要求：
- 只描述图片中明确可见的特征
- 不推测未标注的主尺寸数值
- 不输出关键尺寸、外圆内孔、孔径、公差等几何主字段
```

### 7.2 Creo prompt 仍可前置 txt 约束

creo-primary 路径下，`CREO_TASK.txt` 的技术要求和尺寸标注仍可放在 prompt 前面，但目的变为：
- 帮 VLM 更好理解零件用途和结构
- 不再要求 VLM 复述这些尺寸为主字段

---

## 8. 输出格式

最终仍输出统一 12 字段（保持前端兼容）：

```text
【零件名称】...
【形态】...
【类型】...
【技术要求】...
【关键尺寸】...
【外圆与内孔】...
【螺纹与螺孔】...
【倒角】...
【热处理与探伤】...
【过渡特征】...
【其他特征】...
【图号】...
```

说明：
- `【图号】` 仍由调用方追加
- 无值字段填 `"无"`
- 前端不需要改解析方式

---

## 9. 测试

### 单元测试（`backend/pipeline/test_vlm_feature.py`）

建议新增：

1. `test_extract_geometry_structured_fields_maps_known_geometry`
   - 几何分析输出可正确映射到结构化字段

2. `test_merge_geometry_priority_over_vlm`
   - 几何字段存在时，VLM 不得覆盖尺寸类字段

3. `test_creo_txt_supplements_tolerance_and_thread_spec`
   - 几何给主尺寸，Creo txt 补公差 / 孔深 / 螺纹规格

4. `test_vlm_only_fills_semantic_fields`
   - VLM 返回尺寸类字段时也应被丢弃或忽略

5. `test_missing_geometry_uses_creo_for_available_fields`
   - 几何缺失时，Creo txt 可填对应字段

6. `test_all_missing_fields_fall_back_to_wu`
   - 三层都缺失时，字段输出 `"无"`

### 集成测试

1. **Creo + STEP 都可用**
   - 审阅特征表中的尺寸类字段来自几何层
   - 公差 / 孔深 / 螺纹规格由 Creo txt 补足
   - 零件名称 / 形态 / 类型来自 VLM

2. **无 Creo txt，仅 STEP + 图像**
   - 尺寸字段仍来自几何
   - 技术要求 / 倒角等缺失则填 `"无"`

3. **无 STEP，仅 Creo**
   - 允许 Creo 填其可确定字段
   - 不允许 VLM 补主尺寸

---

## 10. 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/pipeline/vlm_feature.py` | 新增几何结构化提取、VLM 语义提取、三层合并逻辑 |
| `backend/prt_pipeline.py` 或相关 geometry analyzer | 如有必要，补充几何输出到结构化映射层 |
| `backend/feature_report.py` | 如字段归一化逻辑需兼容，做最小调整 |
| `backend/pipeline/test_vlm_feature.py` | 新增双源装配测试 |

---

## 11. 预期效果

实施后，系统行为从：

- **Before**：VLM 主导 + Creo txt 补少量字段

变为：

- **After**：几何硬数据主导 + Creo txt 补标注细节 + VLM 补语义字段

核心收益：

1. 关键尺寸不再由模型自由生成
2. 外形 / 内孔 / 孔类字段精度提高
3. Creo txt 的公差 / 孔深 / 螺纹规格得到保留
4. VLM 仍保留在零件名称、形态、类型上的价值
5. 前端审阅表保持不变，改动集中在后端装配层
