# 工艺生成全链路问题分析 + 实施方案

**时间：** 2026-06-22
**范围：** YOLO 标注 → 特征审阅 → 工艺生成全链路
**约束：** 不改变现有功能、不影响用户操作流程、不迁移架构

---

## 一、日志分析（实测数据）

### 时间线

```
14:08:29  SSE 连接，获取标注数据
14:09:30  标注确认（finalize）
14:09:31  Step 2: VLM 特征提取开始
   ↓
   ↓===== 11 分钟！VLM 卡在这里 =====
   ↓
14:20:08  Step 2: 审阅确认，开始工艺生成
14:20:10  Step 3: 专家判断完成（置信度 0.85）
14:20:22  Task finished（第一次完成）
14:20:57  重新生成请求（用户点击了重新生成）
14:20:59  SSE 重连
14:21:11  第二次完成
```

### 发现的 4 个关键问题

| # | 问题 | 影响 |
|---|------|------|
| A | VLM 特征提取 1 页耗时 11 分钟 | 进度条卡在 45% 不动，用户以为挂了 |
| B | 任务完成后前端又触发了重新生成 | 工艺结果重复生成，浪费 API 调用 |
| C | SSE 事件与前端状态机不同步 | 页面切换时 review_required 事件被静默丢弃 |
| D | RAG prefix_hint="15"（截断的图号） | 检索无法精确定位，低质量候选被注入 |

---

## 二、根因定位

### 问题 A：VLM 耗时过长，进度条无反馈

**后端：** VLM API 调用一次约 11 分钟（doubao seed-2.0-mini），无法干预。

**前端：** `GeneratePage.tsx` line 375，`handleFinalizeAnnotation()` 设置了 `progress=45` 和 `phaseHint='等待特征审阅结果...'`，但接下来 11 分钟进度条完全不更新。

```tsx
// line 373-374: progress 锁死在 45%，没有心跳更新
setProgress(45)
setPhaseHint('等待特征审阅结果...')
```

**架构影响：** 无。只加一个定时器。

### 问题 B：任务完成后重复生成

**后端日志：**
```
14:20:22  [SSE] task finished status=completed
14:20:22  [SSE] client disconnected
14:20:57  收到重新生成请求（POST /api/review/... 第二次）
```

**根因：** 前端 `onComplete()` 在 line 86-100 触发后，设置了 `status='completed'`。但用户可能在第一次完成时没看到结果（因为进度条跳太快或 streaming 还没渲染完），手动点了"重新生成"按钮。也可能是前端 polling（line 207）在 task 完成前误判了状态。

**架构影响：** 无。加防重复提交锁。

### 问题 C：SSE 事件状态机冲突

**`GeneratePage.tsx` line 45-48 的 guard：**
```tsx
onReviewRequired(data) {
    if (processSubmissionLockedRef.current) return
    if (workflowStageRef.current === 'process' || 
        workflowStageRef.current === 'completed') return
    // ... 设置 review 状态
}
```

**问题场景：**
1. 用户完成标注，`workflowStageRef = 'analysis'`
2. VLM 跑 11 分钟
3. 用户等不及，重新上传了个文件，`workflowStageRef = 'analysis'`（新任务）
4. 旧任务的 SSE 发来 `review_required`
5. `workflowStageRef === 'process'`？不，是 `'analysis'` → guard 通过
6. **旧任务的 review 覆盖了新任务的界面！**

**另一个场景：**
1. `handleFinalizeAnnotation()` 设置 `workflowStageRef = 'analysis'`
2. SSE 的 `review_required` 到达
3. Guard: `workflowStageRef === 'analysis'` → 通过
4. 但 `handleFinalizeAnnotation()` 里已经设置了 `activeTab='review'`
5. `onReviewRequired` 又设置了一次 `activeTab='review'`

目前看没问题，但如果 SSE 事件顺序错乱（比如 `process_stream` 先于 `review_required` 到达），前端会崩溃。

**架构影响：** 无。只在现有 guard 加一层 taskId 校验。

### 问题 D：RAG prefix 截断

**日志：** `prefix_hint=15`

实际零件图号 `2704.304.9.0`，但 `_extract_drawing_prefix()` 可能只取了前几位或解析错了。prefix 错误 → RAG 精确检索失败 → 只能用低相似度向量匹配。

这个不用改——process_gen 已经有 RAG 阈值机制（我们刚加的），低相似度时会走纯 LLM。但 prefix 问题值得记录。

---

## 三、实施方案

### 修改 1：VLM 等待期间进度条心跳（`GeneratePage.tsx`）

**位置：** `handleFinalizeAnnotation()` 内，line 373 之后

**改动：** 加一个每秒 +1 的假进度条（45% → 50%），给用户"系统还在跑"的感觉。

```tsx
// 在 setProgress(45) 之后加：
const vlmTicker = setInterval(() => {
  setProgress(prev => Math.min(prev + 1, 49))
}, 5000)
try {
  await finalizeAnnotation(taskId)
} finally {
  clearInterval(vlmTicker)
}
```

**扫描：** 不影响任何其他状态。仅在 `status='processing'` 期间运行。

### 修改 2：防止重复提交锁（`GeneratePage.tsx`）

**位置：** `onComplete()` line 86 附近 + `handleFinalizeAnnotation()` line 369 附近

**改动：** 用 `processSubmissionLockedRef` 在 task 完成后锁定，防止重复触发生成。

```tsx
// onComplete 中：
onComplete() {
    processSubmissionLockedRef.current = true  // ← 新增
    workflowStageRef.current = 'completed'
    ...
}
```

同时在"重新生成"按钮的点击处理中检查这个锁。

**扫描：** `processSubmissionLockedRef` 已存在但只在部分场景使用。扩展到 onComplete 后加锁，handleReset/新上传时解锁即可。

### 修改 3：SSE 事件加 taskId 校验（`GeneratePage.tsx`）

**位置：** `connectStream()` line 41 的每个回调中

**改动：** 在 `onReviewRequired`、`onAnnotationRequired`、`onProcessStream` 等回调开头校验当前 taskId：

```tsx
onReviewRequired(data) {
    // 新增：校验 taskId
    if (data.task_id && data.task_id !== taskId) return
    // 原有 guard 继续...
}
```

**扫描：** taskId 是组件 state。每个 SSE 回调只读 taskId，不修改它。线程安全。

### 修改 4：空工序/无工种过滤（`ProcessPanel.tsx`）

**问题：** 用户描述「进度条到工艺输出显示都有问题」——说明工艺结果中有空行、缺工种等。

**位置：** `frontend-react/src/components/generate/ProcessPanel.tsx`

**改动：** 在渲染工艺表格前加一层过滤：移除空工序行、标记缺工种行。

```tsx
const filtered = processRows.filter(row => {
  const content = row.content || ''
  return content.trim().length > 0  // 过滤空行
})
```

**扫描：** 纯展示层修改，不影响数据存储和 API。

---

## 四、架构扫描

| 检查项 | 状态 |
|--------|------|
| API 接口不变 | ✅ |
| 数据库 Schema 不变 | ✅ |
| SSE 协议不变（只加 taskId 字段校验，服务端无需改动） | ✅ |
| 前端路由不变 | ✅ |
| 状态管理不变（仍用 useState + useRef） | ✅ |
| 文件存储不变 | ✅ |
| 修改文件：`GeneratePage.tsx` + `ProcessPanel.tsx`（仅前端） | ✅ |

---

## 五、实施步骤

| 步骤 | 文件 | 修改项 | 预计影响 |
|------|------|--------|----------|
| 1 | `GeneratePage.tsx` | 进度条心跳 | VLM 期间不显示卡死 |
| 2 | `GeneratePage.tsx` | 防重复提交锁 | 避免重复生成 |
| 3 | `GeneratePage.tsx` | SSE taskId 校验 | 防止事件串台 |
| 4 | `ProcessPanel.tsx` | 空行/无工种过滤 | 工艺表格干净 |

**每一步都可以独立提交和回滚，不互相依赖。**
