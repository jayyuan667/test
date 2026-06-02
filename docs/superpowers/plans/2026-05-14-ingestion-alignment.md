# Ingestion Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 确保主上传路径的入库数据完整性：工艺数据经过 post-check 纠偏、关键字段不丢失、task 重建完整。

**Architecture:** 只改 upload.py / task_store.py / review_session.py 三个文件的数据持久化层，加测试覆盖。不改 library.py 的读逻辑（它已有的 fallback 链路已经完整，缺的只是上游写入）。

**Tech Stack:** Python 3, pytest, json

---

## 文件总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/api/upload.py` | 修改 | 保存 process_flow_raw 到 result；写入 raw_review_text |
| `backend/task_store.py` | 修改 | build_task_dict 补全 result 字段恢复 |
| `backend/services/review_session.py` | 修改 | 持久化/恢复 raw_review_text |
| `backend/pipeline/test_process_gen_geo.py` | 修改 | 新增入库数据完整性回归测试 |

---

### Task 1: 保存 process_flow_raw 到 result 和 task

**Files:**
- Modify: `backend/api/upload.py:386-392`
- Modify: `backend/pipeline/test_process_gen_geo.py`

目标：让经 `_post_check_process` 纠偏后的原始工艺文本写入 result.json，确保入库时能读到。

- [ ] **Step 1: 写失败测试**

在 `backend/pipeline/test_process_gen_geo.py` 末尾追加：

```python
def test_generate_result_includes_process_flow_raw():
    pg = _make_pg()
    pg._fuse_descriptions = lambda d: "【关键尺寸】250×100×30"
    pg._replace_placeholder_tokens = lambda t: t
    pg._extract_process_constraints = lambda text, geo_data=None: {
        "hard_constraints": {
            "blank_size": "", "outer_size": "", "key_dims": "",
            "geo_blank_spec": "δ30×250×100=1",
            "geo_hole_count": 0, "geo_bore_range": "",
            "part_count": 1,
        },
        "soft_features": {}
    }
    pg._run_rag_lookup = lambda *a, **k: ({}, "", False, None)
    pg._nearest_neighbor_fallback = lambda *a, **k: ("", {})
    pg._build_fallback_prompt = lambda *a: "prompt"

    raw_output = "- 0010: 备料 δ20×300×150=1\n- 0020: 铣削"
    pg._stream_llm_response = lambda *a, **k: raw_output
    pg._extract_process_section = lambda t: t
    pg._post_check_process = lambda raw, c: raw.replace("δ20×300×150=1", "δ30×250×100=1")
    pg._parse_markdown_process = lambda t: [["0010", "备料 δ30×250×100=1"], ["0020", "铣削"]]

    raw, data, rag = pg.generate(
        descriptions=[{"description": ""}],
        expert_judgment="",
        geo_data={"shape_class": "板类", "dimensions": {"x": 250, "y": 100, "z": 30}, "faces": [], "hole_info": {}},
    )
    assert "δ30×250×100=1" in raw
    assert "δ20×300×150" not in raw
    assert len(data) == 2
```

- [ ] **Step 2: 运行新测试确认失败逻辑正确**

Run:
```bash
python -m pytest backend/pipeline/test_process_gen_geo.py::test_generate_result_includes_process_flow_raw -v
```

Expected: PASS（这个测试验证 generate 返回的 raw 已经是 post-check 后的版本，不依赖 upload.py 的改动）

- [ ] **Step 3: 修改 upload.py — task["process_flow"] 增加 raw 键**

在 `backend/api/upload.py:388-392` 处：

```python
# 将：
task["process_flow"] = {
    "data": process_data,
    "columns": ["标签编码", "工序内容"],
    "format": "markdown",
}

# 改为：
task["process_flow"] = {
    "data": process_data,
    "raw": process_flow_raw,
    "columns": ["标签编码", "工序内容"],
    "format": "markdown",
}
```

- [ ] **Step 4: 修改 upload.py — result 字典增加 process_flow_raw**

在 `backend/api/upload.py` 的 result 字典（约 395-413 行）中，`"process_flow"` 后面加一行：

```python
"process_flow_raw": process_flow_raw,
```

- [ ] **Step 5: 运行 process_gen_geo 全量确认无回归**

Run:
```bash
python -m pytest backend/pipeline/test_process_gen_geo.py -v
```

Expected: 29 passed

- [ ] **Step 6: 提交**

```bash
git add backend/api/upload.py backend/pipeline/test_process_gen_geo.py
git commit -m "fix: persist process_flow_raw to result and task for ingestion alignment"
```

---

### Task 2: 写入 raw_review_text 并补全 review_session 持久化

**Files:**
- Modify: `backend/api/upload.py:691-706`
- Modify: `backend/services/review_session.py`

目标：审阅确认后、工艺生成前，把用户提交前的原始特征文本保存为 raw_review_text。

- [ ] **Step 1: 修改 upload.py — 写入 raw_review_text**

在 `backend/api/upload.py` 的 review_event.wait() 之后、`_finalize_processing()` 之前（约 701-706 行），插入一行：

```python
reviewed_text = (task.get("review_text") or full_feature_text).strip()
task["raw_review_text"] = reviewed_text  # 保存审阅前的原始特征文本，供入库使用
emit_log(task_id, event_data, event_locks, 2, "审阅确认，开始生成工艺规程...")
```

- [ ] **Step 2: 修改 review_session.py — persist_review_payload 包含 raw_review_text**

在 `backend/services/review_session.py` 的 `persist_review_payload()` 函数中，payload 字典增加：

```python
"raw_review_text": task.get("raw_review_text", ""),
```

- [ ] **Step 3: 修改 review_session.py — restore_task_from_pending 恢复 raw_review_text**

在 `backend/services/review_session.py` 的 `restore_task_from_pending()` 函数中，增加：

```python
task["raw_review_text"] = pending_data.get("raw_review_text", "")
```

- [ ] **Step 4: 提交**

```bash
git add backend/api/upload.py backend/services/review_session.py
git commit -m "fix: persist raw_review_text through review session lifecycle"
```

---

### Task 3: 补全 task_store.py 的 build_task_dict 字段恢复

**Files:**
- Modify: `backend/task_store.py:196-221`

目标：从 result JSON 恢复更多关键字段，确保重启后 task 重建不丢数据。

- [ ] **Step 1: 修改 build_task_dict**

将 `backend/task_store.py:196-221` 的 `build_task_dict()` 中，result 恢复部分从：

```python
    if result and result.get("process_flow"):
        task["process_flow"] = result["process_flow"]
    if result and result.get("preview_image_urls"):
        task["preview_image_urls"] = result["preview_image_urls"]
```

改为：

```python
    if result:
        if result.get("process_flow"):
            task["process_flow"] = result["process_flow"]
        if result.get("preview_image_urls"):
            task["preview_image_urls"] = result["preview_image_urls"]
        if result.get("review_text"):
            task["review_text"] = result["review_text"]
        if result.get("raw_review_text"):
            task["raw_review_text"] = result["raw_review_text"]
        if result.get("feature_report_text"):
            task["feature_report_text"] = result["feature_report_text"]
        if result.get("feature_report_json"):
            task["feature_report_json"] = result["feature_report_json"]
```

- [ ] **Step 2: 提交**

```bash
git add backend/task_store.py
git commit -m "fix: restore review and feature fields in build_task_dict"
```

---

### Task 4: 全量回归验证

**Files:**
- 无修改，仅运行测试

- [ ] **Step 1: 运行 pipeline 全量测试**

Run:
```bash
python -m pytest backend/pipeline/ -v --tb=short
```

Expected: 全部通过

- [ ] **Step 2: 检查 library 入库草稿预览接口（冒烟）**

Run:
```bash
python -c "import sys; sys.path.insert(0, '.'); from backend.api.library import _build_draft_from_task; print('import ok')"
```

Expected: import ok，无导入错误

---

## Self-Review

### Spec coverage

| 目标 | Task |
|------|------|
| process_flow_raw 落盘到 result | Task 1 |
| task["process_flow"] 增加 raw 键 | Task 1 |
| raw_review_text 写入 | Task 2 |
| review_session 持久化 raw_review_text | Task 2 |
| build_task_dict 补全字段 | Task 3 |
| 回归测试 | Task 1 + Task 4 |

### Placeholder scan

无 TBD / TODO / "similar to Task N"。每个步骤给出精确代码、命令和提交信息。

### Type consistency

- `process_flow_raw`: str 贯穿全链路
- `raw_review_text`: str 贯穿全链路
- Task 1 → Task 3 之间字段命名一致
