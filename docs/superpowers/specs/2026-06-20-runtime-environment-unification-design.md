# 运行环境统一与基础稳定性设计

## 1. 背景

当前项目能够在已有 `.venv` 中运行，但安装和启动尚不可复现：

- macOS系统Python为3.9.6，项目虚拟环境为3.11.15。
- 项目没有Python版本声明和依赖锁文件。
- `requirements.txt` 与 `backend/requirements.txt` 是两个独立依赖源，内容已经漂移。
- PDF转换代码优先使用PyMuPDF，但依赖清单没有声明PyMuPDF；回退到`pdf2image`时又依赖系统Poppler。
- YOLO、Creo、FreeCAD和本地视觉模块具有平台或模型文件前提，却和核心后端启动路径存在耦合。
- 安装成功不等于主要能力可用，用户只能从终端日志判断缺失项。

本设计只解决运行环境、依赖、能力检测和跨平台交付，不修改工艺工作流、页面布局、按钮顺序或SSE流式输出。

## 2. 目标

第一阶段完成后：

1. 项目唯一支持的Python主环境为Python 3.11.15。
2. `pyproject.toml`是唯一手工维护的Python依赖定义。
3. `uv.lock`锁定具体版本，macOS与Windows共享锁文件。
4. 从干净克隆执行一套明确命令即可创建环境并启动核心服务。
5. PDF是核心能力，默认不要求系统安装Poppler。
6. YOLO、Creo、FreeCAD等可选能力缺失时，核心后端仍可启动。
7. 后端以结构化接口报告能力状态，前端无需解析终端日志。
8. 环境错误提供明确原因和可执行的修复命令。

## 3. 非目标

本阶段不实施：

- 工艺页面状态机和按钮禁用规则。
- 页面路由、布局或视觉重构。
- SSE流式输出修改。
- PostgreSQL、微服务、Docker或Kubernetes迁移。
- YOLO模型训练。
- Creo在macOS上的模拟支持。
- 完整PLM/MES集成。

## 4. 技术方案

采用：

```text
Python 3.11.15
├── core
├── yolo
├── windows-creo
└── dev
```

依赖管理使用：

- `.python-version`：声明`3.11.15`。
- `pyproject.toml`：项目元数据、Python版本范围、核心依赖和可选依赖组。
- `uv.lock`：锁定实际安装版本。
- `requirements.txt`：由uv导出，仅供兼容部署，不允许手工修改。

`backend/requirements.txt`不再作为安装入口。为避免旧文档或用户继续误用，它应被删除，或替换为仅包含迁移说明的文本文件。实施时优先删除，并同步修改所有文档和脚本。

## 5. Python版本策略

项目要求：

```text
Python == 3.11.15
```

`pyproject.toml`的包兼容范围声明为：

```text
requires-python = ">=3.11,<3.12"
```

本地和CI命令统一使用：

```bash
uv run python ...
```

不允许文档继续使用未限定来源的`python3`创建环境，因为macOS可能解析到系统Python 3.9。

如果用户机器没有Python 3.11.15：

```bash
uv python install 3.11.15
uv sync
```

启动时检测到非3.11版本，环境检查必须返回失败，并显示上述修复命令。

## 6. 依赖分组

### 6.1 核心依赖

核心依赖满足Flask服务启动、图纸解析、数据库、OCR和远程模型API调用：

- Flask
- flask-cors
- Werkzeug
- python-dotenv
- PyMuPDF
- Pillow
- pdf2image
- ezdxf
- matplotlib
- numpy
- rapidocr-onnxruntime
- onnxruntime
- langchain-openai
- langchain-core
- openai
- requests
- httpx
- openpyxl

`pdf2image`保留为兼容回退，但不保证单独安装Python包即可工作。只有系统Poppler可用时，该路径才标记为可用。

### 6.2 YOLO可选依赖

`yolo`组包含：

- ultralytics
- torch
- torchvision（如当前Ultralytics版本需要）

默认`uv sync`不安装该组。需要PyTorch路径时执行：

```bash
uv sync --extra yolo
```

ONNX Runtime属于核心依赖，因为它提供更轻量的跨平台推理路径。模型文件不进入Git。

### 6.3 Windows Creo可选依赖

`windows-creo`组包含：

- pywinauto
- 其他确认确有调用的Win32辅助包

所有依赖附带平台条件：

```text
sys_platform == "win32"
```

安装命令：

```bash
uv sync --extra windows-creo
```

在非Windows平台请求该组时，不安装Windows包，也不使同步失败。

### 6.4 开发依赖

`dev`组包含：

- pytest
- pytest-cov
- ruff
- mypy（仅在已有类型边界可实际检查的范围启用）
- python-docx

前端Playwright继续由`frontend-react/package.json`管理，不进入Python依赖。

## 7. PDF能力

PDF转换顺序保持为：

```text
PyMuPDF
→ pdf2image + Poppler
→ 明确失败
```

PyMuPDF是默认且必须验证的核心路径。环境能力检查应实际导入`fitz`，而不是只检查包元数据。

Poppler检查应寻找：

- `pdfinfo`
- `pdftoppm`

如果PyMuPDF不可用但Poppler完整，则PDF能力仍可用，provider为`poppler`。

如果两条路径均不可用：

- 后端核心服务仍可启动。
- `/api/system/capabilities`返回PDF不可用。
- PDF上传接口在创建任务前返回4xx错误。
- 错误信息必须包含`uv sync`修复命令。
- PNG和JPG上传仍可使用。

## 8. YOLO与模型交付

YOLO能力按以下顺序检测：

```text
best.onnx + onnxruntime
→ best.pt + ultralytics/torch
→ 人工标注降级
```

推荐生产交付ONNX模型。模型不提交Git，默认查找位置为：

```text
db_data/best.onnx
db_data/best.pt
```

新增模型清单文件，例如：

```text
db_data/model-manifest.example.json
```

清单字段：

- `name`
- `version`
- `format`
- `sha256`
- `classes`
- `input_size`
- `confidence_threshold`
- `released_at`

实际模型清单与模型文件作为运行时资产，不包含在Git中；Git只保存示例和校验代码。

YOLO不可用时：

- 后端继续生成空LabelMe标注文件。
- 流程进入人工标注步骤。
- 能力接口返回不可用原因。
- 前端后续可显示“自动预标注不可用，请人工标注”，但本阶段不重构页面流程。

## 9. 平台专属能力

### 9.1 Creo

Windows同时满足以下条件才标记可用：

- `sys.platform == "win32"`
- Creo可执行文件存在。
- Creo基础目录和输出目录有效。
- Win32自动化依赖可以导入。

macOS和Linux返回：

```json
{
  "available": false,
  "applicable": false,
  "reason": "当前平台不支持Creo自动化"
}
```

这不是启动错误。

### 9.2 FreeCAD

FreeCAD为可选能力。检查Python库路径或可执行文件路径，缺失时返回降级状态，不阻止后端启动。

### 9.3 本地视觉分析器

本地OCR、规则引擎或语义增强模块缺失时：

- 模块导入不能阻止`backend.app`启动。
- 只有用户选择本地视觉模式并实际调用时才返回能力缺失错误。

## 10. 能力检测架构

新增独立服务模块，职责仅为检测，不执行业务任务：

```text
backend/services/capabilities.py
```

建议接口：

```python
def collect_capabilities() -> dict:
    ...

def require_capability(name: str) -> tuple[bool, str]:
    ...
```

检测结果不得包含API密钥、完整本地路径或其他敏感信息。

新增API：

```http
GET /api/system/capabilities
```

响应结构：

```json
{
  "ok": true,
  "python": {
    "available": true,
    "version": "3.11.15",
    "required": "3.11.15"
  },
  "database": {
    "available": true,
    "schema_ready": true
  },
  "pdf": {
    "available": true,
    "provider": "pymupdf",
    "reason": ""
  },
  "vision_api": {
    "available": true,
    "reason": ""
  },
  "yolo": {
    "available": false,
    "provider": null,
    "reason": "模型文件不存在"
  },
  "creo": {
    "available": false,
    "applicable": false,
    "reason": "当前平台不支持Creo自动化"
  },
  "freecad": {
    "available": false,
    "reason": "未检测到FreeCAD"
  }
}
```

HTTP 200表示能力检查成功执行，不代表所有可选能力可用。只有检测服务本身发生内部异常时返回5xx。

## 11. 启动检查

启动顺序：

```text
检查Python版本
→ 检查核心模块
→ 加载.env
→ 初始化数据库schema
→ 收集能力状态
→ 输出脱敏摘要
→ 启动Flask
```

阻断启动的条件：

- Python不是3.11。
- Flask等核心Web依赖无法导入。
- 数据库schema初始化失败。
- 输出目录无法创建或写入。

不阻断启动的条件：

- `.env`缺少某个模型API配置。
- PyMuPDF不可用。
- Poppler不可用。
- YOLO运行时或模型不存在。
- Creo、FreeCAD不存在。
- 本地视觉分析器的可选模块不存在。

上传或调用具体能力前必须再次执行轻量校验，避免启动后外部状态变化导致未经解释的后台异常。

## 12. 配置文件行为

`.env`不存在时：

- 初始化脚本从`.env.example`复制。
- 直接启动后端时不自动写文件，但输出明确提示。
- 健康检查和能力接口仍可访问。
- 调用需要密钥的接口时返回4xx配置错误。

日志只显示配置项是否存在和脱敏前缀，不输出完整密钥。

## 13. 安装与启动命令

### 13.1 macOS/Linux核心环境

```bash
uv python install 3.11.15
uv sync
cp .env.example .env
uv run python -m backend.run
```

### 13.2 YOLO环境

```bash
uv sync --extra yolo
uv run python -m backend.run
```

### 13.3 Windows核心环境

```powershell
uv python install 3.11.15
uv sync
Copy-Item .env.example .env
uv run python -m backend.run
```

### 13.4 Windows Creo环境

```powershell
uv sync --extra yolo --extra windows-creo
uv run python -m backend.run
```

现有`setup.bat`和`start.ps1`需要改为调用uv，不再自行创建不同来源的虚拟环境。

## 14. 测试设计

### 14.1 依赖测试

- Python版本为3.11.15。
- `uv lock --check`通过。
- 核心环境可以导入`backend.app`。
- 核心环境不要求torch、ultralytics或pywinauto。
- Windows额外依赖仅在Windows安装。

### 14.2 能力检测单元测试

通过mock覆盖：

- PyMuPDF可用。
- PyMuPDF不可用但Poppler可用。
- 两种PDF provider均不可用。
- ONNX模型与运行时可用。
- PT模型存在但Ultralytics缺失。
- 两种YOLO模型均不存在。
- macOS下Creo标记为不适用。
- Windows配置不完整时Creo不可用但适用。
- 空数据库自动初始化成功。

### 14.3 API测试

- `/api/health`在可选能力缺失时仍返回200。
- `/api/system/capabilities`结构稳定且不泄漏密钥。
- PDF能力缺失时PDF上传返回明确4xx。
- PDF能力缺失时PNG上传不被错误阻止。
- YOLO缺失时流程仍进入人工标注。

### 14.4 启动测试

- 非Windows导入`backend.app`不访问`ctypes.WinDLL`。
- 本地视觉可选模块缺失不阻止应用导入。
- 缺少模型API密钥不阻止健康检查。
- 数据库初始化失败时启动检查返回非零退出状态。

### 14.5 干净克隆验收

macOS和Windows至少分别验证：

1. 克隆仓库。
2. 安装uv和Python 3.11.15。
3. `uv sync`。
4. 创建`.env`。
5. 启动后端。
6. 访问健康检查和能力接口。
7. 上传PNG。
8. 上传PDF。
9. 验证YOLO缺失时人工标注降级。
10. 构建React前端。

## 15. CI设计

基础CI矩阵：

```text
macOS / Python 3.11
Windows / Python 3.11
```

每个平台执行：

```text
uv lock --check
uv sync --frozen
后端启动导入测试
核心单元测试
能力检测测试
前端npm ci
前端npm run build
```

CI不下载真实YOLO模型，不调用真实视觉或LLM API。相关行为通过临时模型文件和mock验证。

## 16. 兼容与迁移

- 现有`.venv`不强制复用。首次迁移建议删除后由uv重建。
- `requirements.txt`在每次锁文件更新后重新导出。
- 所有安装文档和启动脚本必须同步修改，避免用户继续执行旧入口。
- `.env`、数据库、模型和输出目录不进入Git。
- 迁移不修改已有SQLite业务数据。

## 17. 风险与缓解

| 风险 | 缓解 |
|------|------|
| torch在不同平台解析出不同构建 | 放入可选组，核心环境不依赖；优先ONNX |
| uv对部分团队成员陌生 | 提供四条以内的标准安装命令和兼容requirements导出 |
| 删除backend/requirements.txt影响旧脚本 | 同一提交修改全部脚本和文档，并用仓库搜索验证无引用 |
| PyMuPDF升级改变渲染结果 | 锁定版本，并对页数、尺寸和输出文件做回归测试 |
| 能力接口暴露本地信息 | 返回布尔值、provider和脱敏原因，不返回密钥或完整路径 |
| Windows Creo无法在普通CI运行 | 自动测试平台分支和配置检测；真实Creo用人工验收清单 |

## 18. 验收标准

设计实施完成必须满足：

1. `uv sync --frozen`在干净环境成功。
2. `uv run python --version`输出Python 3.11.15。
3. 不安装YOLO和Creo可选组时，`backend.app`可导入并启动。
4. PDF上传默认通过PyMuPDF处理。
5. `/api/system/capabilities`返回约定结构。
6. YOLO模型缺失时进入人工标注，不产生后端启动异常。
7. macOS不加载Win32 API。
8. 空SQLite数据库自动初始化。
9. 核心后端测试和前端生产构建通过。
10. README、INSTALL、START和平台启动脚本只提供统一的新流程。
