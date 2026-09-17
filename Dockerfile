# ---- Stage 1: build the ARENA static bundle (Node exists at build time only) ----
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: DARWIN_core — Python runtime, no Node (PID-002 §5) ----
FROM python:3.12-slim AS base

WORKDIR /app

RUN groupadd --system darwin && useradd --system --gid darwin --home /app darwin

COPY pyproject.toml README.md ./
COPY darwin ./darwin

# ARENA static bundle, packaged into the image at build time (PID-002 §5).
COPY --from=frontend-build /frontend/dist ./darwin/static

RUN pip install --no-cache-dir .

ARG DARWIN_BUILD_COMMIT=unknown
ARG DARWIN_BUILD_TIME=unknown
ENV DARWIN_BUILD_COMMIT=${DARWIN_BUILD_COMMIT} \
    DARWIN_BUILD_TIME=${DARWIN_BUILD_TIME} \
    PYTHONUNBUFFERED=1

RUN chown -R darwin:darwin /app
USER darwin

EXPOSE 8000

CMD ["uvicorn", "darwin.app:app_for_uvicorn", "--factory", "--host", "0.0.0.0", "--port", "8000"]
