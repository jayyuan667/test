#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/smart-process-system/app}"
SHARED_ROOT="${SHARED_ROOT:-/opt/smart-process-system/shared}"
APP_UID="${APP_UID:-986}"
APP_GID="${APP_GID:-986}"

mkdir -p \
  "$SHARED_ROOT/uploads" \
  "$SHARED_ROOT/output" \
  "$SHARED_ROOT/db_data" \
  "$SHARED_ROOT/logs" \
  "$SHARED_ROOT/backups"

copy_if_present() {
  local src="$1"
  local dst="$2"
  if [ -e "$src" ] && [ ! -e "$dst" ]; then
    cp -aL "$src" "$dst"
  fi
}

copy_if_present "$APP_ROOT/history.json" "$SHARED_ROOT/db_data/history.json"
copy_if_present "$APP_ROOT/backend/config.json" "$SHARED_ROOT/db_data/backend-config.json"
copy_if_present "$APP_ROOT/backend/auth.db" "$SHARED_ROOT/db_data/auth.db"
copy_if_present "$APP_ROOT/backend/task_store.db" "$SHARED_ROOT/db_data/task_store.db"

[ -e "$SHARED_ROOT/db_data/history.json" ] || printf '[]\n' > "$SHARED_ROOT/db_data/history.json"
[ -e "$SHARED_ROOT/db_data/backend-config.json" ] || printf '{}\n' > "$SHARED_ROOT/db_data/backend-config.json"

chown -R "$APP_UID:$APP_GID" "$SHARED_ROOT"

echo "Runtime directories are ready under $SHARED_ROOT"
