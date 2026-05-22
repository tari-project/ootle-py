"""Dry-run-only example — estimate fees without committing on-chain.

A dry-run submits the transaction through the indexer's executor but
**does not commit it on-chain**. The result carries the would-be fee,
outcome, and events — perfect for the pre-flight check a fee estimator
or wallet UI runs before asking the user to authorise the real send.

Two dry-runs are issued so callers see both success and failure paths:

* A 1 TARI transfer — expected to commit; prints the estimated fee.
* A wildly over-spending transfer — expected to fail; prints the
  structured reject reason. Importantly, no funds change hands either
  way — the example exits without ever calling ``send_transaction``.

Estimated fees are **not guarantees** — the real send may differ
slightly if chain state changes between dry-run and send.

Self-contained: sender and recipient are generated on the fly, so the
only thing you need to run it is a reachable indexer.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.dry_run_only
"""

from __future__ import annotations

import asyncio

from ootle import Address, AsyncOotleClient, DryRunResult

from ._common import TARI_RESOURCE, faucet_and_wait, indexer_url, new_recipient, new_wallet, tari


def _print_result(label: str, dry_run: DryRunResult) -> None:
    print(f"\n[{label}] tx id: {dry_run.transaction_id}")
    print(f"[{label}] estimated fee: {dry_run.estimated_fee}")

    outcome = dry_run.outcome
    if outcome is None:
        print(f"[{label}] outcome: <missing from payload>")
    elif outcome.is_commit:
        print(f"[{label}] outcome: commit (would succeed on send)")
    elif outcome.is_only_fee_commit:
        print(f"[{label}] outcome: only-fee-commit — {outcome.reason}")
    else:
        print(f"[{label}] outcome: reject — {outcome.reason}")

    if dry_run.events:
        print(f"[{label}] would-be events ({len(dry_run.events)}):")
        for event in dry_run.events:
            print(f"  topic={event.topic} substate_id={event.substate_id}")


async def _dry_run_transfer(
    client: AsyncOotleClient, recipient: Address, amount: int, label: str
) -> None:
    unsigned = await (
        client.account().pay_fee(1000).public_transfer(recipient, TARI_RESOURCE, amount).prepare()
    )
    dry_run = await client.send_dry_run(unsigned)
    _print_result(label, dry_run)


async def main() -> None:
    sender_secret, wallet = new_wallet()
    recipient = new_recipient()
    print(f"Sender address: {sender_secret.to_address().bech32m}")

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Network: {client.network.name}, epoch: {await client.get_epoch()}")
        print("\nFaucet: depositing TARI into the fresh sender ...")
        await faucet_and_wait(client)

        await _dry_run_transfer(client, recipient, tari(1), label="ok")
        await _dry_run_transfer(client, recipient, tari(1_000_000), label="overspend")

    print("\nDone — no transfer was sent. Sender's balance is untouched (minus faucet fee).")


if __name__ == "__main__":
    asyncio.run(main())
