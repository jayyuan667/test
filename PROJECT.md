# 共享项目说明

> `AGENTS.md` 和 `CLAUDE.md` 都只作为入口文件。公共项目背景、协作约定和任务边界以本文件为准。

## 项目定位

- 名称：二维工艺系统 (2D Process Intelligence)
- 一句话定位：AI 辅助的二维图纸工艺编制系统，支持 PDF/PRT 图纸分析、工序生成、知识库管理
- 当前阶段：yolo-react 分支 — React 前端迁移 + 用户认证系统刚完成，待测试和完善

## 术语与风格约定

- 后端：Python 3.11+，Flask + sqlite3，Blueprint 路由模式
- 前端：React 18 + TypeScript + Tailwind CSS 3 + Vite，不使用 react-router
- API 响应格式：统一 `{success: true, data: {...}}`（成功）或 `{success: false, error: {code, message}}`（失败）
- 数据库：task_store.py（任务状态，task_store.db）和 auth_store.py（认证，auth.db）使用相同的 sqlite3+WAL 模式
- Cookie key：`gn_token`（JWT，HttpOnly，SameSite=Lax）
- 前端路由：useState 状态驱动，无 react-router，pages 通过 lazy-mount 保持状态

## 当前重点

1. **用户认证系统刚完成**（2026-06-24）：JWT 登录/注册、三种角色（超级管理员/企业管理员/普通用户）、推理配额控制、管理后台。详见 `docs/superpowers/specs/2026-06-24-user-auth-system-design.md`。
2. **已知待办**（见 `docs/superpowers/HANDOFF-user-auth-system.md`）：
   - Toast 在登录/注册页不显示（useToast 是局部状态，需要改为全局 Context 或通过回调）
   - 企业管理员续期 Modal 需从输入用户 ID 改为下拉选择
   - 缺少单元测试（pytest + Playwright）
   - 生产环境 CORS origin 配置
3. **全链路测试**：登录 → 注册 → 配额消耗 → 管理员操作完整流程

## 适合 Codex 承担的任务

典型任务：

- 精确的 grep / pattern 匹配与定位
- 事实/一致性核查（配置项、常量、接口签名、引用）
- 合规扫描（命名规范、格式、死链 / 断引用）
- 按模块 / 目录的统计与对比

本项目中还适合：

- 编写 pytest 测试（后端 auth_store、auth_service、API 端点）
- 编写 Playwright e2e 测试（登录/注册/管理后台流程）
- 前端 Bug 修复（Toast 全局化、企业管理员下拉选择）
- 代码风格和一致性问题扫描
- 静态分析：检查是否有未使用的导入、死代码、类型不一致

不适合在未获明确确认时承担：

- 架构级别的设计决策
- 新增大型功能模块
- 修改已确立的 API 契约

不确定任务边界时，通过 `.handoff/PROTOCOL.md` 回 `question` 澄清，不要硬做。

## 已知环境坑

- 系统 Python 是 3.9（不支持 `str | None` 语法），必须用 `.venv/bin/python3` 或 `uv run python`
- Vite 前端通过 proxy 将 `/api` 转发到 `http://127.0.0.1:5190`，开发环境无需处理 CORS
- 前端 `useToast` 钩子是局部状态（每个组件独立），不是全局 Context，登录/注册页的 toast 不会显示
- auth.db 首次启动时自动创建并插入 admin/admin123 超级管理员（配额 999999）
- `request<T>()` 返回后端的完整 JSON 响应，auth/admin 接口需要用 `authRequest<T>()` 自动解包 `.data`
