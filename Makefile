.PHONY: install sync test lint format run package package-deps clean pylint dmg installer

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

package-deps:
	uv sync --extra package

package: package-deps
ifeq ($(shell uname -s),Darwin)
	bash packaging/build_icns.sh
endif
	uv run --extra package pyinstaller packaging/shottrainer.spec --noconfirm

dmg: package
	bash packaging/make_dmg.sh

installer: package
	pwsh packaging/make_installer.ps1

clean:
	rm -rf build .pytest_cache .ruff_cache .mypy_cache packaging/icon.icns
	# dist often holds files PyInstaller has just released. Retry once
	# in case the OS hasn't caught up.
	rm -rf dist || (sleep 1 && rm -rf dist)
	find . -type d -name __pycache__ -exec rm -rf {} +
