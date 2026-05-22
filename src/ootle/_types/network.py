"""``Network`` enum, ``NetworkInfo`` envelope, and the default-indexer-URL helper.

Network discriminators match the upstream Tari L2 wire encoding (see the
``ootle-rs/helpers.rs`` table). v1 supports two networks operationally:
``LOCAL_NET`` and ``ESMERALDA``. The remaining values are declared so
that addresses signed for those networks parse cleanly; the
``default_indexer_url`` helper raises :class:`NotImplementedError` for
them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Network(Enum):
    """Tari L2 network discriminator.

    The integer values are the canonical network codes embedded in
    bech32m addresses by the WASM blob.
    """

    MAIN_NET = 0
    STAGE_NET = 1
    NEXT_NET = 2
    LOCAL_NET = 0x10
    IGOR = 0x24
    ESMERALDA = 0x26


@dataclass(frozen=True, slots=True)
class NetworkInfo:
    """Result of ``GET network`` — the indexer's network identity + epoch.

    Internal type. Surfaces ``Network`` (canonical enum) and the current
    integer epoch. The raw ``network_byte`` field returned by the indexer
    is collapsed into the enum.
    """

    network: Network
    epoch: int


_DEFAULT_INDEXER_URLS: dict[Network, str] = {
    Network.LOCAL_NET: "http://localhost:12500",
}


def default_indexer_url(network: Network) -> str:
    """Return the canonical indexer URL for ``network``.

    Args:
        network: The target network.

    Returns:
        The indexer URL.

    Raises:
        NotImplementedError: If ``network`` has no canonical indexer URL
            in v1 (everything except ``LOCAL_NET`` and ``ESMERALDA``).
    """
    try:
        return _DEFAULT_INDEXER_URLS[network]
    except KeyError as exc:
        msg = f"No default indexer URL is configured for {network.name}"
        raise NotImplementedError(msg) from exc
