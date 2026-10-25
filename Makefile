.PHONY: test lint serve

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

serve:
	uv run pv-mcp
