# 智能工艺系统

基于多模型协同的机械零件工艺规程自动生成系统。支持 **PDF 工程图纸**（主流程）和 **Creo PRT 三维模型**（兼容），自动完成 OCR/视觉特征提取、RAG 检索、LLM 工艺生成与导出。

---

## 系统架构（2D 主流程）

```
PDF 工程图纸上传
    │
    ├── OCR 特征提取（PaddleOCR）
    │   ├── 图纸标题栏识别（图号、零件名、材料、比例）
    │   ├── 尺寸标注提取（长宽高、壁厚、孔径）
    │   └── 技术要求识别（热处理、表面处理、检验标准）
    │
    ├── VLM 视觉分析（豆包多模态）—— 厚度交叉校验
    │
    ├── 特征融合 → 工艺规格分析（ProcessSpecAnalyzer）
    │       │
    │       ▼
    │   人工审阅页（可在线编辑特征文本）
    │       │
    │       ▼
    │   RAG 检索（向量 + 关键词 + 图号多路混合）
    │   ├── 优先检索指定工艺库
    │   └── 匹配度 < 0.3 时自动回退公共库
    │       │
    │       ▼
    │   LLM 工艺生成（DeepSeek Chat）
    │       │
    │       ▼
    │   工艺规程展示 + Excel 导出
    │
    └── 可选的 PRT 3D 路径（Creo → FreeCAD 三视图 → 几何分析）
```

---

## 功能特性

| 功能 | 说明 |
|------|------|
| PDF 上传 | 工程图纸 PDF，多页支持，Poppler 转 PNG |
| OCR 特征提取 | PaddleOCR 识别标题栏、尺寸、技术要求 |
| OCR 厚度校验 | VLM 交叉验证 OCR 提取的厚度值 |
| 视觉特征 | 豆包视觉模型提取语义特征和尺寸 |
| 人工审阅 | 特征表格可在线编辑，确认后继续生成 |
| RAG 检索 | 向量相似度 + 图号精确匹配 + 关键词混合排名 |
| 跨库回退 | 私有库匹配度不足时自动补充公共库 |
| 工艺生成 | DeepSeek LLM 基于知识库生成标准工艺规程 |
| 知识库管理 | ZIP 批量导入（drawing/craft PDF 配对） |
| 多库隔离 | 私有库 / 公共库，按项目隔离知识 |
| 数据库浏览 | 在线查看、编辑、删除知识库记录 |
| Excel 导出 | 标准工艺规程格式 |
| 特征缓存 | 同图纸再次上传跳过 VLM，直接恢复 |
| 许可证系统 | RSA-2048 签名，机器码绑定，到期提醒 |

---

## 项目结构

```
2D-v/
├── backend/
│   ├── app.py                       # Flask 主入口
│   ├── config.py                    # 配置管理
│   ├── vector_map_rag.py            # RAG 检索（向量 + 关键词多路混合）
│   ├── feature_report.py            # 特征报告构建
│   ├── library_scope.py             # 多库隔离（kb_library_scopes 表）
│   ├── history.py                   # 历史记录
│   ├── run.py                       # 生产入口脚本
│   ├── api/
│   │   ├── upload.py                # 上传主流程（PDF/PRT/批量）
│   │   ├── batch.py                 # 批量上传
│   │   ├── kb_import.py             # ZIP 知识库导入
│   │   ├── library.py               # 工艺库查询/管理
│   │   ├── result.py                # 结果查询
│   │   ├── events.py                # SSE 实时进度推送
│   │   ├── export.py                # Excel 导出
│   │   ├── history.py               # 历史记录接口
│   │   ├── config.py                # 系统配置接口
│   │   ├── health.py                # 健康检查
│   │   └── image.py                 # 图片服务
│   ├── pipeline/
│   │   ├── vision_analyzer.py       # 云端视觉分析（豆包 VL）
│   │   ├── local_vision_analyzer.py # 本地视觉分析
│   │   ├── vlm_feature.py           # VLM 特征提取 + 厚度推断
│   │   ├── ocr_feature.py           # PaddleOCR 特征提取
│   │   ├── ocr_thickness.py         # OCR 厚度交叉验��
│   │   ├── process_spec_analyzer.py # 工艺规格分析
│   │   ├── process_gen.py           # 工艺规程生成（含跨库回退）
│   │   ├── geometry_analyzer.py     # OpenCASCADE 几何分析（PRT）
│   │   ├── expert_judge.py          # 专家判断
│   │   ├── pdf_converter.py         # PDF 转 PNG
│   │   └── freecad_worker.py        # FreeCAD 截图 worker（PRT）
│   └── services/
│       ├── event_emitter.py         # SSE 事件发射
│       ├── feature_cache.py         # 特征缓存
│       ├── observability.py         # 可观测性
│       ├── review_session.py        # 审阅会话管理
│       └── upload_pipeline.py       # 上传管线编排
├── updated_front/                   # 前端界面
│   ├── demo-industrial-console.html
│   ├── export-file-modal.vue
│   ├── kb_import_selftest.zip       # 示例知识库 ZIP
│   ├── js/
│   │   ├── demo-industrial-console.js
│   │   ├── three-init.js            # Three.js 3D 查看器
│   │   ├── GLTFLoader.js
│   │   └── three.module.min.js
│   └── css/
│       └── industrial-console.css
├── db_data/                         # SQLite 数据库（2d-v.db）
├── .env                             # API Key 配置
├── setup.bat                        # 开发环境初始化
├── switch_mode.bat                  # 云模式/本地模式切换
└── CLAUDE.md                        # AI 助手指引
```

---

## 快速开始（开发环境）

### 前置条件

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 建议 3.13 |
| Poppler | 任意 | PDF 转 PNG（Windows 需手动安装） |
| FreeCAD | 1.0+ | 仅 PRT 3D 路径需要 |

### 1. 一键初始化

运行 `setup.bat`，自动完成虚拟环境创建、依赖安装、`.env` 生成。

### 2. 手动安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. 配置环境变量

```bash
copy .env.example .env
# 编辑 .env，填入 API Key
```

### 4. 启动服务

**推荐（一键启动 + 自动打开浏览器）：**
```bat
updated_front\start_flask_demo.bat
```
脚本自动检测 `.venv`，清理端口占用，等待后端就绪后打开浏览器。

**手动启动：**
```bash
.venv\Scripts\python -m backend.run
```

浏览器访问：**http://localhost:5090/dev/demo-industrial-console**

### 5. 项目迁移

项目目录可自由移动。`start_flask_demo.bat` 使用相对路径，只要 `.venv` 在项目根目录下即可正常启动。若 `.venv` 不存在，会自动回退使用系统 Python。

---

## 安装包部署（给最终用户）

使用 Inno Setup 编译的 EXE 安装包，内嵌 Python 运行时，无需安装任何依赖。

### 编译安装包

```powershell
# 1. 编译 launcher.exe（Go 语言）
cd F:\Work_Dir\package_install_t\build\launcher
go build -ldflags="-H windowsgui" -o ..\..\dist\launcher.exe .

# 2. 编译安装包（Inno Setup 6）
& "C:\Users\...\Inno Setup 6\ISCC.exe" build\installer.iss

# 输出：dist\智能工艺系统_v1_Setup.exe
```

### 用户安装流程

1. 运行安装包 → 选择安装目录 → 可选粘贴激活码
2. 安装完成自动启动 → 浏览器打开界面
3. 无激活码时弹窗显示机器码 → 发给管理员获取 license.lic
4. 系统托盘图标常驻，右键可退出

### 获取机器码

用户运行安装包同级目录的 `get_machine_id.bat`，双击即可显示机器码。

### 签发激活码

```bash
cd license_keygen
python gen_license.py <机器码> <到期日>
# 产出 license_XXXXXXXX.lic，发给用户放入安装目录
```

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/upload` | POST | PRT 单文件上传 |
| `/api/upload_drawing` | POST | PDF/PNG 图纸上传（2D 主入口） |
| `/api/batch_upload` | POST | 批量上传 |
| `/api/review/<id>` | POST | 提交审阅，继续生成 |
| `/api/result/<id>` | GET | 获取任务结果 |
| `/api/events/<id>` | GET | SSE 实时进度流 |
| `/api/export/<id>` | GET | 导出 Excel |
| `/api/history` | GET | 历史记录列表 |
| `/api/config` | GET/POST | 读取/更新系统配置 |
| `/api/library/records` | GET | 工艺库记录列表 |
| `/api/library/scopes` | GET | 库列表 |
| `/api/library/status` | GET | 工艺库状态 |
| `/api/kb/import_zip` | POST | ZIP 知识库导入 |
| `/api/kb/import_folder` | POST | 文件夹直接导入 |
| `/api/kb/sample_zip` | GET | 下载示例 ZIP |

---

## 知识库 ZIP 结构

参见 `F:\小桌面\设计需求\pack_up\zip_package_guide.md`

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `VISION_API_KEY` | 豆包视觉模型 API Key |
| `VISION_API_BASE` | 视觉模型 API 地址 |
| `VISION_MODEL_ID` | 视觉模型 ID |
| `LLM_API_KEY` | DeepSeek API Key |
| `LLM_BASE_URL` | LLM API 地址 |
| `LLM_MODEL` | LLM 模型 ID |
| `EMBEDDING_API_KEY` | 向量嵌入 API Key |
| `EMBEDDING_BASE_URL` | 向量嵌入 API 地址 |
| `EMBEDDING_MODEL` | 向量嵌入模型 ID |
| `POPPLER_PATH` | Poppler bin 目录（Windows 必填） |
| `FEATURIZER_BASE_DIR` | 项目根目录（影响 DB 路径） |
| `FLASK_DEBUG` | `0` 关闭调试模式 |

---

## 技术栈

| 层级 | 组件 |
|------|------|
| 后端框架 | Flask 3.x + Flask-CORS |
| OCR | PaddleOCR (PP-OCRv4) |
| 视觉分析 | 豆包多模态（Ark） |
| LLM | DeepSeek Chat |
| 向量嵌入 | 豆包 Embedding (1024d) |
| 向量检索 | SQLite + 余弦相似度 + RRF 混合排名 |
| 前端 | 原生 HTML/CSS/JS + Three.js |
| 导出 | openpyxl（Excel） |
| 安装包 | Inno Setup 6 + 嵌入式 Python 3.13 + Go launcher |
| 许可证 | RSA-2048 签名 + 机器码绑定 |
