# LLM 上下文优化 — 实现计划

**对应设计**：`2026-06-09-llm-context-optimization-design.md`  
**分支**：2d  
**回退基点**：`af99e64`

---

## 任务一：VisionAnalyzer 双模并行调用

**文件**：`backend/pipeline/vision_analyzer.py`  
**依赖**：无，可独立上线

### 步骤

**1.1 新增两套精简提示词**

在文件顶部新增（替换现有 `_VISION_SYSTEM_PROMPT_V4` 的职责，旧提示保留以备回退）：

```python
_PROMPT_TEXT_EXTRACTION = """
你是专业机械工程图纸文字读取专家。逐页扫描所有图片，原样抄录以下字段（数字不得估算、不得舍入）：

【图号】仅填文件代号
【零件名称】标题栏中的名称
【材料】
【毛坯类型】锻件/铸件/棒料等；无则填"无"
【技术要求】原文，多条用分号分隔
【关键尺寸】所有尺寸标注（带公差保留公差），多条用分号分隔
【尺寸公差】未注公差说明 + 标注公差，多条用分号分隔
【形位公差】公差框格内容（类型+值+基准），多条用分号分隔
【螺纹规格】规格+数量+深度，多条用分号分隔
【表面粗糙度】Ra/Rz 值及未注说明
【倒角】所有倒角尺寸，多条用分号分隔
【线切割】有则填要求，无则填"无"
【热处理与探伤】硬度/热处理/探伤，多条用分号分隔

规则：
- ⚠ 小数精度：φ1.8 不得写成 φ18，原样保留
- 字段无内容填"无"，不得省略字段
- 不做任何推断，只抄图纸可见文字
""".strip()

_PROMPT_VISUAL_ANALYSIS = """
你是专业机械工程图纸视觉分析专家。请综合所有页面（不要只看第一页），判断以下视觉语义字段：

【外形尺寸】
综合主视图（长宽）+ 端视图/剖视图（厚）判断整体外轮廓包络：
- 非圆形：长×宽×厚（取每方向最大外轮廓，不取台阶尺寸）
- 圆形截面：Ø直径×总长
自检：尺寸线是否跨越整个零件？厚度是否来自端视图而非台阶高？

【物料形态】
从以下选一：板料 / 棒料（圆） / 棒料（方） / 铸件 / 锻件 / 其他
依据：≠ 符号=板料；φ×L 格式备料=圆棒；技术要求注明铸/锻件

【形态】一句话描述整体几何形态

【类型】功能类别（如：轴套类-配合件）

【吊面/翻面特征】
综合所有页面检查：
① 是否有仰视图且含加工特征（孔/槽）→ 存在
② 剖视图是否有开口朝下的腔槽
③ 技术要求是否含"翻面"/"背面加工"字样
④ 底面是否有粗糙度符号或虚线隐藏特征
存在任一 → 填"存在，[具体描述]"；完全不存在 → 填"无"

规则：字段无内容填"无"，不得省略字段
""".strip()
```

**1.2 新增并行调用方法**

在 `VisionAnalyzer` 类中新增：

```python
def _call_vlm(self, prompt: str, image_paths: list[str]) -> str:
    """单次 VLM 调用，返回原始文本响应。"""
    # 从现有 analyze_image() 提取调用逻辑，不重复

def analyze_images_parallel(
    self, image_paths: list[str], progress_callback=None
) -> dict:
    """
    两路并行调用，合并结果。
    返回与现有 analyze_images() 兼容的字段字典。
    """
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(self._call_vlm, _PROMPT_TEXT_EXTRACTION, image_paths)
        f2 = ex.submit(self._call_vlm, _PROMPT_VISUAL_ANALYSIS, image_paths)
        text_raw = f1.result()
        visual_raw = f2.result()
    # 解析两路输出，合并成现有字段格式
    return {**_parse_structured_fields(text_raw),
            **_parse_structured_fields(visual_raw)}
```

**1.3 切换调用点**

在 `analyze_images()` 内部将逐页串行改为调用 `analyze_images_parallel()`，  
或在调用侧（`upload_pipeline.py` / `upload.py`）切换入口。

**1.4 验证**

- 用 3 张不同类型图纸（轴类/板类/支架）对比新旧输出
- 重点检查：外形尺寸、吊面/翻面特征、公差字段
- 计时对比，确认并行后耗时缩短

---

## 任务二：ExpertJudge 修复（Step A）

**文件**：`backend/pipeline/expert_judge.py`  
**依赖**：无，可独立合并  
**注意**：Step A 合并后必须通过验证才能执行 Step B

### 步骤

**2.1 新增输出 schema**

```python
from pydantic import BaseModel

class ExpertJudgmentOutput(BaseModel):
    part_number: str          # 图号
    part_type: str            # 零件类型
    material: str             # 材料
    dimensions: str           # 外形尺寸
    surface_treatment: str    # 表面处理
    tolerances: str           # 公差等级
    heat_treatment: str       # 热处理要求
    special_requirements: str # 特殊要求
    confidence: float         # 0.0–1.0
```

**2.2 修改系统提示**

```python
_SYSTEM_PROMPT = """
你是资深机械工艺工程师。根据输入的图纸特征描述，提取结构化摘要。

输出格式（JSON，严格按字段顺序）：
{
  "part_number": "图号，无则填'未知'",
  "part_type": "零件类型，如'板类-安装板'",
  "material": "材料牌号，无则填'未知'",
  "dimensions": "外形尺寸，如'388×358×13'，无则填'未知'",
  "surface_treatment": "表面处理，无则填'无'",
  "tolerances": "关键公差等级，无则填'未知'",
  "heat_treatment": "热处理要求，无则填'无'",
  "special_requirements": "其他特殊要求，无则填'无'",
  "confidence": 0.85
}

要求：
- 每个字段必须输出，无法判断填'未知'而非省略
- confidence 为你对本次提取完整性的自评（0.0 最低，1.0 最高）
- 只输出 JSON，不输出其他文字
""".strip()
```

**2.3 修改 `analyze()` 方法**

使用 `response_format={"type": "json_object"}` 或直接解析 JSON，返回 `ExpertJudgmentOutput` 实例。保留字符串版本 `analyze_as_str()` 供回退期间兼容使用。

**2.4 人工验证（Step A → Step B 的门控）**

用以下 5 类图纸各 1 张运行新 ExpertJudge，检查输出：
- [ ] 轴类零件
- [ ] 板类零件  
- [ ] 支架类零件
- [ ] 带孔板零件
- [ ] 复杂件（多特征）

每张确认：外形尺寸、材料、公差、热处理、特殊要求字段均不为 `"未知"` 且与图纸一致。5 张全部通过后执行任务三。

---

## 任务三：ProcessGenerator 精简 + RAG 自适应（Step B，门控）

**文件**：`backend/pipeline/process_gen.py`  
**依赖**：任务二验证通过后才能执行

### 步骤

**3.1 移除 `fused_description` 入参**

```python
# 修改前
def generate(self, descriptions, expert_judgment, fused_description,
             rag_context, constraints):

# 修改后
def generate(self, expert_judgment: ExpertJudgmentOutput,
             rag_context: str, constraints: dict):
```

同步修改所有调用点（`upload_pipeline.py`），移除 `fused_description=...` 传参。

**3.2 RAG 自适应 k 值**

在 RAG 检索调用前插入：

```python
confidence = expert_judgment.confidence
if confidence >= 0.8:
    rag_k = 1
elif confidence >= 0.5:
    rag_k = 2
else:
    rag_k = 3
```

将 `rag_k` 传入现有的 RAG 检索函数（替换原有固定 k 值）。

**3.3 ContextHarness token 槽位**

在 `_build_controlled_prompt()` 内部新增槽位预算检查：

```python
SLOT_BUDGETS = {
    "system":      500,   # 不裁剪
    "task":        800,   # expert_judgment 序列化文本
    "knowledge":  2000,   # rag_context
    "constraints": 300,
}

def _truncate_to_budget(text: str, max_tokens: int) -> str:
    # 简单估算：4字符≈1token
    limit = max_tokens * 4
    return text[:limit] if len(text) > limit else text
```

**3.4 验证**

端到端跑 3 张图纸，对比移除 `fused_description` 前后的工艺生成结果，确认关键工序无遗漏。

---

## 执行顺序总结

```
任务一（VisionAnalyzer）  ──────────────────► 验证 ► 合并
任务二 Step A（ExpertJudge）─────────────► 验证 ─┐
                                                  ├─► 任务三（绑定合并）
                                                  └─ 5张样本门控
```

任务一和任务二 Step A 可以并行开发，均不依赖对方。

---

## 回退方式

```bash
# 回退单个文件
git checkout af99e64 -- backend/pipeline/vision_analyzer.py
git checkout af99e64 -- backend/pipeline/expert_judge.py
git checkout af99e64 -- backend/pipeline/process_gen.py

# 全部回退
git reset --hard af99e64
```
