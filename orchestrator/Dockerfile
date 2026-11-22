FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/srv/.venv/bin:$PATH" \
    DAGSTER_HOME=/srv DAGSTER_DATA_DIR=/dagster_data DAGSTER_COMPUTE_LOGS_DIR=/dagster_data/logs
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
CMD ["dagster-daemon", "run"]
