# 数据库初始化修复设计

## 目标

新安装或空数据库启动后，知识库常规浏览接口必须可用：

- 自动创建 `kb_library_scopes`
- 自动创建公共向量表 `vectors_v2`
- 自动创建 `kb_import_batches` 和 `kb_import_items`
- 空库浏览返回空列表和未解锁状态，不返回 HTTP 500

## 方案

在 `backend/library_scope.py` 新增幂等初始化入口：

1. 确保数据库目录存在。
2. 调用现有 `ensure_scope_registry()`。
3. 调用现有 `ensure_vector_table(PUBLIC_VECTOR_TABLE)`。
4. 创建知识库导入跟踪表。

`backend/api/library.py` 加载时调用该入口，保证浏览接口就绪。
`browse_unlock_status()` 查询前单独确保导入跟踪表存在，避免被其他脚本直接调用时缺表。

现有 `backend/api/kb_import.py::_ensure_import_tables()` 保持不变，降低对导入流程的影响。

## 数据安全

所有建表操作使用 `CREATE TABLE IF NOT EXISTS`。不删除数据库，不清空记录，
不覆盖现有表或已有数据。

## 测试

使用临时 SQLite 文件验证：

1. 初始化后四张必需表存在。
2. 重复初始化不会报错或删除已有记录。
3. 空库 `browse_unlock_status()` 返回零批次。
4. 空库 `_list_records()` 返回 `total=0` 和空列表。
