#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

command -v uv >/dev/null || {
  echo "uv未安装：https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}
uv run python scripts/runtime_smoke.py

BACKEND_PID=""
FRONTEND_PID=""

FLASK_DEBUG="${FLASK_DEBUG:-0}" uv run python -m backend.run &
BACKEND_PID=$!

cleanup() {
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

npm --prefix frontend-react run dev -- --host 127.0.0.1 &
FRONTEND_PID=$!
wait
