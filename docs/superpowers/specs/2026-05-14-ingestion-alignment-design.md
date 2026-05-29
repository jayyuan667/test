# 入库逻辑对齐工艺生成 — 设计文档

## 目标

确保主上传路径（PRT → 审阅 → 工艺生成 → 入库）的数据完整性：入库时工艺数据必须是经过 `_post_check_process` 纠偏后的版本，且任务重建不丢失关键字段。

## 范围

只修主上传路径（upload.py → result.json → library.py），不改库内直接上传和 ZIP 批量导入路径。

## 改动点

### 1. upload.py — process_flow_raw 落盘

`_finalize_processing()` 的 result 字典新增 `process_flow_raw`，task["process_flow"] 新增 `raw` 键。

### 2. upload.py — raw_review_text 写入

在审阅确认后、工艺生成前，把用户提交前的原始特征文本保存到 `task["raw_review_text"]`。

### 3. task_store.py — build_task_dict 补全字段

从 result 恢复 `review_text`、`feature_report_text`、`feature_report_json`、`process_flow_raw`。

### 4. review_session.py — 持久化补全

确保 `persist_review_payload` / `restore_task_from_pending` 包含 `raw_review_text`。

### 5. 测试 — 回归覆盖

新增/更新测试验证 result 字段完整性和 task 重建正确性。

## 不改

- library 直接上传 PRT（路径 2）
- kb_import ZIP 导入（路径 3）
- GLB 导出一致性
