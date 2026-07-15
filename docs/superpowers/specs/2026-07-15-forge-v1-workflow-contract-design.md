# FORGE v1 工作流契约设计

## 1. 目标

在不破坏现有 VLM、LLM、RAG、OCR、YOLO 和 FreeCAD 核心管线的前提下，新增一套可版本化、可恢复、可测试的 v1 任务契约。第一阶段使用 `/Users/caojiayuan/Documents/测试包/drawing/test.png` 跑通上传、真实进度、结构化特征审阅、工艺生成、结构化工艺表、刷新恢复和导出。

本阶段不实现完整的三栏工程工作台，但所有新契约和前端 workflow module 必须能直接支撑后续工作台，不得再将解析和状态逻辑堆入 `GeneratePage.tsx`。

## 2. 范围

### 2.1 本阶段包含

- 新增 `/api/v1/tasks/*` 任务路由，旧接口保持可用。
- 定义 `TaskSnapshot`、`DrawingResult`、`Feature`、`ProcessOperation`、`TaskEvent` 的 v1 契约。
- 从 SQLite 任务库、现有结果 JSON 和现有事件生成 v1 快照与事件。
- 新增前端 Drawing Workflow module，封装 HTTP、SSE、状态合并、幂等和重连。
- Mock 和真实后端使用同一套 TypeScript 领域类型。
- 将现有 GeneratePage 的核心数据读取切换到 workflow module，保持当前视觉可用。
- 为契约、状态机、事件续传和真实纵向流程增加测试。

### 2.2 本阶段不包含

- 不重设完整三栏工作台。
- 不修改模型提示词、模型配置、特征计算方法或工艺生成规则。
- 不重写知识库、认证、企业隔离、PDF、OCR、YOLO 或 FreeCAD 管线。
- 不删除旧接口和旧 adapter。
- 不伪造置信度、设备、工时、参数或来源。

## 3. 受保护核心

以下文件和其内部算法默认不修改：

- `backend/pipeline/vlm_feature.py`
- `backend/pipeline/process_gen.py`
- `backend/vector_map_rag.py`
- `backend/prt_pipeline.py`
- `backend/pipeline/pdf_converter.py`
- `backend/pipeline/ocr_feature.py`
- `backend/pipeline/yolo_detector.py`
- `backend/pipeline/freecad_worker.py`
- 认证、企业隔离和知识库原始数据

用户已授权在必要时重建旧实现。默认仍通过外围 adapter 保护核心行为；当测试证明 adapter 无法产生真实稳定数据，或旧 module 的兼容实现比重建更复杂、更难测试时，允许重建该 module。重建前必须记录原因、影响范围、基线结果、回退方案和对应的失败测试。重建可更换内部实现，但不得在本阶段同时改变模型、提示词、工艺规则或已验证的核心输入输出语义。

## 4. 总体架构

```text
现有受保护核心管线
          ↓ 原始结果
backend/services/task_snapshot.py
          ↓ DrawingResult v1
backend/api/v1/tasks.py
          ↓ HTTP + SSE
src/features/drawing-workflow/api.ts
          ↓ commands + snapshots
src/features/drawing-workflow/store.ts
          ↓ stable view state
GeneratePage / 后续 Review Workspace
```

路由只处理 HTTP 输入输出；快照 module 只处理旧数据到 v1 数据的标准化；事件 module 只处理事件序列化、回放和续传；前端 store 只处理命令和状态。

## 5. v1 数据契约

### 5.1 TaskSnapshot

```json
{
  "schema_version": "1.0",
  "task": {
    "id": "string",
    "state": "pending|processing|awaiting_annotation|awaiting_review|completed|failed|cancelled",
    "phase": "upload|drawing_analysis|annotation|feature_review|process_generation|export|done",
    "progress": 0,
    "revision": 0,
    "created_at": "ISO-8601|null",
    "updated_at": "ISO-8601|null",
    "error": null
  },
  "drawing": {
    "name": "string",
    "source_kind": "png|jpg|pdf|dxf|prt|unknown",
    "page_count": 1,
    "preview_urls": []
  },
  "features": [],
  "review": {
    "status": "not_ready|pending|confirmed|modified",
    "raw_text": "string|null"
  },
  "process_operations": [],
  "reuse_candidates": [],
  "capabilities": {}
}
```

`state` 是任务持久化状态，`phase` 是用户可理解的当前阶段。前端不得根据 `progress` 或 `error` 推导 `state`。

### 5.2 Feature

```json
{
  "id": "stable-string",
  "kind": "diameter|length|thread|tolerance|surface|material|requirement|geometry|identifier|unknown",
  "label": "M115×3-6g",
  "value": "M115×3-6g|null",
  "unit": "mm|null",
  "tolerance": {
    "upper": null,
    "lower": null,
    "text": "6g|null"
  },
  "source": {
    "method": "vlm|ocr|yolo|geometry|combined|legacy_text",
    "page": 1,
    "bbox": null,
    "evidence_text": "string|null"
  },
  "confidence": null,
  "review_status": "unreviewed|confirmed|modified|rejected",
  "missing_reason": null
}
```

`confidence` 只能来自核心管线的真实输出。旧报告不包含置信度时必须返回 `null`，不得使用类型权重或正则生成数字。

### 5.3 ProcessOperation

```json
{
  "id": "stable-string",
  "code": "0050",
  "trade": "车工|null",
  "content": "粗车外圆",
  "equipment": [],
  "duration_minutes": null,
  "parameters": [],
  "note": null,
  "status": "draft|streaming|complete|modified"
}
```

旧位置数组必须在后端 adapter 中转换。前端不得将设备写入 `time` 或将工时写入 `params`。

### 5.4 TaskEvent

```json
{
  "schema_version": "1.0",
  "seq": 123,
  "task_id": "string",
  "type": "phase_started|phase_progress|feature_ready|operation_upserted|phase_completed|task_completed|task_failed|heartbeat",
  "phase": "drawing_analysis",
  "progress": 35,
  "timestamp": "ISO-8601",
  "payload": {}
}
```

SSE 必须同时输出 `id: <seq>` 和 JSON data。客户端通过 `Last-Event-ID` 或显式 `after=<seq>` 恢复。同一 `seq` 重放不得重复追加工艺行。

## 6. v1 HTTP interface

- `POST /api/v1/tasks`：上传单个图纸并返回初始 `TaskSnapshot`。
- `GET /api/v1/tasks/<task_id>`：返回当前完整快照。
- `GET /api/v1/tasks/<task_id>/events?after=<seq>`：回放并持续输出标准事件。
- `POST /api/v1/tasks/<task_id>/annotations/finalize`：结束标注阶段。
- `POST /api/v1/tasks/<task_id>/review`：提交审阅结果并触发工艺生成。
- `POST /api/v1/tasks/<task_id>/cancel`：取消可取消的任务。
- `GET|POST /api/v1/tasks/<task_id>/export`：导出当前工艺，POST 允许传入人工修改行。

v1 路由允许在内部调用旧 route 背后的已有函数，但不得通过 HTTP 回调本机旧路由。

## 7. 错误契约

```json
{
  "error": {
    "code": "VISION_CONFIG_MISSING",
    "message": "视觉模型配置不完整",
    "retryable": false,
    "phase": "drawing_analysis",
    "details": {}
  }
}
```

任务失败后必须保留已完成阶段、最后事件序号、失败阶段、是否可重试和是否有检查点。普通用户不得获取密钥、文件系统路径或完整异常堆栈。

## 8. 前端 Drawing Workflow module

```text
src/features/drawing-workflow/
├── types.ts       v1 TypeScript 契约
├── api.ts         HTTP 和 SSE adapter
├── reducer.ts     纯函数状态合并与幂等
├── store.ts       命令、连接、重连和快照恢复
├── mock.ts        实现同一 interface 的 Mock adapter
└── *.test.ts     契约、reducer 和重连测试
```

GeneratePage 只向 store 发送用户命令并渲染状态。页面不得新增直接 `fetch`、`EventSource`、Markdown 核心特征解析或轮询循环。

## 9. 兼容与迁移

1. 新增后端 v1 快照 adapter 和契约测试。
2. 新增 v1 事件 adapter 和续传测试。
3. 保持旧 route 响应不变，运行旧接口冒烟测试。
4. 新增前端 workflow module，先通过测试消费固定 fixture。
5. GeneratePage 以 feature flag 或 v1 adapter 切换，保留旧 adapter 回退能力。
6. `test.png` 纵向 E2E 通过后，将 v1 设为默认，但本阶段不删除旧实现。

## 10. 测试设计

### 10.1 后端契约测试

- 对象工艺行映射到正确字段。
- 五列位置数组映射为 `code/trade/content/equipment/duration_minutes`。
- 缺少置信度的旧特征返回 `null`。
- 旧 Markdown 特征标记 `source.method=legacy_text`。
- 不完整任务返回合法空集合，不使用虚构占位数据。
- 企业隔离与旧 route 相同。

### 10.2 事件测试

- `seq` 严格递增。
- `after=N` 不返回 `seq <= N` 的事件。
- SSE 包含 `id:`、`event:` 和标准 JSON `data:`。
- 重连后重放 `operation_upserted` 不会重复工艺行。
- 终止状态产生且只产生一个终止事件。

### 10.3 前端测试

- reducer 忽略旧 `seq`。
- 同 `operation.id` 更新而不追加。
- 快照修订号高于当前修订号时才覆盖完整状态。
- 401 触发统一登录过期流程。
- 403 配额耗尽显示可理解的不可重试错误。
- SSE 断开后使用最后 `seq` 恢复。

### 10.4 真实纵向 E2E

`test.png` 必须完成：

```text
上传
→ 显示真实阶段与进度
→ 显示图纸预览
→ 显示结构化特征和真实来源
→ 完成审阅
→ 生成结构化工艺表
→ 刷新页面并恢复同一任务
→ 导出
```

验收材料包含最终快照 JSON、事件序列、浏览器截图和导出文件。

## 11. 交付门槛

- 新后端契约和事件测试全部通过。
- 新前端 module 测试全部通过。
- 新增 TypeScript 代码 ESLint 零错误。
- Next.js production build 通过。
- 现有后端冒烟和企业隔离测试通过。
- `test.png` 真实 E2E 通过。
- 旧接口仍可运行。
- 没有覆盖 `.env`、数据库、密钥或现有输出文件。

全仓当前 ESLint 存在旧问题，且错误扫描 `.venv`。本阶段必须先修正检查范围，并分开报告“新增代码质量”和“历史存量问题”，不得将历史错误隐藏或伪称为本阶段已修复。

## 12. 回退策略

- 新 v1 路由不替换旧路由。
- 前端通过一个显式配置切换旧 adapter 与 v1 adapter。
- 快照 adapter 只读现有数据，不迁移或重写数据库表。
- 新事件是旧事件的派生视图，本阶段不删除旧事件数据。
- 回退时只需关闭 v1 前端切换；现有管线和数据不受影响。

## 13. 停止条件

如果现有核心输出无法为 `test.png` 提供可验证的特征值、来源或工艺行，实施必须先报告缺失和触发它的失败测试。如果缺失源于可替换的旧实现，允许按本文第 3 节的约束重建；如果缺失源于模型能力或核心算法本身，不得通过伪造数据或改写前端显示掩盖。
