# 安装说明

## 必需环境

| 软件 | 建议版本 | 用途 |
|---|---:|---|
| Git | 2.40+ | 克隆和分支管理 |
| uv | 0.11.22+ | Python 环境和依赖管理 |
| Python | 3.11.15 | 通过 uv 自动安装 |
| Node.js | 20+ | React 前端 |
| npm | 10+ | 前端依赖和构建 |

## macOS / Linux

### 自动安装

```bash
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test
./setup.sh
```

`setup.sh` 不会覆盖已有 `.env`，重复执行可用于补齐依赖。

### 手动安装

```bash
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test

uv python install 3.11.15
uv sync --locked
cp .env.example .env
mkdir -p db_data uploads output
npm --prefix frontend-react ci
```

编辑 `.env` 并填写真实 API Key。

## Windows

### 自动安装

```powershell
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test
.\setup.bat
```

### 手动安装

```powershell
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test

uv python install 3.11.15
uv sync --locked
Copy-Item .env.example .env
mkdir db_data uploads output
npm --prefix frontend-react ci
```

## 可选能力安装

YOLO 预标注由独立 GPU 推理服务提供。后端通过 `YOLO_SERVICE_URL` 调用 GPU 服务，无需在本地安装 ultralytics/torch。

- `uv sync --extra yolo` 仅 GPU 服务端需要；后端不需要安装 ultralytics/torch

Windows Creo 自动化（仅 Windows）：

```bash
uv sync --locked --extra windows-creo
```

## 后端配置

根目录 `.env` 是后端实际配置文件，不提交 Git。

核心配置：

```dotenv
VISION_API_KEY="..."
VISION_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
VISION_MODEL_ID="doubao-seed-2-0-mini-260215"

EMBEDDING_API_KEY="..."
EMBEDDING_BASE_URL="https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
EMBEDDING_MODEL="doubao-embedding-vision-251215"

LLM_API_KEY="..."
LLM_BASE_URL="https://api.deepseek.com/v1"
LLM_MODEL="deepseek-chat"

# YOLO GPU 服务（可选，缺省时降级为本地模型）
YOLO_SERVICE_URL="http://127.0.0.1:8000"
YOLO_SERVICE_TOKEN="your-token-here"
```

如果不使用某项能力，可保留占位值，但调用该能力时会失败或降级。

## 前端配置

默认配置已写入 `frontend-react/.env.example`：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5190/api
VITE_BACKEND_URL=http://127.0.0.1:5190
```

一般无需创建 `frontend-react/.env`。

## YOLO 模型

系统通过独立 GPU 推理服务提供 YOLO 预标注。后端默认通过 `YOLO_SERVICE_URL` 调用 GPU 服务。

本地模型文件（`best.onnx` / `best.pt` 放入 `db_data/`）仅作为 legacy fallback：

- `best.onnx` — ONNX 格式模型（fallback 优先）
- `best.pt` — PyTorch 格式模型（fallback 回退）

可创建 `db_data/model-manifest.json`（参考 `model-manifest.example.json`）来校验本地模型完整性。GPU 服务和本地模型均不可用时系统自动降级为人工标注。

## Poppler（兼容回退）

仅在 PyMuPDF 不可用时作为 PDF 转换后备路径。macOS：

```bash
brew install poppler
```

Windows 可在 `.env` 设置：

```dotenv
POPPLER_PATH=D:\tools\poppler\Library\bin
```

## FreeCAD

PRT/STEP 几何分析和视图生成需要。可设置：

```dotenv
FREECAD_LIB=D:\Program Files\FreeCAD 1.1\lib
FREECAD_BIN=D:\Program Files\FreeCAD 1.1\bin
```

## Creo（仅 Windows）

Creo 能力依赖本机 Creo 安装以及 `backend/config.json` 中的路径配置。

## OnShape

在线 PRT 转换需要在 `.env` 配置：

```dotenv
onshape_credentials="..."
onshape_did="..."
onshape_wid="..."
```

## 安装验证

```bash
uv run python scripts/runtime_smoke.py
npm --prefix frontend-react run build
curl http://127.0.0.1:5190/api/system/capabilities
```

若两条命令均成功，则基础环境安装完成。
