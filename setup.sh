#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

command -v uv >/dev/null || {
  echo "uv未安装：https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}
command -v node >/dev/null || { echo "需要Node.js 20+"; exit 1; }
command -v npm >/dev/null || { echo "需要npm"; exit 1; }

uv python install 3.11.15
EXTRA_ARGS=""
[[ "${INSTALL_YOLO:-0}" == "1" ]] && EXTRA_ARGS="$EXTRA_ARGS --extra yolo"
[[ "${INSTALL_CREO:-0}" == "1" ]] && EXTRA_ARGS="$EXTRA_ARGS --extra windows-creo"
uv sync --locked $EXTRA_ARGS

[[ -f .env ]] || cp .env.example .env
mkdir -p db_data uploads output
npm --prefix frontend-react ci

uv run python scripts/runtime_smoke.py
echo "安装完成。编辑.env后运行 ./start.sh"
