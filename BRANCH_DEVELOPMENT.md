# 2D-r 分支开发说明

## 目录定位

`F:\Work_Dir\2D-r` 是从 `2D-v` 复制出的独立开发副本。源目录未被剪切或删除。

主要目录：

- `backend/`：Flask 后端
- `frontend-react/`：React + Vite 前端
- `frontend-react/node_modules/`：本副本的前端依赖
- `frontend-react/dist/`：本副本的生产构建产物
- `db_data/`：本副本的运行数据

本副本不包含旧的 `frontend/` 目录，React 前端统一使用 `frontend-react/`。

## 独立端口

| 服务 | 地址 |
|---|---|
| Flask 后端与生产构建 | `http://127.0.0.1:5190` |
| 后端健康检查 | `http://127.0.0.1:5190/api/health` |
| React 开发服务器 | `http://127.0.0.1:3200` |
| React 构建预览 | `http://127.0.0.1:3201` |

这些端口与原项目的 `5090/3100/3101` 分离。

## 一键启动开发环境

在 PowerShell 中运行：

```powershell
cd F:\Work_Dir\2D-r
.\start.ps1
```

脚本会启动后端 `5190` 和 React 开发服务器 `3200`。

## 分别启动和调试

后端：

```powershell
cd F:\Work_Dir\2D-r
$env:FLASK_DEBUG = "0"
python -m backend.run
```

前端：

```powershell
cd F:\Work_Dir\2D-r\frontend-react
npm install
npm run dev
```

前端开发服务器会把 `/api` 请求代理到 `http://127.0.0.1:5190`。

## 构建

```powershell
cd F:\Work_Dir\2D-r\frontend-react
npm run build
```

构建完成后，后端根地址 `http://127.0.0.1:5190/` 会加载 `frontend-react/dist`。

## 配置隔离

- 后端本地配置位于项目根目录 `.env`，该文件已被 `.gitignore` 忽略。
- 可提交的配置模板为根目录 `.env.example`。
- 前端配置位于 `frontend-react/.env` 和 `frontend-react/.env.example`。
- 不要把 `2D-v` 的绝对路径写入本副本的运行配置。

## 当前验证结果

- `npm install`：通过，无已知 npm 漏洞
- `npm run build`：通过
- `python -m compileall -q backend`：通过
- 后端 `5190/api/health`：HTTP 200
- 后端生产页面 `5190/`：HTTP 200
- React 开发页面 `3200/`：HTTP 200
