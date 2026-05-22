"""``OotleClient`` — async Tari L2 indexer client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ._balances import get_account_balance, get_account_balances
from ._client_builders import make_account, make_component, make_faucet
from ._client_reads import (
    fetch_substates_for_client,
    get_epoch_for_client,
    get_network_for_client,
    get_substate_for_client,
    watch_events_for_client,
)
from ._client_stealth_reads import ClientStealthReadsMixin
from ._client_writes import ClientWritesMixin
from ._resolver import TransactionInputResolver
from ._transport import IndexerTransport

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    import httpx

    from ootle._sync.builders import IAccount, IComponent, IFaucet
    from ootle._crypto import CryptoProvider
    from ootle._types.address import ComponentAddress, ResourceAddress
    from ootle._types.amount import Amount
    from ootle._types.events import TransactionEvent, TransactionEventFilter
    from ootle._types.network import Network
    from ootle._types.substate import Substate, SubstateId
    from ootle.wallet import OotleWallet


class OotleClient(ClientWritesMixin, ClientStealthReadsMixin):
    """Client for the Tari L2 indexer."""

    __slots__ = (
        "_crypto",
        "_network",
        "_resolver",
        "_transport",
        "transaction_timeout",
        "wallet",
    )

    def __init__(
        self,
        transport: IndexerTransport,
        wallet: OotleWallet | None = None,
        *,
        transaction_timeout: float = 60.0,
        crypto: CryptoProvider | None = None,
    ) -> None:
        self._transport = transport
        self._network: Network | None = None
        self.wallet = wallet
        self.transaction_timeout = transaction_timeout
        # ``None`` defers to the singleton WASM provider lazily — the
        # write and stealth paths resolve it on first use, so a
        # read-only client never instantiates the bridge.
        self._crypto = crypto
        self._resolver = TransactionInputResolver(transport)

    @classmethod
    def connect(
        cls,
        url: str,
        *,
        wallet: OotleWallet | None = None,
        http_client: httpx.Client | None = None,
        transaction_timeout: float = 60.0,
        crypto: CryptoProvider | None = None,
    ) -> Self:
        """Build an unwarmed client. Use as ``async with`` to connect."""
        return cls(
            IndexerTransport(url, http_client=http_client),
            wallet,
            transaction_timeout=transaction_timeout,
            crypto=crypto,
        )

    def open(self) -> Self:
        """Warm the cached network — idempotent."""
        info = self._transport.get_network_info()
        self._network = info.network
        return self

    def close(self) -> None:
        """Close the underlying transport."""
        self._transport.close()

    def __enter__(self) -> Self:
        try:
            self.open()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def network(self) -> Network:
        """The network captured at :meth:`open`-time. Raises ``RuntimeError`` if unopened."""
        if self._network is None:
            # The literal portion is kept out of the f-string so that
            # `unasync` can rewrite `` `await open()` `` → `` `open()` ``
            # in the generated `_sync/` mirror. `unasync` substitutes
            # whole STRING tokens but cannot patch FSTRING_MIDDLE content.
            hint = "call `open()` first."
            msg = f"{type(self).__name__} has not been opened — {hint}"
            raise RuntimeError(msg)
        return self._network

    @property
    def resolver(self) -> TransactionInputResolver:
        """The resolver used by template builders to satisfy want-inputs."""
        return self._resolver

    def get_network(self) -> Network:
        """Round-trip ``GET network`` and return the current network."""
        return get_network_for_client(self._transport)

    def get_epoch(self) -> int:
        """Round-trip ``GET network`` and return the current epoch."""
        return get_epoch_for_client(self._transport)

    def fetch_substate(self, id: SubstateId) -> Substate | None:
        """Return the substate or ``None`` on 404."""
        return self._transport.fetch_substate(id)

    def get_substate(self, id: SubstateId) -> Substate:
        """Return the substate; raise :class:`IndexerClientError` on 404."""
        return get_substate_for_client(self._transport, id)

    def fetch_substates(self, ids: Sequence[SubstateId]) -> dict[SubstateId, Substate]:
        """Batched substate fetch; chunked at 20 per HTTP call."""
        return fetch_substates_for_client(self._transport, ids)

    def get_account_balance(self, account: ComponentAddress, resource: ResourceAddress) -> Amount:
        """Return the balance of ``resource`` held by ``account``."""
        return get_account_balance(self._transport, account, resource)

    def get_account_balances(self, account: ComponentAddress) -> dict[ResourceAddress, Amount]:
        """Return all ``{resource: balance}`` pairs held by ``account``."""
        return get_account_balances(self._transport, account)

    def account(self) -> IAccount:
        """Build a new account transaction (sugar for ``IAccount(self)``)."""
        return make_account(self)

    def faucet(self) -> IFaucet:
        """Build a new public-faucet transaction (sugar for ``IFaucet(self)``)."""
        return make_faucet(self)

    def component(self) -> IComponent:
        """Build a new component transaction (sugar for ``IComponent(self)``)."""
        return make_component(self)

    def watch_events(
        self, filter: TransactionEventFilter | None = None
    ) -> Iterator[TransactionEvent]:
        """Stream matching template events from the indexer SSE channel."""
        return watch_events_for_client(self._transport, filter)
