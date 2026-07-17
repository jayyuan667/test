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
