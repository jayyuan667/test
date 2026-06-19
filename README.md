# 二维工艺系统（YOLO + React）

`yolo-react` 是可独立克隆、安装和调试的 React/Flask 开发分支。

## 技术架构

- 前端：React 18、TypeScript、Vite、Tailwind CSS
- 后端：Python 3.11、Flask、SQLite、SSE
- 图纸处理：PDF/图片、OCR、YOLO 标注、视觉模型
- 工艺生成：特征审阅、RAG 检索、LLM 流式生成

主要业务流程：

```text
上传图纸
  → YOLO 标注审阅
  → 特征审阅
  → 工艺规程流式生成
  → 工艺入库
  → 数据浏览与历史快照
```

## 目录结构

```text
backend/          Flask 后端、API、分析流水线
frontend-react/   React 前端源码与前端测试
scripts/          数据导入和校验工具
docs/             架构、设计和实施文档
setup.sh          macOS/Linux 首次初始化
setup.bat         Windows 首次初始化
start.sh          macOS/Linux 日常启动
start.ps1         Windows 日常启动
```

运行时生成且不提交 Git 的内容：

```text
.env
.venv/
frontend-react/node_modules/
frontend-react/dist/
db_data/  （model-manifest.example.json 除外）
uploads/
output/
history.json
```

## 快速开始

### macOS / Linux

```bash
uv python install 3.11.15
uv sync --locked
cp .env.example .env
npm --prefix frontend-react ci
./start.sh
```

### Windows

```powershell
uv python install 3.11.15
uv sync --locked
Copy-Item .env.example .env
.\start.ps1
```

访问地址：

- React 开发页面：http://127.0.0.1:3200
- Flask API：http://127.0.0.1:5190
- 健康检查：http://127.0.0.1:5190/api/health
- 能力状态：http://127.0.0.1:5190/api/system/capabilities

## 可选能力安装

YOLO 预标注：

```bash
uv sync --locked --extra yolo
```

Windows Creo 自动化（仅 Windows）：

```bash
uv sync --locked --extra windows-creo
```

## 环境诊断

```bash
uv run python scripts/runtime_smoke.py
curl http://127.0.0.1:5190/api/system/capabilities
```

## 构建 React

```bash
cd frontend-react
npm run build
npm run preview
```

预览地址：http://127.0.0.1:3201

后端也会从 `frontend-react/dist` 提供生产构建：http://127.0.0.1:5190/

## 可选外部能力

| 能力 | 说明 |
|------|------|
| PyMuPDF | PDF 转图片（核心依赖，uv sync 自动安装） |
| YOLO (ONNX) | 推荐路径，将模型放入 `db_data/` |
| Poppler | PDF 兼容回退（PyMuPDF 不可用时） |
| FreeCAD | PRT/STEP 几何分析 |
| Creo | Windows 专属 Creo 自动化 |
| OnShape | PRT 在线转换 |

真实模型文件放在 `db_data/` 中，不提交 Git。缺少 YOLO 自动降级为人工标注。缺少 PyMuPDF 和 Poppler 会阻断 PDF 上传，但不影响图片上传。Creo 不适用于 macOS。可选能力安装方式：`uv sync --extra yolo`。

详细说明：

- [安装说明](INSTALL.md)
- [启动与调试](START.md)
- [分支开发约束](BRANCH_DEVELOPMENT.md)
- [后端架构](docs/superpowers/specs/2026-06-17-backend-architecture.md)
