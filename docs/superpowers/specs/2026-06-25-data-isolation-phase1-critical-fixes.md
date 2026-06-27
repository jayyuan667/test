# 数据隔离一期：致命问题修改建议

> 日期：2026-06-25
> 关联设计：`2026-06-25-data-isolation-phase1-design.md`
> 目的：在当前方案已经实施中的前提下，只指出会导致企业隔离失效或误泄漏的关键问题，并给出最低改动建议。

---

## 结论

当前一期方向可以继续，但必须立即修正以下问题，否则即使业务表加了 `enterprise_id`，仍可能通过 `NULL` 数据、`task_id` 直连接口、文件资源接口或未登录接口绕过企业隔离。

最低必须完成三件事：

1. 禁止用 `enterprise_id IS NULL` 判断公共数据。
2. 所有 `task_id` 相关接口统一调用任务访问校验。
3. 所有依赖 `g.current_user` 的隔离接口必须先加 `@login_required`。

---

## 1. 不要用 `enterprise_id IS NULL` 判断公共数据

### 问题

当前设计中 `enterprise_id = NULL` 同时承担了两种语义：

- 平台公共库数据。
- 迁移时无法推断企业归属的数据。

如果查询条件写成：

```sql
enterprise_id = ? OR enterprise_id IS NULL
```

那么无法回填企业归属的私有数据会被所有企业用户看到。这是数据隔离的直接失效。

### 修改建议

公共库必须通过 scope 判定，不通过 `enterprise_id IS NULL` 判定。

建议规则：

```sql
-- 公共数据
scope_type = 'public' OR library_key = 'public'

-- 企业私有数据
enterprise_id = current_user.enterprise_id

-- 未知归属数据
enterprise_id IS NULL AND scope_type != 'public'
```

未知归属数据只能 `super_admin` 可见，普通企业用户不可见。

### 实施要求

`GET /api/library/records`、`GET /api/library/scopes` 等接口不要写：

```sql
enterprise_id = ? OR enterprise_id IS NULL
```

应改成类似：

```sql
enterprise_id = ?
OR scope_type = 'public'
OR library_key = 'public'
```

前提是该记录确实能关联到 scope 信息。无法关联 scope 的 `enterprise_id IS NULL` 数据默认不可见。

---

## 2. 所有 `task_id` 出口必须统一加访问校验

### 问题

当前设计覆盖了 `/history`、`/status`、`/result` 等主要接口，但系统里还有多个接口可以凭 `task_id` 直接读取、导出或修改任务数据。

如果这些接口不校验企业归属，用户只要拿到其他企业的 `task_id`，仍然可以访问数据。

### 必须覆盖的接口

至少补充以下接口：

```text
GET  /api/events/<task_id>
GET  /api/export/<task_id>
POST /api/export/<task_id>
GET  /api/result/<task_id>/asset/<filename>
GET  /api/image/<task_id>/<filename>

GET  /api/annotations/<task_id>
POST /api/annotations/<task_id>/save
GET  /api/annotations/<task_id>/export
POST /api/annotations/<task_id>/finalize

POST /api/review/<task_id>
POST /api/rerun/<task_id>
POST /api/process/<task_id>
POST /api/cancel/<task_id>
```

### 修改建议

新增统一函数，例如：

```python
def assert_task_access(task_id):
    """
    校验当前用户是否可以访问指定 task。

    规则：
      - super_admin：允许访问。
      - enterprise_admin / user：task.enterprise_id 必须等于当前用户 enterprise_id。
      - 未分配企业用户：拒绝访问业务 task。
      - task 不存在：返回 404。
    """
```

所有使用 `task_id` 的接口在读取任务、读取文件、导出、SSE 建连、写 annotation、review、rerun、cancel 前都必须先调用该函数。

文件型接口尤其不能遗漏：

- `/api/result/<task_id>/asset/<filename>`
- `/api/image/<task_id>/<filename>`
- `/api/export/<task_id>`
- `/api/annotations/<task_id>/export`

这些接口即使不返回 JSON，也同样属于数据出口。

---

## 3. 隔离接口必须先加 `@login_required`

### 问题

设计中的 `get_enterprise_scope()` 依赖 `g.current_user`。如果接口没有 `@login_required`，则 `g.current_user` 不可靠，过滤逻辑无法成立。

当前实施不能只在查询层调用 `get_enterprise_scope()`，还必须保证请求已经完成登录认证。

### 修改建议

以下类型接口至少全部加登录保护：

```text
library 私有读写接口
history
result / result asset
events
export
annotations
kb_import
upload 的 review / rerun / process / cancel
```

建议顺序：

```python
@route(...)
@login_required
def endpoint(...):
    ...
```

如接口需要配额或角色校验，再叠加 `@require_quota` / `@require_role`。

---

## 4. 明确 private scope 是企业级还是个人级

### 问题

当前设计写到：

```text
个人工艺库（scope_type=private）：企业内 user_id 过滤
```

但本期 DDL 只加 `enterprise_id`，没有 `owner_user_id`。这只能实现企业级隔离，不能实现同企业用户之间的个人级隔离。

### 修改建议

如果一期只做企业级隔离，应立即改口径：

```text
private scope = 企业私有库，不是个人私有库。
一期只保证企业间隔离，不保证同企业用户之间隔离。
```

如果必须实现个人级隔离，则需要补充字段：

```text
kb_library_scopes.owner_user_id
```

并在 scope 创建、列表、记录读写、删除时同时校验 `enterprise_id` 和 `owner_user_id`。如果当前时间不足，不建议临时承诺个人级隔离。

---

## 5. super_admin 默认不要无参数返回全平台数据

### 问题

设计中同时写了：

```text
super_admin 可跨企业查看，但需显式传参（不可无意识跨企业）
```

以及：

```text
如果不传 enterprise_id，返回全部企业数据。
```

这两者冲突。后一种行为容易造成前端漏传参数时直接暴露全平台数据。

### 修改建议

建议改成：

```text
super_admin 默认不跨企业返回全集。
需要显式传 ?enterprise_id=X 或 ?scope=all。
```

也就是：

```python
if is_super_admin:
    if request.args.get("scope") == "all":
        # 返回全平台
    elif enterprise_id := request.args.get("enterprise_id", type=int):
        # 返回指定企业
    else:
        # 返回空、公共数据，或要求前端显式选择企业
```

---

## 6. 回填失败数据必须默认不可见

### 问题

迁移阶段无法推断企业归属的数据如果设置为 `NULL`，不能进入普通企业用户查询结果。

否则会和公共数据混淆，形成泄漏。

### 修改建议

迁移规则改成：

```text
enterprise_id IS NULL + public scope = 公共数据
enterprise_id IS NULL + 非 public scope = orphan/unknown 数据
```

`orphan/unknown` 数据：

- 普通企业用户不可见。
- enterprise_admin 不可见。
- 仅 super_admin 可见。
- 迁移脚本输出 unresolved 报告，后续人工修复。

报告可以很简单，例如：

```text
table, primary_key, library_key, reason
tasks, <task_id>, <library_key>, cannot infer enterprise_id
vectors_xxx, <id>, <library_key>, scope has no enterprise_id
```

---

## 最低限度落地清单

如果当前没有时间做完整校验，至少完成以下清单：

- [ ] 查询公共库时不再使用单独的 `enterprise_id IS NULL` 条件。
- [ ] 非 public scope 且 `enterprise_id IS NULL` 的数据对普通企业用户不可见。
- [ ] 新增 `assert_task_access(task_id)`。
- [ ] 所有 `task_id` 接口调用 `assert_task_access(task_id)`。
- [ ] result asset、image、export、events、annotations 这些文件/流式接口也调用访问校验。
- [ ] 所有依赖 `g.current_user` 的隔离接口先加 `@login_required`。
- [ ] 文档明确 private scope 一期是企业级私有，不是个人级私有，除非补 `owner_user_id`。
- [ ] super_admin 跨企业全集需要显式 `scope=all`。
- [ ] 迁移脚本输出无法归属数据报告，且这些数据默认不向企业用户展示。

---

## 建议优先级

P0，必须立刻修：

1. `enterprise_id IS NULL` 不能作为公共数据通配。
2. 所有 `task_id` 出口必须加访问校验。
3. 隔离接口必须加 `@login_required`。

P1，建议本期同步修：

1. 明确 private scope 是企业级，不承诺个人级。
2. super_admin 全平台数据必须显式请求。
3. 回填失败数据输出 unresolved 报告。
