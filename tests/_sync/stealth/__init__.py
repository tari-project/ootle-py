"""Synchronous stealth-path tests.

Hand-maintained (not generated from ``tests/_async/stealth/``) — see
``scripts/unasync.py``'s ``HANDMAINTAINED_TEST_DIRS``. These exercise the
synchronous :class:`~ootle.OotleClient` and :class:`~ootle.OotleWallet`
stealth surface against the real vendored WASM provider, which the async
suite cannot cover for the sync tree.
"""
