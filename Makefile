.PHONY: install test test-unit lint audit docs docs-build clean

install:
	uv sync --group test --group types --extra dev --extra dash

test:
	uv run pytest

test-unit:
	uv run pytest -m unit

lint:
	uv run ruff check src tests
	uv run ty check

audit:
	uv sync --group audit --extra dash
	uv run pip-audit

docs:
	quarto preview docs

docs-build:
	quarto render docs

clean:
	rm -rf site/ .pytest_cache/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
