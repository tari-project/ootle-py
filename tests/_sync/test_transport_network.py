"""Transport — ``GET network`` round-trip."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from ootle._sync._transport import IndexerTransport
from ootle._types.network import Network


def test_get_network_info_round_trips(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/network",
        json={"network": "localnet", "network_byte": 0x10, "epoch": 42},
    )
    with IndexerTransport("http://idx") as transport:
        info = transport.get_network_info()
    assert info.network == Network.LOCAL_NET
    assert info.epoch == 42


def test_get_network_info_for_esmeralda(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/network",
        json={"network": "esmeralda", "network_byte": 0x26, "epoch": 1000},
    )
    with IndexerTransport("http://idx") as transport:
        info = transport.get_network_info()
    assert info.network == Network.ESMERALDA
    assert info.epoch == 1000
