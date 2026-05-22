"""Multi-input mask aggregation on the real WASM provider.

A 2-input stealth transfer must no longer raise. Each input's mask is
decrypted via the real ``unblindOutput`` export and the per-input masks
are summed by the real ``aggregateInputMasks`` export, then handed to
balance-proof signing. This drives :func:`fetch_stealth_input_bodies`
directly: a fully balanced 2-stealth-input transfer cannot pass
``validateStealthTransfer`` without purpose-built Rust fixtures (the blob
ships no encrypt export), but the loop + unblind + aggregate is the whole
of multi-input support and runs end-to-end here.

Both inputs reuse the recorded unblind vector, so the two decrypted masks
are equal and their real WASM aggregate is twice the vector mask — exactly
what :meth:`aggregate_input_masks` computes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ootle._async.stealth._authorizer_helpers import (
    fetch_stealth_input_bodies,
    utxo_substate_id,
)
from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle._types.stealth import Mask
from tests._helpers.substates import envelope

from ._builder_helpers import RESOURCE, make_client, recipient_address

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


def _stub_utxo(httpx_mock: HTTPXMock, vec: dict[str, Any], commitment: bytes) -> None:
    """Register the indexer ``GET substates/utxo_…`` engine ``Utxo`` response.

    The engine ``OutputBody`` carries ``public_nonce`` and no commitment — the
    commitment is derived from the substate id (see ``parse_substate_utxo``).
    """
    body: dict[str, Any] = {
        "public_nonce": vec["sender_public_nonce"],
        "encrypted_data": vec["encrypted_data"],
        "minimum_value_promise": 0,
        "viewable_balance": None,
    }
    inner = {"output": body, "spend_condition": {"Signed": vec["sender_public_nonce"]}, "tag": 0}
    sub_id = utxo_substate_id(RESOURCE, commitment)
    httpx_mock.add_response(
        url=f"http://idx/substates/{quote(sub_id.opaque, safe='')}",
        method="GET",
        json=envelope({"Utxo": {"output": inner, "is_frozen": False}}),
        is_reusable=True,
    )


async def test_fetch_two_inputs_aggregates_real_masks(
    httpx_mock: HTTPXMock, stealth_unblind_vector: dict[str, Any]
) -> None:
    vec = stealth_unblind_vector
    provider = WasmCryptoProvider.load_default()
    client = await make_client(httpx_mock, crypto=provider)
    commitment = bytes.fromhex(vec["commitment"])
    _stub_utxo(httpx_mock, vec, commitment)

    resolution = await fetch_stealth_input_bodies(
        client=client,
        resource=RESOURCE,
        inputs=[(recipient_address(), commitment), (recipient_address(), commitment)],
        crypto=provider,
        view_secret=bytes.fromhex(vec["view_secret"]),
    )

    # Both inputs resolved (no NotImplementedError) and both signers required.
    assert len(resolution.required_signers) == 2
    # The aggregated mask is the real WASM sum of the two (equal) decrypted
    # input masks: twice the vector mask.
    mask = Mask(bytes.fromhex(vec["mask"]))
    assert resolution.agg_input_mask == provider.aggregate_input_masks([mask, mask])
    await client.aclose()
