FROM ghcr.io/astral-sh/uv:0.11.21 AS uv
FROM python:3.12.13-slim-bookworm AS api
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends libexpat1=2.5.0-1+deb12u4 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Jakarta
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY ml/pyproject.toml ml/pyproject.toml
COPY pipelines/pyproject.toml pipelines/pyproject.toml
RUN uv sync --locked --no-dev --no-install-project
COPY services/ services/
COPY contracts/ contracts/
RUN uv sync --locked --no-dev --no-editable \
    && useradd --uid 10001 --create-home hirup
USER 10001:10001
CMD ["/app/.venv/bin/uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

# Separate offline/ingest worker: the API image stays independent of ML packages.
FROM api AS pipeline
USER root
RUN --mount=type=cache,target=/root/.cache/uv \
    apt-get update -qq \
    && apt-get install -y --no-install-recommends libgomp1=12.2.0-14+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && UV_NO_CACHE=0 uv sync --locked --no-dev --no-install-workspace --package hirup-ml
COPY ml/src/ ml/src/
COPY ml/configs/ ml/configs/
COPY ml/model_registry.json ml/model_registry.json
COPY pipelines/src/ pipelines/src/
COPY pipelines/configs/ pipelines/configs/
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_NO_CACHE=0 uv sync --locked --no-dev --no-editable --package hirup-ml
ENV HIRUP_DATA_DIR=/data HIRUP_PROJECT_ROOT=/app MPLCONFIGDIR=/tmp/hirup-matplotlib
USER 10001:10001
CMD ["/app/.venv/bin/hirup-ml", "hourly"]

# Test-only target; production does not ship fixtures or development packages.
FROM pipeline AS integration
USER root
RUN --mount=type=cache,target=/root/.cache/uv UV_NO_CACHE=0 uv sync --locked --no-editable
COPY ml/tests/ ml/tests/
COPY pipelines/tests/ pipelines/tests/
COPY tests/ tests/
USER 10001:10001
CMD ["/app/.venv/bin/uvicorn", "tests.contract.demo_backend:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
