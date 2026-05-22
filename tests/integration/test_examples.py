"""End-to-end smoke tests for the runnable ``examples/`` modules.

Marker-gated. Run with ``OOTLE_INDEXER_URL=... pytest -m integration``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

EXAMPLE_TIMEOUT = 120.0
# Self-contained examples: each generates fresh keys and faucets its own
# funds, so a reachable indexer is the only prerequisite. The artifact-
# dependent examples (counter_deploy, template_invoke, publish_template,
# watch_component_events) need a template/WASM/component and are excluded.
EXAMPLE_MODULES: tuple[str, ...] = (
    "examples.balance_query",
    "examples.balance_query_sync",
    "examples.fungible_transfer",
    "examples.dry_run_only",
    "examples.manual_co_signing",
    "examples.workspace_chain",
)


@pytest.mark.parametrize("module", EXAMPLE_MODULES)
def test_example_runs(indexer_url: str, module: str) -> None:
    env = {**os.environ, "OOTLE_INDEXER_URL": indexer_url}
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [sys.executable, "-m", module],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=EXAMPLE_TIMEOUT,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{module} exited {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
