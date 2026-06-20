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
