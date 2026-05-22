"""Sync mirror — a stealth transfer with no ``await`` in sight.

Every async stealth API has a generated sync twin with the same shape;
swap the imports and drop the awaits. This funds a sender with a revealed
faucet claim, then sends a confidential output (plus revealed change) to
a fresh recipient using the sync ``StealthTransfer`` +
``WalletStealthAuthorizer``.

The faucet *stealth-deposit* path needs ``OotleWallet.generate_outputs_statement``,
which stays async on the shared wallet, so the sync flow seeds with a
plain revealed faucet and spends a revealed input into a stealth output.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.stealth.sync_transfer
"""

from __future__ import annotations

from ootle import OotleClient, Output, StealthTransfer, WalletStealthAuthorizer

from ._common import (
    DEFAULT_FAUCET_FEE,
    TARI_RESOURCE,
    indexer_url,
    new_recipient,
    new_wallet,
    tari,
)


def main() -> None:
    """Synchronous stealth transfer, end to end."""
    sender_secret, wallet = new_wallet()
    account = wallet.default_address.to_component_address()
    recipient = new_recipient()

    with OotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"sender:    {sender_secret.to_address().bech32m}")
        print(f"recipient: {recipient.bech32m}")

        unsigned = client.faucet().take_funds().pay_fee(DEFAULT_FAUCET_FEE).prepare()
        sealed = client.seal_transaction(unsigned)
        if not client.send_transaction(sealed).watch().is_commit:
            print("seed faucet did not commit")
            return

        transfer = StealthTransfer(client, TARI_RESOURCE)
        transfer.spend_revealed_input(account, tari(4))
        transfer.to_stealth_output(
            Output(destination=recipient, amount=tari(1), resource_address=TARI_RESOURCE)
        )
        transfer.to_revealed_output(tari(2))
        transfer.pay_fee_from_revealed(tari(1))

        spec = transfer.prepare()
        authorizer = WalletStealthAuthorizer(wallet, spec, view_secret=sender_secret.view_secret)
        hydrated = authorizer.prepare(client)
        sealed = client.seal_transaction(hydrated.unsigned)
        outcome = client.send_transaction(sealed).watch()
        print(f"result: {'committed' if outcome.is_commit else outcome.reason}")


if __name__ == "__main__":
    main()
