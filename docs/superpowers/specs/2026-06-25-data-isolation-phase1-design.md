# 数据隔离一期：企业级租户隔离（Discriminator Column 方案）

> **目标**：在不动数据库架构的前提下，通过业务表加 `enterprise_id` 列 + API 层强制过滤 + 前端默认行为修正，实现企业间数据不可互见的硬隔离。
> **范围**：后端 API 强制过滤 + 前端默认 scope 修正 + 全量测试。
> **原则**：轻量、可交付、为二期文件级隔离打基础。数据泄漏风险最高的默认行为先堵。

---

## 1. 隔离模型

```
┌─────────────────────────────────────────────────────┐
│  auth.db（全局）                                      │
│  users.enterprise_id  ← 用户 → 企业的权威绑定         │
│  super_admin: enterprise_id = NULL（可跨企业）         │
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │ 企业 A   │    │ 企业 B   │    │ 企业 C   │
   │ 业务数据  │    │ 业务数据  │    │ 业务数据  │
   └─────────┘    └─────────┘    └─────────┘

隔离边界：
  - 企业间：强隔离（API 层自动注入 enterprise_id，不可跳过）
  - 平台公共库（scope_type=public）：全局可读，不可写
  - 个人工艺库（scope_type=private）：企业内 user_id 过滤
  - super_admin：可跨企业查看，但需显式传参（不可无意识跨企业）
```

---

## 2. 受影响的数据库表

### 2.1 task_store.db（任务记录 + 历史）

| 表 | 当前 | 加列 |
|---|---|---|
| `tasks` | task_id, pdf_name, status, ... | `enterprise_id INTEGER` |
| `task_events` | task_id, event_type, ... | **不加**（通过 JOIN tasks 获取） |
| `task_results` | task_id, result_json, ... | **不加**（通过 JOIN tasks 获取） |
| `prt_cache` | file_hash, task_id, ... | **不加**（通过 JOIN tasks 获取） |

**理由**：`tasks` 是根实体，子表通过 `task_id` 关联即可推导企业归属。每行只存一份 `enterprise_id` 减少不一致风险。

### 2.2 vectors.db（知识库）

| 表 | 当前 | 加列 |
|---|---|---|
| `kb_library_scopes` | library_key, scope_type, ... | `enterprise_id INTEGER` |
| `kb_import_batches` | batch_id, zip_name, ... | `enterprise_id INTEGER` |
| `kb_import_items` | batch_id, prefix, ... | **不加**（通过 JOIN kb_import_batches） |
| `vectors_v2` | prefix, vector, ... | `enterprise_id INTEGER` |
| `vectors_<key>`（动态 scope 表） | 同 vectors_v2 结构 | `enterprise_id INTEGER` |

**注意**：`scope_type = 'public'` 的 scope（`library_key = 'public'`）其 `enterprise_id` 设为 `NULL`，表示平台级，所有企业可读。

### 2.3 不加列的表

| 表 | 原因 |
|---|---|
| `auth.db` 全部表 | 已有 `enterprise_id`，且 super_admin 需跨企业查询 |
| `kb_import_items` | 通过 `batch_id` JOIN 即可获得企业归属 |
| `task_events` / `task_results` | 通过 `task_id` JOIN 即可 |

---

## 3. API 层强制过滤机制

### 3.1 核心中间件：`get_enterprise_scope()`

```python
# backend/api/_utils.py 新增

from flask import g

def get_enterprise_scope():
    """
    返回当前请求的企业过滤条件。

    Returns:
        (enterprise_id: int | None, is_super_admin: bool)

    规则：
      - super_admin：返回 (None, True)，不做企业过滤
      - enterprise_admin / user：返回 (g.current_user['enterprise_id'], False)，强制过滤
      - 未分配企业用户：返回 (None, False)，只能看公共库
    """
    user = g.current_user
    role = user.get('role', 'user')
    if role == 'super_admin':
        return None, True
    enterprise_id = user.get('enterprise_id')
    if enterprise_id is None:
        return None, False  # 未分配企业用户
    return enterprise_id, False
```

### 3.2 各 API 端点的过滤注入

| API 端点 | 注入方式 |
|---|---|
| `GET /api/library/records` | `WHERE enterprise_id = ? OR enterprise_id IS NULL`（公共库） |
| `GET /api/library/records/<id>` | 读后校验 `record['enterprise_id'] in (None, user_enterprise_id)` |
| `PUT /api/library/records/<id>` | 写前校验：必须属于当前企业 |
| `DELETE /api/library/records/<id>` | 同上 |
| `POST /api/library/commit` | draft 写入时自动带 `enterprise_id` |
| `GET /api/library/scopes` | 只返回 `enterprise_id = ? OR scope_type = 'public'` |
| `DELETE /api/library/scopes/<key>` | 校验 scope 属于当前企业 |
| `GET /api/history` | `WHERE enterprise_id = ?`（super_admin 不过滤） |
| `GET /api/status/<task_id>` | 读后校验 task 属于当前企业 |
| `POST /api/upload` | task 创建时写入 `enterprise_id` |
| `POST /api/kb/import_zip` | batch 创建时写入 `enterprise_id` |
| `GET /api/result/<task_id>` | 读后校验 task 属于当前企业 |

### 3.3 super_admin 的显式跨企业开关

```python
# super_admin 调用时，可选传 ?enterprise_id=X 来限定查看范围
# 如果不传，返回全部企业数据（用于平台总览）
# 后端逻辑：
#   if is_super_admin:
#       filter_id = request.args.get('enterprise_id', type=int)  # 可选
#       # filter_id = None → 不过滤
#       # filter_id = 3   → 只看企业 3
```

---

## 4. 前端默认行为修正（防泄漏第一道防线）

当前代码存在三个导致用户默认进入公共库的入口，必须修正。

### 4.1 知识库浏览页（DbPage.tsx）——默认 scope 改为个人库

**问题**：`loadScopes()` 拿到 scopes 列表后，后端排序把 `public` 排在最前（`ORDER BY CASE WHEN library_key = 'public' THEN 0 ELSE 1 END`），导致 `data.items[0]` 永远是公共库。

```tsx
// 当前代码（DbPage.tsx 约 126 行）
if (data.items?.length && !filterScope) {
  setFilterScope(data.items[0].library_key)  // ← 永远是 'public'
}
```

```tsx
// 修正后：优先选择当前企业/个人的 private scope
const preferredScope = data.items?.find(
  s => s.scope_type !== 'public'            // 优先 private
) ?? data.items?.[0]                        // 没有 private 才用 public
if (preferredScope && !filterScope) {
  setFilterScope(preferredScope.library_key)
}
```

**空状态 fallback 修正**（DbPage.tsx 约 911 行）：

```tsx
// 当前：activeScope?.library_name || '公共工艺库'
// 修正后：不再硬编码公共库
activeScope?.library_name || '工艺库'
```

### 4.2 ZIP 入库页（ZipPage.tsx）——新建库默认不从公共库复制

**问题**：`seedPublic` 默认 `true`，新建个人库时自动从公共库拉全部数据。

```tsx
// 当前代码（ZipPage.tsx 约 30 行）
const [seedPublic, setSeedPublic] = useState(true)  // ← 默认复制公共库
```

```tsx
// 修正后：默认不复制公共库
const [seedPublic, setSeedPublic] = useState(false)
```

**影响**：用户新建个人工艺库时，默认是空库。如需从公共基线初始化，需**显式勾选**"从公共工艺库导入基线数据"。

### 4.3 入库目标默认值修正

**问题**：`selectedScope` 默认 `'__new__'` 配合 `seedPublic=true` 会把公共库数据灌入新建的个人库。

**修正**：`seedPublic=false` 后这个组合风险消除。额外确保 `newLibName` 默认文案不暗示公共库：

```tsx
// 当前
const [newLibName, setNewLibName] = useState('我的工艺库')  // ✅ 没有问题
// 但 visibleScopes 中 enterprise_admin/user 不应看到 public scope
// ——这个已在角色架构 Task 4 中实现，确认不被覆盖即可
```

### 4.4 公共库可见性确认（回归检查）

回顾角色架构 Task 4（`cfdf430`）已有的 `visibleScopes` 过滤：

```tsx
const visibleScopes = scopes.filter(scope => {
  if (user?.role === 'super_admin') return true
  return scope.scope_type !== 'public'
})
```

**确认**：非 super_admin 用户在 ZipPage 看不到 `public` scope，这个逻辑不变。

---

## 5. 未分配企业用户的行为

```
user.enterprise_id = NULL（未分配企业）:
  - 只能看 scope_type = 'public' 的公共库记录
  - 不能看任何企业的私有库记录
  - 不能上传/导入（上传时必须有所属企业）
  - 历史记录返回空
```

这个逻辑与前端已有的 `isUnassignedUser → redirect to profile` 保持一致。

---

## 6. 部署方案

### 5.1 迁移策略

**迁移脚本**：`backend/migrations/001_add_enterprise_id.py`

```python
# 核心逻辑
def migrate():
    for db_path, table in MIGRATIONS:
        conn = sqlite3.connect(db_path)
        # 1. 加列（IF NOT EXISTS 风格）
        if 'enterprise_id' not in existing_columns:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN enterprise_id INTEGER')

        # 2. 回填现有数据
        # 根据已有信息推导 enterprise_id：
        #   - tasks: 通过 upload 时的用户推断（从相关联的 library scope 反推）
        #   - vectors_v2: scope_type='public' → NULL，scope_type='private' →
        #     找到创建该 private scope 的用户 → 取其 enterprise_id
        # 如果无法推断，设为 NULL（在隔离查询中被过滤，需人工修复）

        conn.commit()
```

### 5.2 部署步骤

```
1. 停止 Flask 服务（或启用维护模式）
2. 备份所有 .db 文件
   cp auth.db auth.db.bak-$(date +%Y%m%d)
   cp task_store.db task_store.db.bak-$(date +%Y%m%d)
   cp vectors.db vectors.db.bak-$(date +%Y%m%d)
3. 运行迁移脚本
   python backend/migrations/001_add_enterprise_id.py
4. 验证迁移
   python backend/migrations/001_verify.py
5. 重启 Flask 服务
6. 运行隔离测试套件确认
```

### 5.3 回滚方案

```bash
# 如果迁移后发现问题
cp auth.db.bak-* auth.db
cp task_store.db.bak-* task_store.db
cp vectors.db.bak-* vectors.db
# 重启服务即可
```

### 5.4 零停机迁移（可选，生产环境推荐）

```
1. 先在从库（或 staging）上跑迁移 + 验证
2. 主库加列（ALTER TABLE ADD COLUMN 在 SQLite 中是秒级操作，不锁表）
3. 部署新代码（新代码兼容旧数据：列有默认值 NULL）
4. 后台异步回填 enterprise_id
5. 全部回填完成后，开启强制校验
```

---

## 7. 测试计划

### 6.1 后端单元/集成测试（pytest）

```python
# backend/test_data_isolation.py

class TestEnterpriseIsolation:
    """企业间数据隔离测试"""

    def test_user_cannot_see_other_enterprise_tasks(self):
        """企业 A 用户请求历史记录，不应包含企业 B 的 task"""
        ...

    def test_user_cannot_access_other_enterprise_library_record(self):
        """企业 A 用户请求知识库记录，不应返回企业 B 的记录"""
        ...

    def test_user_cannot_modify_other_enterprise_record(self):
        """企业 A 用户 PUT 企业 B 的记录，应返回 403/404"""
        ...

    def test_user_cannot_delete_other_enterprise_scope(self):
        """企业 A 用户 DELETE 企业 B 的 library scope，应返回 403"""
        ...

    def test_super_admin_can_see_all_enterprises(self):
        """super_admin 可以跨企业查看"""
        ...

    def test_super_admin_can_filter_by_enterprise(self):
        """super_admin 传 ?enterprise_id=2 可以限定范围"""
        ...

    def test_unassigned_user_only_sees_public_library(self):
        """未分配企业用户只能看到 scope_type='public' 的记录"""
        ...

    def test_upload_sets_enterprise_id(self):
        """上传图纸时自动写入 enterprise_id"""
        ...

    def test_zip_import_sets_enterprise_id(self):
        """ZIP 导入时自动写入 enterprise_id"""
        ...


class TestEnterpriseIdBackfill:
    """迁移回填测试"""
    ...
```

### 6.2 Playwright E2E 测试（前端视角）

```typescript
// frontend-react/tests/data-isolation.spec.ts

test('enterprise A admin cannot see enterprise B history', async ({ page }) => {
  // 以企业 A admin 登录
  // 导航到历史记录
  // 确认列表中不出现企业 B 的 task
})

test('enterprise A admin cannot browse enterprise B private library', async ({ page }) => {
  // 以企业 A admin 登录
  // 导航到知识库浏览
  // scope 列表中不应出现企业 B 的 private scope
})
```

### 6.3 测试运行命令

```bash
# 后端
pytest backend/test_data_isolation.py -v

# 前端
cd frontend-react && npx playwright test tests/data-isolation.spec.ts

# 全量回归（确保不破坏现有功能）
pytest backend/test_auth_store.py -q
cd frontend-react && npx playwright test tests/auth-ui.spec.ts tests/db-preview.spec.ts tests/zip-to-db-flow.spec.ts
```

---

## 8. 文件结构

```
后端改动：
  backend/migrations/
    __init__.py
    001_add_enterprise_id.py       ← 迁移脚本
    001_verify.py                  ← 迁移验证
  backend/api/_utils.py            ← 新增 get_enterprise_scope()
  backend/api/library.py           ← 修改：注入 enterprise 过滤
  backend/api/history.py           ← 修改：注入 enterprise 过滤
  backend/api/status.py            ← 修改：task 归属校验
  backend/api/result.py            ← 修改：task 归属校验
  backend/api/upload.py            ← 修改：写入 enterprise_id
  backend/api/kb_import.py         ← 修改：写入 enterprise_id
  backend/api/upload_handler.py    ← 修改：写入 enterprise_id
  backend/library_scope.py         ← 修改：scope 创建时写入 enterprise_id
  backend/task_store.py            ← 修改：tasks 表加列
  backend/test_data_isolation.py   ← 新增：隔离测试

前端改动（默认行为修正）：
  frontend-react/src/pages/DbPage.tsx           ← 修改：默认 scope 改为 private
  frontend-react/src/pages/ZipPage.tsx          ← 修改：seedPublic 默认 false
  frontend-react/tests/data-isolation.spec.ts   ← 新增：隔离 E2E 测试

不动：
  auth.db / auth_store.py          ← 已有 enterprise_id
  frontend-react/src/** 其他页面    ← 不修改
```

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 回填时无法推断某些记录的 `enterprise_id` | 设为 NULL，在查询层面不会泄漏（NULL 记录仅 super_admin 可见），运营侧可人工修复 |
| 某处漏加过滤条件 | 隔离测试覆盖所有数据出口，CI 中强制执行 |
| ORM 无原生 RLS 支持 | 通过 `get_enterprise_scope()` 统一入口，禁止裸写 SQL |
| 性能退化 | `enterprise_id` 列加索引；当前数据量极小（< 10 万行），无影响 |

---

## 10. 二期规划（本次不做）

```
当前一期（Discriminator Column）→ 二期（Per-Tenant DB File）

二期触发条件（满足任一即启动）：
  - 企业数超过 50
  - 合规审计要求物理隔离
  - 需要企业级独立备份/恢复

二期升级路径：
  1. 将 db 路由层从 "WHERE enterprise_id = ?" 改为 "打开 enterprise_<id>.db"
  2. 迁移数据：INSERT INTO enterprise_<id>.db SELECT * FROM shared.db WHERE enterprise_id = <id>
  3. 删除 shared.db 中的该企业数据
  4. 一期打的 enterprise_id 列和测试直接复用
```

---

## 11. 验收标准

- [ ] 企业 A 的 `enterprise_admin` 调用任何 API 都看不到企业 B 的数据
- [ ] 企业 A 的 `user`（已分配）调用任何 API 都看不到企业 B 的数据
- [ ] 未分配企业的用户只能看到 `scope_type='public'` 的记录
- [ ] `super_admin` 可以跨企业查看（传参限定或不传参看全部）
- [ ] 上传/ZIP 导入自动写入正确的 `enterprise_id`
- [ ] **DbPage 打开时默认选中用户的 private scope，不默认展示公共库**
- [ ] **DbPage 空状态不再展示 "公共工艺库" 文案**
- [ ] **ZipPage 新建个人库默认不从公共库复制数据（seedPublic=false）**
- [ ] **非 super_admin 用户在 ZipPage 不可见 public scope（已有逻辑，回归确认）**
- [ ] 现有 35 条 Playwright + 39 条 pytest 全部保持通过
- [ ] 新增隔离测试全部通过
- [ ] 迁移脚本在空库和有数据库上都能幂等执行
