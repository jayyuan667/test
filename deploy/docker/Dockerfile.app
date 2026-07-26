# syntax=docker/dockerfile:1

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /src/frontend-react
COPY frontend-react/package.json frontend-react/package-lock.json ./
RUN npm ci
COPY frontend-react ./
RUN npm run build

FROM python:3.11-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --locked \
    && uv pip install --python .venv/bin/python "gunicorn>=23,<24"

COPY backend ./backend
COPY scripts ./scripts
COPY fonts ./fonts
COPY deploy/docker/entrypoint-app.sh /usr/local/bin/entrypoint-app.sh
COPY --from=frontend-build /src/frontend-react/dist ./frontend-react/dist

RUN chmod +x /usr/local/bin/entrypoint-app.sh \
    && mkdir -p uploads output db_data logs frontend-react \
    && find backend -name "__pycache__" -type d -prune -exec rm -rf {} + \
    && find backend -type f \( -name "*.db" -o -name "*.db-*" -o -name "*.db--*" -o -name "*.bak" -o -name "*.bak-*" \) -delete \
    && rm -f backend/config.json backend/config_cloud.json backend/config_local.json history.json task_store.db \
    && if ! getent group 986 >/dev/null; then groupadd --gid 986 smartproc; fi \
    && if ! getent passwd 986 >/dev/null; then useradd --uid 986 --gid 986 --home-dir /app --shell /usr/sbin/nologin smartproc; fi \
    && chown -R smartproc:smartproc /app

USER smartproc
EXPOSE 5191

ENTRYPOINT ["/usr/local/bin/entrypoint-app.sh"]
CMD ["gunicorn", "--chdir", "/app", "--bind", "0.0.0.0:5191", "--worker-class", "gthread", "--workers", "2", "--threads", "20", "--timeout", "600", "--keep-alive", "5", "backend.app:app"]
