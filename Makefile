.PHONY: install test lint format run package clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

run:
	python -m shottrainer.app.main

package:
	pyinstaller packaging/shottrainer.spec --noconfirm

clean:
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
