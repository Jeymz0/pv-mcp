.PHONY: test lint serve serve-http

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
