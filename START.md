# 启动与调试

## 首次启动

```powershell
.\setup.bat
```

然后编辑 `.env` 填写真实模型配置。

## Windows 一键启动

```powershell
.\start.bat
```

`start.bat` 调用 `start.ps1`，启动：

- Flask 后端：`5190`
- React 开发服务器：`3200`

浏览器会自动打开 http://127.0.0.1:3200。

按 `Ctrl+C` 停止联合启动脚本。脚本退出时会停止它创建的前后端进程。

## 分别调试

### 后端

```powershell
.\.venv\Scripts\Activate.ps1
$env:FLASK_DEBUG = "0"
python -m backend.run
```

验证：

```powershell
Invoke-RestMethod http://127.0.0.1:5190/api/health
```

### 前端

打开另一个终端：

```powershell
cd frontend-react
npm run dev
```

访问：http://127.0.0.1:3200

## 生产构建与预览

```powershell
cd frontend-react
npm run build
npm run preview
```

访问：http://127.0.0.1:3201

构建完成后，也可以只启动后端，并访问：

```text
http://127.0.0.1:5190/
```

后端会加载 `frontend-react/dist`。

## 常用验证

检查端口：

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -In 5190,3200,3201 |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

检查 React 构建：

```powershell
cd frontend-react
npm run build
```

检查后端语法：

```powershell
cd ..
.\.venv\Scripts\python.exe -m compileall -q backend
```

## 常见问题

### `.env` 仍是占位值

现象：视觉模型、向量或 LLM 请求鉴权失败。

处理：编辑根目录 `.env`，填写实际 API Key。仓库不会分发密钥。

### `db_data` 中没有数据库

这是干净克隆的正常状态。系统可启动，但 RAG 和知识库浏览没有记录。通过知识库导入功能创建本地数据。

### 端口被占用

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -In 5190,3200,3201
```

确认进程属于本项目后再停止：

```powershell
Stop-Process -Id <PID>
```

### `npm` 命令不存在

安装 Node.js 20+，重新打开终端后运行：

```powershell
node --version
npm --version
```

### Python 依赖安装失败

先确认 Python 版本为 3.11 或 3.12：

```powershell
.\.venv\Scripts\python.exe --version
```

Python 3.13 不兼容当前 OCR 依赖。如版本不正确，删除 `.venv` 并重新运行 `setup.bat`。

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### PDF、PRT 或 Creo 功能不可用

核心服务不依赖这些外部工具，但相应处理功能需要 Poppler、FreeCAD、Creo 或 OnShape。配置方式见 [INSTALL.md](INSTALL.md)。
