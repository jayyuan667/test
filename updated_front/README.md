# 智能工艺系统 — 前端

基于 Three.js 的工业制造工艺管理 Web 控制台，提供 PRT 模型三维预览、工艺自动生成、知识库管理与历史追溯功能。

## 功能模块

| 模块 | 说明 |
|------|------|
| **工艺入库** | 上传 ZIP 工艺包（PRT + PDF 配对），批量导入知识库，支持冲突替换与批次日志 |
| **工艺生成** | 拖拽上传 PRT 模型，Three.js 三维预览，特征审阅后基于 RAG 检索生成工艺规程 |
| **历史记录** | 按日期筛选历史任务，查看快照预览，支持批量删除 |
| **数据库浏览** | 检索、筛选、编辑、删除知识库记录，支持公共库与个人库切换 |

## 技术栈

- **Three.js** — 浏览器端 PRT/GLTF 模型渲染
- **原生 JavaScript** — 主控台交互逻辑（模块化 DOM 操作，约 80KB）
- **Vue 3** — 工艺文件导出弹窗组件（PDF / Excel 导出，基于 jspdf）
- **Flask 后端** — Python API 服务，提供 PRT 解析、工艺生成、知识库 CRUD
- **SQLite** — 知识库存储（`vector_map_new.db`）

## 项目结构

```
updated_front/
├── css/
│   └── industrial-console.css    # 工业风控制台样式（CSS 变量体系）
├── js/
│   ├── three.module.min.js       # Three.js 核心库
│   ├── three-init.js             # Three.js 初始化 + GLTFLoader 挂载
│   ├── GLTFLoader.js             # GLTF 模型加载器
│   ├── BufferGeometryUtils.js    # 几何体工具函数
│   └── demo-industrial-console.js # 主控台交互逻辑
├── demo-industrial-console.html  # 主页面（单页应用，四页签布局）
├── export-file-modal.vue         # 导出弹窗组件（Vue 3 + Ant Design Vue）
├── start_flask_demo.bat          # 一键启动脚本（Flask 后端 + 打开浏览器）
├── kb_import_selftest.zip        # 工艺入库自测用 ZIP 包
└── pulling_methond.txt           # 导出组件调用说明
```

## 快速启动

### 1. 启动 Flask 后端

```bat
# 在项目根目录（updated_front 的上级目录）执行：
.venv\Scripts\python -m backend.run
```

### 2. 启动前端

```bat
# 直接双击或执行：
start_flask_demo.bat
```

该脚本会自动启动 Flask 后端（端口 5000），等待健康检查通过后打开浏览器访问控制台。

### 3. 手动访问

浏览器打开 `http://127.0.0.1:5000/dev/demo-industrial-console`

## API 端点

前端默认连接 `http://localhost:5000/api`，可在 HTML 中通过 `window.__API_BASE__` 覆盖。主要端点：

- `POST /api/generate` — 上传 PRT 并触发工艺生成
- `POST /api/zip-import` — 上传 ZIP 工艺包入库
- `GET /api/history` — 查询历史任务列表
- `GET /api/db/records` — 查询知识库记录
- `PUT /api/db/records/:id` — 编辑知识库记录
- `DELETE /api/db/records/:id` — 删除知识库记录
- `GET /api/health` — 健康检查

## 依赖

- 浏览器需支持 ES Modules（`importmap`）
- Three.js r152+（CDN 部署或本地 `three.module.min.js`）
- Python 3.10+ / Flask / SQLite（后端）
- 字体：Google Fonts（Noto Sans SC、Rajdhani、JetBrains Mono）
