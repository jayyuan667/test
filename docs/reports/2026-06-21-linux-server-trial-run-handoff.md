# Linux Server Trial Run Handoff Report

**Date:** 2026-06-21  
**Project:** 智能二维工艺系统 / YOLO + React + Flask  
**Purpose:** 记录当前 Linux 服务器试跑进度，方便后续模型或实施人员继续接手。

---

## 1. 当前结论

当前代码已经成功上传到 Linux 内层服务器，并完成基础部署试跑。

已确认：

- 代码包能在服务器解压。
- `uv` 已安装。
- Python 已通过 `uv` 使用 `3.11.15`。
- Node 已切到 `20.x`，npm 满足构建要求。
- `bash scripts/deploy_check.sh` 已通过。
- 前端生产构建成功。
- Flask 后端可启动。
- `/api/health` 正常。
- `/api/system/capabilities` 正常。
- `/` 前端入口正常返回 `index.html`。
- Mac 通过 SSH 端口转发可以访问页面。

当前属于“服务器预上线试跑通过基础环境”的状态，还没有完成完整业务链路验收。

---

## 2. 本地打包情况

本地生成过源码 tar 包：

```text
/Users/caojiayuan/Projects/work/smart-process-system-20260621_161459.tar.gz
```

打包时已排除：

- `.git/`
- `.gitnexus/`
- `.worktrees/`
- `.venv/`
- `node_modules/`
- `frontend-react/dist/`
- `uploads/`
- `output/`
- `db_data/`
- `backups/`
- `.env`
- `backend/config*.json`
- `backend/task_store.db`
- `history.json`
- 日志和缓存文件

注意：解压时 Linux `tar` 出现过 macOS 扩展属性提示：

```text
tar: 忽略未知的扩展头关键字 ‘LIBARCHIVE.xattr.com.apple.lastuseddate#PS’
```

这不是失败，解压后目录结构正常。

---

## 3. 服务器连接结构

当前访问链路是两层 SSH：

```text
Mac
  -> ssh caojiayuan@182.151.23.45
      -> ssh -p 12350 caojiayuan@localhost
          -> 内层 Ubuntu 24.04 服务器 liu4th
```

服务器登录后提示：

```text
Ubuntu 24.04.3 LTS
root filesystem usage about 93%
/mnt/data and /mnt/data-extra also close to warning/danger threshold
```

磁盘空间需要注意。源码包很小，但后续依赖、缓存、日志和运行数据可能继续占空间。

---

## 4. 服务器代码位置

代码已解压到：

```text
~/smart-process-test/test
```

确认过目录结构正常，包含：

```text
backend/
frontend-react/
deploy/
scripts/
pyproject.toml
uv.lock
README.md
```

---

## 5. 服务器环境安装进度

最开始环境状态：

```text
uv: 未安装
node: v18.19.1
npm: 9.2.0
python3: 3.12.3
```

已处理：

### uv

通过以下命令安装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

安装后：

```text
uv 0.11.23 (x86_64-unknown-linux-gnu)
```

### Node

通过 nvm 安装。过程中曾误输入：

```bash
source ~/.bashr
```

正确加载方式：

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
```

然后执行：

```bash
nvm install 20
nvm use 20
```

当前 Node 已满足 `deploy_check.sh`，否则自检不会通过。

### Python

项目使用 `uv` 管理 Python，要求：

```text
Python 3.11.15
```

`deploy_check.sh` 已验证 Python 版本通过。

---

## 6. 部署自检结果

在服务器项目目录执行：

```bash
cd ~/smart-process-test/test
bash scripts/deploy_check.sh
```

结果已通过：

```text
[deploy-check] all checks passed
```

自检过程中确认：

- 前端构建成功：

```text
vite v6.4.3 building for production...
✓ 55 modules transformed.
dist/index.html
dist/assets/index-*.css
dist/assets/index-*.js
✓ built
```

- 后端 runtime smoke 通过：

```json
{
  "ok": true,
  "python": {"available": true, "version": "3.11.15"},
  "database": {"available": true, "schema_ready": true},
  "pdf": {"available": true, "provider": "pymupdf"}
}
```

---

## 7. 当前能力状态

填入部分 key 后，执行：

```bash
curl -f http://127.0.0.1:5190/api/system/capabilities
```

已确认：

```text
python.available = true
database.available = true
database.schema_ready = true
pdf.available = true
pdf.provider = pymupdf
vision_api.available = true
vision_api.provider = doubao
yolo.available = false
freecad.available = false
creo.available = false
```

解释：

- 视觉模型 key 已配置成功。
- YOLO 未启用，因为模型文件不存在。
- FreeCAD 未安装。
- Creo 在 Linux 不支持，属于预期。

---

## 8. 后端启动状态

后端曾通过后台方式启动：

```bash
cd ~/smart-process-test/test
FLASK_DEBUG=0 nohup uv run python -m backend.run > server.log 2>&1 &
```

之后再次启动时报：

```text
Address already in use
Port 5190 is in use by another program.
```

这说明旧后端进程已经占用 `5190`，不是启动失败导致服务不可用。

服务器本机已验证：

```bash
curl -f http://127.0.0.1:5190/api/health
curl -f http://127.0.0.1:5190/api/system/capabilities
curl -I http://127.0.0.1:5190/
```

结果：

```text
/api/health -> 200 OK
/api/system/capabilities -> 200 OK
/ -> HTTP/1.1 200 OK, index.html
```

如需查看进程：

```bash
ss -ltnp | grep 5190
ps aux | grep "python -m backend.run" | grep -v grep
```

如需重启：

```bash
pkill -f "python -m backend.run"
sleep 2
cd ~/smart-process-test/test
FLASK_DEBUG=0 nohup uv run python -m backend.run > server.log 2>&1 &
sleep 3
tail -80 server.log
curl -f http://127.0.0.1:5190/api/health
```

---

## 9. Mac 浏览器访问方式

由于服务跑在内层服务器 `127.0.0.1:5190`，Mac 需要 SSH 端口转发。

推荐使用：

```bash
ssh -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -J caojiayuan@182.151.23.45 \
  -L 5191:127.0.0.1:5190 \
  -p 12350 caojiayuan@localhost
```

然后 Mac 浏览器打开：

```text
http://127.0.0.1:5191
```

说明：

```text
-L 5191:127.0.0.1:5190
```

含义是：

```text
Mac 本地 5191 -> 内层服务器 127.0.0.1:5190
```

所以 Mac 访问 `5191`，不是 `5190`。

如果使用：

```bash
-L 5190:127.0.0.1:5190
```

才是 Mac 访问 `5190`。

之所以使用 `5191`，是为了避免 Mac 本地旧转发或本地服务占用 `5190`。

---

## 10. SSH 连接断开的原因与处理

之前连接断过，判断主要是 SSH/端口转发链路断，不是后端服务停止。

原因：

- 两层 SSH 链路任一层断都会导致 Mac 浏览器访问中断。
- 云厂商 NAT / 防火墙可能断开空闲 TCP。
- Mac 网络切换、睡眠、VPN 变化也会断。
- 原端口转发窗口关闭后，浏览器访问必然中断。

处理方式：

- 使用 `ServerAliveInterval=30` 和 `ServerAliveCountMax=3`。
- 使用 `ssh -N` 作为纯转发窗口，不在里面执行远程命令。
- 如果断了，只需要重新开端口转发；后端通常不需要重启。

---

## 11. 当前还没完成的事项

### 必做

1. 跑真实 PDF 上传链路：

   - 上传 PDF
   - 跳过 YOLO 审阅
   - 进入特征审阅
   - 继续到工艺规程
   - 验证 LLM 工艺生成

2. 验证入库：

   - 工艺入库
   - 数据库/知识库页面能看到记录
   - 如果 Embedding 未配置，检索自测可能是 skipped

3. 验证删除库记录：

   - 删除一条记录
   - 确认不再出现：

   ```text
   sqlite3.OperationalError: no such table: drawing_features
   ```

4. 验证 sample ZIP 导入：

   - 确认不再出现无效 PDF / 路径错误。

5. 检查 `.env`：

   - `VISION_*` 已确认生效。
   - 需要确认 `LLM_*` 是否都填对。
   - 需要确认 `EMBEDDING_*` 是否填对。

### 可选

- 放置 YOLO 模型文件：

```text
~/smart-process-test/test/db_data/best.onnx
```

或在 `.env` 指定：

```bash
YOLO_ONNX_PATH=/home/caojiayuan/smart-process-test/test/db_data/best.onnx
YOLO_WEIGHT_PATH=/home/caojiayuan/smart-process-test/test/db_data/best.pt
```

暂时没有 YOLO 模型不阻塞基础试跑，可通过“跳过 YOLO 审阅”继续流程。

---

## 12. 当前代码/提交注意事项

本地仓库仍有未提交或未跟踪内容，需要后续整理：

```text
M AGENTS.md
M CLAUDE.md
M backend/api/kb_import.py
M backend/test_kb_import_formats.py
M frontend-react/src/pages/GeneratePage.tsx
M frontend-react/tests/upload-flow.spec.ts
?? backups/
?? docs/superpowers/plans/...
```

注意：

- `backups/` 是运行产物，不要提交。
- `AGENTS.md` / `CLAUDE.md` 可能是 GitNexus 自动统计变化，需要决定是否保留。
- `backend/api/kb_import.py` 和 `GeneratePage.tsx` 是之前修复 sample ZIP / YOLO 跳转相关的本地改动，需要确认是否已经进入服务器包。
- 当前上传的 tar 包包含当时工作区内容，不是纯净 git commit 状态。

---

## 13. 后续接手建议

下一位接手者应从这里开始：

1. 确认后端还在：

```bash
curl -f http://127.0.0.1:5190/api/health
```

2. 如 Mac 不能访问页面，重开端口转发：

```bash
ssh -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -J caojiayuan@182.151.23.45 \
  -L 5191:127.0.0.1:5190 \
  -p 12350 caojiayuan@localhost
```

3. 浏览器打开：

```text
http://127.0.0.1:5191
```

4. 跑真实 PDF 流程，并持续看服务器日志：

```bash
cd ~/smart-process-test/test
tail -f server.log
```

5. 如果出现错误，收集：

```bash
tail -120 server.log
curl -f http://127.0.0.1:5190/api/system/capabilities
```

6. 完成业务链路验收后，再考虑 systemd / Nginx 正式化：

```bash
sudo cp deploy/linux/smart-process.service /etc/systemd/system/smart-process.service
sudo systemctl daemon-reload
sudo systemctl enable smart-process
sudo systemctl start smart-process

sudo cp deploy/linux/nginx-smart-process.conf /etc/nginx/sites-available/smart-process
sudo ln -sfn /etc/nginx/sites-available/smart-process /etc/nginx/sites-enabled/smart-process
sudo nginx -t
sudo systemctl reload nginx
```

当前暂未执行 systemd / Nginx 正式安装，只是用 `nohup uv run python -m backend.run` 做试跑。

