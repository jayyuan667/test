# PDF 特征报告字段体系重构 · 设计文档

**日期：** 2026-05-27
**范围：** VLM 提示词 → 后端解析 → 前端审阅 → 下游工序生成，全链路 PDF 侧重构
**分支：** `2d-version`

---

## 一、目标

1. 将 VLM 特征提取从扁平 20 字段升级为**工种导向的五段式结构化报告**
2. 修复审计文档（2026-05-26）中 PDF 链路及共用层的 7 个 bug（P0-P3）
3. 消除 `upload.py` 与 `feature_report.py` 之间的重复代码
4. 前端审阅页从扁平表格改为**分段卡片布局**，突出不确定项
5. 保持 v4 完整回退能力

---

## 二、VLM 提示词 v5

### 改动文件

`backend/pipeline/vision_analyzer.py`

### 结构

从 20 个扁平 `【字段】` 改为 **六段工种导向分组**：

```
你是机械工艺工程师，请分析这张图纸，按以下六段输出。

【格式约束】
- 各段之间用 ━━━ 分隔
- 字段用 【字段】值 格式（保持兼容现有解析器）
- 不存在的内容填"无"
- 数值保留原图纸公差和单位

━━━ 一、基本信息 ━━━
【图号】xxx
【零件名称】xxx
【毛坯类型】锻件/铸件/棒料/板材
【外形尺寸】长×宽×厚（板类）或 φ直径×L（回转体）
【材料牌号】xxx
【技术要求】原文逐条提取，用分号分隔

━━━ 二、回转特征（车削相关）━━━
【外圆台阶】...
【内孔】...
【外螺纹】...
【内螺纹】...
【端面】...
【倒角】...

━━━ 三、平面特征（铣削/钻孔相关）━━━
▸ 正面
  【孔】...
  【铣削】...
  【槽/台阶】...
▸ 背面 ...
▸ 顶面 / 侧面 / 底面（如有）

━━━ 四、热处理与表面 ━━━
【热处理】...
【表面处理】...
【探伤】...

━━━ 五、精度汇总 ━━━
【未注公差】...
【形位公差】...
【粗糙度】...
【特殊工艺】...

━━━ 六、不确定项 ━━━
[经验值] ...
[需确认] ...
[数量存疑] ...
```

### 字段合并/废弃

| 旧字段 | 新位置 |
|--------|--------|
| `弧段与齿形` | 归入【铣削】或【外圆台阶】 |
| `端面与平面` | 归入【端面】和平面特征各面的【铣削】 |
| `线切割` | 归入【特殊工艺】 |
| `标识与检验` | 归入【特殊工艺】 |
| `过渡特征` | 归入【倒角】或各面的【铣削】 |
| `其他特征` | 废弃，归入对应工种段 |
| `关键尺寸` | 废弃，拆分到各工种的尺寸字段 |

旧字段 `螺纹与螺孔` 拆分为 `外螺纹` / `内螺纹`（分别对应车削和钻孔攻丝）。

### 回退

环境变量 `VISION_PROMPT_VERSION=v4` 切回旧版。v4 完整保留为 `_VISION_SYSTEM_PROMPT_V4`。

---

## 三、后端解析层

### 3.1 提示词加载

`vision_analyzer.py` `_get_vision_system_prompt()`:
- 默认返回 v5 (`_VISION_SYSTEM_PROMPT_V5`)
- `VISION_PROMPT_VERSION=v4` 返回旧版
- `VISION_PROMPT_VERSION=legacy` 返回最旧版

### 3.2 报告构建

`feature_report.py` `build_feature_report()`:
- 新增分段感知解析：识别 `━━━ 第N段 标题 ━━━` 作为段边界
- JSON 输出增加 `sections` 结构：

```python
{
  "report_text": "完整报告文本（兼容旧格式）",
  "sections": [
    {"title": "一、基本信息", "fields": [("图号", "xxx"), ...]},
    {"title": "二、回转特征", "fields": [...]},
    {"title": "三、平面特征", "sub_sections": [
      {"face": "正面", "fields": [...]},
      {"face": "背面", "fields": [...]}
    ]},
    ...
  ],
  "uncertain_items": [
    {"type": "经验值", "item": "M52×1.5", "reason": "螺距未标注"}
  ]
}
```

- `REPORT_FIELD_ORDER` 更新为新字段顺序，`FEATURE_SYNONYMS` 补充新别名
- `report_text` 保持纯 `【字段】值` 格式，不含段标题（向下游兼容）

### 3.3 向下游透传

- **ExpertJudge**：不改动，继续接收 `descriptions` 列表中的 `report_text`
- **ProcessGenerator**：新增可选读取 `sections`，按工种段直接映射工种 → 工序模板
- **KB import**：`_normalize_drawing_text` 同时识别 v4/v5 两种格式

### 3.4 消除重复代码（P3）

`upload.py` 中的 `REPORT_FIELD_ORDER`、`FEATURE_SYNONYMS`、`_normalize_feature_label`、`_cleanup_feature_text`、`_extract_inline_feature_pairs` 删除本地副本，改为：
```python
from ..feature_report import (
    REPORT_FIELD_ORDER,
    FEATURE_SYNONYMS,
    normalize_feature_label,
    cleanup_feature_text,
    extract_feature_pairs,
)
```

`_build_feature_review_report` 改为调用 `feature_report.build_feature_report`。

---

## 四、前端审阅页

### 4.1 布局改造

`#reviewTableHost` 从单表格改为 **section-card 堆叠**。

每个段卡片结构：
```html
<div class="section-card">
  <div class="section-card-header">
    <span class="section-title">📐 一、基本信息</span>
    <button class="collapse-toggle">折叠</button>
  </div>
  <div class="section-card-body">
    <table class="step-table review-table">
      ...
    </table>
  </div>
</div>
```

不确定项段 `.section-card.uncertain` 高亮（橙色左边框），始终展开。

### 4.2 新增/改动函数

| 函数 | 类型 | 职责 |
|------|------|------|
| `parseReviewSections(text)` | 新增 | 解析文本 → `[{title, fields}, ...]`。识别 `━━━` 段标题 + `【字段】值`。无段标题时所有字段归入一个默认段 |
| `renderSectionCard(section, i)` | 新增 | 渲染单个段卡片 |
| `renderReviewTable(payload)` | 改动 | 内部调用 `parseReviewSections`，用 `.section-card` 替代 `<table>` 直接注入 |
| `readReviewTable()` | 改动 | 遍历 `.section-card` 内所有 `[data-review-*]` 属性，与现在完全兼容 |
| `serializeReviewFields(fields)` | 不变 | 输出纯 `【字段】值`，不含段标题 |
| `parseReviewFields(text)` | 不变 | 纯 `【字段】值` 解析，忽略 `━━━` 行 |

### 4.3 提交逻辑

用户确认时，前端从 section cards 收集所有字段 → `serializeReviewFields` → 纯 `【字段】值` 文本 → POST `/review/<task_id>`。

段标题**不进入提交文本**，后端收到的仍是纯字段流，ExpertJudge / ProcessGenerator 无需改动。

### 4.4 兼容性

- 旧格式（无段标题）→ `parseReviewSections` 生成一个默认段 → 渲染效果 = 当前扁平表格
- 新格式（有段标题）→ 自动分段展示
- 前端不需知道后端版本

### 4.5 CSS 新增

- `.section-card` — 容器（`border`, `border-radius`, `margin-bottom`）
- `.section-card-header` — 标题栏（`background`, 折叠图标）
- `.section-card-body` — 字段表容器
- `.section-card.uncertain` — 橙色左边框 + 浅黄背景
- `.face-subsection` — 平面特征的子面标签

---

## 五、Bug 修复（7 项）

| # | 问题 | 优先级 | 文件 | 方案 |
|---|------|--------|------|------|
| 1 | `_resume_from_review` 未定义崩溃 | P0 | `upload.py` | 实现该函数，从 pending.json 恢复任务状态，调用 `_finalize_processing` |
| 2 | 蓝本阈值代码 0.7 vs 提示词 0.8 | P1 | `expert_judge.py` | 改 `0.7` → `0.8` |
| 3 | PDF `geo_data` 始终为空 | P2 | `upload.py` `upload_drawing` | 从 v5 的 `外形尺寸` 和 `毛坯类型` 构造简化几何约束（`{"bounds": [L,W,H], "type": "plate"|"shaft"}`） |
| 4 | ExpertJudge 英文提示词 | P2 | `expert_judge.py` | system prompt 改为中文 |
| 5 | upload.py 重复定义 feature_report 函数 | P3 | `upload.py` | 改为 import（见三.4） |
| 6 | `_parse_pdf_document` 缺 import | P3 | `kb_import.py` | 补充 `from ..pipeline.pdf_converter import convert_pdf_to_images`（或移除死代码） |
| 7 | `外形尺寸` 字段缺失 | P0 | 多处 | v5 prompt + 更新 REPORT_FIELD_ORDER（见三.2） |

---

## 六、迁移与兼容

### 回退

- 环境变量 `VISION_PROMPT_VERSION=v4` 切回旧版提示词
- v4 代码完整保留，不做任何改动
- v5 提示词输出中的段标题（`━━━` 行）不进入下游数据流

### 存量数据

- KB 中已入库的 v4 格式记录不受影响
- `_normalize_drawing_text` 同时处理新旧格式
- 前端同时渲染新旧格式

### 变更文件

| 文件 | 改动类型 |
|------|---------|
| `backend/pipeline/vision_analyzer.py` | 新增 v5 prompt |
| `backend/feature_report.py` | 分段解析 + 更新字段顺序 + 新增 sections 输出 |
| `backend/api/upload.py` | 消除重复代码 + PDF geo_data + `_resume_from_review` |
| `backend/pipeline/expert_judge.py` | 阈值 0.7→0.8 + 中文 prompt |
| `backend/api/kb_import.py` | 补 import |
| `updated_front/js/demo-industrial-console.js` | 分段卡片渲染 |
| `updated_front/css/industrial-console.css` | 新增 section-card 样式 |
