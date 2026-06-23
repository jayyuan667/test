# 发现与决策

## 本次任务：Linux 服务器生产上线

### 关键发现

#### 代码审计
- 本地有 **6 个已修改文件**未提交，其中 4 个是关键 bug 修复
- `AGENTS.md` / `CLAUDE.md` 是 GitNexus 自动统计变更，可提交
- `backups/` 是运行时产物，不应进入源码包
- `frontend-react/tests/zip-to-db-flow.spec.ts` 是新增的 14 个测试文件

#### 服务器状态（来自试跑报告）
- 代码在 `~/smart-process-test/test`，使用 nohup 运行
- 根分区 93% 使用率，需关注
- Python 通过 uv 使用 3.11.15，Node 切到了 20.x
- 上次打包时排除了 `.git/`、`node_modules/`、`.venv/` 等
- tar 解压时有 macOS 扩展属性警告，不影响功能
- 两层 SSH 链路，端口转发用 `-L 5191:127.0.0.1:5190`

#### 已确认可用的能力
- python.available = true
- database.available = true, schema_ready = true
- pdf.available = true (pymupdf)
- vision_api.available = true (doubao)
- yolo.available = false (模型文件缺失)
- freecad.available = false
- creo.available = false (Linux 预期不支持)

#### 未确认的关键配置
- LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
- EMBEDDING_API_KEY / EMBEDDING_BASE_URL

#### 已知 Bug 修复状态
| Bug | 修复提交 | 是否在服务器上 |
|-----|---------|--------------|
| drawing_features 表缺失 → 删除库记录崩溃 | e524e8d | ❓ 不确定（tar 包是工作区快照） |
| sample ZIP 导入含无效 PDF | 未提交 | ❌ 不在服务器上 |
| YOLO 跳转后 review 状态残留 | 未提交 | ❌ 不在服务器上 |
| ZIP 入库后 DbPage 锁屏 | 未提交 | ❌ 不在服务器上 |

#### 架构兼容性
- 不需要数据库迁移（SQLite 原地升级，启动自动建表）
- 不需要改前端 API 路径
- .env 格式应向后兼容，需合并新增配置项
- 前端需要重新 build（Vite 构建产物依赖代码版本）

### 技术决策
| 决策 | 理由 |
|------|------|
| 先提交再打包 | 确保服务器代码与 git 一致，可追溯 |
| 保留旧代码备份而不是覆盖 | 快速回退 |
| 用 `--exclude` 精确控制 tar 内容 | 避免上次的"工作区快照"问题 |
| 不改变现有部署架构（nohup→systemd 等业务验收后） | 减少变量 |

### 风险清单
| 风险 | 影响 | 缓解 |
|------|------|------|
| 服务器磁盘满 | 服务不可用 | 部署前 `df -h` 检查 |
| .env 被覆盖 | LLM/Embedding 不可用 | 部署前备份，部署后 diff 对比 |
| 旧进程未完全退出 | 端口冲突 | `ss -ltnp` 确认 5190 空闲后再启动 |
| SSH 链路断开 | 部署中断 | 使用 `screen` 或 `tmux` 保持会话 |
| 前端构建失败 | 页面无法访问 | `npm run build` 在 deploy_check 中已验证 |
| 新代码引入兼容问题 | API 返回异常 | health check 是最小化验证 |

### 资源
- Linux 试跑报告：`docs/reports/2026-06-21-linux-server-trial-run-handoff.md`
- 竞品与技术栈评估：`docs/reports/智能工艺规程系统竞品与技术栈评估报告.docx`
- 工作优先级计划：`docs/reports/智能工艺规程系统当前工作优先级与两周执行计划.docx`
- 服务器代码路径：`~/smart-process-test/test`
- 后端日志：`~/smart-process-test/test/server.log`

---
*此文件记录上线实施的事实依据，决策前应重新读取。*
