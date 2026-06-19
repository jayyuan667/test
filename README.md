# 二维工艺系统（YOLO + React）

`yolo-react` 是可独立克隆、安装和调试的 React/Flask 开发分支。

## 技术架构

- 前端：React 18、TypeScript、Vite、Tailwind CSS
- 后端：Python、Flask、SQLite、SSE
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
setup.bat         Windows 首次初始化
start.bat         Windows 日常启动
start.ps1         后端和前端联合启动脚本
```

运行时生成且不提交 Git 的内容：

```text
.env
.venv/
frontend-react/node_modules/
frontend-react/dist/
db_data/
uploads/
output/
backend/task_store.db
history.json
```

## 快速开始（Windows）

### 1. 克隆分支

```powershell
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test
```

### 2. 初始化

双击 `setup.bat`，或在终端运行：

```powershell
.\setup.bat
```

脚本会：

- 检查 Python、Node.js 和 npm
- 创建 Python 虚拟环境 `.venv`
- 安装后端依赖
- 安装 `frontend-react` 依赖
- 从 `.env.example` 创建 `.env`
- 创建本地运行目录

### 3. 配置模型

编辑根目录 `.env`，至少填写：

```dotenv
VISION_API_KEY="your_vision_api_key"
EMBEDDING_API_KEY="your_embedding_api_key"
LLM_API_KEY="your_llm_api_key"
```

仓库不包含真实密钥。

### 4. 启动

```powershell
.\start.bat
```

启动地址：

- React 开发页面：http://127.0.0.1:3200
- Flask API：http://127.0.0.1:5190
- 健康检查：http://127.0.0.1:5190/api/health

## 分别启动

后端：

```powershell
.\.venv\Scripts\Activate.ps1
$env:FLASK_DEBUG = "0"
python -m backend.run
```

前端：

```powershell
cd frontend-react
npm run dev
```

前端 `/api` 请求会代理到 `http://127.0.0.1:5190`。

## 构建 React

```powershell
cd frontend-react
npm run build
npm run preview
```

预览地址：http://127.0.0.1:3201

后端也会从 `frontend-react/dist` 提供生产构建：

```text
http://127.0.0.1:5190/
```

## 数据库说明

Git 分支不包含生产数据库或历史记录。

- 首次初始化会创建 `db_data/`。
- SQLite 文件会在本地按需生成。
- 空库下可以启动系统，但 RAG 检索没有可用记录。
- 可通过知识库导入功能建立本地数据库。

## 可选外部能力

- Poppler：PDF 转图片的兼容方案
- FreeCAD：PRT/STEP 几何分析和视图生成
- Creo：Creo 原生视图与工程信息提取
- OnShape：PRT 在线转换

这些能力未配置时，核心 React/Flask 服务仍可启动，但对应功能会降级或不可用。

详细说明：

- [安装说明](INSTALL.md)
- [启动与调试](START.md)
- [分支开发约束](BRANCH_DEVELOPMENT.md)
- [后端架构](docs/superpowers/specs/2026-06-17-backend-architecture.md)
