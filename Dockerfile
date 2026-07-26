FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils curl git \
    && rm -rf /var/lib/apt/lists/*

# Node.js for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --locked

# Frontend build
COPY frontend-react ./frontend-react
RUN cd frontend-react && npm ci && npm run build

# App code
COPY backend ./backend
COPY scripts ./scripts
COPY deploy ./deploy
COPY fonts ./fonts
COPY gpu_service ./gpu_service
COPY .env ./

RUN mkdir -p uploads output db_data logs

EXPOSE 5190
CMD ["uv", "run", "gunicorn", "--chdir", "/app", "--bind", "0.0.0.0:5190", "--worker-class", "gthread", "--workers", "2", "--threads", "20", "--timeout", "600", "backend.app:app"]
