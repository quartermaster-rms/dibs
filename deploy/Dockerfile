# syntax=docker/dockerfile:1

# --- Build the React SPA ---
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Backend image (serves api/worker/scheduler/device via the entrypoint) ---
FROM python:3.12-slim AS backend
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/app/frontend/dist \
    UPLOADS_DIR=/data/uploads
RUN useradd --create-home --uid 10001 dibs \
    && mkdir -p /data/uploads && chown -R dibs:dibs /data
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY migrations ./migrations
RUN pip install .
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && chown -R dibs:dibs /app
USER dibs
EXPOSE 8000 8443
ENTRYPOINT ["entrypoint.sh"]
CMD ["api"]
