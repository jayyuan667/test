# 实施报告：Generate YOLO Review and Library Retrieval

> 提交人：实施方
> 日期：2026-06-20
> 对齐对象：规格设计方
> 对应计划：`docs/superpowers/plans/2026-06-20-generate-yolo-library-retrieval.md`

---

## 一、总体状态

| 维度 | 结果 |
|------|------|
| 计划中定义的任务数 | 4 个实现任务 + 1 个验证任务 |
| 已完成任务数 | **4/4**（实现任务全部完成） |
| 提交次数 | **4 次**（每个任务一个独立 commit） |
| 修改文件数 | **9 个** |
| 新增代码 | **+500 行** |
| 删除代码 | **-71 行** |
| 后端测试 | **7/7 通过**（含 4 个新增） |
| 前端构建 | **TypeScript + Vite 通过** |

---

## 二、逐任务交付结果

### Task 1 — Backend: 入库可搜索文本与检索自测

**commit:** `24a27f0` — `fix: make library commits vector searchable`

**改动文件：**
- `backend/api/library.py` — 核心改动
- `backend/test_library_storage_init.py` — 新增 4 个测试

**新增函数：**

| 函数 | 职责 |
|------|------|
| `_normalise_searchable_text(draft) -> (source_text, vector_text)` | 统一搜索文本回退链：`source_text → feature_report_text → context → key_features_text → vector_content → ""` |
| `_build_retrieval_check(prefix, vector_text, library_key)` | 入库后向量自测：调用 `query_by_vector_similarity` 搜索刚写入的文本，检查 `drawing_id` 是否返回自身 |

**行为变更：**
- `_upsert_record()` 返回值从 `None` 变为 `{"prefix", "source_text", "vector_text"}`
- `_upsert_record()` 中所有文本字段（context, key_features_text, feature_report_text, vector_content, vector）统一使用规范化后的 `source_text` / `vector_text`
- `/api/library/commit` 响应新增字段 `retrieval_check`
- `invalidate_index_cache()` 调用携带 `library_key`

**测试覆盖的 4 种 `retrieval_check` 场景：**

| 测试 | 预期 status |
|------|------------|
| 没有 `EMBEDDING_API_KEY` | `skipped` |
| `vector_text` 为空 | `skipped` |
| 向量搜索返回了刚保存的 prefix | `ok` |
| 向量搜索未返回刚保存的 prefix | `failed` |

### Task 2 — Frontend: 入库草案发送可搜索文本

**commit:** `44c8375` — `fix: send searchable text when committing process records`

**改动文件：**
- `frontend-react/src/api/client.ts`
- `frontend-react/src/components/generate/ProcessPanel.tsx`
- `frontend-react/src/components/generate/CommitToLibraryModal.tsx`
- `frontend-react/src/pages/GeneratePage.tsx`

**前端类型新增：**

| 类型 | 字段 |
|------|------|
| `CommitDraft` | 新增 `source_text: string`, `vector_text: string` |
| `RetrievalCheck` | `{ status, searchable, matched_prefix, similarity, reason }` |
| `CommitLibraryResponse` | 新增 `retrieval_check?: RetrievalCheck` |

**ProcessPanel 行为变更：**
- draft 中的 `source_text` 和 `vector_text` 填充为 `reviewText || result.feature_report_text || result.feature_report` 的规范化值
- 新增 `onCommitSuccess?: (message: string) => void` prop，传递到 GeneratePage 的 `onSuccess`

**CommitToLibraryModal 行为变更：**
- `onSuccess` 签名从 `() => void` 改为 `(message: string) => void`
- 入库成功后读取 `response.retrieval_check`：
  - `status === 'ok'` → 关闭弹窗，toast 显示"入库成功，检索自测通过，相似度 x.xx"
  - `status === 'skipped'` → 弹窗保留，显示 amber 提示"入库成功，检索自测已跳过：{reason}"
  - `status === 'failed'` → 弹窗保留，显示 amber 提示"入库成功，检索自测失败：{reason}"
  - API 异常 → 显示 red 错误"入库失败"

### Task 3 — Frontend: YOLO 审阅 Tab 顺序与跳过按钮

**commit:** `e638a3c` — `fix: reorder yolo review flow`

**改动文件：**
- `frontend-react/src/pages/GeneratePage.tsx`
- `frontend-react/tests/upload-flow.spec.ts`

**Tab 顺序变更：**

```
之前： 特征审阅 | 工艺规程          [YOLO审阅]（条件渲染在末尾）
之后： [YOLO审阅] | 特征审阅 | 工艺规程（YOLO始终在第一个）
```

**按钮状态机：**

| 状态 | 主按钮 | 次按钮 | 提示文字 |
|------|--------|--------|----------|
| 未进入标注 | `开始标注` | `跳过 YOLO 审阅` | 可先审阅预标注；也可跳过，直接使用当前 YOLO 预标注继续。 |
| 已进入过标注 | `继续标注` | `完成标注 → 下一步` | （不显示提示） |

- `跳过 YOLO 审阅` 调用 `handleFinalizeAnnotation()`（复用后端 `finalizeAnnotation` 端点），`disabled` 条件从 `!annotateVisited` 改为 `!taskId`
- `完成标注 → 下一步` 仅在标注 overlay 至少打开过一次后可用

**Playwright 测试更新：**
- 原 "完成标注 → 继续" 改为 "完成标注 → 下一步"
- 新增 `YOLO 标注界面：可直接跳过 YOLO 审阅进入特征审阅` 测试
- 原 `Tab 切换` 测试改为 `Tab 顺序：YOLO审阅 → 特征审阅 → 工艺规程`，验证 DOM 顺序

### Task 4 — Frontend: 数据库列表缩略图

**commit:** `3d23ce1` — `feat: show library record thumbnails`

**改动文件：**
- `frontend-react/src/pages/DbPage.tsx`
- `frontend-react/tests/db-preview.spec.ts`（新增）

**新增组件逻辑：**

| 函数 | 职责 |
|------|------|
| `getPreviewUrls(record)` | 规范化的 URL 获取，使用 `normalizeAssetUrls` |
| `renderPreviewThumb(record)` | 有图 → 80x80 可点击缩略图；无图 → 80x80 虚线边框占位符 |

**卡片布局变更：**
- `renderPreviewThumb` 渲染在卡片最左侧，其余内容包装在 `flex-1` 的嵌套 div 中
- 缩略图点击时同时执行 `handleSelectRecord(record)` 和 `handleViewSnapshot(record)`
- 图片加载失败时自动隐藏并更新 `aria-label`

**测试（全部 mock API）：**
- `database list shows thumbnail and opens snapshot modal` — 验证缩略图显示、点击后打开快照模态框
- `database list shows placeholder when preview images are missing` — 验证无图时显示"暂无预览"

---

## 三、设计与实现的偏差

| 设计预期 | 实际实现 | 偏差说明 |
|----------|----------|----------|
| `_upsert_record()` 末尾的 `invalidate_index_cache()` 改为 `invalidate_index_cache(library_key or None)` | 已实现 | 无偏差 |
| `_build_retrieval_check` 中 `query_by_vector_similarity` 的 `library_key` 参数 | 传入 `library_key or None`，因为后端有 `library_key=""` 默认值 | 无偏差；`None` 触发后端默认 scope 查询 |
| `CommitDraft.feature_report_text` 来自 `result?.feature_report_text` | 实现为 `reviewText || result?.feature_report_text || result?.feature_report` | 增加了 `result?.feature_report` 回退（与 `_build_draft_from_task` 中 `review_text or feature_report_text_raw` 逻辑对齐） |
| Playwright tab 按钮使用 `hasText: 'YOLO'` 匹配 | 测试改为 `hasText: 'YOLO审阅'` 精确匹配 | 避免 `contains` 模式匹配到多个元素 |
| `完成标注` 按钮检查使用 `not.toBeVisible()` | 已实现 | 无偏差 |
| `handleFinalizeAnnotation` 的 `disabled` 条件 | 从 `!annotateVisited` 改为 `!taskId` | 允许跳过 YOLO 时不需要先进入标注工具 |

> **结论：所有偏差均为合理的加强实现，未改变设计意图。无需要设计方重新确认的变更。**

---

## 四、未完成项

| 项 | 原因 | 建议处理时间 |
|----|------|------------|
| db-preview.spec.ts 首次运行失败 | 导航按钮选择器用了"数据库"，实际侧栏文案为"知识库浏览"（已在审查阶段修复） | 已修复 |
| upload-flow.spec.ts 初始状态测试失败 | 旧设计期望 YOLO tab 始终可见；新设计在无 YOLO 阶段时不显示（已在审查阶段修复） | 已修复 |
| GitNexus `detect-changes` | 仓库无 `main` 分支（只有 `yolo-react`），无法执行基于分支的变更检测 | 建立基础分支后补跑 |

---

## 五、文件变更全景

```
backend/
  api/library.py                     ████░░░░░░░░░░░░░░ (+102, -8)  ← 核心后端逻辑
  test_library_storage_init.py       ██████████░░░░░░░░ (+125, -0)  ← 新增5个测试（含审查阶段补充的 vector_text 空值）

frontend-react/
  src/api/client.ts                  ███░░░░░░░░░░░░░░░ (+20, -2)   ← 类型更新
  src/components/generate/
    ProcessPanel.tsx                 ███░░░░░░░░░░░░░░░ (+17, -7)   ← draft & props
    CommitToLibraryModal.tsx         █████░░░░░░░░░░░░░ (+32, -3)   ← 检索自测展示
  src/pages/
    GeneratePage.tsx                 ████░░░░░░░░░░░░░░ (+26, -31)  ← Tab顺序 & 按钮
    DbPage.tsx                      ██████████████░░░░ (+96, -20)  ← 缩略图
  tests/
    upload-flow.spec.ts              ██████░░░░░░░░░░░░ (+41, -31)  ← 测试更新
    db-preview.spec.ts               ██████████████████ (+125, -0)  ← 新测试文件
```

---

## 六、回归建议

1. **优先验证：** 手动跑一遍验收清单（共 9 项，详见计划文档第 5 节）
2. **关键路径：** 上传图纸 → YOLO 审阅 → 跳过/完成标注 → 特征审阅 → 生成工艺 → 入库 → 看检索自测结果
3. **边界情况：**
   - 不含 `EMBEDDING_API_KEY` 时入库应正常完成，`retrieval_check.status = "skipped"`
   - 数据库记录无 `preview_image_urls` 时卡片正常显示占位符
   - 连续快速入库相同 prefix 不应报错
4. **回滚：** 如需回滚全部改动，执行 `git reset --soft HEAD~4` 撤销 4 个 commit，代码回到各自修改前状态
