"""``AsyncWalletStealthAuthorizer`` view-secret handling.

Regression cover for the bug where ``from_spec`` defaulted ``view_secret``
to 32 zero bytes: a stealth-input spec would then decrypt every input
mask with the wrong key, aggregate garbage, and sign an invalid balance
proof. The fix makes a missing secret an error on the stealth path and
forwards a supplied secret through to ``unblind_output``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pytest

from ootle._async.stealth._authorizer_helpers import utxo_substate_id
from ootle._async.stealth._builder_helpers import StealthTransferState
from ootle._async.stealth._spec import StealthTransferSpec
from ootle._async.stealth.authorizer import AsyncWalletStealthAuthorizer
from ootle._types.stealth import (
    StealthInput,
    StealthInputsStatement,
    StealthOutputsStatement,
    StealthTransferStatement,
)
from ootle._types.stealth.requirements import SignatureRequirements
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import InvalidArgumentError
from tests._helpers.substates import envelope

from ._builder_helpers import RESOURCE, make_client, recipient_address

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


def _stealth_input_spec(commitment: bytes) -> StealthTransferSpec:
    """A spec carrying a single stealth input — the path that needs a view secret."""
    statement = StealthTransferStatement(
        inputs_statement=StealthInputsStatement(
            inputs=(StealthInput(commitment=commitment),), revealed_amount=0
        ),
        outputs_statement=StealthOutputsStatement.new_revealed_only(0),
    )
    state = StealthTransferState(resource=RESOURCE)
    state.inputs_to_spend[recipient_address()] = StealthInput(commitment=commitment)
    return StealthTransferSpec(
        unsigned=UnsignedTransaction(json='{"instructions": []}'),
        statement=statement,
        signature_requirements=SignatureRequirements.new_must_sign_with_account_key(()),
        output_mask=None,
        state=state,
    )


def _stub_utxo(httpx_mock: HTTPXMock, vec: dict[str, Any], commitment: bytes) -> None:
    """Register the indexer UTXO response (engine ``Utxo`` shape) for the unblind vector.

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


async def test_from_spec_stealth_input_without_view_secret_raises(httpx_mock: HTTPXMock) -> None:
    """A missing secret is rejected, not silently treated as a zero key."""
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    with pytest.raises(InvalidArgumentError, match="view_secret"):
        AsyncWalletStealthAuthorizer.from_spec(client.wallet, _stealth_input_spec(b"\xaa" * 32))
    await client.aclose()


async def test_from_spec_wrong_length_view_secret_raises(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    with pytest.raises(InvalidArgumentError, match="32 bytes"):
        AsyncWalletStealthAuthorizer.from_spec(
            client.wallet, _stealth_input_spec(b"\xaa" * 32), view_secret=b"\x01" * 16
        )
    await client.aclose()


async def test_from_spec_revealed_only_needs_no_view_secret(httpx_mock: HTTPXMock) -> None:
    """The revealed-only path never touches the secret — ``from_spec`` stays a 2-arg call."""
    from ootle._async.stealth.transfer import AsyncStealthTransfer  # noqa: PLC0415

    from ._builder_helpers import COMPONENT  # noqa: PLC0415

    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .prepare()
    )
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer.from_spec(client.wallet, spec)
    new_spec = await auth.prepare(client)
    assert new_spec.statement.balance_proof is None
    await client.aclose()


async def test_from_spec_forwards_view_secret_to_input_decryption(
    httpx_mock: HTTPXMock, stealth_unblind_vector: dict[str, Any]
) -> None:
    """The supplied secret reaches ``unblind_output`` — the input mask is the vector mask.

    With the old zero default the decrypted mask would be garbage and the
    aggregate would not equal the recorded mask.
    """
    from ootle._async.stealth._authorizer_helpers import (  # noqa: PLC0415
        fetch_stealth_input_bodies,
    )

    vec = stealth_unblind_vector
    client = await make_client(httpx_mock)
    commitment = bytes.fromhex(vec["commitment"])
    _stub_utxo(httpx_mock, vec, commitment)
    spec = _stealth_input_spec(commitment)
    assert client.wallet is not None

    auth = AsyncWalletStealthAuthorizer.from_spec(
        client.wallet, spec, view_secret=bytes.fromhex(vec["view_secret"])
    )
    resolution = await fetch_stealth_input_bodies(
        client=client,
        resource=RESOURCE,
        inputs=[(recipient_address(), commitment)],
        crypto=auth._stealth_crypto(client),  # pyright: ignore[reportPrivateUsage]  # internal access
        view_secret=auth._view_secret,  # pyright: ignore[reportPrivateUsage]  # internal access
    )
    assert resolution.agg_input_mask.raw == bytes.fromhex(vec["mask"])
    await client.aclose()
