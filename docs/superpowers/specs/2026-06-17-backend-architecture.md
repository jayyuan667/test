# 当前程序后端设计架构说明

## 目标

本文档描述当前程序的后端设计架构，重点说明启动方式、核心模块、任务状态机、SSE 推送、结果与历史回放、以及安装包运行时的目录与数据持久化方式。前端只作为消费这些接口的展示层，不展开 UI 细节。

## 架构总览

后端是一个以 Flask 为入口的单进程应用，内部使用线程处理长任务，SQLite 作为任务状态的权威存储，内存字典作为运行期缓存。

```text
浏览器 / 安装版前端
        |
        v
   Flask App (backend/app.py)
        |
        +--> API Blueprints
        |     /api/upload
        |     /api/upload_drawing
        |     /api/annotations/*
        |     /api/review/*
        |     /api/status/*
        |     /api/events/*
        |     /api/result/*
        |     /api/history
        |     /api/export/*
        |     /api/library/*
        |
        +--> Pipeline / Services
        |     backend/pipeline/*
        |     backend/services/*
        |
        +--> Persistence
              task_store.db
              history.json
              output/<task_id>/
```

## 运行入口

| 文件 | 作用 |
|---|---|
| `backend/run.py` | 命令行启动入口，导入 `backend.app` 并启动 Flask。 |
| `backend/app.py` | 应用装配层，负责加载环境变量、初始化配置、创建 Flask 实例、注册蓝图、挂载静态资源。 |

`backend/app.py` 做的事情比较明确：

1. 读取 `.env` 和 `config.json`。
2. 初始化 Poppler 路径与日志。
3. 初始化 SQLite。
4. 恢复或取消上次遗留的任务状态。
5. 注入共享内存状态给各个 API 模块。
6. 注册所有 `/api/*` 路由。
7. 提供 React 前端静态资源。

## 核心数据模型

后端同时维护三层数据：

| 层级 | 位置 | 作用 |
|---|---|---|
| 运行态 | `tasks` / `event_data` / `event_locks` | 处理当前会话中的任务、事件流和锁。 |
| 持久态 | `backend/task_store.db` | 任务、事件、结果、PRT 缓存的权威来源。 |
| 文件态 | `output/<task_id>/`、`history.json` | 结果文件、预览图、待审阅快照、历史索引。 |

`task_store.py` 定义了最重要的持久化表：

| 表名 | 作用 |
|---|---|
| `tasks` | 任务主记录，保存状态、进度、输入名、输出目录、库归属等。 |
| `task_events` | SSE 可回放事件流，保存步骤、日志和结构化事件。 |
| `task_results` | 完成态结果 JSON。 |
| `prt_cache` | PRT 文件哈希缓存，避免重复处理同一份模型。 |

## 主要模块职责

| 模块 | 职责 |
|---|---|
| `backend/api/upload.py` | 主业务编排，负责上传、审阅等待、确认、重新生成、完成态落盘。 |
| `backend/api/annotations.py` | 标注保存、加载、导出、标注完成确认。 |
| `backend/api/events.py` | SSE 事件推送与重放。 |
| `backend/api/result.py` | 任务结果查询与资源文件读取。 |
| `backend/api/history.py` | 历史记录列表与删除。 |
| `backend/api/export.py` | Excel / PDF 导出。 |
| `backend/api/status.py` | 任务进度查询。 |
| `backend/api/library.py` | 工艺库导入、检索、浏览与多库隔离。 |
| `backend/services/event_emitter.py` | 统一事件发射函数，负责将事件写入运行态与 SQLite。 |
| `backend/services/review_session.py` | 审阅态快照、恢复和清理。 |
| `backend/services/upload_pipeline.py` | 上传主线的分步编排辅助。 |
| `backend/pipeline/*` | PDF/PRT 转换、OCR、视觉分析、专家判断、工艺生成等底层能力。 |
| `backend/vector_map_rag.py` | 工艺库向量检索与混合检索。 |
| `backend/library_scope.py` | 工艺库作用域、权限与启用状态管理。 |

## 主流程

### 1. PDF 图纸上传流程

典型链路如下：

`/api/upload_drawing` -> 后台线程处理 -> `awaiting_annotation` -> `finalize_annotations` -> `awaiting_review` -> `review` -> `completed`

关键阶段：

1. 上传文件后，后端创建任务记录。
2. `pdf_converter` 将 PDF 转成页面图片。
3. `vision_analyzer` 或 `local_vision_analyzer` 生成页面描述。
4. `feature_report` 汇总成特征报告。
5. 进入 `awaiting_annotation` 或 `awaiting_review`，等待人工确认。
6. 用户确认后，`ProcessGenerator` 生成工艺规程。
7. 结果写入 `task_results` 与 `output/<task_id>/result.json`。

### 2. PRT 上传流程

PRT 走另一条主线：

`/api/upload` -> PRT 转换/截图 -> VLM 特征提取 -> `awaiting_review` -> 确认 -> 工艺生成

关键点：

1. `prt_pipeline.py` 负责 PRT 到 STEP、截图、glTF 等准备工作。
2. `vlm_feature.py` 提供视觉特征文本。
3. `feature_cache.py` / `prt_cache` 负责同图复用。
4. `review_session.py` 负责审阅态恢复。

### 3. 标注确认流程

`backend/api/annotations.py` 只处理标注数据本身，不直接承载工艺生成逻辑。

| 接口 | 作用 |
|---|---|
| `GET /api/annotations/<task_id>` | 读取已保存标注。 |
| `POST /api/annotations/<task_id>/save` | 保存单页标注 JSON 与 YOLO TXT。 |
| `GET /api/annotations/<task_id>/export` | 导出标注 ZIP。 |
| `POST /api/annotations/<task_id>/finalize` | 结束标注阶段，恢复主流程。 |

### 4. 审阅与重新生成

`backend/api/upload.py` 中的 `/api/review/<task_id>` 和 `/api/rerun/<task_id>` 负责人工确认之后的分支。

设计上它们要满足两个原则：

1. 确认后只提交一次，不重复创建任务。
2. 重新生成只复用已有审阅结果，不重新走上传和标注阶段。

### 5. SSE 实时推送

`backend/api/events.py` 是前端实时反馈的关键。

它的策略是：

1. 优先从内存中的 `event_data` 读取最新事件。
2. 如果内存中没有任务，则回退到 SQLite 中的 `task_events`。
3. 任务完成后发送 `complete` 或 `error`。
4. 长时间无数据时发送 keepalive，避免连接被中间层断开。

这意味着 SSE 不是纯内存机制，而是带回放能力的事件流。

## 状态机

后端的任务状态不是任意跳转，而是围绕审阅与生成阶段组织的。

```text
pending
  -> processing
  -> awaiting_annotation
  -> processing
  -> awaiting_review
  -> processing
  -> completed

异常分支:
  -> error
  -> cancelled
```

常见状态含义：

| 状态 | 含义 |
|---|---|
| `pending` | 任务已创建，尚未开始处理。 |
| `processing` | 后端正在做转换、OCR、视觉分析或工艺生成。 |
| `awaiting_annotation` | 等待人工完成标注。 |
| `awaiting_review` | 等待人工确认特征报告。 |
| `completed` | 任务已完成，结果可回放。 |
| `error` | 任务失败。 |
| `cancelled` | 被取消或被重启清理。 |

## 持久化与回放

后端的结果回放主要依赖三个入口：

| 入口 | 作用 |
|---|---|
| `GET /api/result/<task_id>` | 返回当前任务的完整结果视图。 |
| `GET /api/history` | 返回历史记录索引。 |
| `GET /api/events/<task_id>` | 回放任务过程中的事件序列。 |

`backend/api/result.py` 的设计重点是兼容三种来源：

1. 内存任务对象。
2. SQLite 中的任务结果。
3. `output/<task_id>/result.json` 文件。

它同时会把图片 URL 统一标准化到 `/api/result/<task_id>/asset/...`，避免历史快照里出现重复拼接或路径错位。

## 目录结构

| 目录 / 文件 | 说明 |
|---|---|
| `backend/uploads/` | 原始上传文件。 |
| `backend/output/<task_id>/` | 单个任务的产物目录。 |
| `backend/output/<task_id>/result.json` | 完成态结果。 |
| `backend/output/<task_id>/pending_review.json` | 审阅态快照。 |
| `backend/output/<task_id>/annotations/` | 标注文件。 |
| `backend/history.json` | 历史列表。 |
| `backend/task_store.db` | SQLite 任务库。 |
| `backend/db_data/` | 模型、知识库、缓存与预览素材。 |

## 设计原则

### 1. 路由层尽量薄

路由文件主要负责参数校验、状态切换和调用编排，真正的业务逻辑下沉到 `services/` 和 `pipeline/`。

### 2. SQLite 是权威来源

内存状态只用于加速和当前会话，重启后可以从 SQLite 和结果文件恢复。

### 3. 事件流可回放

SSE 事件不只存在于内存里，还会写入 `task_events`，这样断线重连或页面刷新后仍然有机会恢复。

### 4. 结果与历史分离

`result.json` 解决任务结果，`history.json` 解决历史索引，`task_store.db` 解决状态与回放。三者职责不混用。

### 5. 长任务异步化

上传、转换、视觉分析、工艺生成都通过后台线程执行，避免阻塞 HTTP 请求。

## 与前端的边界

前端只负责：

1. 上传文件。
2. 监听 SSE。
3. 展示审阅、标注和工艺规程。
4. 调用确认、重新生成和历史查询接口。

前端不应把自己当成状态源。真正的状态源仍然是后端任务对象 + SQLite + 结果文件。

## 典型排查点

如果后续再遇到问题，优先查这几类位置：

1. `backend/api/upload.py` 是否把状态切到了正确阶段。
2. `backend/api/events.py` 是否还在发送旧事件。
3. `backend/task_store.py` 里的状态和结果是否已经落盘。
4. `backend/api/result.py` 是否能从文件或数据库正确回放。
5. `backend/services/review_session.py` 是否把审阅态恢复完整。

## 小结

当前后端的核心不是单一 API，而是一条“上传 -> 审阅/标注 -> 生成 -> 持久化 -> SSE 回放 -> 历史查询”的闭环。最重要的设计约束是：任务状态要以 SQLite 为准，SSE 要可回放，结果要能从文件与数据库双路恢复，前端切换不应改变后端任务本身。

