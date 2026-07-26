#!/usr/bin/env sh
set -eu

mkdir -p /app/uploads /app/output /app/db_data /app/logs

init_json_file() {
  target="$1"
  default_json="$2"
  if [ ! -e "$target" ]; then
    printf '%s\n' "$default_json" > "$target"
  fi
}

link_runtime_file() {
  target="$1"
  link_path="$2"
  if [ -e "$link_path" ] && [ ! -L "$link_path" ] && [ ! -e "$target" ]; then
    cp "$link_path" "$target"
  fi
  rm -f "$link_path"
  ln -s "$target" "$link_path"
}

init_json_file /app/db_data/history.json "[]"
init_json_file /app/db_data/backend-config.json "{}"

link_runtime_file /app/db_data/history.json /app/history.json
link_runtime_file /app/db_data/backend-config.json /app/backend/config.json
link_runtime_file /app/db_data/auth.db /app/backend/auth.db
link_runtime_file /app/db_data/task_store.db /app/backend/task_store.db

exec "$@"
