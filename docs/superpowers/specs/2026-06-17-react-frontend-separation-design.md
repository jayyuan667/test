# React 前端独立分离设计

## 目标

在不破坏当前项目可运行性的前提下，复制出一个可独立启动、独立调试、独立管理依赖与配置的 React 前端子工程。新子工程作为“干净版本”存在，和现有后端保持联调，但不再依赖根目录里的前端源码组织方式。

## 设计原则

1. 复制，不剪切。原项目保留，避免一次性迁移引入回退风险。
2. 前端独立，后端复用。React 工程独立维护，Flask 后端继续使用现有 `backend/`。
3. 开发态和打包态分离。React 子工程负责源码、测试、构建；安装包工程只消费它的产物。
4. 边界清晰。前端只通过环境变量和 API 与后端通信，不直接读取后端内部状态。

## 推荐方案

推荐采用“同仓库双工程”结构：

- 根目录保留当前 `backend/`、安装包工程和少量编排脚本。
- 新增 `frontend-react/` 作为完整 React 工程副本。
- 以后 React 的所有依赖、配置、测试、构建产物都只落在 `frontend-react/`。

这样做的好处是：

- 目录边界清楚。
- 可以单独启动 React 调试。
- 不破坏现有后端和安装包链路。
- 后续如果要迁成独立仓库，只需要再做一次导出。

## 目录结构

```text
2D-v/
├─ backend/
│  ├─ app.py
│  ├─ api/
│  ├─ pipeline/
│  ├─ services/
│  └─ ...
├─ frontend/
│  └─ 旧前端目录，保留过渡与兼容
├─ frontend-react/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ vite.config.*
│  ├─ tsconfig*.json
│  ├─ src/
│  ├─ public/
│  ├─ tests/
│  ├─ .env
│  └─ dist/
├─ docs/
├─ scripts/
└─ install / packaging 工程
```

## 复制范围

### 复制到 `frontend-react/` 的内容

- React 源码
- 组件、页面、工具函数
- Vite 构建配置
- TypeScript 配置
- 前端测试
- Playwright 或 webapp-testing 相关脚本
- 前端独立环境变量文件
- 前端静态资源

### 不复制或不再共享的内容

- 后端 Python 代码
- 后端任务存储和 pipeline
- 安装包工程的后端部分
- 根目录中只服务于旧前端的临时脚本

## 依赖与配置分离

### React 子工程独立拥有

- `package.json`
- `package-lock.json`
- `node_modules`
- `vite.config.*`
- `tsconfig*.json`
- `.env`, `.env.local`, `.env.production`
- 前端专用测试配置

### 后端继续独立拥有

- `backend/requirements.txt`
- Python 虚拟环境
- `backend/config.json`
- `backend/task_store.db`
- `backend/output/`
- `backend/uploads/`

### 通信边界

React 子工程只通过这些方式和后端交互：

- HTTP API
- SSE `/api/events/<task_id>`
- 静态结果资源 `/api/result/<task_id>/asset/...`

不允许前端直接读取后端内部文件结构作为业务依赖。

## 独立启动方式

### 开发启动

React 子工程应支持独立开发：

```bash
cd frontend-react
npm install
npm run dev
```

默认通过环境变量或本地开发配置连接后端，例如：

- `VITE_API_BASE_URL=http://127.0.0.1:5090`
- `VITE_BACKEND_ORIGIN=http://127.0.0.1:5090`

### 调试启动

前端调试时应能单独启动前端服务，再连接已经运行的后端服务。这样前端问题和后端问题可以分开排查。

## 打包方式

打包流程应以 `frontend-react/dist` 为唯一 React 产物来源：

1. 在 `frontend-react` 中构建前端。
2. 将 `dist` 放入安装包工程的资源目录或复制到后端静态目录。
3. 再执行安装包生成。

这样安装包消费的是“React 子工程的构建结果”，而不是根目录旧前端的临时产物。

## 与现有项目的关系

| 项目 | 角色 |
|---|---|
| `backend/` | 继续作为后端主工程。 |
| `frontend/` | 保留为旧前端过渡目录，不作为未来主入口。 |
| `frontend-react/` | 新的 React 主工程。 |
| 安装包工程 | 读取 `frontend-react/dist` 作为前端产物。 |

## 迁移顺序

### 第一阶段：复制骨架

复制 React 源码和配置到 `frontend-react/`，让它先能独立安装和启动。

### 第二阶段：补齐独立配置

把前端环境变量、代理、测试脚本、构建输出路径全部改成子工程自包含。

### 第三阶段：验证独立运行

确认 `frontend-react` 能单独跑起来，并能连到现有后端完成完整页面调试。

### 第四阶段：切换打包入口

安装包工程改为消费 `frontend-react/dist`。

### 第五阶段：保留旧目录过渡

旧 `frontend/` 暂时保留，等新工程稳定后再决定是否废弃。

## 风险与约束

1. 复制后会出现两套前端源码，必须明确“哪一套是当前主版本”。
2. 两套前端共存时，脚本和文档必须标清楚入口，避免误改旧目录。
3. 如果安装包还在引用旧前端产物，就会出现“新前端改了但安装包没变”的假象。
4. 后端接口不能为了适配新结构而同时兼容两套不一致的前端约定，否则边界又会被污染。

## 验收标准

这次拆分完成后，至少满足下面几点：

1. `frontend-react` 可以独立 `npm install` 和 `npm run dev`。
2. 前端配置不再依赖根目录共享的隐式状态。
3. 后端不需要改成双份工程，也不需要复制一份 Python 服务。
4. 安装包工程能明确指向 `frontend-react/dist`。
5. 旧 `frontend/` 仍然能保留，不影响当前可运行状态。

## 结论

这不是简单搬目录，而是复制出一个“独立可运行、独立可维护”的 React 子工程。当前最稳妥的做法是保留旧工程，新增 `frontend-react/` 作为新主版本，并逐步把构建、测试和安装包入口切过去。

