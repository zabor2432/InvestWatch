FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/srv/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# shared contract adapter (plain module, no install: stdlib only), build context `common` = ../../common
COPY --from=common investwatch_common ./investwatch_common
COPY seed.py .
USER nobody
# data comes from the ./demo directory mounted at /demo (see docker-compose.yml)
CMD ["python", "seed.py"]
