# FulfillOps — one image, several start commands (API, worker, migrate, reset).
# Multistage: the builder has uv and resolves deps; the runtime has only the venv + source.
# Base image: exact patch tag. Record its digest in docs/supply-chain.md:
#   docker buildx imagetools inspect python:3.12.16-slim-trixie --format '{{.Manifest.Digest}}'
ARG PYTHON_IMAGE=python:3.12.16-slim-trixie

# uv is copied from its official image (pinned version), so it never reaches the runtime stage.
FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

FROM ${PYTHON_IMAGE} AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3 \
    UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
# Lockfiles first: this layer is cached until dependencies change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY common/ common/
COPY api/ api/
COPY worker/ worker/
COPY db/ db/

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/opt/venv/bin:$PATH
# Fixed UID/GID 10001 so Kubernetes runAsUser and Compose agree with the image.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/common ./common
COPY --from=builder /app/api ./api
COPY --from=builder /app/worker ./worker
COPY --from=builder /app/db ./db
USER 10001:10001
EXPOSE 8080
# Default = API. Worker: `python -m worker.main`. Migrate: `python -m common.migrate`.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
