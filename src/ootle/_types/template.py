"""``TemplateBlob`` — compiled WASM template binary wrapper."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateBlob:
    """A compiled WASM template binary.

    Accepted by :meth:`IAsyncAccount.publish_template` alongside raw ``bytes``.
    Mirrors Rust's ``tari_ootle_common_types::engine_types::published_template::TemplateBlob``.
    """

    blob: bytes
