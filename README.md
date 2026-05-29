# 工艺规程智能生成系统

基于 AI 大模型的电子装备制造工艺规程自动生成系统。上传工程图纸（PDF/PRT），通过视觉模型分析 + RAG 知识库检索 + LLM 综合推理，自动生成结构化的制造工艺规程，支持 3D 预览、知识库管理、历史追溯与多格式导出。

## 核心功能

| 模块 | 说明 |
|------|------|
| **工艺生成** | 拖拽上传 PRT 模型/PDF 图纸，Three.js 三维预览，特征审阅后基于 RAG 检索生成工艺规程 |
| **工艺入库** | 上传 ZIP 工艺包（PRT + PDF 配对），批量导入知识库，支持冲突替换与批次日志 |
| **历史记录** | 按日期筛选历史任务，查看快照预览，支持批量删除 |
| **知识库管理** | 检索、筛选、编辑、删除知识库记录，支持公共库与个人库切换 |
| **多格式导出** | 工艺文件支持 PPT、Excel、PDF 格式导出 |

## 技术架构

```
┌─────────────────────────────────────────────────┐
│                   前端 (updated_front/)           │
│  Three.js 3D 预览 | Vue 3 导出组件 | 原生 JS 控制台 │
└──────────────────────┬──────────────────────────┘
                       │ HTTP API (Flask)
┌──────────────────────┴──────────────────────────┐
│                  后端 (backend/)                  │
│  Flask REST API | PRT 解析 | PDF 处理 | RAG 引擎  │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────┐
│                  AI 模型层                        │
│  豆包视觉模型 (图像分析) | DeepSeek LLM (推理生成)   │
│  豆包 Embedding (文本向量化)                       │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────┐
│                 外部工具链                         │
│  FreeCAD (3D 模型解析) | Creo (PRT 转换)          │
│  Poppler (PDF 处理) | SQLite (知识库存储)          │
└─────────────────────────────────────────────────┘
```

## 项目结构

```
├── backend/                  # Flask 后端
│   ├── api/                  # REST API 端点 (config, health, image, status)
│   ├── pipeline/             # 核心处理流水线 (视觉分析、工艺生成)
│   ├── services/             # 业务服务层
│   ├── run.py                # 应用入口
│   ├── models.py             # 数据模型定义
│   └── app.py                # Flask 应用工厂
├── updated_front/            # 前端控制台
│   ├── css/                  # 工业风样式
│   ├── js/                   # Three.js + 主控台逻辑
│   ├── demo-industrial-console.html  # 主页面
│   └── export-file-modal.vue # 导出弹窗组件
├── new_logic/                # RAG 检索引擎 (检索/排序/信号)
├── v_model_test/             # 视觉模型测试工具
├── scripts/                  # 批处理与维护脚本
├── data_json/                # 工艺数据 (JSON)
├── db_data/                  # SQLite 知识库存储
├── docs/                     # 设计文档
├── setup.bat                 # 一键环境初始化
├── requirements.txt          # Python 依赖清单
└── .env.example              # 环境变量模板
```

## 环境要求

| 软件 | 版本 | 必要性 | 用途 |
|------|------|--------|------|
| Python | 3.11.x | 必须 | 后端运行 |
| Node.js | >=18 LTS | 必须 | PPT 生成 (pptxgenjs) |
| FreeCAD | 1.1 | 必须 | 3D 模型解析 |
| Git | 任意 | 必须 | 代码管理 |
| Creo Parametric | 9.0 | 可选 | PRT 文件转换 |
| Poppler | 任意 | 可选 | PDF 处理 |

## 快速开始

### 1. 克隆项目

```bat
git clone <仓库地址>
cd my_working
```

### 2. 一键初始化

双击或在 cmd 中运行 `setup.bat`，自动完成：
- 创建 Python 虚拟环境 `.venv`
- 安装所有 Python 依赖
- 从 `.env.example` 生成 `.env` 配置文件
- 检查 FreeCAD 安装路径

### 3. 配置环境变量

编辑 `.env`，填入 API Key：

```
VISION_API_KEY="你的豆包视觉模型Key"
LLM_API_KEY="你的DeepSeek API Key"
EMBEDDING_API_KEY="你的豆包Embedding Key"
```

### 4. 启动系统

```bat
updated_front\start_flask_demo.bat
```

浏览器自动打开 `http://127.0.0.1:5000`，进入工艺生成控制台。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate` | 上传 PRT/PDF 触发工艺生成 |
| POST | `/api/zip-import` | 上传 ZIP 工艺包入库 |
| GET | `/api/history` | 查询历史任务列表 |
| GET | `/api/db/records` | 查询知识库记录 |
| PUT | `/api/db/records/:id` | 编辑知识库记录 |
| DELETE | `/api/db/records/:id` | 删除知识库记录 |
| GET | `/api/config` | 获取系统配置 |
| POST | `/api/config` | 更新系统配置 |
| GET | `/api/health` | 健康检查 |

## 模型配置

| 模型 | 提供商 | 用途 |
|------|--------|------|
| doubao-seed-2-0-mini | 火山引擎 (豆包) | 工程图视觉分析 |
| doubao-embedding-vision | 火山引擎 (豆包) | 文本/图像向量化 |
| deepseek-chat | DeepSeek | LLM 综合推理与工艺生成 |
