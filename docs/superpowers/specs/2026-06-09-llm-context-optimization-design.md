# LLM 上下文优化设计

**日期**：2026-06-09  
**分支**：2d  
**影响模块**：`vision_analyzer.py` / `expert_judge.py` / `process_gen.py`

---

## 背景与目标

当前三个 LLM 组件存在上下文冗余，导致成本偏高、速度偏慢、输出一致性不足：

| 组件 | 问题 |
|------|------|
| `VisionAnalyzer` | 一个 2000+ token 大提示逐页串行调用，既读文字又做视觉推理，互相干扰 |
| `ExpertJudge` | 英文系统提示 + 无结构输出，下游不敢信任，ProcessGenerator 靠 `fused_description` 兜底 |
| `ProcessGenerator` | 同时接收 `fused_description`（原始）和 `expert_judgment`（压缩），信息重复传入 |

目标：**精度不降、速度提升、成本降低**。

---

## 方案：渐进式双模调用 + ExpertJudge 压缩层修复

### 变更一：VisionAnalyzer 拆分为两次并行调用

**原理**：读文字和视觉推理是两种认知模式，混在一个大提示里模型注意力分散。拆开后每次调用焦点清晰，并行执行不增加延迟。

**Call 1 — 文字读取**

- 输入：所有页面图片
- 提示：~400 token，纯文字提取模式
- 负责字段：
  - 图号、零件名称、材料、毛坯类型
  - 技术要求（原文条目）
  - 关键尺寸标注（数字原样抄录）
  - 公差（尺寸公差、形位公差框格数值）
  - 螺纹规格、表面粗糙度
  - 倒角、刻字、线切割要求

**Call 2 — 视觉分析**

- 输入：所有页面图片（保留跨页空间上下文，防止厚度视图、仰视图遗漏）
- 提示：~400 token，视觉推理模式，明确注明「请综合所有页面判断」
- 负责字段：
  - 外形尺寸（轮廓判断：哪条尺寸线是最外轮廓）
  - 物料形态（≠ 符号识别 + 图形形状综合判断）
  - 形态（几何形态一句话描述）
  - 类型（功能类别）
  - 吊面/翻面特征（仰视图存在性 + 底面特征判断）

**执行方式**：`ThreadPoolExecutor` 并行，两路结果合并成现有字段格式，下游零改动。

**为什么 Call 2 也发所有页面**：外形尺寸需要主视图（长宽）+ 端视图（厚），两个视图可能在不同页；吊面判断依赖仰视图，多在第 2 页。只发第 1 页会导致这两个字段失准。

**预期效果**：

| 指标 | 现在 | 优化后 |
|------|------|--------|
| 调用次数（5页PDF） | 5 次串行 | 2 次并行 |
| 提示 token（5页） | 2000×5 = 10,000 | 400×2 = 800 |
| 总输入 token | ~35,000 | ~10,800 |
| VLM 耗时 | ~25–40 秒 | ~8–12 秒 |

---

### 变更二：ExpertJudge 改为可信压缩层（原子变更）

**两步必须绑定，不能拆开执行：**

**Step A：修复 ExpertJudge 输出**

系统提示改为中文，移除英文混用。新增结构化输出 schema：

```python
class ExpertJudgmentOutput(BaseModel):
    part_number: str          # 图号
    part_type: str            # 零件类型
    material: str             # 材料
    dimensions: str           # 外形尺寸字符串
    surface_treatment: str    # 表面处理
    tolerances: str           # 公差等级
    heat_treatment: str       # 热处理要求
    special_requirements: str # 特殊要求
    confidence: float         # 0.0–1.0，模型自评覆盖置信度
```

每个字段必填，无法判断时填 `"未知"`，不允许省略。

**Step B：验证通过后移除 ProcessGenerator 中的 fused_description**

验证标准：用 5 张不同类型样本图纸（轴类/板类/支架/带孔板/复杂件），对比 ExpertJudge 输出与原始 `fused_description`，确认以下字段无遗漏：外形尺寸、材料、公差等级、热处理、特殊要求。验证通过后再合并 Step B。

---

### 变更三：ProcessGenerator 入参精简 + RAG 自适应

**入参变更**（Step B 合并后生效）：

```python
# 移除
- fused_description: str

# 保留
+ expert_judgment: ExpertJudgmentOutput  # 改为结构化类型
+ rag_context: str
+ constraints: dict
```

**RAG 候选自适应**（根据 ExpertJudge 的 confidence 字段）：

```python
if confidence >= 0.8:
    k = 1   # 高置信，精确匹配，取最相关 1 条
elif confidence >= 0.5:
    k = 2   # 中等置信，补充 1 条候补
else:
    k = 3   # 低置信，扩大召回
```

**ContextHarness（ProcessGenerator 内部）**：

按槽位打包 prompt，超出预算按优先级裁剪：

| 槽位 | 预算 | 优先级 |
|------|------|--------|
| 系统提示 | 500 token | 最高（不裁剪）|
| 任务描述（expert_judgment） | 800 token | 高 |
| 知识（rag_context） | 2000 token | 中 |
| 约束（constraints） | 300 token | 低 |

---

## 实现顺序

```
1. VisionAnalyzer 拆分（独立，无依赖）
   └─ 拆分提示词 + 并行调用 + 合并逻辑
   └─ 用现有测试图纸对比新旧输出字段覆盖率

2. ExpertJudge Step A（独立）
   └─ 中文提示 + 结构化输出 schema

3. 验证 ExpertJudge 覆盖率（5张样本）

4. ExpertJudge Step B + ProcessGenerator 精简（绑定）
   └─ 移除 fused_description
   └─ RAG 自适应 k 值
   └─ ContextHarness token 槽位

5. 集成测试（端到端跑 3 张图纸，对比生成结果）
```

---

## 风险与回退

- 所有变更均在独立文件内，`git checkout af99e64 -- <file>` 可单文件回退
- 变更二的两步绑定确保不会出现"ExpertJudge 未修好就移除 fused_description 兜底"的状态
- VisionAnalyzer 变更不影响任何下游接口，可独立上线验证

---

## 不在本次范围

- Agent 调度框架（LangGraph 等）：留待有具体扩展需求时再引入
- PRT 路径的 `vlm_feature.py`：PRT 路径使用不同提示，独立优化
- OCR 作为一级校验：当前 OCR 精度不足以作为主力，保留为可选辅助
