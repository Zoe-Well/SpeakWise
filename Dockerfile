FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPEAKWISE_DATA_DIR=/data \
    FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
RUN uv sync --frozen --no-dev
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["sh", "-c", ".venv/bin/uvicorn backend.src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
