# Startup Integration Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local frontend/backend startup predictable on the Forge workflow ports.

**Architecture:** Keep startup logic in small shell scripts and npm script aliases. Use explicit port checks that diagnose conflicts but never kill processes automatically. Cover command regressions with a lightweight Python test.

**Tech Stack:** Bash, npm scripts, Python pytest/static tests, Next.js, Flask backend.

## Global Constraints

- Backend startup must use `./.venv/bin/python -m backend.app` when the virtual environment exists.
- Backend port defaults to `5390`, but caller-provided `BACKEND_PORT` must win.
- Frontend port defaults to `3002`.
- Port checks print the owning PID and a manual `kill <pid>` suggestion; scripts must not auto-kill.
- Do not commit runtime artifacts, local config JSON, database files, logs, uploads, output files, or secrets.

---

### Task 1: Backend startup contract

**Files:**
- Modify: `start-backend.sh`
- Create: `backend/test_startup_scripts.py`

**Interfaces:**
- Consumes: existing backend entrypoint `backend.app`.
- Produces: a project-root backend startup command that defaults to port `5390` and avoids global `python`.

- [ ] **Step 1: Write the failing test**

Create `backend/test_startup_scripts.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_backend_uses_module_entrypoint_and_project_python():
    script = (ROOT / "start-backend.sh").read_text(encoding="utf-8")

    assert "python app.py" not in script
    assert "-m backend.app" in script
    assert ".venv/bin/python" in script


def test_start_backend_defaults_to_5390_and_checks_port_conflict():
    script = (ROOT / "start-backend.sh").read_text(encoding="utf-8")

    assert "BACKEND_PORT=${BACKEND_PORT:-5390}" in script
    assert "lsof -tiTCP:${BACKEND_PORT}" in script
    assert "kill ${PORT_PID}" in script
```

- [ ] **Step 2: Verify RED**

Run:

```bash
./.venv/bin/python -m pytest backend/test_startup_scripts.py -q
```

Expected: fails because `start-backend.sh` still contains `python app.py` and lacks the explicit port check.

- [ ] **Step 3: Implement backend startup script**

Replace `start-backend.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

BACKEND_PORT=${BACKEND_PORT:-5390}
BACKEND_HOST=${BACKEND_HOST:-0.0.0.0}
FLASK_DEBUG=${FLASK_DEBUG:-0}
export BACKEND_PORT BACKEND_HOST FLASK_DEBUG

if [ -x "${ROOT_DIR}/.venv/bin/python" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "Python interpreter not found. Create .venv or install python3." >&2
  exit 1
fi

PORT_PID="$(lsof -tiTCP:${BACKEND_PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "${PORT_PID}" ]; then
  echo "Backend port ${BACKEND_PORT} is already in use by PID ${PORT_PID}." >&2
  echo "Stop it manually if safe: kill ${PORT_PID}" >&2
  exit 1
fi

echo "Starting Forge backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
exec "${PYTHON_BIN}" -m backend.app
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
./.venv/bin/python -m pytest backend/test_startup_scripts.py -q
```

Expected: `2 passed`.

---

### Task 2: Frontend/npm startup commands

**Files:**
- Modify: `package.json`
- Modify: `backend/test_startup_scripts.py`

**Interfaces:**
- Consumes: `start-backend.sh` from Task 1.
- Produces: npm aliases for backend and frontend startup.

- [ ] **Step 1: Extend the failing test**

Append to `backend/test_startup_scripts.py`:

```python
import json


def test_package_scripts_expose_stable_startup_commands():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert scripts["dev:frontend"] == "next dev --webpack -p 3002"
    assert scripts["start:frontend"] == "next start -p 3002"
    assert scripts["start:backend"] == "./start-backend.sh"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
./.venv/bin/python -m pytest backend/test_startup_scripts.py -q
```

Expected: fails because the new npm scripts are missing.

- [ ] **Step 3: Add npm scripts**

In `package.json`, add these script entries without removing existing scripts:

```json
"dev:frontend": "next dev --webpack -p 3002",
"start:frontend": "next start -p 3002",
"start:backend": "./start-backend.sh"
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
./.venv/bin/python -m pytest backend/test_startup_scripts.py -q
```

Expected: `3 passed`.

---

### Task 3: Verification and commit

**Files:**
- Verify only: `start-backend.sh`, `package.json`, `backend/test_startup_scripts.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: committed startup reliability fix.

- [ ] **Step 1: Run targeted verification**

Run:

```bash
./.venv/bin/python -m pytest backend/test_startup_scripts.py backend/test_task_events_v1.py backend/test_tasks_api_v1.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend workflow verification**

Run:

```bash
npx --no-install tsx --test $(rg --files src/features/drawing-workflow src/components/workflow | rg '\.test\.tsx?$')
```

Expected: all workflow tests pass.

- [ ] **Step 3: Check staged files**

Run:

```bash
git status --short
git diff -- start-backend.sh package.json backend/test_startup_scripts.py
```

Expected: only intended startup files are part of this implementation.

- [ ] **Step 4: Commit**

Run:

```bash
git add start-backend.sh package.json backend/test_startup_scripts.py docs/superpowers/plans/2026-07-17-startup-integration-reliability.md
git commit -m "fix: make local startup deterministic"
```
