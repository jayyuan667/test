# 进度日志

## 会话：2026-06-21 — Linux 服务器生产上线

### 前置工作（已完成）

- [x] 发现并修复 ZipPage sessionStorage 解锁 bug
- [x] 编写 zip-to-db-flow.spec.ts（14 个测试，全部通过）
- [x] 阅读 Linux 试跑报告，确认当前状态和待办清单
- [x] 设计 5 阶段实施方案

### 阶段 1：代码冻结与打包（当前进行中）
- **状态：** in_progress

### 阶段 2：服务器代码更新
- **状态：** pending

### 阶段 3：.env 配置验证
- **状态：** pending

### 阶段 4：业务链路验收
- **状态：** pending

### 阶段 5：生产化
- **状态：** pending

## 本地修改清单

```
 M AGENTS.md                                  — GitNexus 自动统计
 M CLAUDE.md                                  — GitNexus 自动统计
 M backend/api/kb_import.py                  — sample ZIP 有效 PDF 修复
 M backend/test_kb_import_formats.py         — 测试补充
 M frontend-react/src/pages/GeneratePage.tsx  — YOLO 跳转流程修复
 M frontend-react/src/pages/ZipPage.tsx       — sessionStorage 解锁修复
 M frontend-react/tests/upload-flow.spec.ts   — 测试补充
?? frontend-react/tests/zip-to-db-flow.spec.ts — 新增 ZIP→DB 链路测试 (14 tests)
?? backups/                                   — 运行时产物，不提交
```

## 新增文件

| 文件 | 说明 |
|------|------|
| `frontend-react/tests/zip-to-db-flow.spec.ts` | ZIP 入库→数据库浏览完整链路测试，14 个用例 |
