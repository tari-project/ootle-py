# justfile — task runner for the ootle project.
# Run `just` (or `just --list`) to see available recipes.

set shell := ["bash", "-cu"]
set dotenv-load := true

# Default recipe: show the menu of available tasks.
default:
    @just --list

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

# Sync the virtual environment with the lockfile (creates .venv as needed).
sync:
    uv sync --all-groups

# Upgrade all locked dependencies to their latest compatible versions.
upgrade:
    uv lock --upgrade
    uv sync --all-groups

# Add a new runtime dependency. Usage: `just add httpx`.
add package:
    uv add {{package}}

# Add a new development dependency. Usage: `just add-dev mypy`.
add-dev package:
    uv add --group dev {{package}}

# Remove every generated artefact (caches, build output, coverage data).
clean:
    rm -rf .ruff_cache .pytest_cache .coverage coverage.xml htmlcov dist build
    find . -type d -name __pycache__ -prune -exec rm -rf {} +

# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

# Run Ruff lint checks.
lint:
    uv run ruff check .

# Auto-fix lint violations where Ruff can.
lint-fix:
    uv run ruff check --fix .

# Verify formatting without changing files.
format-check:
    uv run ruff format --check .

# Format the codebase in place.
format:
    uv run ruff format .

# Run Pyright in strict mode.
typecheck:
    uv run pyright

# Run the test suite (pass extra args after `--`, e.g. `just test -- -k pattern`).
test *args:
    uv run pytest {{args}}

# Run tests with coverage and emit a terminal + XML report.
coverage:
    uv run pytest --cov --cov-report=term-missing --cov-report=xml

# Run every quality gate the CI pipeline expects.
ci: lint format-check typecheck coverage ci-verify-sync ci-verify-wasm

# ---------------------------------------------------------------------------
# async/sync codegen
# ---------------------------------------------------------------------------

# Regenerate src/ootle/_sync and tests/_sync from their _async twins.
unasync:
    uv run python scripts/unasync.py

# Regenerate _sync to a temp dir and fail on any drift vs. the committed tree.
ci-verify-sync:
    uv run python scripts/unasync.py --check

# ---------------------------------------------------------------------------
# WASM bridge
# ---------------------------------------------------------------------------

# Refresh the vendored WASM blob. Usage: `just update-wasm 0.30.0`.
update-wasm version:
    uv run python scripts/update_wasm.py --version {{version}}

# Vendor a locally built WASM blob. Usage: `just update-wasm-local /path/to/pkg`.
update-wasm-local pkg:
    uv run python scripts/update_wasm.py --from-pkg {{pkg}}

# Verify SHA-256 of the vendored WASM blob and that the loader instantiates.
ci-verify-wasm:
    uv run python -c "from ootle._crypto import load_default_provider; load_default_provider()"

# Convenience: format, fix, type-check, then test. Use during development.
check: format lint-fix typecheck test

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

# Run the Ootle CLI entry point.
run *args:
    uv run ootle {{args}}

# Build wheel + sdist into dist/.
build:
    uv build

# Print the project's resolved Python interpreter.
which-python:
    uv run python -c "import sys; print(sys.executable)"
