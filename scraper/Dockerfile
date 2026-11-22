FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/srv/.venv \
    PATH=/srv/.venv/bin:$PATH

# same layout as the repo: scraper/pyproject.toml points at ../common
WORKDIR /srv/scraper
COPY --from=common . /srv/common
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# headless Chromium for the web collector's JS fallback (PLAYWRIGHT_ENABLED)
ARG INSTALL_PLAYWRIGHT=true
# libatomic1: required by Playwright's bundled Node.js driver on slim images (arm64)
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends libatomic1 \
        && playwright install --with-deps chromium \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# seed files of the firm registry (build context "registry" = docs/firm_registry)
COPY --from=registry . /srv/firm_registry
COPY config config
COPY app app

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
