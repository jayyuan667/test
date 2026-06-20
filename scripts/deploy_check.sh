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
