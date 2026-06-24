# 用户认证与权限系统 — 交接文档

> 日期：2026-06-24 | 分支：yolo-react | 状态：后端完成，前端核心完成

## 概述

为二维工艺系统新增了完整的多租户用户认证与权限管理体系。13 次提交，28 个文件变更（+2475 行）。

## 快速启动

```bash
# 后端
cd /Users/caojiayuan/Projects/work/test
uv run python -m backend.app     # 端口 5190
# 或: .venv/bin/python3 -m backend.app

# 前端
cd /Users/caojiayuan/Projects/work/test/frontend-react
npm run dev                       # 端口 3200，自动代理 /api → 5190
```

**默认管理员账号**：`admin` / `admin123`（超级管理员，配额 999999 次）

## 新增后端文件

| 文件 | 职责 |
|------|------|
| `backend/auth_store.py` | SQLite 数据库层（auth.db），4 张表：enterprises、users、enterprise_admin_grants、quotas |
| `backend/auth_service.py` | JWT 签发/验证、密码哈希、用户注册逻辑 |
| `backend/auth_utils.py` | Flask 装饰器：@login_required、@require_role、@require_quota |
| `backend/api/auth.py` | 认证端点 Blueprint：/api/auth/login、register、logout、me，/api/user/profile、password |
| `backend/api/admin.py` | 管理端点 Blueprint：/api/admin/enterprises、users、grants、quotas |

## 修改的后端文件

| 文件 | 改动 |
|------|------|
| `backend/config.py` | 新增 `get_jwt_secret()` — 从环境变量读取 JWT secret |
| `backend/api/_response.py` | 新增错误码：ERR_UNAUTHORIZED、ERR_FORBIDDEN、ERR_QUOTA_EXCEEDED、ERR_ENTERPRISE_EXPIRED、ERR_USER_EXISTS |
| `backend/api/__init__.py` | 注册 auth_bp、admin_bp |
| `backend/app.py` | CORS 改为显式 origin + supports_credentials=True |
| `backend/api/upload.py` | 上传端点加 @login_required + @require_quota |
| `backend/api/batch.py` | 批量上载端点加 @login_required + @require_quota |
| `backend/api/kb_import.py` | ZIP 导入加文件数校验（>= 30） |
| `pyproject.toml` | 新增 PyJWT 依赖 |

## 新增前端文件

| 文件 | 职责 |
|------|------|
| `frontend-react/src/types/auth.ts` | User、Enterprise、QuotaInfo、AdminUser 类型定义 |
| `frontend-react/src/contexts/AuthContext.tsx` | 全局认证状态（AuthProvider + useAuth hook） |
| `frontend-react/src/pages/LoginPage.tsx` | 全屏登录页 |
| `frontend-react/src/pages/RegisterPage.tsx` | 全屏注册页 |
| `frontend-react/src/pages/ProfilePage.tsx` | 个人中心（账户信息、配额、改密码） |
| `frontend-react/src/pages/admin/AdminPage.tsx` | 管理后台容器（Tab 切换） |
| `frontend-react/src/pages/admin/EnterpriseTab.tsx` | 企业管理（新建/停用/续期） |
| `frontend-react/src/pages/admin/UsersTab.tsx` | 用户管理（分配企业/修改配额/停用） |
| `frontend-react/src/pages/admin/QuotaTab.tsx` | 配额概览 |
| `frontend-react/src/api/client.ts` | 新增 authRequest 辅助 + 13 个 auth/admin API 函数 |

## 修改的前端文件

| 文件 | 改动 |
|------|------|
| `App.tsx` | 重构为 AuthProvider > AppShell > AppLayout 三层结构 |
| `types/index.ts` | PageId 扩展：'profile'、'admin'、'login'、'register' |
| `components/layout/Sidebar.tsx` | 角色菜单 + 退出登录按钮 |
| `api/client.ts` | 所有 fetch 加 credentials、新增 auth/admin 函数 |

## 关键架构决策

- **认证**：JWT 存 HttpOnly Cookie（gn_token），SameSite=Lax，Max-Age=24h
- **角色**：super_admin / enterprise_admin / user 三层
- **配额**：新用户默认 10 次，累计制；企业管理员分配到期的用户配额冻结
- **API 响应格式**：统一 `{success: true, data: {...}}`，前端用 `authRequest<T>()` 自动解包 `.data`
- **前端路由**：无 react-router，用 useState 状态切换 + lazy-mount 模式
- **Vite 代理**：`/api` → `http://127.0.0.1:5190`（开发环境无需跨域）
- **数据库**：auth.db 单独文件，与 task_store.db 隔离，遵循同样的 sqlite3+WAL 模式

## 已知待办

1. **前端 Toast 在登录/注册页不显示**：`useToast` 是局部状态，非全局 Context；登录/注册页的 ToastStack 在 AppShell 中，但 LoginPage 调用 `useToast()` 创建了独立的状态实例。需要将 Toast 做成全局 Context 或通过回调传递。

2. **企业管理员续期需要输入用户 ID**（EnterpriseTab 的 Modal）：目前是手动输入数字 ID，应该改成下拉选择用户。

3. **注册成功后的 toast 提示**因问题 1 不可见，但导航到登录页正常。

4. **前端构建后生产部署**：需要确保生产环境 CORS origin 配置正确（当前只写了 localhost 地址）。

5. **无单元测试**：后端 auth_store/auth_service 有基本的 Python 验证脚本，但缺少正式的 pytest 测试；前端无测试。

## 参考文档

- 设计文档：`docs/superpowers/specs/2026-06-24-user-auth-system-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-24-user-auth-system-plan.md`
- 进度记录：`.superpowers/sdd/progress.md`
