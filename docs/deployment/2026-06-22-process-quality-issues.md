# 工艺生成质量问题分析报告

**时间：** 2026-06-22（追加：2026-06-22 ZIP 入库工艺提取问题）
**状态：** 分析完成，待实施

---

## 问题 1：工序被拆分，拆分后无工种

### 现象
LLM 生成的一条工序被拆成多条，且拆分出的子条目没有工种标记。

### 根因

**文件：** `backend/pipeline/process_gen.py`

**A. LLM 输出了子条目格式（工步 1/工步 2），但解析时被当作独立工序**

`_coalesce_process_lines()`（line 147）负责合并工步子条目到父工序。它以"\n"或"；"分隔，但 LLM 有时输出：

```
- 0050: 数控铣，铣削正面；钻攻正面4×M6深10
  工步1: 铣削正面特征         ← 没有工种，被当作独立行
  工步2: 钻攻4×M6深10          ← 没有工种，被当作独立行
```

这种「工序内容在多行，每行都是工步子项」的格式，`_coalesce_process_lines()` 可能未正确合并，导致子工步变成无工种的独立工序。

**B. 蓝本精确匹配路径未走 LLM，但 `_normalize_standard_process_rows()` 未正确推断工种**

`_normalize_standard_process_rows()`（line 188）处理三种格式：
- `0010@工序内容` → 无工种，需要后推断
- `0010@工种@工序内容` → 有工种
- `0010: 工序内容` → 无工种

当蓝本存储的是老格式（两段式 `0010@工序内容`）且工序内容是"铣削正面；钻攻正面4×M6深10"这种多工步内容时，归一化后可能被 `_TRADE_KEYWORDS` 推断为单一工种，失去子工步的工种区分。

**修改点：**
1. `_coalesce_process_lines()` 增强：识别「工步 N:」格式的子条目，合并到上一道有工种的工序
2. `_normalize_standard_process_rows()` 增强：对多工步内容的行，保留或推断每个工步的工种

---

## 问题 2：部分输出没有工序（空工艺）

### 现象
LLM 生成结果中没有任何工序行（process_list 为空）。

### 根因

**A. RAG 检索到低质量结果，LLM 被误导**

`_run_rag_lookup()`（line 409）使用 `min_similarity=0.20`（line 437）。0.20 的相似度意味着检索结果几乎不相关，但这些不相关的内容仍然会出现在 prompt 的 `rag_context` 中，导致 LLM 被误导生成空输出。

**B. 私有库不足时，公共库兜底也无用**

`best_sim < 0.25` 时（line 458），补充公共库检索。但公共库里如果没有同类型零件，仍然返回低质量结果。

**C. 最近邻兜底无阈值**

`_nearest_neighbor_fallback()` 使用 `min_similarity=0.0`，即无论如何都会返回一个"最近邻"。这个近邻可能完全不相关，却仍被注入 prompt 作为参考。

**修改点：**
1. 提高 `min_similarity` 从 `0.20` → `0.40`
2. 当最佳相似度 `< 0.40` 时，**不注入 RAG 上下文**，让 LLM 基于特征自主生成
3. `_nearest_neighbor_fallback()` 的 `min_similarity` 从 `0.0` → `0.30`

---

## 问题 3：低相似度 RAG 参考造成不合理输出

### 现象
参考了不合适的蓝本工艺，生成的工序与当前零件特征不符（如步数不对、尺寸用错）。

### 根因

**A. `_should_use_blueprint_as_base()` 阈值偏低**

`_should_use_blueprint_as_base()`（line 1244）判定：精确图号匹配 + 相似度 >= 0.70 → 蓝本作为主框架。

0.70 仍然允许相似度不够高的蓝本作为框架。对于不同材料形态/热处理要求的零件，即使图号前缀相同，工序结构也可能完全不同。

**B. 低相似度时不加任何阈值保护**

`safe_similarity` 逻辑只在 `use_blueprint` 路径下生效（`allowed_fragments` 提取）。当 `use_blueprint=False` 但 `rag_context` 仍然包含多个低相似度候选时，LLM 仍会参考它们。

**C. 特征审阅显示值异常（"388-0.1×376±0.1×170±0.1 mm（长×宽×13"）**

这个问题的根因不在 process_gen，而在上游的 VLM 特征提取（`backend/pipeline/` 中的 vision/VLM 输出解析）。特征审阅页面显示的是 VLM 从图纸图片中提取的原始文本，后处理可能未清理截断的文本（"（长×宽×13" 明显被截断了）。

但这个特征异常**直接影响工艺生成质量**：如果特征输入就错了（尺寸截断、缺失），LLM 生成的工艺必定不合理——Garbage In, Garbage Out。

**修改点：**
1. 相似度 < 0.50 时，在 prompt 中**完全移除 RAG 候选列表**（`candidates_info`），只保留结构维度提示
2. 相似度 < 0.40 时，`rag_context` 也不注入，进入纯自主生成模式
3. 特征审阅的尺寸格式化：在 `_fuse_descriptions()` 中对提取的特征文本做完整性检查/截断修复

---

## 架构影响评估

```
受影响文件：
  backend/pipeline/process_gen.py     ← 主要修改
  backend/vector_map_rag.py           ← 相似度阈值调整（可选）

不受影响：
  frontend/                           ← 不涉及
  backend/api/                        ← API 层不涉及
  backend/pipeline/process_spec_analyzer.py  ← 不涉及
  database                            ← 不改 schema
```

**不涉及架构迁移：** 所有修改只在 `process_gen.py` 的阈值和条件判断上，不改变：
- API 接口
- 数据库结构
- 前端展示
- SSE 流式输出
- 文件存储结构

---

## 修改实施方案

### 修改 1：提高 RAG 相似度阈值（`process_gen.py`）

| 位置 | 当前值 | 改为 | 效果 |
|------|--------|------|------|
| line 437: `_run_rag_lookup()` min_similarity | `0.20` | `0.40` | 滤掉低质量检索结果 |
| line 458: 私有库补充公共库阈值 | `< 0.25` | `< 0.40` | 私有库不够时也更审慎 |
| line 529: `_nearest_neighbor_fallback()` min_similarity | `0.0` | `0.30` | 最近邻也要有最低门槛 |

### 修改 2：低相似度时放弃 RAG 上下文（`process_gen.py`）

在 `generate()` 的 step 2 之前（line 261 附近）增加判断：

```python
# 新增：判断 RAG 质量是否足够
best_rag_similarity = rag_results["matches"][0].get("similarity", 0) if rag_results and rag_results.get("matches") else 0

RAG_MIN_SIMILARITY = 0.40  # 低于此值不注入 RAG 上下文

if best_rag_similarity < RAG_MIN_SIMILARITY:
    # 放弃 RAG，纯 LLM 自主生成
    rag_context = ""
    rag_results = None
    use_rag_only = False
    if log_callback:
        log_callback(f"⚠️ 最佳 RAG 相似度 {best_rag_similarity:.1%} < {RAG_MIN_SIMILARITY:.0%}，放弃历史参考，基于特征自主生成")
```

### 修改 3：`_coalesce_process_lines()` 增强

在 line 147 附近，增加对「工步 N:」模式的处理：

```python
# 增强：识别工步子条目格式并合并到父工序
if re.match(r'^\s*工步\s*\d+\s*[:：]', stripped):
    # 这是工步子条目，合并到上一道工序
    if merged_lines:
        merged_lines[-1] = merged_lines[-1] + "；" + stripped
    continue
```

### 修改 4：特征审阅文本截断修复

在 `_fuse_descriptions()` 中检查特征文本完整性，对明显截断的「（长×宽×N」（N 为数字但无单位和闭合括号）做修复标记。

---

## 追加：ZIP 入库工艺提取问题

### 问题 4：入库提取的工艺工序缺工种、格式异常

### 现象
ZIP 入库后，从工艺规程 PDF 提取的工序行出现：
- 部分工序缺少工种（`NNNN@@工序内容` 格式，中间段为空）
- 工序内容被错误拆分
- 入库后知识库中存储的工艺格式不规范

### 根因

**涉及文件：** `backend/pipeline/process_spec_analyzer.py`、`backend/api/kb_import.py`、`backend/api/library.py`

#### A. LLM 提取 Prompt 对工种约束不够严格

`PROCESS_SPEC_PROMPT`（line 25-98）中说了「工序名称（工种）」，但没有明确强制规则：每行必须输出工种，不得留空。当 PDF 中某行的工序名称列为空时，LLM 按 prompt 输出 `NNNN@@工序内容`，导致工种缺失。

#### B. `_parse_process_rows()` 的回退路径不处理工种

`_parse_process_rows()`（line 195）有两套解析逻辑：
- **主路径**（JSON 解析）：按 `(\d{4})@([^@]*)@(.+)` 提取三段式，工种可能为空
- **回退路径**（line-by-line regex）：仅匹配 `(\d{4})\s*[@:：\-\|\s]\s*(.+)` —— **完全不提取工种**，trade 始终设为 `''`

当 LLM 输出的 JSON 解析失败时（格式不规范、JSON 残缺等），回退路径会把所有行变成**无工种**的两段式格式。

#### C. 入库链路无工种检查/补全

`_parse_pdf_process()` → `merge_multipage_rows()` → `_build_record_from_prefix()` → `_build_draft()` → `_upsert_record()` 整个链路中：

```
PDF 图片 → LLM 提取 → 解析 → 合并 → 入库
                                ↑
                        这里没有工种校验
```

没有一步会检查「这个工序行有没有工种」，也没试过从工序内容推断工种。

对比：**process_gen.py 蓝本路径**有 `_TRADE_KEYWORDS`（line 271），能从内容关键词推断工种。但入库链路完全没有这个逻辑。

#### D. process_gen 使用蓝本时的工种推断不完整

当入库的蓝本工艺被 process_gen 检索到时（`_normalize_standard_process_rows()` line 188），如果蓝本行是两段式（无工种），归一化输出就是 `["0010", "工序内容"]` ——仍然没有工种。后续 `_TRADE_KEYWORDS` 只在蓝本精确匹配路径（line 271）做推断，不是所有路径都覆盖。

### 修改方案

### 修改 5：PROCESS_SPEC_PROMPT 加强工种要求（`process_spec_analyzer.py`）

在 prompt 中追加强制规则：

```
- **工种强制规则**：每一道工序的工种字段（第 3 列）不可为空。
  若表格中该列留空，必须根据工序内容合理推断工种并填入，不可输出空工种（NNNN@@格式）。
  常见推断规则：
  - 备料/下料 → 工种填"料"
  - 铣/铣方/铣外形/铣六面 → 工种填"铣"
  - 数控铣/加工中心/CNC → 工种填"数铣"
  - 车/粗车/精车 → 工种填"车"
  - 钻/钻孔 → 工种填"钻"
  - 钳/去毛刺/攻丝/清洗/试装 → 工种填"钳"
  - 镀覆/外协镀 → 工种填"镀覆"
  - 阳极化/氧化/喷漆 → 工种填"表处"
  - 检验/标识/入库 → 工种填"检"
```

### 修改 6：`_parse_process_rows()` 回退路径增加工种推断

在 `process_spec_analyzer.py:195` 的 fallback 路径中，对提取出的内容做关键词推断：

```python
# 回退路径：简化的工种推断
_TRADE_KEYWORDS_FALLBACK = [
    ("料", ["备料", "下料", "毛坯"]),
    ("铣", ["铣方", "铣外形", "铣六面", "铣"]),
    ("数铣", ["数控铣", "CNC", "加工中心"]),
    ("车", ["车削", "车端面", "粗车", "精车"]),
    ("钻", ["钻孔", "钻"]),
    ("钳", ["去毛刺", "清洗", "试装", "钳", "攻丝"]),
    ("镀覆", ["镀覆", "外协镀"]),
    ("表处", ["阳极化", "电镀", "喷漆", "氧化"]),
    ("检", ["检验", "标识", "入库", "检"]),
]

def _infer_trade_from_content(content: str) -> str:
    for trade, keywords in _TRADE_KEYWORDS_FALLBACK:
        for kw in keywords:
            if kw in content:
                return trade
    return ""
```

### 修改 7：入库链路增加工种校验（`kb_import.py`）

在 `_build_record_from_prefix()` 或 `_parse_pdf_process()` 之后，`_upsert_record()` 之前，增加一步：

```python
def _ensure_trade_on_rows(rows: List[str]) -> List[str]:
    """确保每个工序行都有工种。缺失时从内容推断。"""
    fixed = []
    for row in rows:
        if "@@" in row or row.count("@") < 2:
            # 推断工种
            parts = row.split("@", 2)
            code = parts[0]
            content = parts[-1]
            trade = _infer_trade_from_content(content)
            fixed.append(f"{code}@{trade}@{content}" if trade else row)
        else:
            fixed.append(row)
    return fixed
```

### 修改 8：`_extract_trades_from_rows()` 放宽工种匹配（`library.py:325`）

当前正则 `^[一-鿿\-]{1,6}$` 只允许纯中文+连字符。应允许数字（如"数铣"不会被误拦，但"铣3"之类的可能被拦）：

```python
# 放宽：允许中文 + 连字符 + 1-2位数字
if re.match(r'^[一-鿿\-\d]{1,8}$', parts[1]):
```

---

## 架构影响总结

```
受影响文件（完整列表）：
  backend/pipeline/process_gen.py            ← 问题1-3：RAG阈值 + 工步合并 + 纯LLM模式
  backend/pipeline/process_spec_analyzer.py  ← 问题5-6：提取prompt + 回退路径工种
  backend/api/kb_import.py                   ← 问题7：入库链路工种校验
  backend/api/library.py                     ← 问题8：trades提取正则

不受影响：
  frontend/                                  ← 不改
  backend/api/upload.py                      ← 不改（process_gen由upload调用，内部阈值变化对外透明）
  database schema                            ← 不改
  API 接口                                   ← 不改
  SSE 流式输出                               ← 不改
```

