"""Shared pytest fixtures for the ootle test suite."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from ootle._crypto import CryptoProvider, load_default_provider

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def crypto_vectors() -> dict[str, Any]:
    return json.loads((FIXTURES / "crypto_vectors.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def addresses_corpus() -> dict[str, Any]:
    return json.loads((FIXTURES / "addresses_corpus.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def stealth_unblind_vector() -> dict[str, Any]:
    """A known (mask, value, memo) encryption for the WASM unblind round-trip."""
    return json.loads((FIXTURES / "stealth_unblind_vector.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def crypto() -> CryptoProvider:
    return load_default_provider()


@pytest.fixture
def indexer_url() -> str:
    """LocalNet indexer URL from ``OOTLE_INDEXER_URL`` or ``pytest.skip``."""
    url = os.environ.get("OOTLE_INDEXER_URL")
    if not url:
        pytest.skip("OOTLE_INDEXER_URL is not set")
    return url
