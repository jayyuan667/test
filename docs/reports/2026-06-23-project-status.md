# 项目进度总览

**日期：** 2026-06-23
**分支：** yolo-react
**服务器：** liu4th (Ubuntu 24.04)，跳板机 182.151.23.45

---

## 一、部署状态

| 组件 | 状态 | 备注 |
|------|:---:|------|
| Flask 后端 | ✅ | PID 2940161，5190 端口 |
| nginx 反向代理 | ✅ | 80 端口，proxy_pass → 5190 |
| 前端构建 | ✅ | Vite build 通过，dist 已部署 |
| systemd 服务 | ❌ | 未配置（需 sudo） |
| 磁盘空间 |⚠️| 根分区 99%，待清理 |

## 二、访问方式

| 方式 | 状态 | 说明 |
|------|:---:|------|
| `http://gongyi.neusymlab.cn` | 🟡 | DNS 未改（指向 198.18.0.204），需改 hosts 临时用 |
| `http://182.151.23.45` | 🟡 | 直接 IP 被 nginx 301，需管理员加 server_name |
| SSH 隧道 `localhost:5191` | ✅ | 需手动建隧道，容易断 |

### hosts 临时方案

```
182.151.23.45 gongyi.neusymlab.cn
```

Mac: `sudo sh -c 'echo "182.151.23.45 gongyi.neusymlab.cn" >> /etc/hosts'`
Windows: `C:\Windows\System32\drivers\etc\hosts` 加同上行

## 三、管理员待办

1. **DNS**：把 `gongyi.neusymlab.cn` A 记录从 `198.18.0.204` 改为 `182.151.23.45`
2. **nginx**：`server_name` 追加 `182.151.23.45`（IP 直接访问）
3. **磁盘**：清理 `/var/log/btmp`（835MB）、`/tmp`（1.3GB）
4. **systemd**：配置开机自启

## 四、已修复的 Bug

| 日期 | 问题 | 修复 | 状态 |
|------|------|------|:---:|
| 6/21 | ZipPage 入库后 DbPage 锁屏 | 加 sessionStorage 解锁 | ✅ |
| 6/21 | Sample ZIP 无效 PDF | 生成有效占位 PDF | ✅ |
| 6/21 | YOLO 跳过流程 review 状态残留 | 清除 reviewFeedback | ✅ |
| 6/22 | RAG 低相似度误导 LLM | 阈值 0.20→0.40，低相似度走纯 LLM | ✅ |
| 6/22 | 工序拆分工种丢失 | 工步合并 + 入库工种校验 + 提取 prompt 加强 | ✅ |
| 6/22 | VLM 期间进度条卡死 | 8 秒心跳 45→49 | ✅ |
| 6/22 | 任务完成后重复生成 | onComplete 加锁 | ✅ |
| 6/22 | SSE 事件串台 | activeTaskIdRef 校验 | ✅ |
| 6/22 | 工艺表格空行 | 渲染前过滤 | ✅ |

## 五、测试覆盖

| 测试文件 | 数量 | 状态 |
|----------|:---:|:---:|
| `zip-to-db-flow.spec.ts` | 14 | ✅ 全部通过 |
| `db-preview.spec.ts` | 2 | ✅ 全部通过 |
| `upload-flow.spec.ts` | 7 | ✅ 无后端部分通过 |

## 六、代码提交链

```
128aaae fix: pipeline UX - VLM progress heartbeat, anti-resubmit lock, SSE taskId guard...
0d5c60b fix: update copyright to 机器学习与工业智能应用教育部工程研究中心
9e7055c chore: update GitNexus codebase index metadata
bc2e738 test: add ZIP import→DB browse flow tests (14 cases)
d88203c fix: sample ZIP import generates valid PDFs for missing files
56860e7 fix: YOLO skip flow review state + ZIP import sessionStorage unlock
e524e8d fix: tolerate missing legacy feature table on library delete
```

## 七、文档索引

| 文档 | 内容 |
|------|------|
| `docs/deployment/DONT-TOUCH.md` | 服务器保护清单 |
| `docs/deployment/admin-todo.md` | 管理员操作命令 |
| `docs/deployment/ssh-access-guide.md` | SSH 登录 + 模型训练指南 |
| `docs/deployment/2026-06-21-deployment-status.md` | 部署状态 + 回退方案 |
| `docs/deployment/2026-06-21-nginx-sudo-blocker.md` | nginx 配置 + 阻塞记录 |
| `docs/deployment/2026-06-22-process-quality-issues.md` | 工艺质量问题分析 + 实施方案 |
| `docs/deployment/2026-06-22-pipeline-display-fixes.md` | 全链路展示问题分析 |
| `docs/reports/2026-06-21-linux-server-trial-run-handoff.md` | Linux 试跑交接报告 |
| `docs/reports/2026-06-22-image-storage-analysis.md` | 图片存储方案分析 |

## 八、后续计划

1. **DNS 改完** → 所有人直接域名访问，不再需要 hosts/隧道
2. **磁盘清理** → 根分区从 99% 降下来
3. **systemd** → 重启后自动恢复服务
4. **HTTPS** → Let's Encrypt 证书
5. **MinIO** → 中期对象存储（非紧急）
