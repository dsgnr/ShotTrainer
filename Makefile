.PHONY: install sync test lint format run run-hardware package package-demo icons docs docs-serve docs-build docs-test docs-clean clean

ZENSICAL_RUN = uv tool run --from zensical zensical
DOCS_PYTHON = uv run --no-project --python 3.13 python

install:
	npm --prefix frontend ci

sync: install

test:
	cargo test --workspace
	npm --prefix frontend test
	$(MAKE) docs-test

lint:
	cargo fmt --all --check
	cargo clippy --workspace --all-targets -- -D warnings
	npm --prefix frontend run check

format:
	cargo fmt --all

run:
	cargo tauri dev

run-hardware:
	cargo tauri dev --features opencv

package:
	cargo tauri build --features opencv

package-demo:
	cargo tauri build

icons:
	cargo tauri icon frontend/public/icon.svg --output src-tauri/icons

docs: docs-serve
docs-serve:
	$(ZENSICAL_RUN) serve

docs-build:
	$(ZENSICAL_RUN) build --strict
	$(DOCS_PYTHON) scripts/check_docs_seo.py

docs-test:
	$(DOCS_PYTHON) -m unittest discover -s scripts -p 'test_*.py'

docs-clean:
	$(DOCS_PYTHON) -c "import shutil; shutil.rmtree('site', ignore_errors=True)"

clean: docs-clean
	cargo clean
	$(DOCS_PYTHON) -c "import shutil; shutil.rmtree('frontend/dist', ignore_errors=True)"
