"""``WalletStealthAuthorizer`` view-secret handling — sync surface.

Hand-written sync counterpart of
``tests/_async/stealth/test_authorizer_view_secret.py``. Regression cover
for the bug where ``from_spec`` defaulted ``view_secret`` to 32 zero
bytes and silently decrypted stealth input masks with the wrong key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ootle._sync.stealth.authorizer import WalletStealthAuthorizer
from ootle._sync.stealth._builder_helpers import StealthTransferState
from ootle._sync.stealth._spec import StealthTransferSpec
from ootle._types.stealth import (
    StealthInput,
    StealthInputsStatement,
    StealthOutputsStatement,
    StealthTransferStatement,
)
from ootle._types.stealth.requirements import SignatureRequirements
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import InvalidArgumentError

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


def test_from_spec_stealth_input_without_view_secret_raises(httpx_mock: HTTPXMock) -> None:
    """A missing secret is rejected, not silently treated as a zero key."""
    client = make_client(httpx_mock)
    assert client.wallet is not None
    with pytest.raises(InvalidArgumentError, match="view_secret"):
        WalletStealthAuthorizer.from_spec(client.wallet, _stealth_input_spec(b"\xaa" * 32))
    client.close()


def test_from_spec_wrong_length_view_secret_raises(httpx_mock: HTTPXMock) -> None:
    client = make_client(httpx_mock)
    assert client.wallet is not None
    with pytest.raises(InvalidArgumentError, match="32 bytes"):
        WalletStealthAuthorizer.from_spec(
            client.wallet, _stealth_input_spec(b"\xaa" * 32), view_secret=b"\x01" * 16
        )
    client.close()
