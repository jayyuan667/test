# yolo-react 远程开发文档同步设计

## 目标

让新开发者从 GitHub 克隆 `yolo-react` 分支后，仅依赖仓库中的说明和脚本即可完成环境初始化、配置、启动、构建与基本验证。

## 文档职责

- `README.md`：项目概览、架构、快速开始和常用命令。
- `INSTALL.md`：系统要求、首次安装、配置项和可选外部依赖。
- `START.md`：日常启动、分别调试、构建预览、停止服务和故障排查。
- `BRANCH_DEVELOPMENT.md`：分支隔离策略、端口和开发约束。
- `setup.bat`：Windows 首次初始化，安装 Python 与 Node 依赖并生成本地配置。
- `start.bat` / `start.ps1`：启动 Flask 后端与 React 开发服务器。

## 固定约束

- 后端端口：`5190`
- React 开发端口：`3200`
- React 预览端口：`3201`
- React 源码目录：`frontend-react/`
- `.env` 不提交，用户必须从 `.env.example` 创建并填写真实密钥。
- 数据库、历史记录、模型样本和构建产物不随 Git 分支分发。
- FreeCAD、Creo 和 Poppler 作为可选能力说明，不作为核心启动前置条件。

## 验收

1. 文档中不存在把 `2D-v` 当作当前目录的操作命令。
2. 文档中不存在旧端口 `5090/3100/3101` 的启动说明。
3. `setup.bat` 同时检查 Python、Node.js、npm，并安装两端依赖。
4. React 构建通过。
5. 修改后的 Python 文件语法检查通过。
6. 启动脚本语法检查通过。
7. 新提交推送到远端 `yolo-react`。
