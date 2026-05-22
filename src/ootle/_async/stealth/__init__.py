"""Async stealth-transfer builders and authorizer.

The stealth transfer builder, authorizer, and their helpers live here.
All stealth crypto is delegated to the ``StealthCryptoProvider``
Protocol — satisfied by the vendored ``ootle-wasm`` bridge
(:class:`ootle._crypto.WasmCryptoProvider`).
"""

from __future__ import annotations
