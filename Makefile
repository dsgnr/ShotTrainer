.PHONY: install sync test lint format run package clean pylint

install:
	uv sync

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

pylint:
	uv run pylint src/shottrainer

format:
	uv run ruff format .
	uv run ruff check --fix .

run:
	uv run shottrainer

package:
	uv run pyinstaller packaging/shottrainer.spec --noconfirm

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
