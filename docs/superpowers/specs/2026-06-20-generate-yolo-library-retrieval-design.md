# 生成页 YOLO 审阅与工艺入库检索设计

**日期：** 2026-06-20  
**范围：** `frontend-react/src/pages/GeneratePage.tsx`、`ProcessPanel`、工艺入库 API、数据库浏览页、向量检索自测  
**状态：** 已确认设计，待实施计划

## 背景

当前生成页的 tab 展示顺序为：

```text
特征审阅 → 工艺规程 → YOLO审阅
```

这与实际流程不一致。二维图纸路径中，YOLO 预标注发生在特征审阅前，用户应先决定是否检查 YOLO 标注，再进入特征审阅，最后生成工艺规程。

同时，工艺规程页提供“入库”能力，但当前入库草稿主要传 `feature_report_text`。后端 `_upsert_record()` 生成向量时优先读取 `vector_text` 或 `source_text`。因此从“工艺规程页”入库的数据可能没有使用真实特征文本生成向量，影响后续 RAG 向量匹配质量。

数据库浏览页已有 `preview_task_id`、`preview_image_urls`、`preview_total_pages` 字段和详情页“查看快照”能力，但列表卡片没有直接显示图片预览，用户难以确认入库记录对应的图纸。

## 目标

1. 生成页 tab 展示顺序改为：

```text
YOLO审阅 → 特征审阅 → 工艺规程
```

2. YOLO 审阅页支持明确的“跳过 YOLO 审阅”路径。
3. 用户进入标注工具并退出后，YOLO 页按钮语义切换为“继续标注 / 完成标注 → 下一步”。
4. 工艺规程页入库的数据必须可被后续向量检索命中。
5. 数据库列表卡片直接显示图纸缩略图，详情页保留完整快照查看。
6. 入库成功后返回“刚入库 → 立刻可检索”的自测结果。

## 非目标

- 不重构后端任务状态机。
- 不新增 YOLO 标注格式。
- 不改变实际工艺生成算法。
- 不要求全量 backend 既有失败测试在本次修复。
- 不新增前端能力状态面板。

## 设计决策

### 1. Tab 顺序只是展示调整

`ActiveTab` 仍保持：

```ts
type ActiveTab = 'review' | 'annotation' | 'process'
```

只调整 tab bar 渲染顺序：

```text
annotation(YOLO审阅) → review(特征审阅) → process(工艺规程)
```

`YOLO审阅` 仍按现有 `showAnnotationTab` 控制显隐。没有 YOLO 审阅阶段时不强行显示。

### 2. YOLO 页按钮状态

未进入标注工具前：

```text
[开始标注] [跳过 YOLO 审阅]
```

用户点击“开始标注”后打开现有标注 overlay，并设置 `annotateVisited = true`。

用户退出标注工具后：

```text
[继续标注] [完成标注 → 下一步]
```

此时不再把“跳过 YOLO”作为主按钮展示，避免用户已经审阅过标注后仍被提示“跳过”。

“跳过 YOLO 审阅”复用现有 `finalizeAnnotation(taskId)` 路径。后端 `/annotations/<task_id>/finalize` 已支持在 `awaiting_annotation` 状态下继续流程；跳过的业务含义是：不打开标注工具、不做人工修正，直接使用当前 YOLO 预标注或空标注继续后续视觉分析。

### 3. 工艺规程页入库必须带可向量化文本

前端 `CommitDraft` 增加：

```ts
source_text: string
vector_text: string
```

取值规则：

```text
confirmedFeatureText = reviewText || result.feature_report_text || result.feature_report || ''
vector_text = extractable confirmedFeatureText
source_text = confirmedFeatureText
```

`feature_report_text` 继续保留，用于数据库详情展示。

后端 `_upsert_record()` 增加兜底：

```python
source_text = draft.get("source_text") or draft.get("feature_report_text") or draft.get("context") or ""
vector_text = draft.get("vector_text") or source_text
vector = create_query_vector(vector_text)
```

`context`、`key_features_text`、`vector_content` 也应使用同一份可检索文本兜底，避免保存记录可见但检索向量为空。

### 4. 入库后向量自测

`POST /api/library/commit` 成功保存后，后端执行一次同库检索自测：

1. 使用刚保存的 `vector_text` 查询当前 `library_key`。
2. `top_k=5`，`min_similarity=0.0`。
3. 检查返回结果中是否存在刚保存的 `prefix`。

响应增加：

```json
{
  "retrieval_check": {
    "status": "ok",
    "searchable": true,
    "matched_prefix": "ABC123",
    "similarity": 0.83,
    "reason": ""
  }
}
```

如果没有配置 `EMBEDDING_API_KEY`，返回：

```json
{
  "retrieval_check": {
    "status": "skipped",
    "searchable": false,
    "matched_prefix": "",
    "similarity": 0,
    "reason": "EMBEDDING_API_KEY not configured"
  }
}
```

如果向量生成失败或未命中，入库仍成功，但前端必须提示“入库成功，检索自测失败/跳过”，便于用户知道这条记录当前不能保证被向量检索命中。

### 5. 数据库列表图片预览

数据库后端字段已具备：

- `preview_task_id`
- `preview_image_urls`
- `preview_total_pages`

前端数据库列表卡片增加左侧缩略图：

- 有图：显示第一张 `preview_image_urls[0]`
- 无图：显示灰色图纸占位符
- 点击缩略图或详情页“查看快照”打开现有快照 modal

详情页保留现有“查看快照”按钮和 modal，不重写。

## 数据流

### YOLO 跳过路径

```text
annotation_required SSE
→ activeTab = annotation
→ 用户点击“跳过 YOLO 审阅”
→ frontend finalizeAnnotation(taskId)
→ backend annotation_event.set()
→ upload.py 继续视觉分析
→ review_required SSE
→ activeTab = review
```

### 工艺页入库与自测

```text
ProcessPanel rows + reviewText/result.feature_report_text
→ CommitDraft(source_text, vector_text, preview_image_urls)
→ POST /api/library/commit
→ _upsert_record()
   → create_query_vector(vector_text)
   → 保存 vector/vector_content/preview_image_urls
   → invalidate_index_cache(library_key)
→ query_by_vector_similarity(vector_text, library_key)
→ response.retrieval_check
→ 前端 toast 显示自测结果
```

## 错误处理

- `taskId` 缺失：禁用跳过和完成按钮。
- `finalizeAnnotation()` 返回 409：提示当前任务不在 YOLO 审阅状态，并刷新任务状态。
- 入库保存成功但向量自测失败：不回滚入库，只提示检索不可保证。
- 入库保存成功但图片预览为空：数据库列表显示占位图，详情页隐藏“查看快照”或置灰。
- 图片加载 404：缩略图自动回退占位图。

## 测试计划

### 前端

1. GeneratePage tab 顺序测试：
   - `YOLO审阅` 显示时位于最前。
   - `YOLO审阅` 不显示时，顺序为 `特征审阅 → 工艺规程`。
2. YOLO 按钮状态测试：
   - 未进入标注前显示 `开始标注` 和 `跳过 YOLO 审阅`。
   - 进入并退出标注后显示 `继续标注` 和 `完成标注 → 下一步`。
3. ProcessPanel 入库 draft 测试：
   - `CommitDraft.vector_text` 使用 `reviewText`。
   - `preview_image_urls` 保留。
4. DbPage 预览测试：
   - 有 `preview_image_urls` 时列表显示缩略图。
   - 无图时显示占位图。
   - 点击缩略图打开快照 modal。

### 后端

1. `/library/commit` 使用 `vector_text` 生成向量。
2. 缺少 `vector_text/source_text` 时使用 `feature_report_text` 兜底。
3. 保存后响应包含 `retrieval_check`。
4. 无 `EMBEDDING_API_KEY` 时自测返回 `skipped`，入库仍成功。
5. 命中刚保存 prefix 时返回 `searchable=true`。

### 回归

运行任务相关测试：

```bash
uv run pytest \
  backend/test_dependency_manifest.py \
  backend/test_capabilities.py \
  backend/test_startup_checks.py \
  backend/test_capabilities_api.py \
  backend/pipeline/test_pdf_converter.py \
  backend/test_upload_capability_gate.py \
  backend/test_model_manifest.py \
  backend/pipeline/test_yolo_detector.py \
  backend/test_installation_contract.py \
  backend/test_runtime_smoke.py \
  backend/test_library_storage_init.py \
  backend/test_startup_import.py \
  backend/test_kb_import_formats.py \
  -q
```

并运行前端构建：

```bash
npm --prefix frontend-react run build
```

## 验收标准

1. Tab 顺序正确，且不改变流程状态机。
2. 用户可跳过 YOLO 审阅并继续进入特征审阅。
3. 用户进入标注后，YOLO 页按钮切换为“继续标注 / 完成标注 → 下一步”。
4. 从工艺规程页入库的记录：
   - 保存 `vector`。
   - 保存 `vector_content`。
   - 保存 `preview_image_urls`。
   - `/library/commit` 返回 `retrieval_check`。
5. 入库成功后，数据库列表能看到图纸缩略图。
6. 数据库详情页快照可打开并显示图片。

## 风险

| 风险 | 等级 | 处理 |
|------|------|------|
| 跳过 YOLO 误操作 | 中 | 跳过按钮使用弱样式，并只在未进入标注前显示 |
| 向量 API 未配置 | 中 | 入库不失败，自测返回 skipped |
| 入库记录可见但检索不可命中 | 高 | 强制写入 vector_text/source_text 兜底，并返回 retrieval_check |
| 数据库预览图路径失效 | 中 | 缩略图 onError 回退占位图；详情页保留快照入口 |
| 前端 tab 顺序调整影响自动切换 | 低 | 只改渲染顺序，不改 activeTab 状态逻辑 |

