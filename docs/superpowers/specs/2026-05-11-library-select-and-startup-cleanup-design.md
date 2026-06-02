# 设计文档：入库选择已有库 + 启动残留清除

**日期**：2026-05-11  
**状态**：已审批，待实现

---

## 需求概述

两个独立功能，可并行实现：

1. **选择已有库进行入库**：入库目标区改为动态列出已有库 + 新建选项，取代原来的静态三档下拉。
2. **后端重启时工艺生成页残留清除**：DB 中卡住的 `pending`/`processing` 任务标为 `cancelled`；前端检测到重启后重置页面视觉状态。

---

## Feature 1 — 选择已有库进行入库

### 数据流

后端无改动。

- `GET /api/library/scopes` — 已返回所有 scope（`library_key`, `library_name`, `scope_type`, `last_batch_id`）
- `POST /api/kb/import_zip` — 已接受 `library_key` 字段，直接路由到对应向量表

### 前端改动（`updated_front/demo-industrial-console.html` + `demo-industrial-console.js`）

**入库目标卡片**（`#page-zip` 内的 hero-card）：

将静态 `<select id="zipLibraryModeSelect">` + `<input id="zipLibraryNameInput">` 替换为：

1. 一个动态 Radio 卡片列表 `#zipLibraryList`，在以下时机刷新：
   - 页面初始化时
   - 切换到"工艺入库" tab 时
   - 完成一次入库后

2. 卡片渲染规则：
   - 从 `/api/library/scopes` 取所有 scope
   - 每个 scope 渲染一行 Radio 卡片，显示 `library_name`（`scope_type`）
   - 最后追加一行"+ 新建工艺库"Radio 卡片
   - 默认选中：上次选中的 `library_key`（存 `localStorage`）；若无历史则选第一个已有库；若无已有库则选"新建"

3. 选中已有库时：隐藏新建输入区，提交时 `library_key = 选中值`，`library_mode` 传 `"existing"`（后端已有逻辑：有 `library_key` 就直接用）

4. 选中"新建"时：显示库名称输入框 + "是否复制公共基线" checkbox，行为与现在完全一致（`library_mode = "private_seed_public"` 或 `"private_empty"`）

5. 降级：若 API 失败，回退为原静态三选项

6. `#zipActiveLibraryChip` 随选中项更新显示当前目标库名

### 提交逻辑变化

```
// 原来
{ library_mode, library_name, library_key: "" }

// 新：选已有库
{ library_mode: "existing", library_name: "", library_key: "my_lib_abc" }

// 新：选新建（不变）
{ library_mode: "private_seed_public", library_name: "张三-液压项目库", library_key: "" }
```

**后端需补一个路径**（`backend/api/kb_import.py` → `import_zip_knowledge`）：

当 `library_key` 非空且该库已存在时，直接 `resolve_scope(library_key)` 写入 `target_scope`，跳过 `ensure_scope`（否则 `INSERT OR REPLACE` 会用空 `library_name` 覆盖原库名）。

```python
# 在 import_zip_knowledge 中，原有 if normalized_mode == "public" 之后：
elif library_key and (existing_scope := resolve_scope(library_key)):
    target_scope = existing_scope
    mark_scope_batch(target_scope["library_key"], batch_id)
else:
    # 原有新建逻辑不变
    proposed_key = sanitize_identifier(library_key or library_name or f"user_{batch_id}")
    ...
```

`resolve_scope` 在 `library_scope.py` 中已存在，只做查找，无副作用。

---

## Feature 2 — 后端重启时残留清除

### 后端改动

**`backend/task_store.py`** — 新增函数：

```python
def cancel_stale_tasks() -> int:
    """Mark tasks interrupted by a backend restart as cancelled."""
    with _conn() as c:
        c.execute(
            "UPDATE tasks SET status='cancelled', updated_at=? WHERE status IN ('pending','processing')",
            (datetime.now().isoformat(),)
        )
        return c.execute("SELECT changes()").fetchone()[0]
```

**`backend/app.py`** — 在 `tasks = {}` 之后、路由注册之前：

```python
import uuid
from .task_store import init_db, cancel_stale_tasks

init_db()
_stale = cancel_stale_tasks()
if _stale:
    logger.info("Startup: cancelled %d stale tasks from previous session", _stale)

STARTUP_TOKEN = uuid.uuid4().hex
```

新增路由（加在现有路由注册之后）：

```python
@app.route("/api/startup_token")
def startup_token():
    return jsonify({"token": STARTUP_TOKEN})
```

### 前端改动

**`updated_front/js/demo-industrial-console.js`** — 在 `DOMContentLoaded` 最早期加入：

```javascript
async function checkStartupToken() {
  try {
    const res = await fetch('/api/startup_token');
    const { token } = await res.json();
    const stored = localStorage.getItem('__startup_token__');
    if (stored !== token) {
      localStorage.setItem('__startup_token__', token);
      return true;
    }
  } catch (_) {}
  return false;
}
```

若返回 `true`（后端重启）则执行 `resetProcessPage()`：

```javascript
function resetProcessPage() {
  // 清进度状态（已有函数）
  resetProcessStreamState('');
  // 清结果面板
  if (processResult) processResult.innerHTML = initialProcessPanelHTML;
  // 清 localStorage 中的 task_id
  localStorage.removeItem('__last_task_id__');
  // dropzone 文案归位（如有修改过）
  const dzTitle = document.querySelector('#prtDropzone .dropzone-title');
  const dzCopy  = document.querySelector('#prtDropzone .dropzone-copy');
  if (dzTitle) dzTitle.textContent = '拖放 PRT 文件到此处';
  if (dzCopy)  dzCopy.textContent  = '支持 .prt / .prt.N 格式，单个文件';
}
```

已完成任务的 `result.json` 文件**不受影响**，历史记录页和知识库浏览页均不重置。

---

## 关键文件

| 文件 | 改动 |
|------|------|
| `backend/task_store.py` | 新增 `cancel_stale_tasks()` |
| `backend/app.py` | 启动时调 `cancel_stale_tasks()`，生成 `STARTUP_TOKEN`，新增 `/api/startup_token` 路由 |
| `backend/api/kb_import.py` | `import_zip_knowledge` 新增"已有库直接 resolve"路径 |
| `updated_front/demo-industrial-console.html` | 入库目标卡片改为动态 Radio 列表 |
| `updated_front/js/demo-industrial-console.js` | `checkStartupToken()` + `resetProcessPage()`；入库提交逻辑适配新选库字段 |

---

## 实现顺序

1. `task_store.py` — `cancel_stale_tasks()`（最小改动，无依赖）
2. `app.py` — 启动清除 + `startup_token` 路由
3. `demo-industrial-console.js` — `checkStartupToken` + `resetProcessPage`
4. `demo-industrial-console.html` + JS — 入库目标动态列表

---

## 验证方式

**Feature 2**：
1. 上传一个 PRT，不等完成直接重启后端
2. 刷新前端：工艺生成页应显示初始空状态，不再显示上次的进度
3. `task_store.db` 中该任务 status 应为 `cancelled`
4. 历史记录页中已完成的旧任务仍可查看

**Feature 1**：
1. 先入库一个 ZIP 创建私有库
2. 再次进入入库页：应显示刚才的库 + "新建"选项
3. 选中已有库后上传第二个 ZIP：应导入到同一个库（`library_key` 匹配）
4. 若 `/api/library/scopes` 请求失败：页面降级为原静态三选项，无 JS 报错
