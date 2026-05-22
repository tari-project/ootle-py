"""Read-only balance query example — sync interface.

Mirror of ``balance_query.py`` using the blocking ``OotleClient`` rather
than ``AsyncOotleClient``. Both clients ship with ootle and share the
same surface; pick whichever fits your application's concurrency model.

Self-contained: faucets a fresh account, then reads its balances back.
The shared :mod:`examples._common` framework is async, so — like
``examples/stealth/sync_transfer.py`` — the sync faucet/watch is inlined
here while the pure helpers (URL, wallet, constants) are reused.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.balance_query_sync
"""

from __future__ import annotations

from ootle import OotleClient

from ._common import DEFAULT_FAUCET_FEE, TARI_RESOURCE, indexer_url, new_wallet


def main() -> None:
    secret, wallet = new_wallet()
    account = wallet.default_address.to_component_address()

    with OotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Funding fresh account {account} ...")
        unsigned = client.faucet().take_funds().pay_fee(DEFAULT_FAUCET_FEE).prepare()
        sealed = client.seal_transaction(unsigned)
        client.send_transaction(sealed).watch()

        print(f"\nQuerying TARI balance for {secret.to_address().bech32m} ({account})...")
        tari_balance = client.get_account_balance(account, TARI_RESOURCE)
        print(f"TARI balance: {tari_balance}")

        print(f"\nQuerying all balances for {account}...")
        all_balances = client.get_account_balances(account)
        if not all_balances:
            print("  (no vaults found)")
        else:
            for resource, balance in all_balances.items():
                print(f"  {resource}: {balance}")


if __name__ == "__main__":
    main()
