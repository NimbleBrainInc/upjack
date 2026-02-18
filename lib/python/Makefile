.PHONY: install format format-check lint typecheck test test-cov test-e2e check clean

install:
	uv sync --group dev

format:
	uv run ruff format src/ tests/

format-check:
	uv run ruff format --check src/ tests/

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run ty check src/

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=src/upjack --cov-report=term-missing

test-e2e:
	uv sync --group e2e
	uv run pytest e2e/ -v -s

check: format-check lint typecheck test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
