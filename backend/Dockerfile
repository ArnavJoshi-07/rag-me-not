# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.14.7

FROM ghcr.io/astral-sh/uv:0.12.21 AS uv

# ---- build: resolve the locked dependencies into a venv ----
FROM python:${PYTHON_VERSION}-slim-trixie AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project

# ---- runtime: venv + migrations only, no uv, runs as a non-root user ----
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALEMBIC_CONFIG=/app/alembic/alembic.ini

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY alembic ./alembic

USER app

# any alembic command works: `docker compose run --rm migrate downgrade -1`
ENTRYPOINT ["alembic"]
CMD ["upgrade", "head"]
