# 工艺审核智能体（Agent 2）— 设计文档

> **日期**：2026-05-15

---

## 1. 目标

在工艺生成智能体（Agent 1）输出工艺后，由工艺审核智能体（Agent 2）对工艺进行严格审核，找出格式问题、参数来源缺失、工序逻辑错误和工艺完整性缺口，将问题反馈给 Agent 1 由其修改，人工确认后触发下一轮，最多 `max_rounds` 轮后标记人工介入。Agent 2 只找问题，不修改工艺。

---

## 2. 系统架构

### 2.1 三智能体角色

| 智能体 | 职责 | 状态 |
|---|---|---|
| Agent 1：工艺生成 | RAG + LLM 生成工艺 | 已有 |
| Agent 2：工艺审核 | 规则 + LLM 双层审核，输出结构化问题报告 | 本文档 |
| Agent 3：工艺修改 | 根据审核报告定向修改工艺 | 后续 |

### 2.2 数据流

```
Agent 1 输出
  (process_flow: [[tag, content], ...])
        ↓
  ProcessAuditor.audit()
        ├─ [Layer 1] RuleChecker          ← 确定性规则，纯代码
        │     ├─ 编号连续性检查
        │     ├─ 工序必填字段检查
        │     └─ 参数来源匹配（特征表 + 行业标准正则）
        │
        └─ [Layer 2] LLMAuditor           ← LLM 语义审核
              ├─ 工序逻辑顺序合理性
              ├─ 参数来源定性判断
              └─ 工艺完整性评估
        ↓
  AuditReport (结构化 JSON)
        ↓
  写入 task_store (audit_result / audit_round)
        ↓
  前端展示 → 用户确认 → 触发 Agent 1 修改
        ↓
  重入 ProcessAuditor（最多 max_rounds 轮，默认 3）
  超出 → status="needs_human"
```

### 2.3 模块位置

新建 `backend/pipeline/process_auditor.py`，与 `process_gen.py` 并列。

---

## 3. AuditReport 结构

```json
{
  "pass": false,
  "round": 1,
  "status": "needs_fix",
  "issues": [
    {
      "id": "rule-0030-missing_param_source",
      "seq": "0030",
      "layer": "rule",
      "type": "missing_param_source",
      "severity": "error",
      "detail": "数值 '840°C' 无来源：未在当前零件特征表中找到，也不匹配行业标准模式",
      "suggestion": "在审阅特征表中补充热处理参数，或确认是否为行业标准值"
    }
  ]
}
```

**status 取值**：
- `passed`：无 error 级问题，可入库
- `needs_fix`：存在问题，等待用户确认后触发修改
- `needs_human`：已达 max_rounds，停止自动循环，需人工介入

---

## 4. Layer 1 规则引擎

### 4.1 编号连续性

- 工序号为 0010 步进的四位数字
- 跳号超过一步（如 0010→0030）→ `warning`
- 末尾无检验工序（内容含"检验"或"检查"）→ `warning`

### 4.2 工序类型必填字段

| 工序类型关键词 | 必须包含 | 缺失级别 |
|---|---|---|
| 备料 | 尺寸数值（如 `δ20×390×248`） | error |
| 热处理 / 淬火 / 回火 / 退火 | 温度数值（如 `840°C`、`180℃`） | error |
| 镀 / 氧化 / 涂层 | 表面处理规格或厚度 | warning |
| 车 / 铣 / 磨 / 钻 | 无强制 | — |

### 4.3 参数来源匹配

对工艺文本中出现的数值型参数，尝试定位来源：

- **来源 A（零件特征表，`source=feature`）**：在 `review_text` 的硬约束字段中找到匹配值
- **来源 B（行业标准，`source=standard`）**：匹配预定义正则模式
  - 粗糙度：`Ra\d+\.?\d*`
  - 倒角：`C\d+\.?\d*`
  - 圆角：`R\d+\.?\d*`
  - 螺纹：`M\d+[×x]\d+`
  - 硬度：`HRC\d+`、`HB\d+`
  - 温度：`\d+[°℃]`（仅热处理工序）
- **无来源（`source=unknown`）**：两者均无匹配 → `error`，detail 注明具体数值和工序号

---

## 5. Layer 2 LLM 语义审核

### 5.1 输入上下文

```
- 当前工艺完整文本（工序列表）
- 当前零件审阅特征表（review_text）
- Layer 1 已发现的问题列表（避免重复报）
```

### 5.2 三类审核任务

**① 工序逻辑顺序**
检查粗加工→半精加工→精加工→热处理→表面处理→检验的基本顺序是否合理；标注明显颠倒的工序对（如精磨在热处理之前）。

**② 参数来源定性判断**
对 Layer 1 标注为 `source=unknown` 的参数，LLM 判断：
- 属于可接受工艺惯例（如"去毛刺"无数值）→ 降级为 `warning` 或忽略
- 属于必须溯源的关键数值（切削余量、公差带、关键尺寸）→ 维持 `error`

**③ 工艺完整性**
结合零件特征表，检查重要加工特征是否未被工艺覆盖（如特征表有螺纹孔但工艺无攻牙工序）→ `warning`。

### 5.3 System Prompt 结构

```
你是一名机械工艺审核专家。
任务：对以下工艺进行审核，只找问题，不修改工艺。
规则：
1. 参数若无来源（特征表或行业标准），必须标注为问题
2. 工序顺序若违反基本加工逻辑，必须标注
3. 零件特征表中存在但工艺中未覆盖的加工特征，必须标注
输出格式：JSON 数组，每项含 seq/type/severity/detail/suggestion
不允许输出修改后的工艺文本。
```

### 5.4 输出合并

Layer 1 + Layer 2 的 issues 按 `(seq, type)` 去重后合并，组成最终 `AuditReport`。

---

## 6. 异步队列与多轮循环

### 6.1 task_store 新增字段

在现有 `tasks` 表新增两列（`ALTER TABLE` 迁移）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `audit_result` | TEXT (JSON) | 最新一次 AuditReport |
| `audit_round` | INTEGER | 已完成审核轮次，默认 0 |

### 6.2 多轮循环状态机

```
任意轮次审核后, 无 error 级 issues  → status=passed（流程结束，可入库）
audit_round < max_rounds, issues存在 → status=needs_fix → 等待用户确认
用户确认 → 触发 Agent 1 修改 → audit_round+1 → 重新审核
audit_round >= max_rounds, issues仍存在 → status=needs_human → 停止自动循环
```

`max_rounds` 从 `config.py` 读取，配置键 `AUDIT_MAX_ROUNDS`，默认值 `3`。

### 6.3 新增 API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/audit/<task_id>` | 返回最新 AuditReport |
| POST | `/api/audit/<task_id>/confirm` | 用户确认，传入忽略的 issue id 列表，触发 Agent 1 修改 |
| POST | `/api/audit/<task_id>/skip` | 人工强制通过，记录操作日志 |

`confirm` 请求体：
```json
{ "ignored_issue_ids": ["rule-0030-missing_param_source"] }
```

### 6.4 调用时机

- **首次审核**：Agent 1 `generate()` 完成后，在 `upload.py` 的 `_finalize_processing()` 中调用 `ProcessAuditor.audit()`
- **后续轮次**：`POST /api/audit/<task_id>/confirm` 端点触发 Agent 1 重生成，完成后自动触发下一轮审核

---

## 7. 前端（最小化改动）

工艺生成完成后，在现有工艺展示区下方新增**审核结果折叠面板**：

- 绿色：`passed`（无问题）
- 黄色：仅 `warning`
- 红色：存在 `error`，显示问题列表 + "确认修改"按钮（`confirm` 端点）
- 灰色：`needs_human`，显示"已达最大审核轮次，请人工介入"

---

## 8. 测试

### 8.1 单元测试（`backend/pipeline/test_process_auditor.py`）

| 测试用例 | 验证内容 |
|---|---|
| `test_rule_numbering_gap` | 0010→0030 跳号被检出 |
| `test_rule_missing_blank_size` | 备料工序无尺寸 → error |
| `test_rule_heat_treatment_no_temp` | 热处理无温度 → error |
| `test_rule_param_source_feature` | 数值在 review_text 中 → source=feature |
| `test_rule_param_source_standard` | Ra3.2 匹配行业标准正则 → source=standard |
| `test_rule_param_no_source` | 孤立数值无来源 → error |
| `test_max_rounds_triggers_human` | 第 4 轮返回 needs_human |
| `test_issues_dedup` | Layer 1 + Layer 2 同一 issue 不重复 |

### 8.2 集成测试

1. **正常通过路径**：完整特征表 + 规范工艺 → `pass=True`，0 errors
2. **单轮修复路径**：Agent 1 输出缺温度 → error → confirm → Agent 1 重生成 → 审核通过
3. **超轮终止路径**：连续 3 轮仍有 error → `status=needs_human`，不再自动触发

---

## 9. 涉及文件

| 文件 | 操作 |
|---|---|
| `backend/pipeline/process_auditor.py` | 新建：RuleChecker + LLMAuditor + ProcessAuditor |
| `backend/pipeline/test_process_auditor.py` | 新建：单元测试 |
| `backend/task_store.py` | 新增 audit_result / audit_round 字段 |
| `backend/api/upload.py` | `_finalize_processing()` 后触发首次审核 |
| `backend/app.py` | 注册 /api/audit 端点 |
| `backend/config.py` | 新增 AUDIT_MAX_ROUNDS=3 |
| `updated_front/demo-industrial-console.html` | 新增审核结果折叠面板 |
| `updated_front/js/demo-industrial-console.js` | 审核结果渲染 + confirm 按钮逻辑 |

---

## 10. 不做

- 不实现 Agent 3（工艺修改智能体）——后续单独设计
- 不修改 `process_gen.py` 的生成逻辑
- 不改变现有工艺入库路径（library.py）
- 不重建 task_store 表结构，仅追加列
