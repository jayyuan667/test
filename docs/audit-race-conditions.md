# 竞态与 Bug 审计报告

> 原则：能简单就不要复杂，不堆逻辑，每个优化可回退

---

## 一、竞态问题（按严重性排序）

### 【高】竞态-1: SSE 连接跨阶段复用 ✅ 已修复
- **文件**: `GeneratePage.tsx`
- **修复**: `handleConfirmReview` 和 `handleRerun` 在 `submitReview` 前关闭旧 SSE (`esRef.current?.close()`)，提交后重新连接 (`connectStream(taskId)`)
- **状态**: 已修复，已验证编译通过

### 【中】竞态-2: streaming effect 的 displayedRows 依赖 ✅ 已修复
- **文件**: `ProcessPanel.tsx`
- **修复**: 新增 `enqueuedCodesRef` (Set) 跟踪已入队的 code，streaming effect 不再依赖 `displayedRows`，effect 执行频率大幅降低
- **状态**: 已修复，已验证编译通过

### 【中】竞态-3: TypingRow 定时器叠加 ✅ 已修复
- **文件**: `TypingRow.tsx`
- **修复**: `typeField` 开始时清除前一个 `timerRef.current`
- **状态**: 已修复，已验证编译通过

### 【低】竞态-4: onShapesChanged 回调风暴 ⏭️ 暂不处理
- **文件**: `AnnotationPanel.tsx`
- **原因**: 当前行为可接受，添加 debounce 增加复杂度，收益低

### 【低】竞态-5: auto-save 和手动保存并发 ⏭️ 暂不处理
- **文件**: `AnnotationPanel.tsx`
- **原因**: 后端幂等，重复保存无副作用

---

## 二、Bug 列表

### 【中】Bug-1: parseStreamingRows 未使用 ✅ 已删除
- **文件**: `ProcessPanel.tsx`

### 【中】Bug-2: hasStreamingContent 未使用 ✅ 已删除
- **文件**: `ProcessPanel.tsx`

### 【低】Bug-3: tradeBadgeClass 重复定义 ⏭️ 暂不处理
- **原因**: 仅两处使用，提取到共享文件增加模块依赖，收益低

### 【低】Bug-4: displayedRows O(n) 去重 ✅ 已修复
- **修复**: 改用 `enqueuedCodesRef` (Set) O(1) 查找

### 【低】Bug-5: 标注 fetch 无法感知删除 ⏭️ 暂不处理
- **原因**: 极端场景，实际使用中不影响

---

## 三、优化完成情况

| # | 优化项 | 状态 | 复杂度 |
|---|--------|------|--------|
| 1 | 修复 SSE 跨阶段复用 | ✅ 完成 | 低 |
| 2 | streaming effect 简化 | ✅ 完成 | 低 |
| 3 | 清理死代码 | ✅ 完成 | 极低 |
| 4 | TypingRow 定时器保护 | ✅ 完成 | 极低 |
