# Linux 服务器上线迁移方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans if this plan is later turned into implementation work. This document is a deployment/migration plan only; it does not require code changes.

**Goal:** 在当前功能尚未完全完善的前提下，把系统以可回滚、可维护、可继续迭代的方式部署到 Linux 服务器。

**Architecture:** 首版按单机部署处理：Nginx 对外暴露 HTTP，后端 Flask 负责 API、SSE 与生产版 React 静态资源，SQLite 和运行产物保存在服务器持久化目录。功能未完善的模块不强行补齐，先通过配置、能力检查和运维边界保证线上版本稳定可用。

**Tech Stack:** Python 3.11.15、uv、Flask、SQLite、SSE、React 18、Vite、Node 20、Nginx、systemd、PyMuPDF、可选 Poppler/YOLO/Embedding/LLM。

---

## 1. 当前上线判断

当前系统适合先上“内部试运行版 / 单机验证版”，不适合直接按公网高并发生产系统处理。

可以上线的原因：

- 前后端已经有清晰入口：`backend/run.py`、`backend/app.py`、`frontend-react/dist`。
- 后端可以直接提供生产版 React 静态文件。
- SQLite、上传文件、输出文件都在本地目录，适合单机首版。
- 缺少 YOLO、Creo、FreeCAD 等能力时，系统已有部分降级路径。

主要风险：

- `backend/run.py` 当前用 Flask 内置服务器启动，首版内网可临时使用，但正式对外建议补 Gunicorn 或 Waitress 类 WSGI 服务。
- SSE 需要 Nginx 正确配置长连接和关闭缓冲。
- SQLite、`uploads/`、`output/`、`db_data/`、`backend/task_store.db` 都是有状态数据，不能跟随代码目录随意删除。
- Python 版本被启动检查固定为 `3.11.15`，服务器必须严格匹配。
- PDF/图像处理在 Linux 上依赖系统库，不能只看 Python 依赖安装是否成功。

---

## 2. 推荐部署形态

### 首版：单机一体化部署

```text
用户浏览器
  ↓
Nginx :80/:443
  ↓
Flask 服务 :5190
  ├─ /api/*              后端 API + SSE
  ├─ /assets/*           React 构建资源
  ├─ /                  React index.html
  ├─ uploads/            上传暂存
  ├─ output/             任务结果、图片、知识库导入产物
  ├─ db_data/2d-v.db     工艺库 / 向量库 SQLite
  └─ backend/task_store.db 任务状态 SQLite
```

首版不建议拆成前后端两个服务。当前后端已经能服务 `frontend-react/dist`，这样少一个跨域、少一个部署面，也更适合明后天上线。

### 后续演进形态

第二阶段再拆：

- Nginx 直接服务 `frontend-react/dist`
- API 走 Gunicorn 多 worker
- SQLite 迁移到 PostgreSQL 或至少独立数据卷
- 异步任务队列承接 PDF/视觉/LLM 长任务
- 对象存储保存上传文件、输出图片和快照

---

## 3. 服务器环境要求

### OS

推荐：

- Ubuntu 22.04 LTS 或 Ubuntu 24.04 LTS
- x86_64
- 至少 4 核 CPU / 8GB RAM / 80GB 磁盘

如果要跑本地 YOLO 或 OCR，建议：

- 8 核 CPU / 16GB RAM 起步
- 有 GPU 时后续单独做 CUDA/torch 适配，不放进首版上线阻塞项

### 系统包

```bash
sudo apt update
sudo apt install -y \
  git curl ca-certificates build-essential \
  nginx \
  poppler-utils \
  libgl1 libglib2.0-0 \
  fonts-noto-cjk
```

说明：

- `poppler-utils` 是 PyMuPDF 失败时的 PDF 回退能力准备。
- `libgl1`、`libglib2.0-0` 用于避免 OpenCV 在 Linux 上 import 失败。
- `fonts-noto-cjk` 避免中文导出或图片渲染缺字体。

### 运行时版本

```bash
python: 3.11.15
node: >=20 <21
npm: >=10
uv: 最新稳定版即可
```

当前后端启动检查要求 Python 精确等于 `3.11.15`。服务器不要用系统 Python 直接跑。

---

## 4. macOS 与 Linux 适配点

| 项目 | macOS 当前开发 | Linux 服务器要求 | 风险 |
|---|---|---|---|
| Python | uv 安装 3.11.15 | uv 安装 3.11.15 | 必须精确版本 |
| Node | Node 20 | Node 20 | 构建一致即可 |
| PyMuPDF | 可用 | 可用，但需验证 PDF 样本 | 中 |
| Poppler | 可选 | 建议安装 `poppler-utils` | 中 |
| OpenCV | 通常直接可用 | 需要 `libgl1` / `libglib2.0-0` | 高 |
| 文件路径 | `/Users/...` | `/opt/...` 或 `/srv/...` | 需要避免硬编码 |
| SQLite | 本地文件 | 必须持久化和备份 | 高 |
| Creo | 不适用 | Linux 也不适用 | 首版置空 |
| FreeCAD | 可选 | 后续单独适配 | 中 |
| YOLO 模型 | `db_data/best.onnx` 等 | 放入服务器 `db_data/` | 中 |

结论：PyMuPDF 不是不适配 macOS 或 Linux；之前的问题更像是样本 PDF/ZIP 产物无效或路径产物异常。Linux 上重点是系统库和真实样本验证。

---

## 5. 服务器目录规划

建议不要直接把运行数据放在随机工作目录。首版可以这样：

```text
/opt/smart-process-system/
  app/                    Git 代码
  shared/
    uploads/              上传暂存
    output/               任务输出、知识库导入产物
    db_data/              2d-v.db、模型、预览图
    logs/                 后端日志
    backups/              SQLite 和运行数据备份
  releases/
    20260621_xxxxxx/      后续做发布版本目录
```

但当前代码默认使用仓库内：

```text
uploads/
output/
db_data/
backend/task_store.db
backend.log
```

所以首版有两种选择：

1. 快速方案：代码目录即运行目录，直接备份这些目录和文件。
2. 稳定方案：使用软链接把仓库内运行目录指向 `/opt/smart-process-system/shared/`。

推荐首版使用稳定方案：

```bash
ln -sfn /opt/smart-process-system/shared/uploads /opt/smart-process-system/app/uploads
ln -sfn /opt/smart-process-system/shared/output /opt/smart-process-system/app/output
ln -sfn /opt/smart-process-system/shared/db_data /opt/smart-process-system/app/db_data
```

`backend/task_store.db` 当前路径固定在 `backend/` 目录内，首版先保留在代码目录并纳入备份；后续建议改为环境变量可配置。

---

## 6. 环境变量准备

服务器 `.env` 建议至少包含：

```bash
FLASK_DEBUG=0

VISION_MODE=doubao
VISION_API_KEY=
VISION_API_BASE=
VISION_MODEL_ID=

LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=

EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=
EMBEDDING_TRUST_ENV=1

YOLO_ONNX_PATH=/opt/smart-process-system/app/db_data/best.onnx
YOLO_WEIGHT_PATH=/opt/smart-process-system/app/db_data/best.pt
YOLO_DEVICE=cpu
YOLO_CONF=0.25
YOLO_IOU=0.45
YOLO_IMG_SIZE=1280

POPPLER_PATH=/usr/bin
BACKEND_LOG_PATH=/opt/smart-process-system/shared/logs/backend.log
```

如果明后天只上线空功能 / 演示骨架：

- 可以先不填 YOLO 模型。
- 可以先不填 Embedding，入库自测会返回 skipped，不应阻断业务。
- 如果需要真实“特征审阅 + 工艺生成”，必须填视觉模型和 LLM。

不要把 `.env`、模型文件、SQLite 数据库提交到 Git。

---

## 7. 首次部署步骤

### 7.1 创建用户和目录

```bash
sudo useradd --system --create-home --shell /bin/bash smartproc
sudo mkdir -p /opt/smart-process-system/{app,shared/uploads,shared/output,shared/db_data,shared/logs,shared/backups}
sudo chown -R smartproc:smartproc /opt/smart-process-system
```

### 7.2 拉代码

```bash
sudo -iu smartproc
cd /opt/smart-process-system
git clone <repo-url> app
cd app
git checkout <release-branch-or-commit>
```

### 7.3 安装 Python

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv python install 3.11.15
uv sync --locked
```

如果要启用 YOLO：

```bash
uv sync --locked --extra yolo
```

### 7.4 安装前端依赖并构建

```bash
npm --prefix frontend-react ci
npm --prefix frontend-react run build
```

### 7.5 准备运行目录

```bash
rm -rf uploads output db_data
ln -s /opt/smart-process-system/shared/uploads uploads
ln -s /opt/smart-process-system/shared/output output
ln -s /opt/smart-process-system/shared/db_data db_data
```

### 7.6 写入 `.env`

```bash
cp .env.example .env
chmod 600 .env
```

如果仓库没有 `.env.example`，直接创建 `.env`，内容按第 6 节填写。

### 7.7 启动前自检

```bash
uv run python scripts/runtime_smoke.py
uv run pytest backend/test_startup_checks.py backend/test_runtime_smoke.py -q
FLASK_DEBUG=0 uv run python -m backend.run
```

另开终端检查：

```bash
curl -f http://127.0.0.1:5190/api/health
curl -f http://127.0.0.1:5190/api/system/capabilities
curl -I http://127.0.0.1:5190/
```

---

## 8. systemd 服务

首版临时可用 Flask 内置服务，但 systemd 必须管起来。

创建 `/etc/systemd/system/smart-process.service`：

```ini
[Unit]
Description=Smart Process System
After=network.target

[Service]
Type=simple
User=smartproc
Group=smartproc
WorkingDirectory=/opt/smart-process-system/app
Environment=FLASK_DEBUG=0
EnvironmentFile=/opt/smart-process-system/app/.env
ExecStart=/home/smartproc/.local/bin/uv run python -m backend.run
Restart=always
RestartSec=5
StandardOutput=append:/opt/smart-process-system/shared/logs/systemd.out.log
StandardError=append:/opt/smart-process-system/shared/logs/systemd.err.log

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable smart-process
sudo systemctl start smart-process
sudo systemctl status smart-process --no-pager
```

正式对外前建议新增 Gunicorn 依赖，并将 `ExecStart` 改成类似：

```bash
uv run gunicorn -w 1 --threads 8 -b 127.0.0.1:5190 --timeout 300 backend.app:app
```

注意：当前任务状态有内存态和 SSE 长连接，首版不要盲目开多个 worker。先用 `-w 1 --threads 8`，后续重构任务状态和事件总线后再扩多进程。

---

## 9. Nginx 配置

创建 `/etc/nginx/sites-available/smart-process`：

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 100m;

    location / {
        proxy_pass http://127.0.0.1:5190;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/events/ {
        proxy_pass http://127.0.0.1:5190;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        add_header X-Accel-Buffering no;
    }
}
```

启用：

```bash
sudo ln -sfn /etc/nginx/sites-available/smart-process /etc/nginx/sites-enabled/smart-process
sudo nginx -t
sudo systemctl reload nginx
```

如果后续上 HTTPS，用 certbot 或公司网关终止 TLS。SSE 配置仍需保留。

---

## 10. 上线前准备清单

### 代码与构建

- [ ] 确认上线 commit SHA。
- [ ] `git status` 无非预期改动。
- [ ] `uv sync --locked` 成功。
- [ ] `npm --prefix frontend-react ci` 成功。
- [ ] `npm --prefix frontend-react run build` 成功。
- [ ] `frontend-react/dist/index.html` 存在。

### 配置

- [ ] `.env` 已放到服务器，权限 `600`。
- [ ] `FLASK_DEBUG=0`。
- [ ] 视觉模型配置按是否启用填写。
- [ ] LLM 配置按是否启用填写。
- [ ] Embedding 配置按是否启用填写。
- [ ] `POPPLER_PATH=/usr/bin`。
- [ ] YOLO 模型文件如需启用，已放入 `db_data/`。

### 数据

- [ ] `uploads/`、`output/`、`db_data/` 已持久化。
- [ ] `backend/task_store.db` 已纳入备份。
- [ ] 如从 macOS 迁移已有数据，复制 `db_data/2d-v.db`、`output/`、必要的 `uploads/`。
- [ ] 迁移后执行一次知识库列表和检索验证。

### 系统服务

- [ ] `smart-process.service` 已启用。
- [ ] 服务重启后 `/api/health` 正常。
- [ ] Nginx `client_max_body_size` 足够。
- [ ] `/api/events/` 关闭 proxy buffering。
- [ ] 防火墙只开放 80/443，不直接暴露 5190。

### 样本验收

- [ ] 上传 1 个真实 PDF。
- [ ] 能进入 YOLO 审阅或跳过 YOLO。
- [ ] 能进入特征审阅。
- [ ] 能生成或至少稳定显示未配置能力提示。
- [ ] 工艺入库在无 Embedding 时显示 skipped，不出现红色异常。
- [ ] 数据库浏览页面可打开。
- [ ] 导入 sample ZIP 不出现无效 PDF 错误。

---

## 11. 回滚方案

首版必须能在 5 分钟内回滚。

### 发布前备份

```bash
cd /opt/smart-process-system/app
git rev-parse HEAD > /opt/smart-process-system/shared/backups/last_good_commit.txt
tar -czf /opt/smart-process-system/shared/backups/runtime_$(date +%Y%m%d_%H%M%S).tar.gz \
  db_data output backend/task_store.db
```

### 回滚代码

```bash
sudo -iu smartproc
cd /opt/smart-process-system/app
git checkout $(cat /opt/smart-process-system/shared/backups/last_good_commit.txt)
npm --prefix frontend-react ci
npm --prefix frontend-react run build
uv sync --locked
sudo systemctl restart smart-process
```

### 回滚数据

只有确认是数据迁移损坏时才回滚数据。回滚前先停止服务：

```bash
sudo systemctl stop smart-process
```

恢复 `db_data/`、`output/`、`backend/task_store.db` 后再启动。

---

## 12. 运维与维护策略

### 日志

需要至少关注：

- `/opt/smart-process-system/shared/logs/backend.log`
- `/opt/smart-process-system/shared/logs/systemd.out.log`
- `/opt/smart-process-system/shared/logs/systemd.err.log`
- `/var/log/nginx/access.log`
- `/var/log/nginx/error.log`

建议后续加 logrotate，避免日志占满磁盘。

### 备份

每天至少备份：

- `db_data/2d-v.db`
- `backend/task_store.db`
- `output/`
- `.env` 的加密备份或密钥托管记录

`uploads/` 通常可短期保留；如果用户需要追溯原始上传，也应备份。

### 监控

首版最低限度：

- systemd 服务存活
- `/api/health` HTTP 200
- 磁盘空间
- 内存使用
- Nginx 5xx 数量

后续建议补：

- 任务失败率
- PDF 解析失败率
- LLM/Embedding 调用失败率
- SSE 中断率
- 入库成功率

---

## 13. 当前功能未完善时的上线策略

不要把未完善能力伪装成完整功能。首版页面和能力状态应该遵守：

- 没有 YOLO 模型：允许人工审阅或跳过 YOLO。
- 没有 Embedding：入库可以成功，但检索自测显示 skipped。
- 没有 LLM：工艺生成应返回清晰配置提示，不进入假进度。
- Creo 功能：Linux 首版明确不支持。
- FreeCAD/OnShape：未配置时不作为上线阻塞项。

上线目标是“稳定可演示、可收集问题、可持续迭代”，不是一次性补完所有能力。

---

## 14. 后续必须补的工程化改造

优先级从高到低：

1. 引入生产 WSGI 服务依赖，例如 Gunicorn，并固化 systemd 启动命令。
2. 将 `backend/task_store.db`、`db_data/2d-v.db`、`uploads/`、`output/` 改为环境变量可配置。
3. 增加 `/api/health` 深度检查：数据库可写、输出目录可写、模型配置状态。
4. 增加部署脚本：`scripts/deploy_check.sh`、`scripts/backup_runtime.sh`。
5. 增加 Linux CI smoke：Python 3.11.15、Node 20、前端构建、后端启动、PDF 样本解析。
6. 给知识库导入加更明确的错误分类：无效 PDF、路径错误、解析失败、匹配失败。
7. 长任务迁移到队列，SSE 只负责事件推送，不承担任务生命周期。
8. SQLite 迁移方案：首选 PostgreSQL；如果继续 SQLite，至少要单 writer 策略和备份锁。

---

## 15. 推荐上线节奏

### D-1：服务器准备

- 安装系统包、Python、Node、uv。
- 拉代码、构建前端。
- 准备 `.env`。
- 启动 systemd。
- Nginx 代理。

### D-Day：功能验收

- 验证健康检查。
- 验证真实 PDF 上传。
- 验证 YOLO 跳过/下一步。
- 验证特征审阅页面。
- 验证工艺生成或配置缺失提示。
- 验证工艺入库和数据库浏览。
- 验证 sample ZIP。

### D+1：维护补强

- 加备份任务。
- 加 logrotate。
- 补 Gunicorn。
- 补部署脚本。
- 梳理未完善功能的 UI 提示。

---

## 16. 不建议明后天上线前做的事

- 不建议临时重构数据库层。
- 不建议同时引入 Docker、队列、PostgreSQL、对象存储。
- 不建议在没有 GPU 验证的情况下承诺服务器 YOLO/GPU 性能。
- 不建议把 macOS 的 `output/` 绝对路径直接写入配置或数据库。
- 不建议打开 Flask debug。
- 不建议直接公网暴露 5190。

---

## 17. 最小上线命令摘要

```bash
sudo apt update
sudo apt install -y git curl ca-certificates build-essential nginx poppler-utils libgl1 libglib2.0-0 fonts-noto-cjk

sudo useradd --system --create-home --shell /bin/bash smartproc
sudo mkdir -p /opt/smart-process-system/{shared/uploads,shared/output,shared/db_data,shared/logs,shared/backups}
sudo chown -R smartproc:smartproc /opt/smart-process-system

sudo -iu smartproc
cd /opt/smart-process-system
git clone <repo-url> app
cd app
uv python install 3.11.15
uv sync --locked
npm --prefix frontend-react ci
npm --prefix frontend-react run build
rm -rf uploads output db_data
ln -s /opt/smart-process-system/shared/uploads uploads
ln -s /opt/smart-process-system/shared/output output
ln -s /opt/smart-process-system/shared/db_data db_data
cp .env.example .env
chmod 600 .env
uv run python scripts/runtime_smoke.py
```

然后配置 systemd 和 Nginx，执行：

```bash
sudo systemctl start smart-process
curl -f http://127.0.0.1:5190/api/health
```

