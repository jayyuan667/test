# 用户认证与权限管理系统设计

> 日期：2026-06-24 | 状态：设计完成 | 分支：yolo-react

## 1. 概述

为二维工艺系统新增完整的多租户用户认证与权限管理体系。支持多企业独立使用，区分超级管理员、企业管理员、普通用户三种角色，实现基于 JWT 的无状态认证、推理配额控制、知识库上传校验。

---

## 2. 核心决策

| 决策项 | 方案 | 理由 |
|--------|------|------|
| 认证方式 | 用户名 + 密码，预留企业微信/LDAP 扩展接口 | 当前内网小团队使用，未来可扩展 |
| Session 管理 | JWT 存 HttpOnly Cookie，预留 Redis 升级路径 | 零依赖起步，架构抽象 SessionStore 接口方便日后切换 |
| 角色模型 | 超级管理员 / 企业管理员 / 普通用户 三层 | 支持多企业独立管理 + 全局管控 |
| 注册方式 | 开放注册，自动加入"未分配企业"，受限功能 | 降低管理员的创建负担 |
| 配额策略 | 新用户默认 10 次推理，累计制（企业管理员分配次数叠加），不清零 | 灵活且可追踪 |
| 企业管理员续期 | 超级管理员设置有效期，到期后该企业所有用户配额冻结 | 自然支持 SaaS 收费模式 |
| 数据存储 | 独立 SQLite（auth.db），抽象 UserStore 接口预留 MySQL/PG | 当前零依赖，架构上可替换 |
| 知识库校验 | 解压后文件数 >= 30，否则拒绝并提示 | 简单有效的质量控制 |

---

## 3. 角色与权限矩阵

| 能力 | 超级管理员 | 企业管理员 | 普通用户（未分配） | 普通用户（已分配） |
|------|:---:|:---:|:---:|:---:|
| 工艺生成（推理） | ✅ | ✅ | ❌ | ✅ |
| 工艺入库 | ✅ | ✅ | ❌ | ✅ |
| 历史记录 | ✅ | ✅ | ❌ | ✅ |
| 知识库浏览 | ✅ | ✅ | ❌ | ✅ |
| 个人中心 | ✅ | ✅ | ✅ | ✅ |
| 修改本企业用户配额 | ✅ | ✅ | ❌ | ❌ |
| 管理本企业用户 | ✅ | ✅ | ❌ | ❌ |
| 创建/停用企业 | ✅ | ❌ | ❌ | ❌ |
| 企业管理员续期 | ✅ | ❌ | ❌ | ❌ |
| 停用/注销任意用户 | ✅ | ❌ | ❌ | ❌ |
| 修改全局用户配额 | ✅ | ❌ | ❌ | ❌ |

---

## 4. 数据库模型（auth.db）

```sql
-- 企业/租户表
CREATE TABLE enterprises (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active   BOOLEAN DEFAULT 1
);

-- 用户表
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user',
    enterprise_id   INTEGER,
    is_active       BOOLEAN DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
);

-- 企业管理员授权表
CREATE TABLE enterprise_admin_grants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER UNIQUE NOT NULL,
    enterprise_id   INTEGER NOT NULL,
    granted_by      INTEGER NOT NULL,
    expires_at      TIMESTAMP NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (enterprise_id) REFERENCES enterprises(id),
    FOREIGN KEY (granted_by) REFERENCES users(id)
);

-- 推理配额表
CREATE TABLE quotas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    total_granted   INTEGER DEFAULT 10,
    used            INTEGER DEFAULT 0,
    granted_by      INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 关键业务规则

- **新用户注册**：自动创建 `role='user'`, `enterprise_id=NULL`, `quotas.total_granted=10`
- **企业管理员到期**：查询 `enterprise_admin_grants.expires_at < now()`，到期企业下所有用户推理被拒绝
- **配额校验**：`quotas.used < total_granted` AND `user.is_active=1` AND 企业管理员未到期
- **注销用户**：设置 `is_active=0`，数据保留不物理删除
- **超级管理员识别**：`role='super_admin'`，不依赖 enterprise_id

---

## 5. JWT 认证设计

### 5.1 JWT Payload

```json
{
    "sub": 123,
    "username": "zhangsan",
    "role": "enterprise_admin",
    "ent_id": 5,
    "iat": 1719234567,
    "exp": 1719320967
}
```

### 5.2 Cookie 配置

| 属性 | 值 | 说明 |
|------|-----|------|
| Key | `gn_token` | 避免冲突 |
| HttpOnly | `True` | 防 XSS |
| SameSite | `Lax` | 防 CSRF，允许同站跳转 |
| Secure | 生产环境 `True` | 仅 HTTPS |
| Max-Age | 86400s（24h） | 与 JWT exp 一致 |

### 5.3 认证流程

```
登录 POST /api/auth/login {username, password}
  -> bcrypt 验证密码
  -> 检查 is_active、企业管理员到期状态
  -> 签发 JWT -> Set-Cookie -> 返回 {user: {...}}

后续请求
  -> @login_required 装饰器
  -> 从 Cookie 取 gn_token -> 解密验证 -> 注入 request.current_user

登出 POST /api/auth/logout
  -> Clear Cookie
  -> (v2: token 加入 Redis 黑名单)
```

### 5.4 抽象层设计

```python
class TokenStore(ABC):
    def create_token(self, user) -> str: ...
    def validate_token(self, token) -> Optional[User]: ...
    def revoke_token(self, token) -> None: ...

class JWTTokenStore(TokenStore):   # v1 实现
class RedisTokenStore(TokenStore): # v2 实现
```

---

## 6. 后端架构

### 6.1 新增文件

```
backend/
├── auth_store.py      # 用户/企业/配额 数据库操作（与 task_store.py 同模式）
├── auth_service.py    # 认证业务逻辑（JWT签发/验证、密码hash）
├── auth_utils.py      # @login_required 装饰器、角色检查
└── api/
    ├── auth.py        # /api/auth/login, /api/auth/register, /api/auth/logout, /api/auth/me
    └── admin.py       # /api/admin/enterprises, /api/admin/users, /api/admin/quotas
```

### 6.2 现有文件修改

| 文件 | 改动 |
|------|------|
| `api/__init__.py` | 注册 `auth_bp`、`admin_bp` |
| `api/_response.py` | 新增 `ERR_UNAUTHORIZED`、`ERR_FORBIDDEN`、`ERR_QUOTA_EXCEEDED`、`ERR_ENTERPRISE_EXPIRED` |
| `api/upload.py` | 上传入口加 `@login_required` + `@require_quota` |
| `api/batch.py` | 批量上传入口加 `@login_required` + `@require_quota` |
| `api/kb_import.py` | ZIP 导入加文件数校验（>=30） |
| `app.py` | CORS 改为 `supports_credentials=True` + 显式 origin |

### 6.3 API 端点

```
# 认证
POST   /api/auth/login          # 登录
POST   /api/auth/register       # 注册
POST   /api/auth/logout         # 登出
GET    /api/auth/me             # 获取当前用户信息

# 用户
PUT    /api/user/password       # 修改密码
GET    /api/user/profile        # 个人中心信息（含配额）

# 管理（超级管理员 + 企业管理员）
GET    /api/admin/enterprises   # 企业列表
POST   /api/admin/enterprises   # 创建企业
PUT    /api/admin/enterprises/<id>  # 更新企业（停用/启用）
GET    /api/admin/users         # 用户列表（按企业筛选）
PUT    /api/admin/users/<id>    # 更新用户（配额/停用/角色）
POST   /api/admin/grants        # 企业管理员续期
GET    /api/admin/quotas        # 配额概览
```

### 6.4 装饰器

```python
@login_required           # 验证 JWT，注入 request.current_user
@require_role('admin')    # 角色检查
@require_quota            # 推理次数检查，通过后 used += 1
```

---

## 7. 前端架构

### 7.1 路由重构

```
App
├── AuthContext.Provider                    # 新增：全局认证状态
├── [未登录]
│   ├── /login       -> LoginPage           # 全屏，无 Sidebar
│   └── /register    -> RegisterPage        # 全屏，无 Sidebar
└── [已登录]
    └── AppLayout                          # 包含 Sidebar + main
        ├── /generate     -> GeneratePage   # 现有
        ├── /zip          -> ZipPage        # 现有
        ├── /history      -> HistoryPage    # 现有
        ├── /db           -> DbPage         # 现有
        ├── /profile      -> ProfilePage    # 新增
        └── /admin        -> AdminPage      # 新增（角色守卫）
```

### 7.2 新增文件

```
frontend-react/src/
├── contexts/
│   └── AuthContext.tsx        # 认证上下文（currentUser, login, logout, isAuthenticated）
├── pages/
│   ├── LoginPage.tsx          # 登录页
│   ├── RegisterPage.tsx       # 注册页
│   ├── ProfilePage.tsx        # 个人中心
│   └── admin/
│       ├── AdminPage.tsx      # 管理后台（路由容器）
│       ├── EnterpriseTab.tsx  # 企业管理 Tab
│       ├── UsersTab.tsx       # 用户管理 Tab
│       └── QuotaTab.tsx       # 配额概览 Tab
├── components/
│   └── shared/
│       ├── ProtectedRoute.tsx # 路由守卫
│       └── RoleBadge.tsx      # 角色 Badge
├── api/
│   └── client.ts              # 新增 auth API 函数 + credentials: 'include'
└── types/
    └── index.ts               # 新增 User, Enterprise, Quota 类型
```

### 7.3 现有文件修改

| 文件 | 改动 |
|------|------|
| `App.tsx` | 重构为认证感知路由（登录/未登录分叉） |
| `components/layout/Sidebar.tsx` | 根据角色显示/隐藏菜单项 + 新增"个人中心""管理后台" |
| `types/index.ts` | `PageId` 增加 `'profile'`、`'admin'` |
| `api/client.ts` | 所有请求加 `credentials: 'include'` |

### 7.4 Sidebar 菜单按角色

| 菜单项 | 普通用户 | 企业管理员 | 超级管理员 |
|--------|:---:|:---:|:---:|
| 工艺入库 | ✅ | ✅ | ✅ |
| 工艺生成 | ✅ | ✅ | ✅ |
| 历史记录 | ✅ | ✅ | ✅ |
| 知识库浏览 | ✅ | ✅ | ✅ |
| 个人中心 | ✅ | ✅ | ✅ |
| 管理后台 | - | ✅（本企业） | ✅（全局） |

---

## 8. UI 设计规范

### 8.1 设计基调

- **色彩策略**：Restrained（克制型），中性色主导，单一强调色 <10%
- **强调色**：`#f97316`（品牌橙色），新增 `#0369A1`（管理后台信息蓝）
- **字体**：Plus Jakarta Sans（替换现有默认）
- **动效**：最少化（150-200ms 过渡，仅 hover/active）
- **圆角**：统一 8px

### 8.2 组件规范

| 组件 | 规范 |
|------|------|
| 按钮-主要 | `bg-orange-500 hover:bg-orange-600 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors duration-150` |
| 按钮-次要 | `border border-slate-300 text-slate-700 hover:bg-slate-50 px-6 py-2.5 rounded-lg transition-colors duration-150` |
| 按钮-危险 | `text-red-600 hover:bg-red-50 px-4 py-2 rounded-lg transition-colors duration-150` |
| 输入框 | `border border-slate-300 rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 outline-none transition` |
| 卡片 | `bg-white border border-slate-200 rounded-lg p-6` |
| 表格 | `w-full text-sm`，thead `bg-slate-50 text-slate-600 font-medium`，tbody tr `border-b border-slate-100 hover:bg-slate-50` |
| Badge | `px-2.5 py-0.5 rounded-full text-xs font-medium` |
| Toast | 右上角固定，3-5 秒自动消失 |
| Modal | 居中弹出，`bg-black/40` 遮罩，白色卡片 8px 圆角 |

### 8.3 登录/注册页布局

- 全屏居中，无 Sidebar
- 背景色：`#F8FAFC`
- 表单卡片：白色背景 + 1px `#E2E8F0` 边框 + 8px 圆角
- Label 在输入框上方（非 placeholder-as-label）
- 密码框带显示/隐藏切换
- 错误提示：红色文字在对应字段下方

### 8.4 管理后台布局

- 顶部 Tab 切换（企业管理 / 用户管理 / 配额概览）
- 选中 Tab：底部 2px 橙色下划线
- 表格使用 `overflow-x-auto` 包裹
- 分页：底部居中
- 状态 Badge：绿色=正常，红色=到期，灰色=停用

---

## 9. 知识库上传校验

在现有 `/api/kb/import_zip` 端点增加前置校验：

```python
def validate_zip_file_count(zip_path: str, min_files: int = 30) -> Optional[str]:
    """解压后统计文件数，不足返回错误信息，否则返回 None"""
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zf:
        file_count = len([f for f in zf.namelist() if not f.endswith('/')])
    if file_count < min_files:
        return f"数据量太少，压缩包内文件数为 {file_count}，必须大于 {min_files} 个文件"
    return None
```

---

## 10. 安全性考虑

- 密码使用 `bcrypt` / `werkzeug.security` 哈希存储
- JWT secret key 从环境变量 `JWT_SECRET_KEY` 读取，开发环境自动生成
- 所有管理端 API 加 `@require_role` 校验
- Cookie 设置 HttpOnly + SameSite=Lax
- 推理次数扣减在 API 层原子操作（SQLite `UPDATE ... SET used = used + 1`）

---

## 11. 架构偏移防范

### 已识别的关键节点与对策

| 节点 | 风险 | 对策 |
|------|------|------|
| App.tsx 路由重构 | 登录页需在 Sidebar 之外 | 两层结构：未登录渲染 LoginPage，已登录渲染 AppLayout |
| CORS 配置 | `origins: "*"` 与 `credentials: 'include'` 冲突 | 改为显式 origin 配置 |
| 现有 API 客户端 | `fetch` 未带 credentials | 统一加 `credentials: 'include'` |
| 全局状态 | 无 Context，useState 散落 | 新增 AuthContext，不引入 Redux |
| Blueprint 注册 | 需遵循现有模式 | 新增 auth_bp/admin_bp，在 `api/__init__.py` 注册 |
| 数据库模式 | 现有 task_store.py 用原生 sqlite3 | auth_store.py 同目录、同模式 |

---

## 12. 依赖

### 后端新增

```
PyJWT>=2.8.0        # JWT 签发与验证
```

### 前端新增

无（纯 React + Tailwind CSS + fetch，无需额外库）

---

## 13. 不在本设计范围内

- 企业微信/LDAP 实际对接（仅预留接口）
- Redis 部署与集成（仅预留接口）
- 计费/支付系统
- 审计日志
- 多语言 i18n
