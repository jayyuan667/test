# 安装说明

## 必需环境

| 软件 | 建议版本 | 用途 |
|---|---:|---|
| Git | 2.40+ | 克隆和分支管理 |
| Python | 3.11 或 3.12 | Flask 后端和 RapidOCR |
| Node.js | 20+ | React 前端 |
| npm | 随 Node.js 安装 | 前端依赖和构建 |

## Windows 自动安装

```powershell
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test
.\setup.bat
```

`setup.bat` 不会覆盖已有 `.env`，重复执行可用于补齐依赖。

## Windows 手动安装

```powershell
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

cd frontend-react
npm install
cd ..

Copy-Item .env.example .env
New-Item -ItemType Directory -Force db_data, uploads, output | Out-Null
```

编辑 `.env` 并填写真实 API Key。

> Python 3.13 当前不兼容 `rapidocr-onnxruntime`。Windows 的 `setup.bat` 会优先选择 Python 3.11，其次选择 3.12。

## Linux/macOS 手动安装

```bash
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

cd frontend-react
npm install
cd ..

cp .env.example .env
mkdir -p db_data uploads output
```

`start.ps1` 仅适用于 Windows。Linux/macOS 请分别运行前后端。

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
```

如果不使用某项能力，可保留占位值，但调用该能力时会失败或降级。

## 前端配置

默认配置已写入 `frontend-react/.env.example`：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:5190/api
VITE_BACKEND_URL=http://127.0.0.1:5190
```

一般无需创建 `frontend-react/.env`。需要覆盖配置时：

```powershell
Copy-Item frontend-react\.env.example frontend-react\.env
```

## 可选依赖

### Poppler

仅在 PDF 转换后备路径需要。Windows 可在 `.env` 设置：

```dotenv
POPPLER_PATH=D:\tools\poppler\Library\bin
```

### FreeCAD

PRT/STEP 几何分析和视图生成需要。可设置：

```dotenv
FREECAD_LIB=D:\Program Files\FreeCAD 1.1\lib
FREECAD_BIN=D:\Program Files\FreeCAD 1.1\bin
```

### Creo

Creo 能力依赖本机 Creo 安装以及 `backend/config.json` 中的路径配置。

### OnShape

在线 PRT 转换需要在 `.env` 配置：

```dotenv
onshape_credentials="..."
onshape_did="..."
onshape_wid="..."
```

## 安装验证

```powershell
.\.venv\Scripts\python.exe -c "import flask; print('backend dependencies: OK')"

cd frontend-react
npm run build
cd ..
```

若两条命令均成功，则基础环境安装完成。
