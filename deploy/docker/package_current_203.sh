#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/smart-process-system/app}"
SHARED_ROOT="${SHARED_ROOT:-/opt/smart-process-system/shared}"
OUT_DIR="${OUT_DIR:-$APP_ROOT/deploy/docker/packages}"
STAMP="$(date +%Y%m%d_%H%M%S)"
PACKAGE_DIR="$OUT_DIR/smart-process-203-$STAMP"
APP_NAME="$(basename "$APP_ROOT")"

mkdir -p "$PACKAGE_DIR"

bash "$APP_ROOT/deploy/docker/prepare_runtime.sh"

tar \
  --exclude="$APP_NAME/.env" \
  --exclude="$APP_NAME/.env.*" \
  --exclude="$APP_NAME/.venv" \
  --exclude="$APP_NAME/frontend-react/node_modules" \
  --exclude="$APP_NAME/frontend-react/dist" \
  --exclude="$APP_NAME/frontend-react/dist.bak-*" \
  --exclude="$APP_NAME/uploads" \
  --exclude="$APP_NAME/output" \
  --exclude="$APP_NAME/db_data" \
  --exclude="$APP_NAME/db_data.local" \
  --exclude="$APP_NAME/output.local" \
  --exclude="$APP_NAME/uploads.local" \
  --exclude="$APP_NAME/backend/*.db*" \
  --exclude="$APP_NAME/backend/config*.json" \
  --exclude="$APP_NAME/backend/*.bak*" \
  --exclude="$APP_NAME/backend/*deploy-local*" \
  --exclude="$APP_NAME/backend/__pycache__" \
  --exclude="$APP_NAME/backend/*/__pycache__" \
  --exclude="$APP_NAME/backend/*/*/__pycache__" \
  --exclude="$APP_NAME/backend/*.pyc" \
  --exclude="$APP_NAME/backend/*/*.pyc" \
  --exclude="$APP_NAME/backend/*/*/*.pyc" \
  --exclude="$APP_NAME/backend/sample_zip" \
  --exclude="$APP_NAME/scripts/__pycache__" \
  --exclude="$APP_NAME/scripts/*.pyc" \
  --exclude="$APP_NAME/gpu_service/__pycache__" \
  --exclude="$APP_NAME/gpu_service/*.pyc" \
  --exclude="$APP_NAME/*.log" \
  --exclude="$APP_NAME/*.db" \
  --exclude="$APP_NAME/*.bak*" \
  --exclude="$APP_NAME/*deploy-local*" \
  --exclude="$APP_NAME/deploy/docker/packages" \
  -C "$(dirname "$APP_ROOT")" \
  -czf "$PACKAGE_DIR/app-source.tar.gz" \
  "$APP_NAME"

tar -C "$(dirname "$SHARED_ROOT")" -czf "$PACKAGE_DIR/runtime-shared.tar.gz" "$(basename "$SHARED_ROOT")"

cp "$APP_ROOT/deploy/docker/docker-compose.prod.yml" "$PACKAGE_DIR/"
cp "$APP_ROOT/deploy/docker/.env.docker.example" "$PACKAGE_DIR/"
cp "$APP_ROOT/deploy/docker/README.md" "$PACKAGE_DIR/"

if [ "${INCLUDE_SECRETS:-0}" = "1" ]; then
  cp "$APP_ROOT/.env" "$PACKAGE_DIR/.env.docker"
  chmod 600 "$PACKAGE_DIR/.env.docker"
  echo "Included real .env as .env.docker because INCLUDE_SECRETS=1"
else
  echo "Skipped real .env. Set INCLUDE_SECRETS=1 only for controlled offline migration."
fi

if docker image inspect smart-process/app:203-20260721 >/dev/null 2>&1; then
  docker save smart-process/app:203-20260721 | gzip > "$PACKAGE_DIR/smart-process-app-image.tar.gz"
fi

if docker image inspect smart-process/yolo-gpu:203-20260721 >/dev/null 2>&1; then
  docker save smart-process/yolo-gpu:203-20260721 | gzip > "$PACKAGE_DIR/smart-process-yolo-gpu-image.tar.gz"
fi

tar -C "$OUT_DIR" -czf "$OUT_DIR/smart-process-203-$STAMP.tar.gz" "smart-process-203-$STAMP"

echo "$OUT_DIR/smart-process-203-$STAMP.tar.gz"
