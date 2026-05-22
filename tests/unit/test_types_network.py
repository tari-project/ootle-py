"""``Network`` enum and ``default_indexer_url``."""

from __future__ import annotations

import pytest

from ootle._types.network import Network, default_indexer_url


def test_network_values_match_wire_codes() -> None:
    assert Network.LOCAL_NET.value == 0x10
    assert Network.ESMERALDA.value == 0x26
    assert Network.MAIN_NET.value == 0
    assert Network.STAGE_NET.value == 1
    assert Network.NEXT_NET.value == 2
    assert Network.IGOR.value == 0x24


def test_default_indexer_url_resolves_local_net() -> None:
    assert default_indexer_url(Network.LOCAL_NET) == "http://localhost:12500"


@pytest.mark.parametrize(
    "network",
    [Network.MAIN_NET, Network.STAGE_NET, Network.NEXT_NET, Network.IGOR],
)
def test_default_indexer_url_raises_for_unsupported(network: Network) -> None:
    with pytest.raises(NotImplementedError):
        default_indexer_url(network)
