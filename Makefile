.PHONY: test lint serve serve-http ci

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

serve:
	uv run pv-mcp

serve-http:
	uv run pv-mcp http

ci:
	uv sync --frozen --extra agent
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest --cov=pv_mcp --cov-report=term-missing
	req=$$(mktemp); \
	uv export --frozen --no-dev --extra agent --no-emit-project --format requirements.txt -o "$$req" >/dev/null; \
	uv run pip-audit --requirement "$$req" --disable-pip --progress-spinner off; \
	status=$$?; rm -f "$$req"; exit $$status
