# VLM 工程图读取提示词优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 改写 `_VLM_ENGINEERING_DRAWING_PROMPT` 中 `【外形尺寸】` 和 `【尺寸公差】【形位公差】` 两个字段的指令，使 VLM 能正确跨视图合并外形尺寸并减少公差漏读。

**Architecture:** 仅修改 `backend/pipeline/vlm_feature.py` 中的提示词常量字符串，不改任何函数逻辑。先写失败测试，再改提示词，确认测试全部通过后提交。

**Tech Stack:** Python 3, pytest, `backend/pipeline/vlm_feature.py`, `backend/pipeline/test_vlm_feature.py`

**Spec:** `docs/superpowers/specs/2026-05-21-vlm-engineering-drawing-prompt-design.md`

---

## 文件清单

| 文件 | 操作 |
|---|---|
| `backend/pipeline/vlm_feature.py` | Modify: 改写 `_VLM_ENGINEERING_DRAWING_PROMPT`（第 59–84 行）中 `【外形尺寸】` 和 `【尺寸公差】【形位公差】` 的指令文本 |
| `backend/pipeline/test_vlm_feature.py` | Modify: 在 `test_extract_creo_primary_features_builds_structured_prompt` 末尾追加两个新断言，验证新提示词内容 |

---

## Task 1: 为新提示词内容写失败测试

**Files:**
- Modify: `backend/pipeline/test_vlm_feature.py`（函数 `test_extract_creo_primary_features_builds_structured_prompt`，约第 332–377 行）

- [ ] **Step 1: 在现有测试函数末尾追加新断言**

找到 `test_extract_creo_primary_features_builds_structured_prompt` 函数（约第 332 行），在最后一个 `assert` 之后追加：

```python
    # 新提示词：外形尺寸应包含三步推理引导
    assert "第一步" in captured["prompt"], "外形尺寸三步推理缺失"
    assert "视图类型" in captured["prompt"], "视图类型映射指令缺失"
    # 新提示词：公差字段应包含显式扫描清单
    assert "公差符号" in captured["prompt"], "尺寸公差扫描清单缺失"
    assert "公差框格" in captured["prompt"], "形位公差框格扫描指令缺失"
```

- [ ] **Step 2: 运行测试确认新断言失败**

```
cd F:\Work_Dir\new_3dversion\my_working
python -m pytest backend/pipeline/test_vlm_feature.py::test_extract_creo_primary_features_builds_structured_prompt -v
```

预期输出：`FAILED` — `AssertionError: 外形尺寸三步推理缺失`（当前提示词不含"第一步"）

---

## Task 2: 改写 `_VLM_ENGINEERING_DRAWING_PROMPT`

**Files:**
- Modify: `backend/pipeline/vlm_feature.py`（第 59–84 行）

- [ ] **Step 1: 找到提示词常量**

打开 `backend/pipeline/vlm_feature.py`，定位 `_VLM_ENGINEERING_DRAWING_PROMPT = """` 的位置（约第 59 行）。

- [ ] **Step 2: 用新版本替换提示词**

将 `_VLM_ENGINEERING_DRAWING_PROMPT` 替换为以下内容（保持首尾 `"""` 和 `.strip()` 不变）：

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

- [ ] **Step 3: 运行 Task 1 中的测试，确认新断言现在通过**

```
python -m pytest backend/pipeline/test_vlm_feature.py::test_extract_creo_primary_features_builds_structured_prompt -v
```

预期输出：`PASSED`

---

## Task 3: 运行全量测试并提交

**Files:**
- 无新增文件

- [ ] **Step 1: 运行全量测试**

```
python -m pytest backend/pipeline/test_vlm_feature.py -v
```

预期输出：所有测试 `PASSED`，零 `FAILED`。

> 注意：`test_extract_creo_primary_features_builds_structured_prompt` 中原有的 `assert "逐张扫描" in captured["prompt"]` 仍应通过，因为改后提示词首行保留了"请先逐张扫描图片中的数字标注和文字标注"。

- [ ] **Step 2: 如有失败，对照失败信息定位原因**

常见原因及处理：
- `"逐张扫描" not in captured["prompt"]`：检查改后提示词第一行是否保留原句"请先逐张扫描图片中的数字标注和文字标注，再按字段输出"。
- `"第一步" not in captured["prompt"]`：检查 `_VLM_ENGINEERING_DRAWING_PROMPT` 是否已按 Task 2 Step 2 更新。

- [ ] **Step 3: 提交**

```
git add backend/pipeline/vlm_feature.py backend/pipeline/test_vlm_feature.py
git commit -m "feat: improve VLM engineering drawing prompt for multi-view dim synthesis and tolerance scan"
```
