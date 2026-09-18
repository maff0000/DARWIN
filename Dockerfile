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

# PID-004B Workshop UI enablement: `darwin.workshop.workspace`'s default
# workspace root (`/srv/DARWIN/workspaces`) was never actually writable by
# the `darwin` runtime user this image runs as -- `/srv` in a bare
# `python:3.12-slim` base image is root-owned, mode 0755, and this
# Dockerfile never created `/srv/DARWIN` at all before this line. Every
# Workshop mutation's `_sync_workspace_best_effort` call has therefore
# always failed with a silently-swallowed PermissionError in every real
# deployment of this exact image (best-effort by design -- PID-004 sec47:
# a workspace-sync failure must never fail the API call -- which is
# exactly why nothing surfaced this until the Workshop UI's own
# workspace-loss E2E proof went looking at the container's filesystem
# directly). Narrow fix: create the directory and hand it to `darwin`
# before dropping root, same as `/app` just below.
RUN mkdir -p /srv/DARWIN/workspaces && chown -R darwin:darwin /srv/DARWIN
RUN chown -R darwin:darwin /app
USER darwin

EXPOSE 8000

CMD ["uvicorn", "darwin.app:app_for_uvicorn", "--factory", "--host", "0.0.0.0", "--port", "8000"]
