# Smart Process Docker Deployment

This Docker package mirrors the current 203 deployment without changing the running systemd service.

## What Is Packaged

- `smart-process/app`: Flask backend plus built React frontend, listening on container port `5191`.
- `smart-process/yolo-gpu`: FastAPI YOLO service, listening on container port `8010`, with the seven binary YOLO models copied into the image.
- Runtime data remains outside images under `/opt/smart-process-system/shared`:
  - `uploads`
  - `output`
  - `db_data`, including `2d-v.db`, previews, auth DB, task DB, workflow records, and Docker runtime JSON state.
  - `logs`

Secrets are not copied into images. Use `deploy/docker/.env.docker` on the target server.

## Target Server Prerequisites

- Ubuntu 22.04 or 24.04.
- Docker Engine.
- Docker Compose v2 plugin.
- NVIDIA driver compatible with CUDA 12.4.
- NVIDIA Container Toolkit for the `yolo-gpu` service.
- At least 30 GiB RAM is recommended for the current ZIP import workload.

## Build On A Server With Internet

```bash
cd /opt/smart-process-system/app
cp deploy/docker/.env.docker.example deploy/docker/.env.docker
bash deploy/docker/prepare_runtime.sh
docker compose -f deploy/docker/docker-compose.prod.yml build
docker compose -f deploy/docker/docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:5191/api/health
curl -fsS http://127.0.0.1:8010/health
```

If host nginx is kept, proxy public `5190` to `127.0.0.1:5191`, matching the current 203 topology.

## Offline Package From 203

Run this on 203 after images have been built:

```bash
cd /opt/smart-process-system/app
bash deploy/docker/package_current_203.sh
```

To include real secrets for a controlled internal migration package:

```bash
cd /opt/smart-process-system/app
INCLUDE_SECRETS=1 bash deploy/docker/package_current_203.sh
```

The generated archive contains source, runtime data, Docker deployment files, and any locally built images.

## Restore On The New Server

```bash
sudo mkdir -p /opt/smart-process-system
cd /opt/smart-process-system
sudo tar -xzf /path/to/app-source.tar.gz
sudo tar -xzf /path/to/runtime-shared.tar.gz
sudo chown -R 986:986 /opt/smart-process-system/shared
cd /opt/smart-process-system/app
cp deploy/docker/.env.docker.example deploy/docker/.env.docker
```

Fill `deploy/docker/.env.docker` with the production keys and the same `YOLO_SERVICE_TOKEN` for both services.

If image tarballs are present:

```bash
gunzip -c /path/to/smart-process-app-image.tar.gz | docker load
gunzip -c /path/to/smart-process-yolo-gpu-image.tar.gz | docker load
```

Then start:

```bash
cd /opt/smart-process-system/app
bash deploy/docker/prepare_runtime.sh
docker compose -f deploy/docker/docker-compose.prod.yml up -d
docker compose -f deploy/docker/docker-compose.prod.yml ps
```

## Validation

```bash
curl -fsS http://127.0.0.1:5191/api/health
curl -fsS http://127.0.0.1:8010/health
docker compose -f deploy/docker/docker-compose.prod.yml logs --tail=200 app
docker compose -f deploy/docker/docker-compose.prod.yml logs --tail=200 yolo-gpu
```

Open the public nginx address and validate:

- Login.
- Upload a drawing.
- Skip YOLO review and wait on feature review.
- ZIP import busy prompt when more than two ZIP imports are submitted.
- Knowledge-base thumbnail browsing.

## Known Risk

203 currently times out when contacting Docker Hub. If the target server has the same network restriction, build images on a machine that can reach Docker Hub, run `docker save`, and transfer the image tarballs.
