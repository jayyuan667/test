# 数据隔离一期 交付报告

> **交付日期**：2026-06-25
> **分支**：`yolo-react`
> **关联设计**：`docs/superpowers/specs/2026-06-25-data-isolation-phase1-design.md`
> **关联修改方案**：`docs/superpowers/specs/2026-06-25-data-isolation-phase1-critical-fixes.md`
> **报告目的**：供评审人独立验证交付物是否满足设计要求

---

## 1. 交付目标

在不动数据库文件架构的前提下，通过以下三层防御实现企业间数据不可互见：

| 层 | 机制 | 故障后果 |
|---|---|---|
| DB Schema | 业务表加 `enterprise_id` 列 + 索引 | 无此列则无法写入企业归属 |
| API 强制过滤 | `get_enterprise_scope()` + `assert_task_access()` | 漏加一处端点即泄漏 |
| 前端默认行为 | DbPage/ZipPage 默认不走公共库 | 用户无意识触发公共库访问 |

---

## 2. 改动范围

### 2.1 新建文件（5 个）

| 文件 | 职责 |
|---|---|
| `backend/migrations/__init__.py` | 包标记 |
| `backend/migrations/001_add_enterprise_id.py` | 幂等迁移脚本 + unresolved 报告 |
| `backend/migrations/001_verify.py` | 迁移后验证所有表具备 `enterprise_id` |
| `backend/test_data_isolation.py` | 7 条企业隔离 pytest 测试 |
| `frontend-react/tests/data-isolation.spec.ts` | 2 条前端默认行为 Playwright 测试 |

### 2.2 修改文件（15 个）

**后端核心（11 个）：**

| 文件 | 改动说明 |
|---|---|
| `backend/task_store.py` | `tasks` 表加 `enterprise_id` 列 + `insert_task()` 接受参数 |
| `backend/library_scope.py` | `kb_library_scopes`/`kb_import_batches`/动态 `vectors_*` 表加列；`ensure_scope()` 接受 `enterprise_id` |
| `backend/api/_utils.py` | 新增 `get_enterprise_scope()` + `assert_task_access()` |
| `backend/api/library.py` | 所有 library 端点注入 enterprise 过滤（`scope_type='public'` 判定，非 `IS NULL`） |
| `backend/api/history.py` | `@login_required` + enterprise 过滤 + super_admin 需显式传参 |
| `backend/history.py` | `add_history_entry()` / `get_history()` 支持 `enterprise_id` |
| `backend/api/upload.py` | task 创建写入 `enterprise_id`；review/rerun/process/cancel 加 `@login_required` + `assert_task_access` |
| `backend/api/status.py` | `@login_required` + task 归属校验 |
| `backend/api/result.py` | `@login_required` + task 归属校验 + 文件回退路径校验 + asset 路径校验 |
| `backend/api/kb_import.py` | `@login_required` + batch 创建写入 `enterprise_id` |
| `backend/api/events.py` | `@login_required` + `assert_task_access`（SSE 流之前验证） |

**后端补漏（4 个，P0 审查发现）：**

| 文件 | 改动说明 |
|---|---|
| `backend/api/export.py` | `@login_required` + `assert_task_access`（2 端点） |
| `backend/api/image.py` | `@login_required` + `assert_task_access`（2 端点） |
| `backend/api/annotations.py` | `@login_required` + `assert_task_access`（4 端点） |

**前端（2 个）：**

| 文件 | 改动说明 |
|---|---|
| `frontend-react/src/pages/DbPage.tsx` | 默认 scope 优先选 private；空状态 fallback 不再说"公共工艺库" |
| `frontend-react/src/pages/ZipPage.tsx` | `seedPublic` 默认 `false`，不从公共库复制数据 |

---

## 3. 关键设计决策（评审关注点）

### 3.1 公共库判定方式

**不用 `enterprise_id IS NULL`，改用 `scope_type = 'public'`**。

理由：
- `enterprise_id = NULL` 同时承载了"平台公共数据"和"迁移阶段无法推断归属的 orphan 数据"两种语义
- 如果查询条件写成 `enterprise_id = ? OR enterprise_id IS NULL`，orphan 数据会被所有企业用户看到
- 公共库记录的特征是 `scope_type = 'public'`，这在 `kb_library_scopes` 表中有明确标记

### 3.2 private scope 定义

**一期是企业级私有库，不是个人级私有库**。

理由：
- 本期 DDL 只加了 `enterprise_id`，没有 `owner_user_id`
- 个人级隔离需要额外字段和校验逻辑，留给二期
- 同企业用户之间的数据可见性不在本期保证范围内

### 3.3 super_admin 跨企业行为

**默认不返回全平台数据，需要显式 `?scope=all` 或 `?enterprise_id=X`**。

理由：
- 设计中"不需传参即可查看全部"与"不可无意识跨企业"存在冲突
- 默认空结果强制前端/调用方显式声明意图
- 防止前端漏传参数时意外暴露全平台数据

### 3.4 `assert_task_access(task_id)` 统一校验

**所有凭 `task_id` 访问数据的端点（包括文件流、SSE）统一调用此函数**。

理由：
- 当前系统至少有 15+ 个端点接受 `task_id` 参数
- 如果逐个手写校验，遗漏概率高
- 统一函数保证校验逻辑一致，且可审计

---

## 4. 隔离规则汇总

| 角色 | `enterprise_id` 为 NULL 的 orphan 数据 | 公共库数据 | 本企业数据 | 其他企业数据 |
|---|---|---|---|---|
| `super_admin`（显式 `scope=all`） | ✅ 可见 | ✅ 可见 | ✅ 可见 | ✅ 可见 |
| `super_admin`（默认） | ❌ | ✅ | ❌ | ❌ |
| `enterprise_admin` | ❌ | ✅ 只读 | ✅ 读写 | ❌ 404 |
| `user`（已分配企业） | ❌ | ✅ 只读 | ✅ 只读 | ❌ 404 |
| `user`（未分配企业） | ❌ | ✅ 只读 | ❌ | ❌ |

---

## 5. 验证结果

### 5.1 后端测试

```bash
pytest backend/test_auth_store.py -q         # 39 passed
pytest backend/test_data_isolation.py -v     # 6 passed, 1 skipped
```

隔离测试覆盖：
- 企业 A 用户看不到企业 B 的历史记录 ✅
- super_admin 可跨企业查看 ✅
- super_admin 可按 `?enterprise_id=N` 过滤 ✅
- 未分配企业用户只能看到 public scope ✅
- 上传自动写入 enterprise_id ✅
- ZIP 导入表具备 enterprise_id 列 ✅

### 5.2 前端测试

```bash
npx playwright test tests/auth-ui.spec.ts      # 18 passed
npx playwright test tests/db-preview.spec.ts    # 6 passed
npx playwright test tests/zip-to-db-flow.spec.ts# passed
npx playwright test tests/data-isolation.spec.ts# 2 active passed, 2 skipped
```

前端隔离测试覆盖：
- DbPage 打开默认选中 private scope，不是公共库 ✅
- ZipPage 新建库默认不从公共库复制数据 ✅

### 5.3 构建

```bash
cd frontend-react && npm run build  # PASS
```

### 5.4 迁移

```bash
python backend/migrations/001_add_enterprise_id.py  # 幂等通过
python backend/migrations/001_verify.py             # exit 0，全部表确认
```

---

## 6. 已知局限（不在本期范围内）

1. **同企业用户间隔离**：private scope 是企业级，同一企业的 `user` 和 `enterprise_admin` 可以看到企业内部所有私有库记录。这是设计决策，非遗漏。

2. **回填完整性**：迁移脚本输出 `unresolved` 报告列出无法推断 `enterprise_id` 的记录。这些记录对普通企业用户不可见，需运营人员手工修复。

3. **`history.json` 文件型存储**：`history.json` 的隔离依赖 `get_history()` 的应用层过滤。该文件没有数据库级别的索引优化。数据量大时可迁移到 SQLite。

4. **`upload_drawing` 端点的 `@login_required` 未加**：该端点在设计范围内已有 `@login_required`（原本就有），确认无需修改。

---

## 7. 部署注意事项

1. **必须运行迁移**：`python backend/migrations/001_add_enterprise_id.py`
2. **必须运行验证**：`python backend/migrations/001_verify.py`，确认退出码 0
3. **先备份**：`cp *.db *.db.bak-$(date +%Y%m%d)`
4. **回滚**：直接恢复备份文件 + 重启服务即可
5. **迁移幂等**：多次运行安全，ALTER TABLE 前检查 `PRAGMA table_info`

---

## 8. 提交历史

```
8cc22b1 fix: add auth guards to annotations endpoints (missed in P0 wave)
fb12e18 fix: tighten super_admin defaults + private scope semantics (P1)
b0caf51 fix: harden enterprise isolation per supervisor review (P0)
e71d001 test: add enterprise data isolation pytest suite
9de3450 test: add frontend E2E data isolation tests + regression sweep
b2249dd fix: default to private scope, prevent public library data leakage
a7b6e33 fix: harden API auth gates, prevent unauthenticated enterprise bypass
239f6e2 feat: add API-layer enterprise isolation enforcement
1d66a55 feat: add enterprise_id columns to business tables + migration scripts
```

---

## 9. 评审清单

请评审人逐项确认：

- [ ] 所有数据出口端点是否有 `@login_required`？（events/export/image/annotations/result/library/history/status/upload）
- [ ] 是否还有任何地方用 `enterprise_id IS NULL` 作为公共数据判定？
- [ ] `assert_task_access(task_id)` 是否在所有 `task_id` 端点被调用？
- [ ] super_admin 默认行为是否要求显式传参？
- [ ] 前端 DbPage 默认 scope 是否为 private？
- [ ] 前端 ZipPage `seedPublic` 默认是否为 false？
- [ ] 设计文档是否明确 private scope 是企业级？
- [ ] 迁移脚本是否幂等 + 输出 unresolved 报告？
- [ ] 全量回归测试是否通过？
