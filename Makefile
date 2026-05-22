# Makefile — most-used commands for the ootle project.
# Mirrors the justfile for environments that prefer GNU Make.
# Run `make help` to see the available targets.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV ?= uv

# Forward extra CLI args to the underlying tool (e.g. `make test ARGS="-k pattern"`).
ARGS ?=

.PHONY: help sync upgrade clean lint lint-fix format format-check typecheck \
        test coverage check ci run build update-wasm update-wasm-local \
        ci-verify-wasm unasync ci-verify-sync

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "; printf "\nUsage: make \033[36m<target>\033[0m\n\n"} \
	     /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------- environment ----------------------------------------------------

sync: ## Sync the virtualenv with the lockfile.
	$(UV) sync --all-groups

upgrade: ## Refresh the lockfile and re-sync dependencies.
	$(UV) lock --upgrade
	$(UV) sync --all-groups

clean: ## Remove caches, build output and coverage artefacts.
	rm -rf .ruff_cache .pytest_cache .coverage coverage.xml htmlcov dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# ---------- quality gates --------------------------------------------------

lint: ## Run Ruff lint checks.
	$(UV) run ruff check .

lint-fix: ## Auto-fix Ruff lint findings.
	$(UV) run ruff check --fix .

format: ## Format code with Ruff.
	$(UV) run ruff format .

format-check: ## Verify formatting without rewriting files.
	$(UV) run ruff format --check .

typecheck: ## Run Pyright in strict mode.
	$(UV) run pyright

test: ## Run pytest. Pass extra args via `ARGS="..."`.
	$(UV) run pytest $(ARGS)

coverage: ## Run pytest with coverage reporting.
	$(UV) run pytest --cov --cov-report=term-missing --cov-report=xml

check: format lint-fix typecheck test ## Local pre-commit pass.

ci: lint format-check typecheck coverage ci-verify-sync ci-verify-wasm ## Strict pipeline equivalent of CI.

# ---------- async/sync codegen --------------------------------------------

unasync: ## Regenerate src/ootle/_sync and tests/_sync from their _async twins.
	$(UV) run python scripts/unasync.py

ci-verify-sync: ## Regenerate _sync to a temp dir and assert byte-equality with the committed tree.
	$(UV) run python scripts/unasync.py --check

# ---------- WASM bridge ----------------------------------------------------

update-wasm: ## Refresh the vendored WASM blob (requires WASM_VERSION=x.y.z).
	@if [ -z "$(WASM_VERSION)" ]; then \
		echo "error: WASM_VERSION is required, e.g. make update-wasm WASM_VERSION=0.30.0" >&2; \
		exit 1; \
	fi
	$(UV) run python scripts/update_wasm.py --version $(WASM_VERSION)

update-wasm-local: ## Vendor a locally built WASM blob (requires PKG=/path/to/pkg).
	@if [ -z "$(PKG)" ]; then \
		echo "error: PKG is required, e.g. make update-wasm-local PKG=/path/to/pkg" >&2; \
		exit 1; \
	fi
	$(UV) run python scripts/update_wasm.py --from-pkg $(PKG)

ci-verify-wasm: ## Verify SHA-256 of the vendored WASM blob and that the loader instantiates.
	$(UV) run python -c "from ootle._crypto import load_default_provider; load_default_provider()"

# ---------- application ----------------------------------------------------

run: ## Run the Ootle CLI entry point.
	$(UV) run ootle $(ARGS)

build: ## Build wheel + sdist into dist/.
	$(UV) build
