"""Read-only balance query example.

Python equivalent of ``ootle-rs/examples/balance_query.rs`` (public path
only — the stealth UTXO decryption demo lives under ``examples/stealth``).

Self-contained: faucets a fresh account, then reads its balances back —
so the only thing you need to run it is a reachable indexer.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.balance_query
"""

from __future__ import annotations

import asyncio

from ootle import AsyncOotleClient

from ._common import TARI_RESOURCE, faucet_and_wait, indexer_url, new_wallet


async def main() -> None:
    secret, wallet = new_wallet()
    account = wallet.default_address.to_component_address()

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Funding fresh account {account} ...")
        await faucet_and_wait(client)

        # The bech32m string is the user-facing form; the indexer wants the
        # derived on-chain component address (mirrors Rust's `to_account_address`).
        print(f"\nQuerying TARI balance for {secret.to_address().bech32m} ({account})...")
        tari_balance = await client.get_account_balance(account, TARI_RESOURCE)
        print(f"TARI balance: {tari_balance}")

        print(f"\nQuerying all balances for {account}...")
        all_balances = await client.get_account_balances(account)
        if not all_balances:
            print("  (no vaults found)")
        else:
            for resource, balance in all_balances.items():
                print(f"  {resource}: {balance}")


if __name__ == "__main__":
    asyncio.run(main())
