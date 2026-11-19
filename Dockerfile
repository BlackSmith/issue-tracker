# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ATTACHMENT_DIR=/data/attachments
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 tracker \
    && useradd --uid 10001 --gid tracker --no-create-home tracker \
    && mkdir -p /data/attachments \
    && chown tracker:tracker /data/attachments
COPY backend/alembic.ini ./
COPY backend/migrations/ ./migrations/
COPY backend/app/ ./app/
USER tracker
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM nginxinc/nginx-unprivileged:1.28-alpine AS frontend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /build/dist/ /usr/share/nginx/html/
EXPOSE 8080
