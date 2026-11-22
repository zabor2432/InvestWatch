FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/srv/.venv \
    PATH=/srv/.venv/bin:$PATH

# same layout as the repo: migrations/pyproject.toml points at ../common
WORKDIR /srv/migrations
COPY --from=common . /srv/common
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

COPY alembic.ini .
COPY alembic alembic
CMD ["alembic", "upgrade", "head"]
