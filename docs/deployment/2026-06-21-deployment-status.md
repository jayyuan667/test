# 部署状态报告

**时间：** 2026-06-21 23:30  
**分支：** yolo-react  
**服务器：** liu4th (Ubuntu 24.04, via 182.151.23.45)

---

## 关键路径节点扫描

| CP | 节点 | 状态 | 备注 |
|----|------|------|------|
| CP1 | 代码冻结 | ✅ | 6 次提交，tar 包就绪 |
| CP2 | 服务器部署 | ✅ | health 200, capabilities OK |
| CP3 | 业务验收 | ✅ | 4 项通过（见下） |
| CP4 | 生产化 | 🟡 | nginx/systemd 需 sudo |

## 架构现状（防漂移基准）

```
当前架构不变：
  应用层：Flask backend.run → 0.0.0.0:5190
  前端：React/Vite build → Flask static serve
  数据库：SQLite → ~/smart-process-test/test/db_data/
  进程：nohup uv run python -m backend.run (PID 2940161)
  Python：3.11.15 (via uv)
  Node：v20.20.2 (via nvm)
  
未变更项：
  - 无数据库迁移
  - 无微服务拆分
  - 无中间件引入
  - API 路径不变
  - 前端路由不变
```

## 部署的提交

```
0d5c60b fix: update copyright to 机器学习与工业智能应用教育部工程研究中心
9e7055c chore: update GitNexus codebase index metadata
bc2e738 test: add ZIP import→DB browse flow tests (14 cases)
d88203c fix: sample ZIP import generates valid PDFs for missing files
56860e7 fix: YOLO skip flow review state + ZIP import sessionStorage unlock
```

## 业务验收结果

| 测试 | 方法 | 结果 |
|------|------|------|
| 4.1 Sample ZIP 导入 | POST /api/kb/import_zip | ✅ 8 matched, 0 errors |
| 4.3 知识库记录 | GET /api/library/records | ✅ 8 records visible |
| 4.4 删除记录 | DELETE /api/library/records/8 | ✅ success, total 8→7 |
| 4.5 端口转发访问 | Mac → SSH tunnel → liu4th:5190 | ✅ health 200 |

## 能力状态

```
python.available     = true (3.11.15)
database.available   = true, schema_ready
pdf.available        = true (pymupdf)
vision_api.available = true (doubao)
llm_api              = configured (deepseek-chat)
embedding            = configured
yolo.available       = false (模型文件缺失，不阻塞)
freecad.available    = false (未安装)
creo.available       = false (Linux 不支持)
```

## 待处理问题

| 问题 | 严重度 | 阻塞项 | 处理方式 |
|------|--------|--------|----------|
| nginx 域名配置 | 🟡 | 域名未生效 | 需管理员 sudo，配置已写好 |
| 磁盘 99% | 🔴 | 可能宕机 | 需清理 /tmp (1.3G), /var/log/btmp (835M) |
| systemd 服务 | 🟡 | 重启不自动恢复 | 需 sudo |
| YOLO 模型 | 🟢 | 不阻塞 | 可后续放置 best.onnx |

## 管理员待办

```bash
# 1. nginx 域名
sudo cp ~/gongyi-nginx.conf /etc/nginx/sites-available/gongyi
sudo ln -sf /etc/nginx/sites-available/gongyi /etc/nginx/sites-enabled/gongyi
sudo nginx -t && sudo systemctl reload nginx

# 2. 清理磁盘
sudo rm -f /var/log/btmp.1  # 626M
sudo journalctl --vacuum-size=200M

# 3. systemd 服务（可选）
sudo cp ~/smart-process-test/test/deploy/linux/smart-process.service /etc/systemd/system/
# 需要调整 User/WorkingDirectory/ExecStart 为 caojiayuan 用户
```

## 回退方案

```bash
# 恢复旧代码
cd ~/smart-process-test
pkill -f "python -m backend.run"
mv test test.new
mv test.backup.20260621_231222 test
cp test/.env .env.backup.20260621_231222 test/.env
cd test
FLASK_DEBUG=0 nohup uv run python -m backend.run > server.log 2>&1 &
```

---

*关联：[[task_plan]] [[findings]] [[2026-06-21-nginx-sudo-blocker]]*

---

## ⛔ 严禁操作（保护当前进度）

以下操作会直接破坏已部署的系统，**任何人不可执行**：

| 禁止操作 | 影响 | 崩溃程度 |
|----------|------|----------|
| `rm -rf ~/smart-process-test/test` | 清空运行中代码 | 🔴 服务立即宕机 |
| 修改或删除 `.env` 中的 `VISION_*`/`LLM_*`/`EMBEDDING_*` key | LLM/视觉/检索全部不可用 | 🔴 核心功能失效 |
| 手动改/删 `db_data/` 目录下的 `.db` 文件 | 数据库损坏 | 🔴 知识库全部丢失 |
| `pkill -f "python -m backend.run"` 后不重启 | 服务停止 | 🔴 网站无法访问 |
| 删除 `test.old` 目录 | 失去唯一回退副本 | 🟡 无法快速回退 |
| 修改 `frontend-react/src/App.tsx` 的 copyright | 刚改好的版权被覆盖 | 🟢 可再改 |
| `rm -rf frontend-react/dist/` | 前端 404 | 🔴 页面打不开 |
| 非管理员手动改 nginx/systemd 配置 | 配置漂移 | 🟡 后续部署混乱 |

### 绝对不可动的文件/目录

```
~/smart-process-test/test/.env           ← LLM/视觉/嵌入 key
~/smart-process-test/test/db_data/       ← SQLite 数据库
~/smart-process-test/test/frontend-react/dist/  ← 前端构建产物
~/smart-process-test/test.old/           ← 回退用的旧版本
~/smart-process-test/test.old/.env       ← 旧版 key 备份
~/smart-process-test/.env.backup.*       ← .env 备份
```

### 回退方法（仅紧急情况）

```bash
cd ~/smart-process-test
pkill -f "python -m backend.run"
mv test test.broken
cp -r test.old test
cp .env.backup.20260621_231222 test/.env
cd test
FLASK_DEBUG=0 nohup uv run python -m backend.run > server.log 2>&1 &
curl -f http://127.0.0.1:5190/api/health
```
