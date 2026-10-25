# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM base AS runtime
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin pv \
    && mkdir -p /data \
    && chown pv:pv /data
WORKDIR /app
COPY --from=builder --chown=pv:pv /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PV_MCP_TRANSPORT=http \
    PV_MCP_HTTP_HOST=0.0.0.0 \
    PV_MCP_HTTP_PORT=8000 \
    PV_MCP_RESOURCE_URL=http://127.0.0.1:8000/mcp \
    OPENFDA_CACHE_PATH=/data/openfda.sqlite
USER pv
EXPOSE 8000
CMD ["pv-mcp", "http"]
