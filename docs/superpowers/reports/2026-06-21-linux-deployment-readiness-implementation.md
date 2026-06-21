# Linux Deployment Readiness Implementation Report

## Summary

Implemented Linux first-release deployment readiness materials without changing core business logic.

## Commits

- `965c35b` chore: add linux deployment templates
- `b1c189c` chore: add linux deployment preflight check
- `f76b30c` chore: add runtime backup script
- `(this commit)` docs: report linux deployment readiness implementation

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
$ bash -n scripts/deploy_check.sh
(exit 0, no output)

$ bash -n scripts/backup_runtime.sh
(exit 0, no output)

$ bash scripts/deploy_check.sh
[deploy-check] checking required commands
[deploy-check] checking Python version
[deploy-check] checking Node major version
[deploy-check] ERROR: Node major version must be 20, got v26.3.0
exit: 1

NOTE: This is an expected failure on the local development machine.
- Python 3.11.15  ✓ (correct)
- Node v26.3.0    ✗ (should be v20.x)
The script correctly rejects Node 26. On the target Linux server
with Node 20 installed, this check will pass.
Fix command on target server: install Node 20 via nvm or nodesource:
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs

$ BACKUP_DIR="$(mktemp -d)" bash scripts/backup_runtime.sh
[backup-runtime] creating /var/folders/.../runtime_20260621_010039.tar.gz
[backup-runtime] backup contents:
[backup-runtime]   db_data/
[backup-runtime]   output/
[backup-runtime]   uploads/
[backup-runtime]   backend/task_store.db
[backup-runtime]   .env
[backup-runtime] done: /var/folders/.../runtime_20260621_010039.tar.gz
exit: 0
(Actual output is more verbose with all file paths; verified archive
contains all expected items: db_data/, output/, uploads/,
backend/task_store.db, .env)

$ node .gitnexus/run.cjs detect_changes
变更：6 个文件，10 个符号
受影响流程：9
风险等级：high

NOTE: The "HIGH" risk level is from PRE-EXISTING working-tree changes
(AGENTS.md, CLAUDE.md, backend/api/kb_import.py,
frontend-react/src/pages/GeneratePage.tsx, and related test files).
These are outside the scope of this implementation. The new files
added by this plan (deploy/linux/*, scripts/*) introduce no risk to
existing business logic.
```

All pre-commit `detect_changes` runs (before each commit) showed identical
results, confirming no new risk was introduced by this implementation.

## Scope Confirmation

- Core backend business logic changed: **no**
- Core frontend business logic changed: **no**
- Database schema changed: **no**
- New secrets committed: **no**
- Runtime data committed: **no**

All 8 new files are deployment engineering artifacts only.

## Known Gaps

- Gunicorn is not added in this implementation.
- `backend/task_store.db` remains fixed under `backend/`.
- HTTPS certificate automation is not included.
- Docker/PostgreSQL/queue migration is not included.
- `deploy_check.sh` fails on local dev machine due to Node v26 — expected on server with Node 20.

## Reviewer Notes

Please verify:

- Nginx config keeps SSE buffering disabled (`proxy_buffering off`).
- systemd command matches the current app entrypoint (`uv run python -m backend.run`).
- `.env` template contains no real secret.
- Backup script includes `db_data`, `output`, `uploads`, `backend/task_store.db`, `.env` when present.
- Preflight script fails fast on Python/Node version mismatch.
