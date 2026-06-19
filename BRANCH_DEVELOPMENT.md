# yolo-react 分支开发说明

## 定位

`yolo-react` 是独立的 React/Flask 开发分支，可以直接从 GitHub 克隆，不依赖开发者机器上的 `2D-v` 或安装版目录。

## 固定目录

- `backend/`：Flask API 和业务流水线
- `frontend-react/`：React + Vite 前端
- `db_data/`：本地知识库数据，不提交 Git
- `uploads/`、`output/`：本地任务文件，不提交 Git

旧 `frontend/` 目录不属于该分支。所有 React 修改必须进入 `frontend-react/`。

## 固定端口

| 服务 | 端口 |
|---|---:|
| Flask 后端 | 5190 |
| React 开发服务器 | 3200 |
| React 构建预览 | 3201 |

不要将该分支改回原项目使用的 `5090/3100/3101`。

## 开发流程

```powershell
git clone -b yolo-react https://github.com/jayyuan667/test.git
cd test
.\setup.bat
```

配置 `.env` 后：

```powershell
.\start.bat
```

## 配置隔离

- 根目录 `.env`：后端本地密钥和外部工具路径。
- `frontend-react/.env`：可选的前端本地覆盖。
- 两个文件都不提交 Git。
- 可提交模板分别为 `.env.example` 和 `frontend-react/.env.example`。

## 依赖隔离

- Python 依赖安装到 `.venv/`。
- Node 依赖安装到 `frontend-react/node_modules/`。
- React 构建输出到 `frontend-react/dist/`。
- 这些目录全部由当前克隆独立维护。

## 提交前检查

```powershell
cd frontend-react
npm run build
cd ..

.\.venv\Scripts\python.exe -m compileall -q backend
git status
```

提交前确认没有包含：

- `.env`
- API Key 或私钥
- SQLite 数据库
- `node_modules`
- `dist`
- 上传文件、历史记录或测试截图
