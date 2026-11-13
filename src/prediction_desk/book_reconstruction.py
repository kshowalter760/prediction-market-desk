
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class ReconstructionUpdate:
    timestamp_ms: int
    side: str
    price: Decimal
    size: Decimal


@dataclass(frozen=True)
class ReconstructedBook:
    timestamp_ms: int
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    bid_depth: Decimal
    ask_depth: Decimal
    imbalance: Decimal | None


def validate_level(
    side: str,
    price: Decimal,
    size: Decimal,
) -> None:
    if side not in ("BUY", "SELL"):
        raise ValueError("Invalid order-book side")

    if (
        not isinstance(price, Decimal)
        or not price.is_finite()
        or not ZERO < price < ONE
    ):
        raise ValueError("Invalid order-book price")

    if (
        not isinstance(size, Decimal)
        or not size.is_finite()
        or size < ZERO
    ):
        raise ValueError("Invalid order-book size")


class BookReconstructor:
    def __init__(
        self,
        timestamp_ms: int,
        bids: Iterable[tuple[Decimal, Decimal]],
        asks: Iterable[tuple[Decimal, Decimal]],
    ):
        if type(timestamp_ms) is not int or timestamp_ms <= 0:
            raise ValueError("Invalid snapshot timestamp")

        self.timestamp_ms = timestamp_ms
        self._bids: dict[Decimal, Decimal] = {}
        self._asks: dict[Decimal, Decimal] = {}

        for side, levels, target in (
            ("BUY", bids, self._bids),
            ("SELL", asks, self._asks),
        ):
            for price, size in levels:
                validate_level(side, price, size)

                if price in target:
                    raise ValueError("Duplicate snapshot price level")

                if size > ZERO:
                    target[price] = size

        self._validate_not_crossed()

    def _validate_not_crossed(self) -> None:
        if self._bids and self._asks:
            if max(self._bids) >= min(self._asks):
                raise ValueError("Locked or crossed order book")

    def apply(self, update: ReconstructionUpdate) -> None:
        if not isinstance(update, ReconstructionUpdate):
            raise TypeError("Expected ReconstructionUpdate")

        if (
            type(update.timestamp_ms) is not int
            or update.timestamp_ms < self.timestamp_ms
        ):
            raise ValueError("Out-of-order update timestamp")

        validate_level(
            update.side,
            update.price,
            update.size,
        )

        target = (
            self._bids
            if update.side == "BUY"
            else self._asks
        )

        previous_size = target.get(update.price)

        if update.size == ZERO:
            target.pop(update.price, None)
        else:
            target[update.price] = update.size

        try:
            self._validate_not_crossed()
        except ValueError:
            if previous_size is None:
                target.pop(update.price, None)
            else:
                target[update.price] = previous_size
            raise

        self.timestamp_ms = update.timestamp_ms


    def apply_batch(
        self,
        updates: Iterable[ReconstructionUpdate],
    ) -> None:
        updates = list(updates)

        if not updates:
            return

        candidate_bids = self._bids.copy()
        candidate_asks = self._asks.copy()
        candidate_timestamp = self.timestamp_ms

        for update in updates:
            if not isinstance(
                update,
                ReconstructionUpdate,
            ):
                raise TypeError(
                    "Expected ReconstructionUpdate"
                )

            if (
                type(update.timestamp_ms) is not int
                or update.timestamp_ms < candidate_timestamp
            ):
                raise ValueError(
                    "Out-of-order update timestamp"
                )

            validate_level(
                update.side,
                update.price,
                update.size,
            )

            target = (
                candidate_bids
                if update.side == "BUY"
                else candidate_asks
            )

            if update.size == ZERO:
                target.pop(update.price, None)
            else:
                target[update.price] = update.size

            candidate_timestamp = update.timestamp_ms

        if candidate_bids and candidate_asks:
            if max(candidate_bids) >= min(candidate_asks):
                raise ValueError(
                    "Locked or crossed order book"
                )

        self._bids = candidate_bids
        self._asks = candidate_asks
        self.timestamp_ms = candidate_timestamp


    def state(self) -> ReconstructedBook:
        bids = tuple(
            sorted(
                self._bids.items(),
                key=lambda item: item[0],
                reverse=True,
            )
        )

        asks = tuple(
            sorted(
                self._asks.items(),
                key=lambda item: item[0],
            )
        )

        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None

        spread = (
            best_ask - best_bid
            if best_bid is not None and best_ask is not None
            else None
        )

        bid_depth = sum(
            (size for _, size in bids),
            ZERO,
        )

        ask_depth = sum(
            (size for _, size in asks),
            ZERO,
        )

        total_depth = bid_depth + ask_depth

        imbalance = (
            (bid_depth - ask_depth) / total_depth
            if total_depth > ZERO
            else None
        )

        return ReconstructedBook(
            timestamp_ms=self.timestamp_ms,
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            imbalance=imbalance,
        )
