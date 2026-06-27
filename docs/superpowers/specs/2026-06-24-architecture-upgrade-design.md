# 架构升级设计规格

**日期：** 2026-06-24
**状态：** 设计完成，待确认
**分支：** yolo-react

---

## 执行优先级

```
P0（立即）：YOLO Ultralytics CPU 推理 + 标注流程恢复
P1（短期）：MinIO 对象存储 — 自动生命周期清理，解磁盘问题
P2（中期）：PostgreSQL + pgvector — 先可行性分析，再决定迁移节奏
P3（版本稳定后）：Docker Compose 容器化（B 方案 — 全用 Docker）
```

---

## 模块 1：MinIO 对象存储

**访问方式：** 公开 bucket + HTTP 直连

**Bucket 规划：**
| 路径 | 内容 | 生命周期 |
|------|------|----------|
| `pages/<task_id>/` | PDF 渲染页、标注图 | 90 天后自动删除 |
| `imports/<batch_id>/` | ZIP 导入产物 | 180 天后自动删除 |
| `uploads/<task_id>/` | 原始上传文件 | 永久保留 |
| `previews/<batch_id>/` | 知识库预览图 | 永久保留 |

**代码改动：**
- `config.py`：加 MinIO 连接配置（endpoint, access_key, secret_key, bucket）
- `result.py`：图片服务改为从 minio 获取 URL → 302 重定向
- `upload.py`：上传后异步推送到 minio
- `kb_import.py`：导入产物推送到 minio
- `frontend`：URL 格式不变，flask 做代理，前端无感

**迁移策略：**
1. 本地 docker-compose 启动 minio → 改代码 → 前端测试
2. 服务器部署 → 新旧并存（minio 优先，本地文件回退）
3. 稳定后批量导入旧文件 → 停旧目录

---

## 模块 2：PostgreSQL + pgvector

**分工：**
| | PostgreSQL | SQLite |
|------|------|------|
| 存什么 | 知识库记录、向量嵌入、导入批次 | 任务状态、SSE 事件 |
| 备份 | pg_dump（重要数据）| 不需要（丢了不影响） |
| 迁移 | Alembic 管理 schema | 启动时自动建表 |

**风险点：** 当前 pgvector 迁移可能改动较大，建议先做可行性分析评估改动量，再决定是否执行。

---

## 模块 3：Docker Compose

**方案：** B — 开发和生产全用 Docker

**编排：**
```yaml
services:
  app       # Flask :5190
  postgres  # :5432 (pgvector)
  minio     # :9000 (API) + :9001 (控制台)
  nginx     # :80 → 前端 dist（本地开发用，服务器上已有宿主机 nginx）
```

**注意：** nginx 在容器化部署时已有宿主机版本，线上保留宿主机 nginx。

---

## 模块 4：VLM 模型选型分析

### 当前状态
- 模型：doubao Seed 2.0 Mini
- 实测耗时：1-3 分钟/页
- 在通用中文多模态基准上排名靠前（SuperCLUE-VLM 2026.04）

### 工业图纸识别基准（IndustryBench-MIPU，阿里巴巴 2026.06.22）

| 模型 | 单图 F1 | 精确率 | 特征 |
|------|:---:|:---:|------|
| Qwen 3.5 Plus | **81.3%** | 88.1% | 单图最佳，多图跌至第4 |
| Qwen 3.5-397B-A17B | 76.0% | — | 综合稳健 |
| Gemini 3.1 Pro | — | **93.8%** | 精确率最高，多图F1 65.1%排名第1 |
| GPT-5.4 | — | — | 多图F1 60.5%，中文中游 |

### 中文OCR基准（CC-OCR V2，2026.05）

| 模型 | 总分 |
|------|:---:|
| Qwen3.6-Plus | **75.77** |
| Qwen3.5-Plus | 73.03 |
| Doubao Seed 2.0 Pro | 72.15 |
| Gemini 3.1 Pro | 70.17 |

### 中文多模态基准（SuperCLUE-VLM，2026.04）

| 模型 | 总分 |
|------|:---:|
| Doubao Seed 2.0 Pro | **90.66** |
| Gemini 3.1 Pro | 89.35 |
| Qwen3.5 系列 | ~89 |

### 工程图纸尺寸/公差提取（IDP Benchmark）

| 模型 | 提取准确率 |
|------|:---:|
| Gemini 2.5 Pro | **79.96%** |
| OpenAI o4 mini | 77.34% |
| Claude Opus 4 | 40.49% |
| Qwen VL Plus | 20.38% |

### 结论

1. Doubao 在通用中文视觉上排第1，但在工业图纸细分场景未被评测
2. Qwen 系在工业产品参数提取（IndustryBench-MIPU）和中文 OCR（CC-OCR）上均排前列
3. Gemini 精确率高但中文场景非强项
4. Claude/GPT 在工业图纸上表现明显差于国产模型

VLM 选型由用户自行决定。代码层改动仅需修改 `backend/pipeline/vision_analyzer.py` 中的 API endpoint 和模型 ID。

---

## 模块 5：YOLO Ultralytics CPU 推理

**当前状态：** YOLO 功能未启用（模型文件缺失）

**目标方案：** Ultralytics PyTorch 原版 + CPU 推理（不导 ONNX，避免精度损失）

**改动范围：**
- 下载/放置 ultralytics 模型权重（best.pt）
- `yolo_detector.py`：确认 PyTorch CPU 推理路径
- 前端标注流程已完整，只需模型就位即可恢复

**依赖：** `ultralytics` + `torch`（已在 pyproject.toml 可选中，通过 `uv sync --extra yolo` 安装）

---

## 模块 6：容器化注意事项

等待版本稳定后执行。本地需确保所有功能在 Docker 中可运行后再上传服务器。

---

## 架构不变项（扫描）

| 项目 | 状态 |
|------|:---:|
| API 接口 | 不变 |
| 前端路由 | 不变 |
| SSE 流式输出 | 不变 |
| 工艺生成流程 | 不变 |
| 知识库数据结构 | 不变（PG 模式兼容） |
