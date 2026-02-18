.PHONY: install check format lint typecheck run run-smoke run-case

install:
	uv sync --group dev

check: format lint
	@echo "All checks passed."

format:
	uv run ruff format --check .

lint:
	uv run ruff check .

typecheck:
	uv run ty check

run:
	uv run python run.py

run-smoke:
	uv run python run.py --tags smoke

run-case:
	uv run python run.py --case $(CASE)

dry-run:
	uv run python run.py --dry-run
