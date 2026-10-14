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
RUN uv sync --locked --no-dev --no-install-project
COPY services/ services/
COPY contracts/ contracts/
RUN uv sync --locked --no-dev --no-editable \
    && useradd --uid 10001 --create-home hirup
USER 10001:10001
CMD ["/app/.venv/bin/uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

# Test-only target; production does not ship fixtures or development packages.
FROM api AS integration
USER root
RUN uv sync --locked --no-editable
COPY tests/ tests/
USER 10001:10001
CMD ["/app/.venv/bin/uvicorn", "tests.contract.demo_backend:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
