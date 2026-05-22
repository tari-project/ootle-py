"""Manual co-signing example: explicit authorize → attach → seal hand-off.

Python port of the manual co-authorisation slice of
``ootle-rs/examples/fungible_transfer.rs`` (lines 107-126). Where
``fungible_transfer.py`` registers a second signer on the same wallet
(implicit auto-fold at seal time), this example shows the *explicit*
hand-off pattern: produce a :class:`TransactionAuthorization` in one
wallet, ship its JSON blob over the wire, and attach it in another
wallet before sealing.

This is how you co-sign with a hardware wallet, an HSM, or a multi-
party human-approval flow without giving the orchestrating client
access to the second private key.

Self-contained: both key holders and the recipients are generated on the
fly, so the only thing you need to run it is a reachable indexer.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.manual_co_signing
"""

from __future__ import annotations

import asyncio

from ootle import (
    AsyncOotleClient,
    LocalSigner,
    OotleSecretKey,
    TransactionAuthorization,
    TransactionRequest,
    UnsignedTransaction,
)
from ootle._crypto import load_default_provider

from ._common import (
    NETWORK,
    TARI_RESOURCE,
    faucet_and_wait,
    indexer_url,
    new_recipient,
    new_wallet,
    tari,
    wait,
)

# In a realistic cross-process co-signing flow, wallet B is just a key
# plus a signing function (HSM, hardware wallet, remote signer). It
# needs the unsigned transaction body *and* the seal signer's public
# key — both public data — to produce a signature that commits to the
# right seal_pk. ``OotleWallet.authorize`` always commits to its own
# default signer's pk; for the explicit hand-off we drop down to the
# ``Signer`` Protocol and call ``add_signature`` with A's pk directly.


async def main() -> None:
    # Two independent key holders. In a realistic deployment B lives in
    # a separate process; here we co-locate them so the JSON blob
    # hand-off can be illustrated with comments. Wallet A is a full
    # ``OotleWallet`` because it seals + sends; B is just a
    # ``LocalSigner`` — the realistic remote-signer surface.
    a_secret, wallet_a = new_wallet()
    b_secret = OotleSecretKey.random(NETWORK)
    signer_b = LocalSigner(b_secret)
    a_address = a_secret.to_address()
    sender_account = a_address.to_component_address()

    print(f"Wallet A (orchestrator + seal): {a_address.bech32m}")
    print(f"Wallet B (co-signer):           {b_secret.to_address().bech32m}")

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet_a) as client:
        print(f"\nNetwork: {client.network.name}, epoch: {await client.get_epoch()}")

        # Step 1: faucet TARI into wallet A's account (single signer,
        # the implicit path — same as fungible_transfer.py).
        await faucet_and_wait(client)

        # Step 2: wallet A prepares the unsigned multi-transfer to fresh
        # recipients. The transaction body is final from here — any
        # mutation would invalidate the co-signature.
        recipient1 = new_recipient()
        recipient2 = new_recipient()
        unsigned = await (
            client.account()
            .pay_fee(1000)
            .public_transfer(recipient1, TARI_RESOURCE, tari(2))
            .public_transfer(recipient2, TARI_RESOURCE, tari(1))
            .prepare()
        )

        # ------------------------------------------------------------------
        # >>> Process boundary: wallet A → wallet B
        # In a real deployment wallet A serialises `unsigned.json` and
        # ships the string (plus A's owner_pk) to wallet B over the wire.
        # ------------------------------------------------------------------
        unsigned_blob: str = unsigned.json
        seal_pk: bytes = a_address.owner_pk
        print(f"\nUnsigned tx blob ({len(unsigned_blob)} bytes) -> wallet B")

        # On wallet B's side: rehydrate, sign with B's secret committing
        # to A's owner_pk as the seal_pk, return the JSON blob. Wallet B
        # never sees any of A's secrets — only public data.
        unsigned_received = UnsignedTransaction(json=unsigned_blob)
        crypto = load_default_provider()
        auth_blob: str = signer_b.add_signature(unsigned_received.json, seal_pk, crypto=crypto)

        # ------------------------------------------------------------------
        # <<< Process boundary: wallet B → wallet A
        # ------------------------------------------------------------------
        print(f"Authorization blob ({len(auth_blob)} bytes) <- wallet B")

        # Back to wallet A: parse the auth blob, attach it via the
        # TransactionRequest, then seal + send. The seal step folds B's
        # pre-computed signature into the envelope before A signs.
        auth_received = TransactionAuthorization(json=auth_blob)
        request = TransactionRequest().with_transaction(unsigned).add_authorization(auth_received)
        sealed = client.seal_transaction(request)
        pending = await client.send_transaction(sealed)
        await wait("co-signed transfer", pending)

        # Step 3: print balances.
        sender_balance = await client.get_account_balance(sender_account, TARI_RESOURCE)
        print(f"\nSender TARI balance: {sender_balance}")
        for label, addr in (("Recipient 1", recipient1), ("Recipient 2", recipient2)):
            balance = await client.get_account_balance(addr.to_component_address(), TARI_RESOURCE)
            print(f"{label} TARI balance: {balance}")


if __name__ == "__main__":
    asyncio.run(main())
