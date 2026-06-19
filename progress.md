# 进度日志

## 会话：2026-06-20

### 阶段 1：现状审计与方案确认
- **状态：** complete

### 阶段 2：设计规格
- **状态：** complete

### 阶段 3：实施计划
- **状态：** complete

### 阶段 4：实现与增量验证
- **状态：** complete
- 执行的操作：
  - Task 1: 建立 Python 和依赖契约（uv + pyproject.toml + uv.lock）
  - Task 2: 纯运行时能力检测（7 项能力检测，不加载模型）
  - Task 3: 暴露能力 API（/api/system/capabilities）和启动阻断检查
  - Task 4: PDF 转换确定性 provider 选择和上传门禁（HIGH RISK，已回归）
  - Task 5: ONNX 优先 + 模型清单校验
  - Task 6: 统一跨平台安装/启动脚本（setup.sh, start.sh, setup.bat, start.ps1）
  - Task 7: 运行时烟雾检查 + CI（runtime.yml）
  - Task 8: 文档重写 + 最终验收

### 阶段 5：完整验收
- **状态：** complete

## 最终测试结果

| 测试集 | 数量 | 结果 |
|--------|------|------|
| 依赖契约 | 3 | ✅ |
| 能力检测 | 7 | ✅ |
| 启动检查 | 3 | ✅ |
| 能力 API | 1 | ✅ |
| PDF 转换/门禁 | 4 | ✅ |
| 模型清单 | 2 | ✅ |
| YOLO 检测器 | 2 | ✅ |
| 安装契约 | 5 | ✅ |
| 烟雾检查 | 1 | ✅ |
| 启动导入 | 1 | ✅ |
| 知识库导入格式 | 3 | ✅ |
| 数据库初始化 | 12 | ✅ |
| **总计** | **44** | **全部通过** |

## 验证清单

| 项目 | 状态 |
|------|------|
| `.python-version` = `3.11.15` | ✅ |
| `uv lock --check` 通过 | ✅ |
| `uv sync --locked` 不含 YOLO/Creo | ✅ |
| `backend/requirements.txt` 已删除 | ✅ |
| `requirements.txt` 由 uv 导出 | ✅ |
| PDF 默认 PyMuPDF | ✅ |
| PDF 缺失 → 422 pre-task | ✅ |
| `/api/system/capabilities` 无敏感数据 | ✅ |
| ONNX 优先 PT 兜底 | ✅ |
| 缺失模型 → 人工标注 | ✅ |
| macOS 无 pywinauto | ✅ |
| SQLite 空库初始化 | ✅ |
| 前端构建通过 | ✅ |
| SSE 流未改动 | ✅ |

## 提交记录

```
9ff08f4 docs: finalize reproducible runtime setup
deb3eaa build: unify cross-platform setup scripts
74ccd52 ci: verify runtime on macos and windows
ef30f9b feat: prefer onnx yolo model delivery
6e1c53e fix: make pdf conversion capability-aware
cbbe8c4 feat: add startup preflight and capabilities api
8ce7102 feat: add runtime capability detection
84ab309 build: unify python dependencies with uv
```
