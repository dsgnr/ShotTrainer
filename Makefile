.PHONY: install sync test lint format run package package-deps clean pylint dmg installer docs docs-serve docs-build docs-clean

# mkdocs deps aren't pinned into pyproject.toml since they're only used
# for documentation builds. uv's --with flag installs them into the run
# environment on demand, which mirrors what CI does in .github/workflows/docs.yml.
MKDOCS_RUN = uv run --with mkdocs --with mkdocs-material mkdocs

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
	uv run --extra package python packaging/build_nuitka.py

dmg: package
	bash packaging/make_dmg.sh

installer: package
	pwsh packaging/make_installer.ps1

# Live-reload preview at http://127.0.0.1:8000/.
docs: docs-serve
docs-serve:
	$(MKDOCS_RUN) serve

# Build the static site into site/ with the same --strict gate CI uses,
# so doc warnings (broken links, missing nav entries) fail the build.
docs-build:
	$(MKDOCS_RUN) build --strict

docs-clean:
	rm -rf site

clean: docs-clean
	rm -rf build .pytest_cache .ruff_cache .mypy_cache packaging/icon.icns
	# dist often holds files Nuitka has just released. Retry once
	# in case the OS hasn't caught up.
	rm -rf dist || (sleep 1 && rm -rf dist)
	# Nuitka may leave intermediate build trees if it was killed mid-run.
	rm -rf packaging/ShotTrainer.build packaging/ShotTrainer.dist packaging/ShotTrainer.onefile-build
	find . -type d -name __pycache__ -exec rm -rf {} +
