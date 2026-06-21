# Linux deployment templates

This directory contains copyable templates for the first Linux online version.

## Server assumptions

- Ubuntu 22.04 LTS or 24.04 LTS
- App user: `smartproc`
- App root: `/opt/smart-process-system/app`
- Runtime data root: `/opt/smart-process-system/shared`
- Backend port: `127.0.0.1:5190`
- Public traffic goes through Nginx on `80` or `443`

## Install system packages

```bash
sudo apt update
sudo apt install -y \
  git curl ca-certificates build-essential \
  nginx \
  poppler-utils \
  libgl1 libglib2.0-0 \
  fonts-noto-cjk
```

## Create user and directories

```bash
sudo useradd --system --create-home --shell /bin/bash smartproc
sudo mkdir -p /opt/smart-process-system/{shared/uploads,shared/output,shared/db_data,shared/logs,shared/backups}
sudo chown -R smartproc:smartproc /opt/smart-process-system
```

## Install app

```bash
sudo -iu smartproc
cd /opt/smart-process-system
git clone <repo-url> app
cd app
git checkout <release-commit>

curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv python install 3.11.15
uv sync --locked

npm --prefix frontend-react ci
npm --prefix frontend-react run build

# Safe migration: move real directories aside if they exist;
# for symlinks (repeat deployment), just replace them.
for dir in uploads output db_data; do
  if [ -e "$dir" ] && [ ! -L "$dir" ]; then
    mv "$dir" "${dir}.local.$(date +%Y%m%d_%H%M%S)"
  else
    rm -f "$dir"
  fi
done
ln -sfn /opt/smart-process-system/shared/uploads uploads
ln -sfn /opt/smart-process-system/shared/output output
ln -sfn /opt/smart-process-system/shared/db_data db_data

cp deploy/linux/env.production.example .env
chmod 600 .env
```

Edit `.env` on the server and fill only the capabilities needed for this release.

## Install systemd service

```bash
sudo cp /opt/smart-process-system/app/deploy/linux/smart-process.service /etc/systemd/system/smart-process.service
sudo systemctl daemon-reload
sudo systemctl enable smart-process
sudo systemctl start smart-process
sudo systemctl status smart-process --no-pager
```

## Install Nginx config

```bash
sudo cp /opt/smart-process-system/app/deploy/linux/nginx-smart-process.conf /etc/nginx/sites-available/smart-process
sudo ln -sfn /etc/nginx/sites-available/smart-process /etc/nginx/sites-enabled/smart-process
sudo nginx -t
sudo systemctl reload nginx
```

## Install logrotate config

```bash
sudo cp /opt/smart-process-system/app/deploy/linux/logrotate-smart-process /etc/logrotate.d/smart-process
sudo logrotate -d /etc/logrotate.d/smart-process
```

## Preflight check

```bash
cd /opt/smart-process-system/app
bash scripts/deploy_check.sh
```

## Runtime backup

```bash
cd /opt/smart-process-system/app
bash scripts/backup_runtime.sh
```
