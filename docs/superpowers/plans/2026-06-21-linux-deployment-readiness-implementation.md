# Linux Deployment Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改核心业务逻辑的前提下，补齐 Linux 首版上线所需的部署模板、自检脚本、备份脚本和验收清单，让明后天服务器部署有可执行材料。

**Architecture:** 本计划只增加部署工程文件：`deploy/linux/` 放 systemd、Nginx、环境变量模板和服务器安装说明；`scripts/` 放本地可执行的上线自检和备份脚本；`docs/superpowers/reports/` 放实施报告模板。后端业务、前端业务、数据库结构、LLM/YOLO/Embedding 功能均不在本计划内修改。

**Tech Stack:** Bash、systemd、Nginx、Python 3.11.15、uv、Node 20、npm、Flask、React/Vite、SQLite。

## Global Constraints

- 不修改核心业务逻辑文件：`backend/api/*`、`backend/pipeline/*`、`frontend-react/src/*` 不在本计划范围内。
- 不引入 Docker、PostgreSQL、Redis、Celery、对象存储。
- 不把 `.env`、API Key、模型文件、SQLite 数据库、上传文件、输出文件提交到 Git。
- Python 版本必须保持 `3.11.15`，Node 必须保持 `>=20 <21`。
- 所有脚本必须可重复执行，失败时要输出明确错误并返回非 0 退出码。
- 实施人员每个任务完成后单独提交；提交前必须运行 `node .gitnexus/run.cjs detect_changes` 或项目当前可用的 GitNexus 变更检测命令。

---

## File Structure

实施人员需要创建这些文件：

```text
deploy/
  linux/
    README.md                         Linux 首版部署操作说明
    env.production.example            生产环境变量模板，不含真实密钥
    smart-process.service             systemd 服务模板
    nginx-smart-process.conf          Nginx 反向代理模板，包含 SSE 配置
    logrotate-smart-process           日志轮转模板

scripts/
  deploy_check.sh                     上线前自检脚本
  backup_runtime.sh                   运行数据备份脚本

docs/superpowers/reports/
  2026-06-21-linux-deployment-readiness-implementation.md
                                      实施报告，记录实际改动、测试结果、未完成项
```

不修改这些文件：

```text
backend/run.py
backend/app.py
backend/config.py
backend/task_store.py
backend/vector_map_rag.py
frontend-react/src/**
```

---

### Task 1: Add Linux deployment templates

**Files:**
- Create: `deploy/linux/README.md`
- Create: `deploy/linux/env.production.example`
- Create: `deploy/linux/smart-process.service`
- Create: `deploy/linux/nginx-smart-process.conf`
- Create: `deploy/linux/logrotate-smart-process`

**Interfaces:**
- Consumes: Existing app entrypoint `uv run python -m backend.run`
- Consumes: Existing production frontend path `frontend-react/dist`
- Produces: Copyable server deployment templates for systemd, Nginx, `.env`, and logrotate

- [ ] **Step 1: Create deployment directory**

Run:

```bash
mkdir -p deploy/linux
```

Expected: `deploy/linux` exists.

- [ ] **Step 2: Create production env template**

Create `deploy/linux/env.production.example` with exactly this content:

```bash
# Copy this file to /opt/smart-process-system/app/.env on the Linux server.
# Do not commit real secrets.

FLASK_DEBUG=0

# Vision model. Required for real feature review / drawing analysis unless VISION_MODE=local is used.
VISION_MODE=doubao
VISION_API_KEY=
VISION_API_BASE=
VISION_MODEL_ID=

# LLM. Required for process generation.
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=

# Embedding. Optional for first online version; missing key should make retrieval self-check skipped.
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=
EMBEDDING_TRUST_ENV=1

# YOLO. Optional for first online version; missing model should allow manual review or skip flow.
YOLO_ONNX_PATH=/opt/smart-process-system/app/db_data/best.onnx
YOLO_WEIGHT_PATH=/opt/smart-process-system/app/db_data/best.pt
YOLO_DEVICE=cpu
YOLO_CONF=0.25
YOLO_IOU=0.45
YOLO_IMG_SIZE=1280

# PDF fallback.
POPPLER_PATH=/usr/bin

# Extra backend log location.
BACKEND_LOG_PATH=/opt/smart-process-system/shared/logs/backend.log
```

- [ ] **Step 3: Create systemd service template**

Create `deploy/linux/smart-process.service` with exactly this content:

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

- [ ] **Step 4: Create Nginx template with SSE-safe proxying**

Create `deploy/linux/nginx-smart-process.conf` with exactly this content:

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

- [ ] **Step 5: Create logrotate template**

Create `deploy/linux/logrotate-smart-process` with exactly this content:

```text
/opt/smart-process-system/shared/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
```

- [ ] **Step 6: Create Linux deployment README**

Create `deploy/linux/README.md` with exactly this content:

````markdown
# Linux deployment templates

This directory contains copyable templates for the first Linux online version.

## Server assumptions

- Ubuntu 22.04 LTS or 24.04 LTS
- App user: `smartproc`
- App root: `/opt/smart-process-system/app`
- Runtime data root: `/opt/smart-process-system/shared`
- Backend port: `127.0.0.1:5190`
- Public traffic goes through Nginx on `80` or `443`

## Install system packages

```bash
sudo apt update
sudo apt install -y \
  git curl ca-certificates build-essential \
  nginx \
  poppler-utils \
  libgl1 libglib2.0-0 \
  fonts-noto-cjk
```

## Create user and directories

```bash
sudo useradd --system --create-home --shell /bin/bash smartproc
sudo mkdir -p /opt/smart-process-system/{shared/uploads,shared/output,shared/db_data,shared/logs,shared/backups}
sudo chown -R smartproc:smartproc /opt/smart-process-system
```

## Install app

```bash
sudo -iu smartproc
cd /opt/smart-process-system
git clone <repo-url> app
cd app
git checkout <release-commit>

curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv python install 3.11.15
uv sync --locked

npm --prefix frontend-react ci
npm --prefix frontend-react run build

rm -rf uploads output db_data
ln -s /opt/smart-process-system/shared/uploads uploads
ln -s /opt/smart-process-system/shared/output output
ln -s /opt/smart-process-system/shared/db_data db_data

cp deploy/linux/env.production.example .env
chmod 600 .env
```

Edit `.env` on the server and fill only the capabilities needed for this release.

## Install systemd service

```bash
sudo cp /opt/smart-process-system/app/deploy/linux/smart-process.service /etc/systemd/system/smart-process.service
sudo systemctl daemon-reload
sudo systemctl enable smart-process
sudo systemctl start smart-process
sudo systemctl status smart-process --no-pager
```

## Install Nginx config

```bash
sudo cp /opt/smart-process-system/app/deploy/linux/nginx-smart-process.conf /etc/nginx/sites-available/smart-process
sudo ln -sfn /etc/nginx/sites-available/smart-process /etc/nginx/sites-enabled/smart-process
sudo nginx -t
sudo systemctl reload nginx
```

## Install logrotate config

```bash
sudo cp /opt/smart-process-system/app/deploy/linux/logrotate-smart-process /etc/logrotate.d/smart-process
sudo logrotate -d /etc/logrotate.d/smart-process
```

## Preflight check

```bash
cd /opt/smart-process-system/app
bash scripts/deploy_check.sh
```

## Runtime backup

```bash
cd /opt/smart-process-system/app
bash scripts/backup_runtime.sh
```

````

- [ ] **Step 7: Validate templates**

Run:

```bash
test -f deploy/linux/README.md
test -f deploy/linux/env.production.example
test -f deploy/linux/smart-process.service
test -f deploy/linux/nginx-smart-process.conf
test -f deploy/linux/logrotate-smart-process
grep -q "proxy_buffering off" deploy/linux/nginx-smart-process.conf
grep -q "FLASK_DEBUG=0" deploy/linux/env.production.example
grep -q "uv run python -m backend.run" deploy/linux/smart-process.service
```

Expected: all commands exit `0`.

- [ ] **Step 8: Commit**

Run:

```bash
node .gitnexus/run.cjs detect_changes
git add deploy/linux
git commit -m "chore: add linux deployment templates"
```

Expected: commit contains only files under `deploy/linux/`.

---

### Task 2: Add deployment preflight script

**Files:**
- Create: `scripts/deploy_check.sh`

**Interfaces:**
- Consumes: Existing `pyproject.toml`, `frontend-react/package.json`, `backend/run.py`, `scripts/runtime_smoke.py`
- Produces: A repeatable local/server preflight command: `bash scripts/deploy_check.sh`

- [ ] **Step 1: Create preflight script**

Create `scripts/deploy_check.sh` with exactly this content:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
  echo "[deploy-check] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[deploy-check] $*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

info "checking required commands"
require_cmd uv
require_cmd node
require_cmd npm

info "checking Python version"
PY_VERSION="$(uv run python - <<'PY'
import sys
print(".".join(map(str, sys.version_info[:3])))
PY
)"
if [ "$PY_VERSION" != "3.11.15" ]; then
  fail "Python must be 3.11.15, got $PY_VERSION"
fi

info "checking Node major version"
NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
if [ "$NODE_MAJOR" != "20" ]; then
  fail "Node major version must be 20, got $(node -v)"
fi

info "checking frontend lockfile install state"
if [ ! -d frontend-react/node_modules ]; then
  fail "frontend-react/node_modules missing; run: npm --prefix frontend-react ci"
fi

info "checking frontend production build"
npm --prefix frontend-react run build
test -f frontend-react/dist/index.html || fail "frontend-react/dist/index.html missing after build"

info "checking runtime directories"
mkdir -p uploads output db_data
test -w uploads || fail "uploads is not writable"
test -w output || fail "output is not writable"
test -w db_data || fail "db_data is not writable"

info "checking backend runtime smoke"
uv run python scripts/runtime_smoke.py

info "checking Flask app import"
FLASK_DEBUG=0 uv run python - <<'PY'
from backend.app import app
print(app.name)
PY

info "checking deployment templates"
test -f deploy/linux/env.production.example || fail "deploy/linux/env.production.example missing"
test -f deploy/linux/smart-process.service || fail "deploy/linux/smart-process.service missing"
test -f deploy/linux/nginx-smart-process.conf || fail "deploy/linux/nginx-smart-process.conf missing"
grep -q "proxy_buffering off" deploy/linux/nginx-smart-process.conf || fail "nginx SSE buffering config missing"

info "all checks passed"
```

- [ ] **Step 2: Make script executable**

Run:

```bash
chmod +x scripts/deploy_check.sh
```

Expected: `test -x scripts/deploy_check.sh` exits `0`.

- [ ] **Step 3: Validate shell syntax**

Run:

```bash
bash -n scripts/deploy_check.sh
```

Expected: exits `0`.

- [ ] **Step 4: Run preflight locally**

Run:

```bash
bash scripts/deploy_check.sh
```

Expected:

```text
[deploy-check] all checks passed
```

If it fails because local Node/Python dependencies are not installed, the implementation report must include the exact failure and the command needed to fix it. Do not hide the failure.

- [ ] **Step 5: Commit**

Run:

```bash
node .gitnexus/run.cjs detect_changes
git add scripts/deploy_check.sh
git commit -m "chore: add linux deployment preflight check"
```

Expected: commit contains only `scripts/deploy_check.sh`.

---

### Task 3: Add runtime backup script

**Files:**
- Create: `scripts/backup_runtime.sh`

**Interfaces:**
- Consumes: Runtime paths `db_data`, `output`, `uploads`, `backend/task_store.db`, `.env`
- Produces: Timestamped tar archive under `backups/` or `$BACKUP_DIR`

- [ ] **Step 1: Create backup script**

Create `scripts/backup_runtime.sh` with exactly this content:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="$BACKUP_DIR/runtime_$STAMP.tar.gz"

info() {
  echo "[backup-runtime] $*"
}

mkdir -p "$BACKUP_DIR"

INCLUDES=()

if [ -d db_data ]; then
  INCLUDES+=("db_data")
fi

if [ -d output ]; then
  INCLUDES+=("output")
fi

if [ -d uploads ]; then
  INCLUDES+=("uploads")
fi

if [ -f backend/task_store.db ]; then
  INCLUDES+=("backend/task_store.db")
fi

if [ -f .env ]; then
  INCLUDES+=(".env")
fi

if [ "${#INCLUDES[@]}" -eq 0 ]; then
  echo "[backup-runtime] ERROR: no runtime files found to back up" >&2
  exit 1
fi

info "creating $ARCHIVE"
tar -czf "$ARCHIVE" "${INCLUDES[@]}"

info "backup contents:"
tar -tzf "$ARCHIVE" | sed 's/^/[backup-runtime]   /'

info "done: $ARCHIVE"
```

- [ ] **Step 2: Make script executable**

Run:

```bash
chmod +x scripts/backup_runtime.sh
```

Expected: `test -x scripts/backup_runtime.sh` exits `0`.

- [ ] **Step 3: Validate shell syntax**

Run:

```bash
bash -n scripts/backup_runtime.sh
```

Expected: exits `0`.

- [ ] **Step 4: Run backup in a temporary target directory**

Run:

```bash
BACKUP_DIR="$(mktemp -d)" bash scripts/backup_runtime.sh
```

Expected output includes:

```text
[backup-runtime] done:
```

Expected: one `runtime_*.tar.gz` archive exists in the temporary directory.

- [ ] **Step 5: Commit**

Run:

```bash
node .gitnexus/run.cjs detect_changes
git add scripts/backup_runtime.sh
git commit -m "chore: add runtime backup script"
```

Expected: commit contains only `scripts/backup_runtime.sh`.

---

### Task 4: Add implementation report

**Files:**
- Create: `docs/superpowers/reports/2026-06-21-linux-deployment-readiness-implementation.md`

**Interfaces:**
- Consumes: Results from Task 1-3
- Produces: Review-ready implementation report for acceptance

- [ ] **Step 1: Create implementation report**

Create `docs/superpowers/reports/2026-06-21-linux-deployment-readiness-implementation.md` with exactly this structure, replacing command outputs with real results:

```markdown
# Linux Deployment Readiness Implementation Report

## Summary

Implemented Linux first-release deployment readiness materials without changing core business logic.

## Commits

- `<sha>` chore: add linux deployment templates
- `<sha>` chore: add linux deployment preflight check
- `<sha>` chore: add runtime backup script

## Files Added

- `deploy/linux/README.md`
- `deploy/linux/env.production.example`
- `deploy/linux/smart-process.service`
- `deploy/linux/nginx-smart-process.conf`
- `deploy/linux/logrotate-smart-process`
- `scripts/deploy_check.sh`
- `scripts/backup_runtime.sh`
- `docs/superpowers/reports/2026-06-21-linux-deployment-readiness-implementation.md`

## Verification

```text
bash -n scripts/deploy_check.sh
<paste result>

bash -n scripts/backup_runtime.sh
<paste result>

bash scripts/deploy_check.sh
<paste result>

BACKUP_DIR="$(mktemp -d)" bash scripts/backup_runtime.sh
<paste result>

node .gitnexus/run.cjs detect_changes
<paste result>
```

## Scope Confirmation

- Core backend business logic changed: no
- Core frontend business logic changed: no
- Database schema changed: no
- New secrets committed: no
- Runtime data committed: no

## Known Gaps

- Gunicorn is not added in this implementation.
- `backend/task_store.db` remains fixed under `backend/`.
- HTTPS certificate automation is not included.
- Docker/PostgreSQL/queue migration is not included.

## Reviewer Notes

Please verify:

- Nginx config keeps SSE buffering disabled.
- systemd command matches the current app entrypoint.
- `.env` template contains no real secret.
- Backup script includes `db_data`, `output`, `uploads`, `backend/task_store.db`, `.env` when present.
- Preflight script fails fast on Python/Node version mismatch.
```

- [ ] **Step 2: Fill real commit SHAs and command outputs**

Run:

```bash
git log --oneline -5
bash -n scripts/deploy_check.sh
bash -n scripts/backup_runtime.sh
BACKUP_DIR="$(mktemp -d)" bash scripts/backup_runtime.sh
node .gitnexus/run.cjs detect_changes
```

Paste the real outputs into the report.

- [ ] **Step 3: Commit**

Run:

```bash
node .gitnexus/run.cjs detect_changes
git add docs/superpowers/reports/2026-06-21-linux-deployment-readiness-implementation.md
git commit -m "docs: report linux deployment readiness implementation"
```

Expected: commit contains only the implementation report.

---

## Acceptance Checklist for Reviewer

After implementation, reviewer should check:

- [ ] No core business files changed unless explicitly approved.
- [ ] `deploy/linux/env.production.example` has no real API keys.
- [ ] `deploy/linux/nginx-smart-process.conf` contains `proxy_buffering off` in `/api/events/`.
- [ ] `deploy/linux/smart-process.service` runs from `/opt/smart-process-system/app`.
- [ ] `scripts/deploy_check.sh` checks Python `3.11.15`, Node major `20`, frontend build, runtime directories, runtime smoke, Flask import, and deployment templates.
- [ ] `scripts/backup_runtime.sh` creates a timestamped tar archive and includes runtime data when present.
- [ ] Both scripts pass `bash -n`.
- [ ] Implementation report includes real command outputs.
- [ ] GitNexus `detect_changes` output is included before final handoff.

---

## Explicit Non-Goals

- Do not fix YOLO / feature review / process generation behavior in this plan.
- Do not change `backend/run.py` to Gunicorn in this plan.
- Do not move SQLite paths to environment variables in this plan.
- Do not change database schema.
- Do not add Docker.
- Do not deploy to the real server from this plan unless separately authorized.

