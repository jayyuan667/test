# 启动与调试

## 首次启动

```bash
./setup.sh   # macOS/Linux
```

或

```powershell
.\setup.bat  # Windows
```

然后编辑 `.env` 填写真实模型配置。

## macOS / Linux 一键启动

```bash
./start.sh
```

## Windows 一键启动

```powershell
.\start.ps1
```

启动：

- Flask 后端：`5190`
- React 开发服务器：`3200`

按 `Ctrl+C` 停止。脚本退出时会清理前后端进程。

## 分别调试

### 后端

```bash
FLASK_DEBUG=0 uv run python -m backend.run
```

验证：

```bash
curl http://127.0.0.1:5190/api/health
curl http://127.0.0.1:5190/api/system/capabilities
```

### 前端

```bash
cd frontend-react
npm run dev
```

访问：http://127.0.0.1:3200

## 生产构建与预览

```bash
cd frontend-react
npm run build
npm run preview
```

访问：http://127.0.0.1:3201

构建完成后，也可以只启动后端，并访问 http://127.0.0.1:5190/（后端会加载 `frontend-react/dist`）。

## 环境诊断

```bash
uv run python scripts/runtime_smoke.py
```

该脚本检查 Python 版本、数据库、PDF、YOLO、Creo、FreeCAD 等能力状态，核心能力失败会报错，可选能力不可用仅打印警告。

也支持运行时查询：

```bash
curl http://127.0.0.1:5190/api/system/capabilities
```

## 常见问题

### `uv` 命令不存在

安装 uv：https://docs.astral.sh/uv/getting-started/installation/

```bash
brew install uv       # macOS
```

或

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
```

### `.env` 仍是占位值

现象：视觉模型、向量或 LLM 请求鉴权失败。

处理：编辑根目录 `.env`，填写实际 API Key。仓库不会分发密钥。

### `db_data` 中没有数据库

这是干净克隆的正常状态。系统可启动，但 RAG 和知识库浏览没有记录。通过知识库导入功能创建本地数据。

### Python 版本不正确

```bash
uv python install 3.11.15
uv sync --locked
```

### 端口被占用

```bash
lsof -i :5190 -i :3200  # macOS/Linux
```

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 5190,3200,3201  # Windows
```

### PDF、PRT 或 Creo 功能不可用

核心服务不依赖这些外部工具。PDF 依赖 PyMuPDF（`uv sync` 自动安装），YOLO 缺失时降级为人工标注，Creo 仅适用于 Windows。详细配置见 [INSTALL.md](INSTALL.md)。
